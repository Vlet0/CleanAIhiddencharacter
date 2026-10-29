#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate demo files with planted artifacts to exercise texclean."""
import zipfile
from pathlib import Path

HERE = Path(__file__).parent

TEX = (
    "\ufeff% sample_dirty.tex -- planted artifacts for testing texclean\n"
    "\\documentclass{article}\n"
    "\\usepackage{amsmath}\n"
    "\\begin{document}\n"
    "\n"
    "Smart quotes: \u201cdeep learning\u201d and \u2018stochastic\u2019 models.\n"
    "Dashes: an en\u2013dash, an em\u2014dash, ellipsis\u2026 and \u00a9 2026 ACME.\n"
    "Hidden: cla\u200bsic, re\u00adsearch, bidi:\u202eevil\u202c, nbsp:\u00a0here.\n"
    "Tags: pay\u200bload\U000e0041\U000e0042\U000e0043 (ABC hidden as tag chars).\n"
    "VS: warn\ufe0f\U000e0101 and mixed\U000e0142 selectors.\n"
    "Homoglyph: Te\u0430ching (that 'a' is Cyrillic, not Latin).\n"
    "Mojibake: Nh\u00c3\u00b3m nghi\u00ean c\u1ee9u (Nh\u00c3\u00b3m is broken, nghi\u00ean is legit).\n"
    "The energy is $E = mc^2_i\u200b$ and unicode in math stays: $a \u2014 b$.\n"
    "\n"
    "\\begin{verbatim}\n"
    "code \"quoted \u2014 dash\" and cla\u200bsic inside verbatim\n"
    "\\end{verbatim}\n"
    "\n"
    "\\begin{equation}\n"
    "\\alpha + \u00ad\\beta = \\gamma\n"
    "\\end{equation}\n"
    "\n"
    "Trailing whitespace here   \n"
    "Fine Vietnamese stays: \u0111\u00e0o t\u1ea1o v\u00e0 nghi\u00ean c\u1ee9u.\n"
    "\\end{document}\n"
)

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)
RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)
DOC_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body><w:p><w:r><w:t>"
    "cla\u200bsic mo\u00addel with nbsp:\u00a0here, tags \U000e0041\U000e0042 "
    "and Nh\u00c3\u00b3m"
    "</w:t></w:r></w:p></w:body></w:document>"
)

(HERE / "sample_dirty.tex").write_text(TEX, encoding="utf-8", newline="\n")
with zipfile.ZipFile(HERE / "sample_dirty.docx", "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", CONTENT_TYPES)
    z.writestr("_rels/.rels", RELS)
    z.writestr("word/document.xml", DOC_XML)
print("wrote sample_dirty.tex + sample_dirty.docx with planted artifacts")
