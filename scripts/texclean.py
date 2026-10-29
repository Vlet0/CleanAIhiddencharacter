#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
texclean -- deterministic text/LaTeX sanitizer. Pure Python 3 stdlib, offline, no AI.

Passes
  [A] hidden chars : zero-width (U+200B U+200C U+200D U+2060 U+FEFF U+180E,
                     U+2061-U2064, U+206A-U+206F), soft hyphen (U+00AD), bidi
                     controls (U+061C, U+202A-202E, U+2066-2069), tag characters
                     (U+E0000-E007F), variation selectors (U+FE00-FE0F,
                     U+E0100-E01EF), stray C0/C1 controls, leading BOM
  [B] spaces       : NBSP/thin/figure space -> space, CRLF -> LF, trailing whitespace
  [C] typography   : ' ' -> ` '   " " -> `` ''   en dash -> --   em dash -> ---
                     ellipsis -> \\ldots{} (or ... with --ellipses dots)
                     (c)(r)(tm)deg -> TeX macros                  [tex mode only]
  [D] audits       : homoglyph confusables (Cyrillic/Greek lookalikes), mojibake
                     (UTF-8 read as latin-1), leftover non-ASCII. Report-only by
                     default; opt in with --fix-confusables / --fix-mojibake.

Protected regions (only pass [A] runs inside -- code and math must stay intact):
  verbatim / lstlisting / minted / alltt environments,
  inline math $...$ , \\(...\\) , display \\[...\\] ,
  equation / align / gather / multline / displaymath (+ starred variants)

Known heuristics (documented, not bugs): `$...$` detection can pair two `$amount`
currencies on one line; inside protected regions NBSP and unicode punctuation are
left as-is on purpose.

Usage
  python texclean.py FILE_OR_DIR [-r] [--in-place] [--no-backup]
      [--mode tex|plain|docx] [--ellipses tex|dots]
      [--fix-confusables] [--fix-mojibake] [--collapse-spaces]

Default output: <name>.clean.<ext> next to the input. --in-place overwrites the
original (a .bak copy is kept unless --no-backup).
"""

import argparse
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------- constants

ZW_CHARS = set("\u200b\u200c\u200d\u2060\ufeff\u180e"
               "\u2061\u2062\u2063\u2064"       # invisible times/separator/plus
               "\u206a\u206b\u206c\u206d\u206e\u206f")  # deprecated format chars
BIDI_CHARS = set("\u061c\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
SOFT_HYPHEN = "\u00ad"
TAG_LO, TAG_HI = 0xE0000, 0xE007F          # tag characters (invisible payload)
VS_LO1, VS_HI1 = 0xFE00, 0xFE0F            # variation selectors 1-16
VS_LO2, VS_HI2 = 0xE0100, 0xE01EF          # variation selectors 17-256
SPACE_LIKE = {
    "\u00a0": " ",  # no-break space
    "\u2009": " ",  # thin space
    "\u200a": " ",  # hair space
    "\u2007": " ",  # figure space
    "\u202f": " ",  # narrow no-break space
    "\u3000": " ",  # ideographic space
}

TYPO_TEX = {
    "\u2018": "`",
    "\u2019": "'",
    "\u201c": "``",
    "\u201d": "''",
    "\u2013": "--",
    "\u2014": "---",
    "\u00a9": "\\copyright{}",
    "\u00ae": "\\textregistered{}",
    "\u2122": "\\texttrademark{}",
    "\u00b0": "\\textdegree{}",
}
TYPO_NAMES = {
    "\u2018": "single quotes U+2018",
    "\u2019": "single quotes U+2019",
    "\u201c": "double quotes U+201C",
    "\u201d": "double quotes U+201D",
    "\u2013": "en dashes U+2013",
    "\u2014": "em dashes U+2014",
    "\u00a9": "copyright signs",
    "\u00ae": "registered signs",
    "\u2122": "trademark signs",
    "\u00b0": "degree signs",
}

# Latin letters from other alphabets that render identically to a-z -- used to
# hide words from humans and from text matching. Audit only, never silent.
CONFUSABLES = {
    "\u0430": ("a", "Cyrillic a"),
    "\u0435": ("e", "Cyrillic ie"),
    "\u043e": ("o", "Cyrillic o"),
    "\u0440": ("p", "Cyrillic er"),
    "\u0441": ("c", "Cyrillic es"),
    "\u0445": ("x", "Cyrillic ha"),
    "\u0443": ("y", "Cyrillic u"),
    "\u0456": ("i", "Cyrillic iota"),
    "\u0455": ("s", "Cyrillic dze"),
    "\u0458": ("j", "Cyrillic je"),
    "\u04bb": ("h", "Cyrillic shha"),
    "\u0501": ("d", "Cyrillic komi de"),
    "\u03bf": ("o", "Greek omicron"),
    "\u03c1": ("p", "Greek rho"),
    "\u03b1": ("a", "Greek alpha"),
    "\u03bd": ("v", "Greek nu"),
    "\u0261": ("g", "IPA script g"),
}

# UTF-8 bytes misinterpreted as latin-1: A+-BF, C2 xx, the curly-quote family
# (e2 80 8x -> U+00E2 U+20AC U+008x), Cyrillic d0/d1 prefixes.
MOJIBAKE_RE = re.compile(
    "\u00c3[\u0080-\u00bf]|\u00c2[\u0080-\u00bf]"
    "|\u00e2\u20ac[\u0080-\u00bf]|\u00d0[\u0080-\u00bf]|\u00d1[\u0080-\u00bf]"
)

VERB_ENV = re.compile(
    r"\\begin\{(verbatim\*?|lstlisting|minted|alltt)\}.*?\\end\{\1\}", re.S)
MATH_ENV = re.compile(
    r"\\begin\{(equation\*?|align\*?|alignat\*?|gather\*?|multline\*?"
    r"|flalign\*?|displaymath|math)\}.*?\\end\{\1\}", re.S)
DOLLAR2 = re.compile(r"(?<!\\)\$\$.*?(?<!\\)\$\$", re.S)
DOLLAR1 = re.compile(r"(?<!\\)\$[^$\n]*?(?<!\\)\$")
BRACKET_MATH = re.compile(r"\\\[.*?\\\]", re.S)
PAREN_MATH = re.compile(r"\\\(.*?\\\)", re.S)
PROTECTED_PATTERNS = (VERB_ENV, MATH_ENV, DOLLAR2, BRACKET_MATH, PAREN_MATH, DOLLAR1)

WT_RUN = re.compile(r"(<w:t[^>]*>)(.*?)(</w:t>)", re.S)

# ---------------------------------------------------------------- passes


def hidden_pass(s, counts):
    """Delete characters that must never appear in a document (pass [A])."""
    out = []
    for ch in s:
        o = ord(ch)
        if ch in ZW_CHARS:
            counts["zero-width removed"] += 1
        elif ch in BIDI_CHARS:
            counts["bidi controls removed"] += 1
        elif ch == SOFT_HYPHEN:
            counts["soft hyphens removed"] += 1
        elif TAG_LO <= o <= TAG_HI:
            counts["tag characters removed"] += 1
        elif VS_LO1 <= o <= VS_HI1 or VS_LO2 <= o <= VS_HI2:
            counts["variation selectors removed"] += 1
        elif o < 32 and ch not in "\t\n\r":
            counts["stray C0 controls removed"] += 1
        elif 0x80 <= o <= 0x9F:
            counts["C1 controls removed"] += 1
        else:
            out.append(ch)
    return "".join(out)


def fix_mojibake(s, counts):
    def repl(m):
        try:
            fixed = m.group(0).encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return m.group(0)
        return fixed

    s, n = MOJIBAKE_RE.subn(repl, s)
    if n:
        counts["mojibake sequences fixed"] += n
    return s


def fix_confusables(s, counts):
    for ch, (latin, name) in CONFUSABLES.items():
        if ch in s:
            counts["homoglyphs fixed -> latin"] += s.count(ch)
            s = s.replace(ch, latin)
    return s


def space_pass(s, counts):
    for ch, repl in SPACE_LIKE.items():
        if ch in s:
            counts["space-like -> space (%s)" % hex(ord(ch))] += s.count(ch)
            s = s.replace(ch, repl)
    return s


def typography_pass(s, args, counts):
    if args.mode != "tex":
        return s
    for ch, repl in TYPO_TEX.items():
        if ch in s:
            counts["typography: %s" % TYPO_NAMES[ch]] += s.count(ch)
            s = s.replace(ch, repl)
    if "\u2026" in s:
        target = "\\ldots{}" if args.ellipses == "tex" else "..."
        counts["typography: ellipses U+2026"] += s.count("\u2026")
        s = s.replace("\u2026", target)
    return s


def text_pass(s, args, counts):
    """All passes for a normal (non-math, non-verbatim) text segment."""
    if args.fix_mojibake:
        s = fix_mojibake(s, counts)
    s = hidden_pass(s, counts)
    s = space_pass(s, counts)
    s = typography_pass(s, args, counts)
    if args.fix_confusables:
        s = fix_confusables(s, counts)
    if args.collapse_spaces:
        s, n = re.subn(r"[ ]{2,}", " ", s)
        if n:
            counts["space runs collapsed"] += n
    # strip trailing whitespace only right before a newline -- a segment can end
    # mid-line (e.g. just before inline math) and that space is load-bearing
    s, n = re.subn(r"[ \t]+(?=\n)", "", s)
    if n:
        counts["lines with trailing whitespace"] += n
    return s


# ------------------------------------------------------------- segmentation


def find_protected(text):
    spans = []
    for pat in PROTECTED_PATTERNS:
        for m in pat.finditer(text):
            spans.append((m.start(), m.end()))
    spans.sort()
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def clean_document(text, args, counts):
    spans = find_protected(text)
    parts = []
    pos = 0
    for s, e in spans:
        if pos < s:
            parts.append(text_pass(text[pos:s], args, counts))
        # protected: only pass [A]; math/code content must not be rewritten
        parts.append(hidden_pass(text[s:e], counts))
        pos = e
    if pos < len(text):
        parts.append(text_pass(text[pos:], args, counts))
    return "".join(parts), len(spans)


# ------------------------------------------------------------------ audits


def line_col(text, idx):
    line = text.count("\n", 0, idx) + 1
    col = idx - text.rfind("\n", 0, idx) + 1
    return line, col


def audit(text):
    findings = []
    for ch, (latin, name) in CONFUSABLES.items():
        for m in re.finditer(re.escape(ch), text):
            ln, col = line_col(text, m.start())
            findings.append(
                "line %d col %d: %r (%s, U+%04X) looks like '%s'"
                % (ln, col, ch, name, ord(ch), latin))
    mm = list(MOJIBAKE_RE.finditer(text))
    for m in mm[:10]:
        ln, col = line_col(text, m.start())
        findings.append("line %d col %d: %r mojibake (utf-8 read as latin-1)"
                        % (ln, col, m.group(0)))
    if len(mm) > 10:
        findings.append("... and %d more mojibake sequences" % (len(mm) - 10))
    leftovers = Counter(c for c in text
                        if ord(c) > 126 and c not in "\n\r\t")
    if leftovers:
        shown = ", ".join("%s x%d (U+%04X)" % (repr(c), n, ord(c))
                          for c, n in leftovers.most_common(20))
        findings.append(
            "non-ASCII kept for review -- Vietnamese diacritics are expected; "
            "dashes/quotes inside math or verbatim are protected: " + shown)
    return findings


# ------------------------------------------------------------------- files


def process_text_file(path, args):
    counts = defaultdict(int)
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
        counts["BOM stripped"] += 1
    decoded_note = None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
        decoded_note = ("file is NOT valid UTF-8; decoded as latin-1 "
                        "-- run --fix-mojibake and re-check")
    if b"\r\n" in raw:
        counts["CRLF -> LF"] = raw.count(b"\r\n")
        text = text.replace("\r\n", "\n")

    clean, n_protected = clean_document(text, args, counts)
    findings = audit(clean)

    out = write_output(path, clean, args)
    report(path, out, counts, findings, n_protected, decoded_note)
    return counts


def process_docx(path, args):
    counts = defaultdict(int)
    out = path.with_name(path.stem + ".clean" + path.suffix)

    def repl(m):
        inner = m.group(2)
        inner = hidden_pass(inner, counts)
        inner = space_pass(inner, counts)
        if args.fix_mojibake:
            inner = fix_mojibake(inner, counts)
        return m.group(1) + inner + m.group(3)

    with zipfile.ZipFile(path) as zin, \
            zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = WT_RUN.sub(repl, data.decode("utf-8")).encode("utf-8")
            zout.writestr(item, data)
    findings = ["docx: text runs cleaned in word/document.xml "
                "(hidden chars + spaces only; typography left as unicode)"]
    report(path, out, counts, findings, 0, None)
    return counts


def write_output(path, clean, args):
    if args.in_place:
        if not args.no_backup:
            path.with_name(path.name + ".bak").write_bytes(path.read_bytes())
        out = path
    else:
        out = path.with_name(path.stem + ".clean" + path.suffix)
    out.write_text(clean, encoding="utf-8", newline="\n")
    return out


def report(path, out, counts, findings, n_protected, decoded_note):
    print("== %s" % path)
    if decoded_note:
        print("  !! " + decoded_note)
    if not counts:
        print("  nothing to change -- already clean")
    for key in sorted(counts):
        print("  %-42s %d" % (key + ":", counts[key]))
    print("  protected regions (math/verbatim, only hidden chars): %d" % n_protected)
    if findings:
        print("  audit:")
        for f in findings:
            print("    - " + f)
    print("  -> %s" % out)
    print()


# -------------------------------------------------------------------- main


def gather_targets(args):
    p = Path(args.path)
    if p.is_file():
        return [p]
    if not p.is_dir():
        sys.exit("error: no such file or directory: %s" % p)
    exts = {".tex", ".txt", ".md", ".docx"} | set(args.ext or [])
    it = p.rglob("*") if args.recursive else p.iterdir()
    return sorted(f for f in it if f.is_file() and f.suffix.lower() in exts)


def pick_mode(path, args):
    if args.mode:
        return args.mode
    s = path.suffix.lower()
    return "docx" if s == ".docx" else "tex" if s == ".tex" else "plain"


def main():
    ap = argparse.ArgumentParser(
        description="Deterministic text/LaTeX sanitizer (no AI, offline).")
    ap.add_argument("path", help="file or directory")
    ap.add_argument("-r", "--recursive", action="store_true")
    ap.add_argument("--ext", action="append",
                    help="extra extension to include, e.g. --ext .bib")
    ap.add_argument("--mode", choices=["tex", "plain", "docx"], default=None,
                    help="default: tex for .tex, docx for .docx, plain otherwise")
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--ellipses", choices=["tex", "dots"], default="tex")
    ap.add_argument("--fix-confusables", action="store_true",
                    help="replace Cyrillic/Greek lookalike letters with Latin")
    ap.add_argument("--fix-mojibake", action="store_true",
                    help="repair utf-8 text that was read/saved as latin-1")
    ap.add_argument("--collapse-spaces", action="store_true")
    args = ap.parse_args()

    grand = Counter()
    nfiles = 0
    for f in gather_targets(args):
        mode = pick_mode(f, args)
        args.mode = mode
        if mode == "docx":
            grand += process_docx(f, args)
        else:
            grand += process_text_file(f, args)
        nfiles += 1

    if not nfiles:
        print("no matching files found.")
    elif sum(grand.values()) == 0:
        print("summary: all %d file(s) already clean, nothing changed." % nfiles)
    else:
        print("summary: %d change(s) across %d file(s)."
              % (sum(grand.values()), nfiles))


if __name__ == "__main__":
    main()
