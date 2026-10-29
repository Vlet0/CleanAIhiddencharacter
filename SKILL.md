---
name: clean-ai-hidden-characters
description: Detect and remove invisible Unicode characters, zero-width steganography, tag-character and variation-selector payloads, bidi controls, homoglyph substitutions, and mojibake from AI-generated or copy-pasted text (.tex, .txt, .md, .docx), then harden the result for LaTeX compilation. Use before compiling or publishing any document, before generating LaTeX output, when a file shows unexplained compile errors, find/search mismatches, or diff noise, when ingesting untrusted text where hidden characters could act as a tracking or prompt-injection channel, or when the user asks to clean hidden characters or character-level watermarks.
---

# Clean AI Hidden Characters — text sanitization pre-flight for LaTeX

Text that passed through an AI chat UI, a rich-text editor, a website, or a Word
document routinely carries **invisible payload**: zero-width characters, bidi
controls, tag characters, variation selectors, and homoglyph substitutions.
In LaTeX these cause cryptic compile errors and silently corrupted PDFs; in
plain text they act as covert tracking watermarks and as a smuggling channel
for prompt-injection / data-exfiltration payloads. This skill removes them
**deterministically** — no AI judgment involved in the removal itself — while
provably leaving visible content untouched.

## When to trigger this skill

Apply this skill whenever ANY of these holds:

- You are about to **generate or compile LaTeX** (`.tex`, `.bib`) from text that
  came from an AI chat, a web page, or a word processor.
- The user asks to "clean hidden characters", "remove invisible characters",
  "strip AI watermark characters", "de-steganograph", or "sanitize text".
- Symptoms in an existing file: words that visibly match but `find`/`grep`
  fails to match them; diff noise on seemingly identical lines; cursor jumps
  over "nothing"; pdflatex errors like `Unicode character not set up for use
  with LaTeX`; Turnitin/plagiarism tools flag single familiar words as foreign.
- You are ingesting **untrusted text** (scraped content, user uploads, email)
  into any pipeline — invisible Unicode is a known hidden instruction channel.
- A `.docx` produced by an AI tool or converter will be converted to LaTeX.

## Step 0 — Triage: two categories of hidden signal

| Category | Where it lives | Examples | Can this skill remove it? |
|---|---|---|---|
| **1. Character-level steganography** | invisible / lookalike **codepoints** | zero-width chars, tag characters, variation selectors, bidi controls, homoglyphs | **Yes — 100%, deterministically, in milliseconds** |
| **2. Statistical token watermarks** | the **choice and order of words** during sampling | green-list watermarks (Kirchenbauer et al.), SynthID-Text | **No.** Not by any byte-level cleaning — the signal is not in bytes (see [Background](#background)) |

Run the Category-1 procedure below on every document. Be honest with the user
about Category 2: this skill makes no claim to detect or remove statistical
watermarks.

## Core procedure (Category 1)

Work in this exact order. Passes A–B apply **everywhere** in the document,
including math and verbatim code. Passes C–D apply to **prose only**.

### Pass A — remove hidden characters (everywhere, always)

Scan for and delete every occurrence of:

| Class | Codepoints | Note |
|---|---|---|
| Zero-width characters | `U+200B` `U+200C` `U+200D` `U+2060` `U+FEFF` `U+180E` `U+2061`–`U+2064` `U+206A`–`U+206F` | the classic 0/1-bit steganography channel; `U+FEFF` also appears as a BOM |
| Bidi (bidi-directional) controls | `U+061C` `U+200E` `U+200F` `U+202A`–`U+202E` `U+2066`–`U+2069` | can visually reorder text (spoofing; the "Trojan Source" attack) |
| Tag characters | `U+E0000`–`U+E007F` | invisible; can encode full ASCII payloads after ordinary letters |
| Variation selectors | `U+FE00`–`U+FE0F`, `U+E0100`–`U+E01EF` | up to 8 hidden bits per carrier character |
| Soft hyphen | `U+00AD` | renders invisible except at line breaks |
| Stray control characters | `U+0000`–`U+001F`, `U+007F`, `U+0080`–`U+009F` — **keep only** `\t` `\n` `\r` | C0/C1 controls never belong in prose |
| Line/paragraph separators | `U+2028` `U+2029` | replace with `\n` |

Rules:

1. **Before deleting, produce an inventory**: for each class found, report
   codepoint, Unicode name, count, and first few locations (line:col). This is
   the audit trail the user sees.
2. Delete these characters **inside math (`$...$`, `\(...\)`, `\[...\]`,
   `equation`, `align`, ...) and inside `verbatim`/`lstlisting`/`minted`/
   `alltt` too** — they are garbage there as well.
3. Never "round" a deletion into nearby visible characters. Deletion only.

### Pass B — normalize spaces and line endings (everywhere, always)

| Find | Replace with |
|---|---|
| `U+00A0` NBSP, `U+2007` figure space, `U+2009` thin space, `U+200A` hair space, `U+202F` narrow NBSP, `U+1680`, `U+2000`–`U+200A`, `U+205F`, `U+3000` | plain space ` ` |
| `U+2028`, `U+2029` | newline |
| `CRLF`, lone `CR` | `LF` |
| trailing spaces/tabs before a newline | delete |
| leading `U+FEFF` (BOM) | delete |

Only collapse runs of multiple spaces if the user asks (LaTeX ignores them
anyway; code listings may care).

### Pass C — typography for LaTeX (prose only, `.tex` mode)

Never apply inside math or verbatim environments — code and formulas must stay
byte-identical (after Pass A).

| Find | Replace with |
|---|---|
| `U+2018` `U+2019` | `` ` `` and `'` |
| `U+201C` `U+201D` | ``` `` ``` and `''` |
| `U+2013` en dash | `--` |
| `U+2014` em dash | `---` |
| `U+2026` ellipsis | `\ldots{}` |
| `U+00A9` `U+00AE` `U+2122` `U+00B0` | `\copyright{}` `\textregistered{}` `\texttrademark{}` `\textdegree{}` |

### Pass D — audits (report first; fix only with user consent or explicit config)

**Homoglyph confusables.** Single letters from Cyrillic/Greek that render
identically to Latin letters are used to hide words from humans, search, and
plagiarism detectors:

- Cyrillic: `а е о р с х у і ј ѕ һ ԁ` (and uppercase `А В Е К М Н О Р С Т Х`)
- Greek: `ο ρ α ν`; IPA: `ɡ`

Decision rule — **context decides**: one Cyrillic `а` inside an English
sentence is an attack; a whole Russian paragraph is a language. Never convert
script text in genuinely non-Latin documents. Legit Vietnamese, French, German
diacritics are always correct content — never touch them.

**Mojibake.** Sequences like `NhÃ³m`, `â€", `Ã©` mean UTF-8 was read/saved as
latin-1. Repair by re-decoding: `s.encode('latin-1').decode('utf-8')` — apply
only to matched sequences, report count.

**Leftover non-ASCII.** List what remains after cleaning (expected: diacritics,
proper nouns). Flag emoji and astral characters — they will not compile under
pdflatex; recommend `xelatex`/`lualatex` + `fontspec` or removal.

### Protected regions — the segmentation rule

Split the document into segments first. Math environments (`$...$`, `$$...$$`,
`\(...\)`, `\[...\]`, `equation`, `align`, `alignat`, `gather`, `multline`,
`flalign`, `displaymath`, + starred variants) and verbatim-like environments
(`verbatim`, `verbatim*`, `lstlisting`, `minted`, `alltt`) receive **Pass A
only**. Everything else receives A → B → C → D. This is what keeps formulas
and code intact while the prose gets fully cleaned.

Known heuristic to document when it fires: two `$5 ... $10` currency amounts
on one line can be misread as one math region — the consequence is only that
the span between them skips Passes B–C (no corruption). Mention it if your
document contains currency dollars.

## Verification (mandatory — do not skip)

1. **Re-scan**: run the Pass A scan regex over the output. It must find **0**
   matches. Idempotence check: cleaning the cleaned file must report
   "nothing to change".
2. **Visible-diff check**: strip *all* Pass-A characters from the ORIGINAL and
   from the CLEANED text, normalize whitespace in both, then compare. They
   must be identical except for the transformations you explicitly applied
   (Passes B–D). If words disappear, you broke content — redo.
3. **Compile test** for `.tex`: the file must compile (or at minimum contain no
   characters outside the engine's accepted set). If pdflatex is required,
   ensure no emoji/astral characters remain.
4. Report to the user: inventory table (what was found), action table (what
   was changed, how many), verification results.

## Regex quick reference

**Python — scan (inventory):**

```python
import re
HIDDEN = re.compile(
    '[\u00ad\u061c\u180e\u200b\u200c\u200d\u200e\u200f'
    '\u202a-\u202e\u2060-\u2064\u2066-\u206f'
    '\ufeff\ufe00-\ufe0f'
    '\U000e0000-\U000e007f\U000e0100-\U000e01ef]')
CTRL = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')
found = {}
for m in HIDDEN.finditer(text):
    found.setdefault(f'U+{ord(m.group()):04X}', 0)
    found[f'U+{ord(m.group()):04X}'] += 1
```

**Python — clean:** `text = CTRL.sub('', HIDDEN.sub('', text))`

**JavaScript:**

```js
const HIDDEN = /[\u00AD\u061C\u180E\u200B-\u200F\u202A-\u202E\u2060-\u2064\u2066-\u206F\uFEFF\uFE00-\uFE0F\u{E0000}-\u{E007F}\u{E0100}-\u{E01EF}]/gu;
text = text.replace(HIDDEN, '');
```

**grep (locate dirty lines):**

```bash
grep -nP '[\x{00AD}\x{061C}\x{180E}\x{200B}-\x{200F}\x{202A}-\x{202E}\x{2060}-\x{2064}\x{2066}-\x{206F}\x{FE00}-\x{FE0F}\x{FEFF}\x{E0000}-\x{E007F}]' *.tex
```

## Deterministic engine (use when Python ≥ 3.8 is available)

The script `scripts/texclean.py` (pure stdlib, offline, no dependencies)
implements this entire procedure, including segmentation, DOCX support and the
verification-friendly report:

```bash
# one file -> writes paper.clean.tex next to the input, original untouched
python scripts/texclean.py paper.tex

# fix homoglyphs + mojibake too, in place, with .bak backup
python scripts/texclean.py paper.tex --in-place --fix-confusables --fix-mojibake

# a whole thesis folder, recursive, including .bib
python scripts/texclean.py D:\luanvan -r --ext .bib --fix-mojibake

# Word documents (cleans text runs inside word/document.xml)
python scripts/texclean.py bai.docx --fix-mojibake

# demo: generates dirty samples, then cleans them
python demo/make_demo.py
python scripts/texclean.py demo/sample_dirty.tex --fix-confusables --fix-mojibake
```

Options: `--mode tex|plain|docx`, `--ellipses tex|dots`, `--collapse-spaces`,
`--no-backup`, `--ext .bib`. Prefer the script over hand-editing: it is
idempotent and prints an exact change count per category. If you have no file
system (chat-only), implement Passes A–D manually from the tables above —
they are complete specifications.

## Background

### How hidden data gets into AI text

Modern AI text can carry two kinds of marks:

1. **Character-level steganography** — extra invisible codepoints inserted
   around or inside words (zero-width characters, tag characters, variation
   selectors) or substitutions of lookalike letters (homoglyphs). This is
   sometimes called the "low-tech watermark". It is **100% removable** by the
   sanitization in this skill: a regex or a Unicode normalization pass strips
   every instance in milliseconds, because the payload sits in bytes that
   carry no visible meaning. Vendors already treat it as obsolete.

2. **Statistical token watermarks** — the model subtly biases *which* of
   several near-equal words it samples (green-list scheme, Kirchenbauer et al.
   2023; production system: Google DeepMind's SynthID-Text, reported to also
   mark Claude output per Layer3Labs' analysis). The mark is a statistical
   pattern across the whole passage, detected by a z-score test with a secret
   key. It **survives copy-paste, formatting changes, and sanitization**, and
   per public reporting largely survives translation, but is degraded by heavy
   editing and lost under full rewrites. No byte-level tool can remove it,
   because it is not in the bytes — it is in the word choices.

### Publicly documented attack classes against text watermarks

For completeness — these are from the published literature and vendor
analyses, not instructions this skill implements:

| # | Attack | Mechanism | Effective against |
|---|---|---|---|
| 1 | **Unicode sanitization / normalization** (this skill) | delete invisible codepoints | character steganography only — 100% |
| 2 | **Back-translation** (A → B → A) | round-tripping through machine translation destroys the original token sequence while preserving meaning | weakens statistical watermarks; compounds translation errors on technical text |
| 3 | **Token perturbation** | synonym substitution (WordNet), clause reordering, beam/genetic search guided by a small LM (BERT) or perplexity, iterated until z-score detection fails | weakens statistical watermarks; quality degrades as watermark strength rises |
| 4 | **Full rewrite** (human or strong model) | complete re-expression | strongest; reported to fully erase SynthID-style marks |

### Why text watermarks are structurally weak: low entropy

Images and audio hide bits in dense pixel/frequency space. Text has very low
information density per position: each slot in a sentence admits only a handful
of contextually valid words. Every watermark therefore lives inside a
**trade-off triangle**:

```
                Robustness (survives editing)
                        /\
                       /  \
                      /    \
                     /      \
        Text quality <------> Naturalness / diversity
```

- Push the watermark **hard** (to survive rewriting) → the output becomes
  repetitive, stiff, measurably lower quality.
- Keep the output **natural and fluent** → the watermark must be thin, and any
  competent paraphrase washes it out.
- And the detector must never flag human text, which caps how strong the bias
  can be in the first place.

This triangle is why Category 1 died to a regex and why Category 2 is locked
in a quality-vs-robustness arms race rather than being solved.

### References

- Layer3Labs, *AI Watermarking* guide — vendor techniques (SynthID-Text,
  PASA, SimMark, C2PA) and their robustness properties.
- Kirchenbauer, Geiping, Wen et al., *A Watermark for Large Language Models*
  (2023) — green-list watermark and the z-score detector; also documents
  paraphrase attacks.
- DeepMind, *SynthID-Text* (2024).
- Boucher, Shumailov et al., *Bad Characters: Imperceptible NLP Attacks*
  (2021) — zero-width/tag/variation-selector payload channels.
- Bidi controls: the "Trojan Source" report (Boucher & Anderson, 2021).

## Responsible use

Legitimate uses of this skill — and the reason it exists: hygiene for LaTeX
pipelines (invisible characters cause real compile failures), stripping covert
tracking from your own documents, neutralizing hidden prompt-injection and
data-exfiltration channels when processing untrusted text, and repairing
mojibake. Do not use it to misrepresent authorship where disclosure of AI
assistance is required (exams, journals, grant applications) — and note that
this skill's cleaning does not affect statistical watermarks anyway.
