# Universal Game Translator Plus

**AI-powered game CSV localization tool** — แปลข้อความเกมจากไฟล์ CSV ด้วย AI หลายเจ้า

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)

---

## ภาษาไทย

### คืออะไร

Universal Game Translator Plus เป็นโปรแกรม GUI สำหรับแปลข้อความเกมจากไฟล์ CSV โดยใช้ AI API หลายเจ้า ออกแบบมาเพื่อนักแปลเกม (Game Localization) ที่ต้องการแปลข้อความจำนวนมากอย่างรวดเร็ว

### ความสามารถ

- **Multi-Provider AI:** รองรับ Google Gemini, Anthropic Claude, DeepSeek, OpenAI, และ Local LLM (Ollama/LM Studio)
- **Auto-Learn Game Tags:** ตรวจจับแท็กเกม (`<font>`, `{0}`, `[Action]`, `|A|`, `%s`, `\n`) อัตโนมัติจากไฟล์ และปกป้องไม่ให้ AI แก้ไข
- **Batch Processing:** แบ่งข้อความเป็น batch, retry อัตโนมัติเมื่อ API ล่ม/rate limit
- **Hallucination Block:** ตรวจจับคำหลอน (Canary Words) และบล็อกไม่ให้เซฟลงไฟล์
- **Resume Support:** อ่านไฟล์แปลเดิม ข้ามรายการที่แปลแล้ว หยุดเมื่อไหร่ก็มาต่อได้
- **Atomic Save:** เซฟลง `.tmp` ก่อน `os.replace` — ข้อมูลไม่พังแม้เน็ตหลุด
- **Auto-Detect Format:** รองรับ delimiter แบบ comma (`,`), tab (`\t`), pipe (`|`) และ whitespace
- **Auto-Detect Encoding:** รองรับ UTF-8, UTF-16 (LE/BE), UTF-8 BOM
- **Convert / Restore:** แปลงไฟล์ format ไหนก็ได้ (เช่น tab-separated character dialogue) → standard CSV → แปล → แปลงกลับ format เดิม

### วิธีใช้

#### 1. ติดตั้ง

```bash
pip install -r src/requirements.txt
```

#### 2. รัน

```bash
cd src
python app.py
```

#### 3. แปลงไฟล์ (ถ้า format ไม่ใช่ standard CSV)

1. เลือกไฟล์ต้นฉบับ (tab/pipe/whitespace delimited)
2. กดปุ่ม **Convert** (สีฟ้า) → ได้ไฟล์ `_standard.csv`
3. ไฟล์ที่แปลงจะถูกเลือกให้อัตโนมัติ

#### 4. แปล

1. ใส่ API Key (หรือใช้ Environment Variable: `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`)
2. เลือก Model
3. (Optional) ใส่ Canary Words และ Custom Glossary
4. กด **Analyze & Translate**

#### 5. แปลงกลับ (ถ้าใช้ Convert)

1. หลังแปลเสร็จ กดปุ่ม **Restore** (สีม่วง)
2. ได้ไฟล์ `_restored.csv` ใน format เดิม

#### 6. Build .exe

```bash
cd src
build.bat
```

### รายการแก้ไขจากต้นฉบับ (Changelog)

| วันที่ | แก้ไข |
|-------|--------|
| 2026-05-26 | **CSV save:** ใช้ `csv.writer` แทน f-string — แก้ bug key มี comma/pipes พัง |
| 2026-05-26 | **Thread safety:** เพิ่ม lock + guard ห้าม spawn สอง thread พร้อมกัน |
| 2026-05-26 | **Stop button:** ปุ่ม Start ไม่กลับมาจนกว่า thread เก่าตายสนิท |
| 2026-05-26 | **Canary check:** เปลี่ยนเป็น case-insensitive |
| 2026-05-26 | **API Key:** รองรับ Environment Variables |
| 2026-05-26 | **Dependencies:** Pin versions (`requests>=2.28`, `customtkinter>=5.2`) |
| 2026-05-26 | **Glossary:** Persist ข้าม session (เซฟลง config.json) |
| 2026-05-26 | **`.tmp` cleanup:** ลบไฟล์ `.tmp` ทิ้งถ้า `os.replace` ล้มเหลว |
| 2026-05-26 | **Unit tests:** 30 tests (`pytest`) |
| 2026-05-26 | **Delimiter auto-detect:** รองรับ comma, tab, pipe, whitespace |
| 2026-05-26 | **Header detection:** ข้ามแถว header อัตโนมัติ |
| 2026-05-26 | **Pipe tags:** `\|A\|`, `\|Left Stick\|` ถูก detect และ mask เป็น `[TAG_N]` |
| 2026-05-26 | **Convert/Restore:** แปลงไฟล์ format ไหนก็ได้ → standard → แปลงกลับ |
| 2026-05-26 | **Encoding detection:** รองรับ UTF-8, UTF-16 LE/BE, UTF-8 BOM, Latin-1 |
| 2026-05-26 | **Dead code:** ลบ `translator.py` (ซ้ำกับ engine, ใช้ config format เก่า) |
| 2026-05-28 | **TXT (one per line):** Convert/Restore รองรับไฟล์ `.txt` แบบหนึ่งบรรทัดหนึ่งข้อความ (Uncharted 4) |
| 2026-05-28 | **Format selector:** Dropdown เลือก format ก่อน Convert (Auto / CSV-TSV / TXT) |
| 2026-05-28 | **Pipe tag auto-detect fix:** `\|L3\|` ใน `.txt` ไม่ถูกเข้าใจผิดเป็น column delimiter |
| 2026-05-28 | **Unit tests:** เพิ่มอีก 3 tests รวมเป็น 33 tests |
| 2026-05-28 | **UX/UI:** แสดง % ความคืบหน้า, ป้ายสถานะสี (Ready/Translating/Complete), ปุ่ม Stop ปิดตอน idle |
| 2026-05-28 | **Subtitles mode:** Convert เฉพาะบรรทัดที่ยังไม่แปลไทย, Restore รวมกลับโดยรักษาบรรทัดที่แปลแล้ว |

### รูปแบบไฟล์ที่รองรับ

| Format | Delimiter | ตัวอย่าง |
|--------|-----------|----------|
| Standard CSV | `,` | `ID_001,"Hello World"` |
| Tab-separated | `\t` | `Barret\tHa! Bring it on!` |
| Pipe-separated | `\|` | `ID_001\|Hello World` |
| Whitespace | `\s{2,}` | `Key1    Value One` |

### Environment Variables

```bash
export GEMINI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export DEEPSEEK_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
```

---

## English

### Features

- **Multi-Provider AI:** Google Gemini, Anthropic Claude, DeepSeek, OpenAI, Local LLM
- **Auto-Learn Game Tags:** Detects game variables (`<font>`, `{0}`, `[Action]`, `|A|`, `%s`, `\n`) and protects them
- **Batch Processing:** Splits text into batches with auto retry on rate limits
- **Hallucination Block:** Detects AI-generated hallucinated words via canary word list
- **Resume Support:** Reads existing translations, skips already-translated entries
- **Atomic Checkpoint Save:** `.tmp` first, then `os.replace` — no data corruption
- **Auto-Detect Delimiter:** comma, tab, pipe, whitespace
- **Auto-Detect Encoding:** UTF-8, UTF-16 LE/BE, UTF-8 BOM, Latin-1
- **Convert / Restore:** Any format → standard CSV → translate → restore to original

### Quick Start

```bash
pip install -r src/requirements.txt
cd src
python app.py
```

### Workflow

1. **Convert** (if needed): Select file → click **Convert** (blue)
2. **Translate**: Set API key + model → click **Analyze & Translate**
3. **Restore** (if converted): Click **Restore** (purple) → original format restored

### Supported APIs

| Provider | Model Prefix | API Key Env Var |
|----------|-------------|-----------------|
| Google Gemini | `gemini-*` | `GEMINI_API_KEY` |
| Anthropic Claude | `claude-*` | `ANTHROPIC_API_KEY` |
| DeepSeek | `deepseek-*` | `DEEPSEEK_API_KEY` |
| OpenAI | `gpt-*`, `o1-*`, `o3-*` | `OPENAI_API_KEY` |
| Local LLM | `custom-local-llm` | (no key needed) |

### Build .exe

```bash
cd src
build.bat
```

---

## Credits

Forked and enhanced from **[memolyviza2012-max/Universal_Translator](https://github.com/memolyviza2012-max/Universal_Translator)** — original concept and base implementation by NodNuatTranslator.

### Key improvements in this fork

- CSV data corruption fix (keys with commas/quotes)
- Thread safety (overlapping session guard)
- Case-insensitive canary detection
- Environment variable API key support
- Delimiter auto-detection (comma/tab/pipe/whitespace)
- Encoding auto-detection (UTF-8/UTF-16)
- Convert/Restore for non-standard formats
- Pipe-wrapped tag detection (`|...|`)
- Header row detection and skipping
- Glossary persistence across sessions
- `.tmp` file cleanup
- Dead code removal (`translator.py`)
- TXT one-per-line support (Uncharted 4 format)
- Subtitles mode: extract untranslated lines only, merge back preserving translated lines
- Convert format selector dropdown (Auto / CSV-TSV / TXT / Subtitles)
- UX/UI: progress %, status indicator (Ready/Translating/Complete), Stop button disabled when idle
- 33 unit tests (pytest)
- Dependency version pinning
