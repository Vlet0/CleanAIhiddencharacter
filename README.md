[🇻🇳 Tiếng Việt](README.vi.md) | **English**

# CleanAIHiddenCharacter

**Deterministically strip invisible Unicode characters, zero-width steganography, homoglyphs and mojibake from AI-generated text before compiling or publishing — pure algorithm, no AI, fully verifiable.**

---

## The problem this solves

Text that passed through an AI chat, a website, or a Word file routinely carries **invisible payload**:

| Class | Characters | Harm |
|---|---|---|
| Zero-width | `U+200B` `U+200C` `U+200D` `U+2060` `U+FEFF` `U+180E` `U+2061`–`U+2064` | 0/1-bit steganography channel — the "low-tech" watermark |
| Bidi controls | `U+202A`–`U+202E` `U+2066`–`U+2069` `U+061C` | visually reorder text — reader spoofing (Trojan Source) |
| Tag characters | `U+E0000`–`U+E007F` | hide a whole invisible ASCII payload after ordinary letters |
| Variation selectors | `U+FE00`–`U+FE0F` `U+E0100`–`U+E01EF` | up to 8 hidden bits per carrier character |
| Homoglyphs | Cyrillic `а е о р с х...` posing as Latin letters | evade search and plagiarism detection |
| Mojibake | `NhÃ³m`, `â€"` | UTF-8 misread as latin-1 |
| Odd whitespace | NBSP, thin/hair space, `U+3000`... | compile errors, noisy diffs |

In **LaTeX** these cause cryptic compile failures and silently corrupted PDFs. In **security** terms they are a covert channel for prompt injection and data exfiltration.

## What's in this repo

| File | Role |
|---|---|
| [`SKILL.md`](SKILL.md) | **A complete, self-contained skill for any AI** (Claude, GPT, Gemini, local LLMs): the 4-pass procedure, full codepoint tables, regexes for Python/JS/grep, math/verbatim protection rules, mandatory verification gates |
| [`scripts/texclean.py`](scripts/texclean.py) | The deterministic engine — Python 3 stdlib only, offline, nothing to install. Handles `.tex` `.txt` `.md` `.docx` `.bib` |
| [`demo/make_demo.py`](demo/make_demo.py) | Generates demo files with every kind of planted artifact for testing |

## Quick start

### 1. Run the script (no AI needed)

```bash
python demo/make_demo.py                                          # create dirty samples
python scripts/texclean.py demo/sample_dirty.tex --fix-confusables --fix-mojibake

python scripts/texclean.py paper.tex                              # one file
python scripts/texclean.py D:\thesis -r --ext .bib                # a whole folder
python scripts/texclean.py bai.docx                               # Word files
python scripts/texclean.py paper.tex --in-place --no-backup       # overwrite in place
```

By default output goes to `filename.clean.tex`, the original stays untouched. The script is **idempotent** — re-running it on a clean file reports "nothing to change".

### 2. Install as a skill for Claude Code / Claude / Cursor

```bash
git clone https://github.com/Vlet0/CleanAIhiddencharacter.git
mkdir -p ~/.claude/skills
cp -r CleanAIhiddencharacter ~/.claude/skills/clean-ai-hidden-characters
```

The AI will then apply it automatically whenever you ask to clean hidden characters, or before producing LaTeX.

### 3. Any other AI (plain chat)

Paste the full contents of [`SKILL.md`](SKILL.md) into the system prompt / start of the conversation — the file is written to be **fully self-contained** (character tables + regexes + procedure) for AIs with no file access.

## The 4 passes

```
[A] Hidden chars  → delete zero-width, bidi, tag chars, variation selectors,
                    soft hyphen, C0/C1 controls, BOM       (runs EVERYWHERE, incl. math)
[B] Whitespace    → NBSP/thin/figure space → space; CRLF → LF; strip trailing WS
[C] Typography    → " " → ``''  – → --  — → ---  … → \ldots{}   (prose only, tex mode)
[D] Audits        → Cyrillic/Greek homoglyphs, mojibake — REPORT first, fix behind a flag
```

**Protected regions**: `verbatim`, `lstlisting`, `minted`, `alltt` and all math regions (`$...$`, `equation`, `align`...) receive pass [A] only — formulas and code must stay byte-identical. Legitimate Vietnamese diacritics are always preserved.

## Background: two kinds of watermark in AI text

| | Character watermark (low-tech) | Statistical watermark (green-list / SynthID-Text) |
|---|---|---|
| Where it hides | invisible bytes inserted into the text | **word choices** during model sampling (statistical pattern, z-score detector) |
| Removable by sanitization/regex? | **100%, in milliseconds** | **No** — the signal is not in the bytes |
| Survives copy-paste? | Yes (until sanitized) | Yes; degraded by paraphrasing, lost under full rewrites |

Text has **low entropy** (each slot in a sentence admits only a few contextually valid words), so every watermark is trapped in a **trade-off triangle**:

```
                Robustness (survives editing)
                        /\
                       /  \
                      /    \
     Text quality <------> Naturalness / diversity
```

Push the watermark hard → the output gets stiff and repetitive; keep the output natural → the watermark must be thin and any paraphrase washes it out. That is why character watermarks died to a regex, and why statistical watermarks remain in a quality-vs-robustness arms race.

## Verification (what makes this repo different)

Every cleaning run must pass three gates:

1. **Re-scan** the output with the scan regex → must find **0** hidden characters (idempotent).
2. **Visible-diff**: strip all invisible characters from both original and cleaned text and compare → visible content is **identical** except for the declared transforms.
3. **Compile test** for `.tex`.

## Honest limitations

- The skill removes **character-level watermarks** and all invisible characters completely; it does **not** detect or remove statistical watermarks (no byte-level tool can — see the background section).
- `$...$` detection is heuristic: two currency amounts `$5 ... $10` on one line can be read as one math region (that span then skips passes B–C; nothing breaks).
- Inside math/verbatim, Unicode punctuation is left as-is on purpose.
- `.docx` cleaning covers hidden characters + whitespace in text runs only.

## License & references

MIT — see [`LICENSE`](LICENSE). Key references: [Layer3Labs — AI Watermarking](https://www.layer3labs.io/guides/ai-watermarking), Kirchenbauer et al. 2023 (*A Watermark for Large Language Models*), DeepMind *SynthID-Text* 2024, Boucher et al. 2021 (*Bad Characters*, *Trojan Source*).
