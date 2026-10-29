#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for texclean. Run: python -m unittest discover -s tests -v"""

import sys
import unittest
import zipfile
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import texclean  # noqa: E402


class Args:
    """Minimal argparse stand-in: tex mode, no optional fixes."""

    mode = "tex"
    ellipses = "tex"
    fix_confusables = False
    fix_mojibake = False
    collapse_spaces = False
    in_place = False
    no_backup = False


def clean(s, **overrides):
    args = Args()
    for k, v in overrides.items():
        setattr(args, k, v)
    counts = defaultdict(int)
    out, _ = texclean.clean_document(s, args, counts)
    return out, counts


class TestLineCol(unittest.TestCase):
    def test_columns_are_one_based(self):
        t = "ab\ncd"
        self.assertEqual(texclean.line_col(t, 0), (1, 1))
        self.assertEqual(texclean.line_col(t, 1), (1, 2))
        self.assertEqual(texclean.line_col(t, 3), (2, 1))
        self.assertEqual(texclean.line_col(t, 4), (2, 2))


class TestHiddenChars(unittest.TestCase):
    DIRTY = ("a\u200bb\u200cc\u200dd\u2060e\ufefff\u180eg\u2061h\u2062i\u2063"
             "j\u2064k\u206al\u206bm\u206cn\u206do\u206ep\u206fq\u061cr"
             "\u202as\u2066t\U000e0041u\ufe00v\ufe0fw\U000e0100x\U000e01ef"
             "y\u00adz\x01\x7f\x85")

    def test_all_hidden_classes_removed(self):
        out, counts = clean(self.DIRTY)
        self.assertEqual(out, "abcdefghijklmnopqrstuvwxyz")
        self.assertGreater(counts["zero-width removed"], 0)
        self.assertGreater(counts["tag characters removed"], 0)
        self.assertGreater(counts["variation selectors removed"], 0)
        self.assertGreater(counts["bidi controls removed"], 0)
        self.assertGreater(counts["soft hyphens removed"], 0)
        self.assertGreater(counts["stray C0 controls removed"], 0)
        self.assertGreater(counts["C1 controls removed"], 0)

    def test_tab_newline_kept(self):
        # CRLF -> LF happens at file-read level (process_text_file), not here
        out, _ = clean("a\tb\nc\nd")
        self.assertEqual(out, "a\tb\nc\nd")


class TestProtectedRegions(unittest.TestCase):
    def test_math_content_untouched(self):
        src = "before $a \\times b$ after"
        out, _ = clean(src)
        self.assertEqual(out, src)

    def test_verbatim_content_untouched(self):
        src = ("\\begin{verbatim}\n"
               "code \"quoted \u2014 dash\" and  double  spaces\n"
               "\\end{verbatim}\n")
        out, _ = clean(src)
        self.assertIn("code \"quoted \u2014 dash\" and  double  spaces", out)

    def test_equation_env_untouched(self):
        src = "\\begin{equation}\n\\alpha + \\beta = \\gamma\n\\end{equation}"
        out, _ = clean(src)
        self.assertEqual(out, src)

    def test_hidden_removed_even_inside_math(self):
        out, counts = clean("$E = mc^2_i\u200b$")
        self.assertEqual(out, "$E = mc^2_i$")
        self.assertEqual(counts["zero-width removed"], 1)

    def test_escaped_dollar_not_a_math_region(self):
        src = r"price is \$5 and \$10 total"
        out, _ = clean(src)
        self.assertEqual(out, src)


class TestTypography(unittest.TestCase):
    def test_quotes_dashes_ellipsis(self):
        out, _ = clean("\u201cAI\u201d and \u2018ml\u2019, a\u2013b, c\u2014d, e\u2026f")
        self.assertEqual(out, "``AI'' and `ml', a--b, c---d, e\\ldots{}f")

    def test_plain_mode_skips_typography(self):
        out, _ = clean("\u201cAI\u201d \u2014 \u2026", mode="plain")
        self.assertEqual(out, "\u201cAI\u201d \u2014 \u2026")

    def test_typography_not_applied_inside_verbatim(self):
        src = "\\begin{verbatim}\nx \u2014 y\n\\end{verbatim}"
        out, _ = clean(src)
        self.assertIn("x \u2014 y", out)


class TestWhitespace(unittest.TestCase):
    def test_nbsp_replaced(self):
        out, _ = clean("a\u00a0b\u2009c")
        self.assertEqual(out, "a b c")

    def test_trailing_whitespace_stripped(self):
        out, _ = clean("line one   \nline two\t\n")
        self.assertEqual(out, "line one\nline two\n")

    def test_final_line_trailing_whitespace_stripped(self):
        out, _ = clean("last line   ")
        self.assertEqual(out, "last line")

    def test_space_before_inline_math_kept(self):
        out, _ = clean("word $x$ word")
        self.assertEqual(out, "word $x$ word")


class TestConfusables(unittest.TestCase):
    def test_uppercase_confusables_audited(self):
        findings = texclean.audit("Te\u0430ching \u0410BC")
        confusable_hits = [f for f in findings if "looks like" in f]
        self.assertEqual(len(confusable_hits), 2)

    def test_fix_confusables(self):
        out, counts = clean("Te\u0430ching", fix_confusables=True)
        self.assertEqual(out, "Teaching")
        self.assertEqual(counts["homoglyphs fixed -> latin"], 1)

    def test_vietnamese_diacritics_not_flagged(self):
        # Vietnamese text may appear in the non-ASCII leftover info line, but
        # no homoglyph/mojibake finding may ever point at it
        findings = texclean.audit("\u0111\u00e0o t\u1ea1o")
        self.assertEqual([f for f in findings if "looks like" in f], [])
        self.assertEqual([f for f in findings if "mojibake" in f], [])


class TestMojibake(unittest.TestCase):
    def test_fix(self):
        out, counts = clean("Nh\u00c3\u00b3m", fix_mojibake=True)
        self.assertEqual(out, "Nh\u00f3m")
        self.assertEqual(counts["mojibake sequences fixed"], 1)


class TestIdempotence(unittest.TestCase):
    DIRTY_TEX = (
        "Hidden: cla\u200bsic, re\u00adsearch, nbsp:\u00a0here.\n"
        "Tags: pay\U000e0041\U000e0042 and warn\ufe0f\U000e0101.\n"
        "Smart: \u201cdeep\u201d \u2014 dash\u2026\n"
        "Math stays: $E = mc^2_i\u200b$ and $a \u2014 b$.\n"
        "\\begin{verbatim}\nkeep \u2014 \"this\" cla\u200bsic\n\\end{verbatim}\n"
    )

    def test_second_run_changes_nothing(self):
        once, _ = clean(self.DIRTY_TEX)
        args = Args()
        counts1, counts2 = defaultdict(int), defaultdict(int)
        once2, _ = texclean.clean_document(once, args, counts1)
        self.assertEqual(once, once2)
        self.assertEqual(sum(counts1.values()), 0)


class TestFileProcessing(unittest.TestCase):
    def test_text_file_roundtrip(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "doc.tex"
            p.write_text("cla\u200bsic \u201cAI\u201d doc\u2026\n",
                         encoding="utf-8")
            args = Args()
            texclean.process_text_file(p, args)
            out = (Path(tmp) / "doc.clean.tex").read_text(encoding="utf-8")
            self.assertEqual(out, "clasic ``AI'' doc\\ldots{}\n")

    def test_docx_text_runs_cleaned(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "doc.docx"
            with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("word/document.xml",
                           '<?xml version="1.0"?><w:document '
                           'xmlns:w="http://schemas.openxmlformats.org/'
                           'wordprocessingml/2006/main"><w:body><w:p><w:r>'
                           '<w:t>cla\u200bsic nbsp\u00a0here</w:t></w:r></w:p>'
                           "</w:body></w:document>")
            args = Args()
            args.fix_mojibake = False
            texclean.process_docx(p, args)
            with zipfile.ZipFile(Path(tmp) / "doc.clean.docx") as z:
                xml = z.read("word/document.xml").decode("utf-8")
            self.assertIn("clasic nbsp here", xml)


if __name__ == "__main__":
    unittest.main()
