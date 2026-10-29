# CleanAIHiddenCharacter

**Vệ sinh ký tự ẩn trong văn bản AI trước khi xuất bản / biên dịch LaTeX — bằng thuật toán thuần túy, xác định được 100%, không cần AI.**
*Deterministically strip invisible Unicode characters, zero-width steganography, homoglyphs and mojibake from AI-generated text before compiling or publishing — pure algorithm, no AI, fully verifiable.*

---

## Vấn đề nào được giải quyết?

Văn bản đi qua chat AI, trang web, hay file Word thường mang theo **tải trọng vô hình**:

| Loại | Ký tự | Tác hại |
|---|---|---|
| Zero-width | `U+200B` `U+200C` `U+200D` `U+2060` `U+FEFF` `U+180E` `U+2061`–`U+2064` | kênh giấu tin 0/1-bit — watermark "kỹ thuật thấp" |
| Bidi controls | `U+202A`–`U+202E` `U+2066`–`U+2069` `U+061C` | đảo chiều hiển thị — đánh lừa người đọc (Trojan Source) |
| Tag characters | `U+E0000`–`U+E007F` | giấu cả chuỗi ASCII vô hình sau chữ thường |
| Variation selectors | `U+FE00`–`U+FE0F` `U+E0100`–`U+E01EF` | giấu tới 8 bit mỗi ký tự |
| Homoglyph | Cyrillic `а е о р с х...` giả mạo chữ Latin | trốn tìm kiếm, kiểm tra đạo văn |
| Mojibake | `NhÃ³m`, `â€"` | UTF-8 bị đọc nhầm thành latin-1 |
| Khoảng trắng lạ | NBSP, thin/hair space, `U+3000`... | lỗi biên dịch, diff ồn |

Với **LaTeX** mấy ký tự này gây lỗi biên dịch khó hiểu và PDF bị hỏng âm thầm. Với **bảo mật**, chúng là kênh giấu lệnh prompt-injection / rò rỉ dữ liệu.

## Repo chứa gì

| File | Vai trò |
|---|---|
| [`SKILL.md`](SKILL.md) | **Skill hoàn chỉnh cho bất kỳ AI nào** (Claude, GPT, Gemini, local LLM): quy trình 4 pass, bảng mã ký tự đầy đủ, regex cho Python/JS/grep, quy tắc bảo vệ vùng math/verbatim, kiểm chứng bắt buộc |
| [`scripts/texclean.py`](scripts/texclean.py) | Engine deterministic — Python 3 stdlib, offline, không cần cài gì. Hỗ trợ `.tex` `.txt` `.md` `.docx` `.bib` |
| [`demo/make_demo.py`](demo/make_demo.py) | Tạo file demo có cài sẵn mọi loại "bẫy" để test |

## Dùng ngay

### 1. Chạy script (không cần AI)

```bash
python demo/make_demo.py                                          # tạo file bẩn mẫu
python scripts/texclean.py demo/sample_dirty.tex --fix-confusables --fix-mojibake

python scripts/texclean.py paper.tex                              # 1 file
python scripts/texclean.py D:\luanvan -r --ext .bib               # cả thư mục
python scripts/texclean.py bai.docx                               # file Word
python scripts/texclean.py paper.tex --in-place --no-backup       # sửa tại chỗ
```

Mặc định ghi ra `tenfile.clean.tex`, bản gốc giữ nguyên. Script **idempotent** — chạy trên file đã sạch sẽ báo "nothing to change".

### 2. Cài làm skill cho Claude Code / Claude / Cursor

```bash
git clone https://github.com/Vlet0/CleanAIhiddencharacter.git
mkdir -p ~/.claude/skills
cp -r CleanAIhiddencharacter ~/.claude/skills/clean-ai-hidden-characters
```

Từ đó AI tự động áp dụng whenever bạn yêu cầu dọn ký tự ẩn hoặc trước khi dịch LaTeX.

### 3. Cho AI bất kỳ (chat thường)

Dán toàn bộ nội dung [`SKILL.md`](SKILL.md) vào system prompt / đầu cuộc trò chuyện — file được viết để **tự chứa đầy đủ** (bảng mã + regex + quy trình) cho AI không có quyền chạy file.

## 4 pass của thuật toán

```
[A] Ký tự ẩn    → xóa zero-width, bidi, tag chars, variation selectors,
                  soft hyphen, C0/C1 controls, BOM      (chạy MỌI nơi, kể cả math)
[B] Khoảng trắng → NBSP/thin/figure space → space; CRLF → LF; xóa trailing WS
[C] Typography  → " " → ``''  – → --  — → ---  … → \ldots{}   (chỉ văn xuôi, chế độ tex)
[D] Kiểm toán   → homoglyph Cyrillic/Hy Lạp, mojibake — BÁO CÁO trước, sửa khi có cờ
```

**Bảo vệ vùng nhạy cảm**: `verbatim`, `lstlisting`, `minted`, `alltt` và toàn bộ vùng math (`$...$`, `equation`, `align`...) chỉ nhận pass [A] — công thức và code phải nguyên vẹn byte. Chữ tiếng Việt hợp lệ luôn được giữ.

## Kiến thức nền: 2 loại watermark trong văn bản AI

| | Watermark ký tự (low-tech) | Watermark thống kê (green-list / SynthID-Text) |
|---|---|---|
| Giấu ở đâu | byte vô hình chèn vào văn bản | **lựa chọn từ** khi model sampling (mẫu thống kê, kiểm định z-score) |
| Sanitization/regex xóa được? | **100%, vài mili-giây** | **Không** — tín hiệu không nằm trong byte |
| Chống chịu copy-paste? | Có (cho tới khi bị dọn) | Có; suy giảm khi diễn đạt lại, mất khi viết lại toàn bộ |

Văn bản có **entropy thấp** (mỗi vị trí chỉ có vài từ đồng nghĩa hợp ngữ cảnh), nên mọi watermark đều kẹt trong **tam giác đánh đổi**:

```
                Khả năng kháng chỉnh sửa (Robustness)
                        /\
                       /  \
                      /    \
     Chất lượng văn bản <--> Tính tự nhiên / Đa dạng
```

Ép watermark mạnh → văn bản gượng gạo; ưu tiên tự nhiên → watermark "mỏng", dễ bị paraphrase cuốn trôi. Đó là lý do watermark ký tự đã chết dưới regex, còn watermark thống kê vẫn trong cuộc chạy đẽ giáp chất lượng.

## Kiểm chứng (điều làm repo này khác biệt)

Mọi lần làm sạch đều phải qua 3 cổng:

1. **Re-scan** đầu ra bằng regex quét → phải ra **0** ký tự ẩn (idempotent).
2. **Visible-diff**: bóc toàn bộ ký tự vô hình khỏi bản gốc lẫn bản sạch, so sánh → nội dung nhìn thấy **giống hệt** trừ các biến đổi đã khai báo.
3. **Compile test** với `.tex`.

## Giới hạn trung thực

- Skill xóa sạch **watermark cấp ký tự** và mọi ký tự ẩn; **không** phát hiện/xóa watermark thống kê (không byte-level tool nào làm được — xem phần kiến thức nền).
- Nhận diện `$...$` là heuristic: hai số tiền `$5 ... $10` cùng dòng có thể bị coi là một vùng math (chỉ làm phần đó bỏ pass B–C, không phá file).
- Trong math/verbatim, dấu Unicode được giữ nguyên chủ ý.
- `.docx` chỉ dọn ký tự ẩn + khoảng trắng trong text runs.

## Đóng góp & giấy phép

MIT — xem [`LICENSE`](LICENSE). Tham khảo chính: [Layer3Labs — AI Watermarking](https://www.layer3labs.io/guides/ai-watermarking), Kirchenbauer et al. 2023 (*A Watermark for Large Language Models*), DeepMind *SynthID-Text* 2024, Boucher et al. 2021 (*Bad Characters*, *Trojan Source*).

---

### English TL;DR

Deterministic, offline, pure-stdlib sanitizer that strips invisible Unicode (zero-width, bidi, tag characters, variation selectors), homoglyphs and mojibake from `.tex/.txt/.md/.docx` — with math/verbatim regions protected byte-for-byte and a mandatory verify step (re-scan = 0 findings, visible content provably unchanged). Ships as a CLI script **and** a self-contained `SKILL.md` any AI agent can execute. Removes character-level steganography 100%; does not (and cannot) remove statistical token watermarks — the README explains both honestly, including the robustness/quality/naturalness trade-off triangle.
