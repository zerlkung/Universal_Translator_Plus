import csv
import time
import requests
import os
import re
import json
import threading
import xml.etree.ElementTree as ET

class TranslatorEngine:
    def __init__(self, log_callback=None, progress_callback=None):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.is_running = False
        self._worker_thread = None
        self._lock = threading.Lock()

    def log(self, message, level="INFO"):
        formatted_msg = f"[{level}] {message}"
        if self.log_callback:
            self.log_callback(formatted_msg)
        else:
            print(formatted_msg)

    def _detect_encoding(self, file_path):
        with open(file_path, 'rb') as f:
            bom = f.read(4)
        if bom.startswith(b'\xff\xfe') or bom.startswith(b'\xfe\xff'):
            return 'utf-16'
        if bom.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        return 'utf-8'

    def _read_file(self, file_path, mode='r'):
        for enc in [self._detect_encoding(file_path), 'utf-8', 'latin-1']:
            try:
                f = open(file_path, mode, encoding=enc)
                f.readline()
                f.seek(0)
                return f
            except (UnicodeDecodeError, UnicodeError):
                continue
        return open(file_path, mode, encoding='latin-1')

    def detect_delimiter(self, file_path):
        try:
            with self._read_file(file_path) as f:
                lines = [f.readline() for _ in range(10)]
            lines = [l for l in lines if l.strip()]
            if not lines:
                return ','
            counts = {',': 0, '\t': 0, '|': 0}
            for line in lines:
                for delim in counts:
                    counts[delim] += line.count(delim)
            best = max(counts, key=counts.get)
            return best if counts[best] > 0 else ','
        except Exception:
            return ','

    def _looks_like_header(self, row):
        if not row or len(row) < 2:
            return False
        combined = ' '.join(str(c) for c in row).lower()
        markers = ['do not delete', "don't delete", 'character', 'name', 'dialogue', 'text']
        return any(m in combined for m in markers)

    def _needs_translation(self, text):
        """Check if a text line needs translation (not already Thai, not placeholder)."""
        stripped = text.strip()
        if not stripped:
            return False
        if stripped == '[EmptyString]':
            return False
        if stripped.isdigit() or stripped.lstrip('-').isdigit():
            return False
        # Skip ID/label lines (e.g. "Id: [0x002F4C90]")
        if stripped.lower().startswith('id:'):
            return False
        # Already has Thai characters → already translated
        if re.search(r'[฀-๿]', stripped):
            return False
        # Has arrow separator with Thai on the right → already translated
        arrow_match = re.search(r'\s+(?:->|→)\s+', stripped)
        if arrow_match:
            parts = stripped.split(arrow_match.group(), 1)
            if len(parts) == 2 and re.search(r'[฀-๿]', parts[1]):
                return False
        return True

    def _filter_untranslated_lines(self, file_path):
        """Read a subtitles .txt file, return only lines needing translation.
        Returns (rows, delimiter, has_header) where rows are [[text], ...] and
        a parallel list of original line indices is stored for mapping.
        """
        with self._read_file(file_path) as f:
            all_lines = [line.rstrip('\n\r') for line in f]

        rows = []
        line_indices = []
        for i, line in enumerate(all_lines):
            if self._needs_translation(line):
                rows.append([line])
                line_indices.append(i)

        self.log(f"Subtitles: {len(all_lines)} total, {len(rows)} need translation, "
                 f"{len(all_lines) - len(rows)} already translated/skipped.")
        return rows, 'subtitles', False, line_indices

    def _parse_xml_all(self, file_path):
        """Parse a game StringTable XML file, return ALL entries.
        Returns (rows, delimiter, has_header, string_ids).
        """
        tree = ET.parse(file_path)
        root = tree.getroot()
        items = root.findall('.//LocalisableString')

        rows = []
        string_ids = []
        for item in items:
            sid = item.get('StringID', '')
            content = item.find('Content')
            text = content.text if content is not None and content.text else ''
            if text.strip():  # skip truly empty
                rows.append([text])
                string_ids.append(sid)

        self.log(f"XML: {len(rows)} entries extracted from {len(items)} total.")
        return rows, 'xml', False, string_ids

    def _parse_csv_3col(self, file_path):
        """Parse a 3-column CSV (key,source,translation).
        Returns (rows, delimiter, has_header, keys).
        """
        delim = self.detect_delimiter(file_path)
        with self._read_file(file_path) as f:
            reader = csv.reader(f, delimiter=delim)
            all_rows = [row for row in reader if any(c.strip() for c in row)]

        if not all_rows:
            return [], ',', False, []

        # Detect header
        has_header = self._looks_like_header(all_rows[0]) or (
            len(all_rows[0]) >= 3 and all_rows[0][0].strip().lower() == 'key')
        header_row = all_rows[0] if has_header else None
        data_rows = all_rows[1:] if has_header else all_rows

        # Extract rows where source has text and translation is empty
        rows = []
        keys = []
        skipped_empty = 0
        skipped_done = 0
        for r in data_rows:
            if len(r) < 2:
                continue
            key = r[0].strip() if r[0] else ''
            source = r[1].strip() if len(r) > 1 else ''
            translation = r[2].strip() if len(r) > 2 else ''

            if not source:
                skipped_empty += 1
                continue
            if translation and re.search(r'[฀-๿]', translation):
                skipped_done += 1
                continue

            rows.append([source])
            keys.append(key)

        self.log(f"CSV 3-col: {len(rows)} need translation ({skipped_empty} empty, "
                 f"{skipped_done} already translated) from {len(data_rows)} total rows.")
        return rows, 'csv3col', False, keys  # has_header=False: header already stripped

    def _try_parse_rows(self, file_path, force_delim=None):
        """Try to parse a file with auto-detected delimiter. Returns (rows, delimiter, has_header).

        If force_delim is set, skips auto-detection and uses the given delimiter.
        Valid values: None (auto), ',', '\t', '|', 'whitespace', 'newline', 'subtitles', 'xml', 'csv3col'.
        Note: 'subtitles'/'xml'/'csv3col' returns 4-tuple (rows, delim, has_header, indices/ids/keys).
        """
        if force_delim == 'subtitles':
            return self._filter_untranslated_lines(file_path)

        if force_delim == 'xml':
            return self._parse_xml_all(file_path)

        if force_delim == 'csv3col':
            return self._parse_csv_3col(file_path)

        if force_delim == 'newline':
            with self._read_file(file_path) as f:
                raw_lines = [line.rstrip('\n\r') for line in f if line.strip()]
            return [[line] for line in raw_lines], 'newline', False

        if force_delim == 'subtitles':
            return self._filter_untranslated_lines(file_path)

        delim = force_delim if force_delim else self.detect_delimiter(file_path)
        with self._read_file(file_path) as f:
            raw_lines = [line.rstrip('\n\r') for line in f if line.strip()]

        if not raw_lines:
            return [], ',', False

        # Try csv.reader with detected delimiter
        with self._read_file(file_path) as f:
            reader = csv.reader(f, delimiter=delim)
            rows = [row for row in reader if any(c.strip() for c in row)]

        # Reject false delimiter detection (e.g. | in game tags)
        col_counts = [len(r) for r in rows]
        delim_rejected = False
        if col_counts:
            most_common = max(set(col_counts), key=col_counts.count)
            if most_common <= 1:
                rows = []
                delim_rejected = True
            elif delim == '|' and len(set(col_counts)) > 2:
                rows = []
                delim_rejected = True

        # If delimiter didn't split well, try whitespace (2+ spaces)
        # Skip whitespace if | was rejected — likely game tags, not whitespace-delimited
        if not (delim_rejected and delim == '|') and (not rows or all(len(r) <= 1 for r in rows)):
            rows = []
            for line in raw_lines:
                parts = re.split(r'\s{2,}', line)
                parts = [p.strip() for p in parts if p.strip()]
                if len(parts) >= 2:
                    rows.append(parts)
            if rows:
                delim = 'whitespace'

        # Last resort: newline-delimited (one text per line)
        if not rows:
            rows = [[line] for line in raw_lines]
            delim = 'newline'

        if not rows:
            return [], delim, False

        has_header = self._looks_like_header(rows[0])
        return rows, delim, has_header

    def convert_to_standard(self, input_path, output_path=None, force_delim=None):
        """Convert any supported format to standard ID_00XXX,'Text' CSV.

        Returns (output_path, mapping_path).
        If force_delim is set, skips auto-detection. Use 'newline' for one-text-per-line .txt files.
        """
        if output_path is None:
            base, _ = os.path.splitext(input_path)
            output_path = f"{base}_standard.csv"

        result = self._try_parse_rows(input_path, force_delim=force_delim)
        if len(result) == 4:
            rows, delim, has_header, extra = result
        else:
            rows, delim, has_header = result
            extra = None

        if not rows:
            self.log("No parseable rows found in file.", "ERROR")
            return None, None

        data_rows = rows[1:] if has_header else rows
        header_row = rows[0] if has_header else None

        mapping = {
            "delimiter": delim,
            "has_header": has_header,
            "header": header_row,
            "mapping": {},
        }
        mapping["original_file"] = os.path.abspath(input_path)
        if delim == 'csv3col' and extra:
            # _parse_csv_3col already stripped header; store it from original
            with self._read_file(input_path) as f:
                reader = csv.reader(f, delimiter=self.detect_delimiter(input_path))
                first = next(reader, None)
            if first and len(first) >= 3 and first[0].strip().lower() == 'key':
                mapping["header"] = first

        id_width = max(5, len(str(len(data_rows))))
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            for i, row in enumerate(data_rows):
                sid = f"ID_{i + 1:0{id_width}d}"
                if delim in ('newline', 'subtitles', 'xml', 'csv3col'):
                    text = row[0] if row else ""
                    if delim == 'subtitles' and extra:
                        mapping["mapping"][sid] = str(extra[i])
                    elif delim == 'xml' and extra:
                        mapping["mapping"][sid] = extra[i]  # StringID
                    elif delim == 'csv3col' and extra:
                        mapping["mapping"][sid] = extra[i]  # original key
                    else:
                        mapping["mapping"][sid] = str(i)
                else:
                    text = row[1] if len(row) >= 2 else (row[0] if row else "")
                    original_col1 = row[0] if row else ""
                    mapping["mapping"][sid] = original_col1
                writer.writerow([sid, text])

        mapping_path = output_path + ".mapping.json"
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)

        self.log(f"Converted {len(data_rows)} entries -> {output_path}")
        self.log(f"Mapping saved -> {mapping_path}")
        return output_path, mapping_path

    def restore_from_standard(self, translated_path, mapping_path, output_path=None):
        """Convert translated standard CSV back to original format using mapping.

        Returns output_path.
        """
        if output_path is None:
            base, _ = os.path.splitext(translated_path)
            output_path = f"{base}_restored.csv"

        if not os.path.exists(mapping_path):
            self.log(f"Mapping file not found: {mapping_path}", "ERROR")
            return None

        with open(mapping_path, 'r', encoding='utf-8') as f:
            mapping = json.load(f)

        orig_delim = mapping.get("delimiter", ",")
        has_header = mapping.get("has_header", False)
        header = mapping.get("header", None)
        id_to_col1 = mapping.get("mapping", {})

        translated = {}
        try:
            with open(translated_path, 'r', encoding='utf-8') as f:
                for row in csv.reader(f):
                    if len(row) >= 2:
                        translated[row[0]] = row[1]
        except Exception as e:
            self.log(f"Error reading translated file: {e}", "ERROR")
            return None

        # CSV 3-col format: write key,source,translation with translations filled
        if orig_delim == 'csv3col':
            orig_file = mapping.get("original_file", "")
            if not orig_file or not os.path.exists(orig_file):
                self.log(f"Original 3-col file not found: {orig_file}", "ERROR")
                return None
            delim = self.detect_delimiter(orig_file)
            with self._read_file(orig_file) as f:
                reader = csv.reader(f, delimiter=delim)
                all_rows = [row for row in reader]
            # Build reverse lookup: key -> translated text
            key_to_trans = {}
            for id_key, orig_key in id_to_col1.items():
                if id_key in translated:
                    key_to_trans[orig_key] = translated[id_key]
            updated = 0
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, delimiter=delim)
                for row in all_rows:
                    if len(row) >= 3 and row[0].strip() in key_to_trans:
                        row[2] = key_to_trans[row[0].strip()]
                        updated += 1
                    # Pad to 3 columns if needed
                    while len(row) < 3:
                        row.append('')
                    writer.writerow(row)
            self.log(f"CSV 3-col: Updated {updated} translation cells, wrote {len(all_rows)} rows.")

        # XML format: parse original, update translated entries by StringID
        elif orig_delim == 'xml':
            base, ext = os.path.splitext(output_path)
            if ext.lower() == '.csv':
                output_path = base + '.xml'
            orig_file = mapping.get("original_file", "")
            if not orig_file or not os.path.exists(orig_file):
                self.log(f"Original XML file not found: {orig_file}", "ERROR")
                return None
            tree = ET.parse(orig_file)
            root = tree.getroot()
            # Build reverse lookup: StringID -> ID_00XXX
            stringid_to_idkey = {v: k for k, v in id_to_col1.items()}
            updated = 0
            for item in root.findall('.//LocalisableString'):
                sid = item.get('StringID', '')
                id_key = stringid_to_idkey.get(sid)
                if id_key and id_key in translated:
                    content = item.find('Content')
                    if content is not None:
                        content.text = translated[id_key]
                        updated += 1
            # Write with XML declaration
            tree.write(output_path, encoding='utf-8', xml_declaration=True)
            self.log(f"XML: Updated {updated} entries, wrote to {output_path}.")

        # Newline format: write one text per line, ordered by original line index
        elif orig_delim == 'newline':
            base, ext = os.path.splitext(output_path)
            if ext.lower() == '.csv':
                output_path = base + '.txt'
            lines = []
            for sid, line_idx in id_to_col1.items():
                text = translated.get(sid, "")
                lines.append((int(line_idx), text))
            lines.sort(key=lambda x: x[0])
            with open(output_path, 'w', encoding='utf-8') as f:
                for _, text in lines:
                    f.write(text + '\n')

        elif orig_delim == 'subtitles':
            base, ext = os.path.splitext(output_path)
            if ext.lower() == '.csv':
                output_path = base + '.txt'
            orig_file = mapping.get("original_file", "")
            if not orig_file or not os.path.exists(orig_file):
                self.log(f"Original subtitles file not found: {orig_file}", "ERROR")
                return None
            with self._read_file(orig_file) as f:
                all_lines = [line.rstrip('\n\r') for line in f]
            # Splice in translations
            for sid, line_idx_str in id_to_col1.items():
                if sid in translated:
                    idx = int(line_idx_str)
                    if idx < len(all_lines):
                        all_lines[idx] = translated[sid]
            # Clean up arrow-separator lines: keep only Thai part, discard source language
            # Handles both ASCII " -> " and Unicode " → " (AI output often uses Unicode arrow)
            arrow_pattern = re.compile(r'\s+(?:->|→)\s+')
            cleaned = 0
            for i, line in enumerate(all_lines):
                m = arrow_pattern.search(line)
                if m:
                    parts = line.split(m.group(), 1)
                    if len(parts) == 2 and re.search(r'[฀-๿]', parts[1]):
                        all_lines[i] = parts[1]
                        cleaned += 1
            if cleaned:
                self.log(f"Cleaned {cleaned} arrow-separator lines (kept Thai only).")
            with open(output_path, 'w', encoding='utf-8') as f:
                for line in all_lines:
                    f.write(line + '\n')
            self.log(f"Merged {len(translated)} translations into {len(all_lines)} lines.")

        elif orig_delim == "whitespace":
            orig_delim = "    "
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                if has_header and header:
                    f.write(orig_delim.join(str(c) for c in header) + "\n")
                for sid, col1 in id_to_col1.items():
                    text = translated.get(sid, "")
                    f.write(f"{col1}{orig_delim}{text}\n")
        else:
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, delimiter=orig_delim)
                if has_header and header:
                    writer.writerow(header)
                for sid, col1 in id_to_col1.items():
                    text = translated.get(sid, "")
                    writer.writerow([col1, text])

        self.log(f"Restored {len(id_to_col1)} entries -> {output_path}")
        return output_path

    def analyze_file(self, file_path, delimiter=','):
        self.log("Analyzing file for auto-learning...")
        if not os.path.exists(file_path):
            self.log(f"File not found: {file_path}", "ERROR")
            return "No rules found (file not found)."

        try:
            with self._read_file(file_path) as f:
                reader = csv.reader(f, delimiter=delimiter)
                all_rows = [row for i, row in enumerate(reader) if i < 500 and len(row) >= 2]
            if all_rows and self._looks_like_header(all_rows[0]):
                rows = all_rows[1:]
            else:
                rows = all_rows
        except Exception as e:
            self.log(f"Error reading file: {e}", "ERROR")
            return "No rules found (read error)."

        # Scan for patterns
        found_tags = set()
        tag_pattern = re.compile(r'(<[^>]+>|\n|\r|%[sdiefg]|\{\d+\}|\[[^\]]+\]|\|[^|]+\|)')
        for row in rows:
            text = row[1]
            tags = tag_pattern.findall(text)
            for t in tags:
                if t not in found_tags:
                    found_tags.add(t)

        if found_tags:
            self.log(f"Detected tags/variables: {', '.join(found_tags)}")
            rules = "\n=== 4. AUTO-LEARNED RULES ===\n"
            rules += "- IMPORTANT: Ensure the following tags/variables remain exactly as they appear in the source text: "
            rules += ", ".join(found_tags) + "\n"
            return rules
        else:
            self.log("No specific tags or variables detected in the first 500 rows.")
            return ""

    def mask_tags(self, text):
        tag_pattern = r'(<[^>]+>|\\n|\\r|\n|\r|%[sdiefg]|\{\d+\}|\[[^\]]+\]|\|[^|]+\|)'
        tags = re.findall(tag_pattern, text)
        masked_text = text
        placeholders = {}
        for idx, tag in enumerate(tags):
            placeholder = f"[TAG_{idx}]"
            if placeholder not in placeholders:
                placeholders[placeholder] = tag
            masked_text = masked_text.replace(tag, placeholder, 1)
        return masked_text, placeholders

    def unmask_tags(self, translated_text, placeholders):
        unmasked = translated_text
        for placeholder, original_tag in placeholders.items():
            unmasked = unmasked.replace(placeholder, original_tag)
        return unmasked

    def save_checkpoint(self, master_dict, keys_order, filepath, delimiter=','):
        tmp_file = filepath + ".tmp"
        try:
            out_dir = os.path.dirname(filepath)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(tmp_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, delimiter=delimiter)
                for k in keys_order:
                    writer.writerow([k, master_dict.get(k, "")])
        except Exception as e:
            self.log(f"Save .tmp failed: {e}", "ERROR")
            return

        try:
            os.replace(tmp_file, filepath)
        except Exception as e:
            self.log(f"Replace original file failed: {e}", "ERROR")
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass

    def run_translation(self, config):
        with self._lock:
            if self._worker_thread and self._worker_thread.is_alive():
                self.log("Translation already in progress. Stop it first before starting a new one.", "WARN")
                return
            self.is_running = True
            self._worker_thread = threading.Thread(target=self._process_translation, args=(config,), daemon=True)
            self._worker_thread.start()

    def stop_translation(self):
        if self.is_running:
            self.is_running = False
            self.log("Stopping translation process... (Will stop after current batch)")

    def _process_translation(self, config):
        api_key = config.get("api_key", "")
        model = config.get("model", "deepseek-chat")
        input_csv = config.get("input_csv", "")
        output_csv = config.get("output_csv", "")
        base_prompt = config.get("system_prompt", "")
        canary_words = [w.strip() for w in config.get("canary_words", "").split(",") if w.strip()]
        glossary = config.get("glossary", "")

        batch_target_chars = 3000
        max_retries = 5

        if not api_key and model != "custom-local-llm":
            env_prefix_map = {
                "gemini": "GEMINI_API_KEY",
                "claude": "ANTHROPIC_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "gpt-": "OPENAI_API_KEY",
                "o1-": "OPENAI_API_KEY",
                "o3-": "OPENAI_API_KEY",
            }
            for prefix, env_var in env_prefix_map.items():
                if model.startswith(prefix):
                    api_key = os.environ.get(env_var, "")
                    break
            if not api_key:
                api_key = os.environ.get("OPENAI_API_KEY", "")

        if not api_key and model != "custom-local-llm":
            self.log("API Key is missing!", "ERROR")
            self.is_running = False
            return

        # Auto-Learn
        delimiter = self.detect_delimiter(input_csv)
        if delimiter != ',':
            self.log(f"Detected delimiter: {repr(delimiter)}")
        learned_rules = self.analyze_file(input_csv, delimiter)
        final_system_prompt = base_prompt + "\n\n=== 3. OFFICIAL GLOSSARY ===\n" + glossary + "\n" + learned_rules
        self.log("System prompt compiled successfully.")

        master_dict = {}
        if os.path.exists(output_csv):
            try:
                with self._read_file(output_csv) as f:
                    for row in csv.reader(f, delimiter=delimiter):
                        if len(row) >= 2:
                            master_dict[row[0]] = row[1]
                self.log(f"Loaded existing translation: {len(master_dict)} items.")
            except Exception as e:
                self.log(f"Error reading output CSV: {e}", "ERROR")

        if not os.path.exists(input_csv):
            self.log(f"Input file not found: {input_csv}", "ERROR")
            self.is_running = False
            return

        keys_order = []
        try:
            with self._read_file(input_csv) as f:
                reader = csv.reader(f, delimiter=delimiter)
                all_rows = list(reader)
            data_rows = all_rows
            if all_rows and self._looks_like_header(all_rows[0]):
                self.log("Header row detected, skipping first row.")
                data_rows = all_rows[1:]
            for row in data_rows:
                if len(row) >= 2:
                    k, v = row[0], row[1]
                    keys_order.append(k)
                    if k not in master_dict:
                        master_dict[k] = v
        except Exception as e:
            self.log(f"Error reading input CSV: {e}", "ERROR")
            self.is_running = False
            return

        self.log(f"Total entries to process: {len(keys_order)}")

        pending_tasks = []
        for string_id in keys_order:
            text = master_dict[string_id]
            if not text.strip() or bool(re.search(r'[\u0E00-\u0E7F]', text)) or re.match(r'^\{\d+\}$', text.strip()):
                continue
            
            masked_text, placeholders = self.mask_tags(text)
            if not re.sub(r'\[TAG_\d+\]', '', masked_text).strip():
                continue

            pending_tasks.append({
                "id": string_id,
                "masked_text": masked_text,
                "placeholders": placeholders,
                "raw_key": string_id
            })

        self.log(f"Entries waiting for translation: {len(pending_tasks)}")
        
        if not pending_tasks:
            self.log("Everything is already translated!")
            if self.progress_callback:
                self.progress_callback(1.0)
            self.is_running = False
            return

        batches = []
        current_batch = []
        current_chars = 0
        for task in pending_tasks:
            current_batch.append(task)
            current_chars += len(task["masked_text"])
            if current_chars >= batch_target_chars:
                batches.append(current_batch)
                current_batch = []
                current_chars = 0
        if current_batch:
            batches.append(current_batch)

        self.log(f"Divided into {len(batches)} batches.")

        translated_count = 0
        failed_count = 0
        total_batches = len(batches)

        for idx, batch in enumerate(batches, 1):
            if not self.is_running:
                self.log("Translation stopped by user.")
                break

            self.log(f"Processing Batch {idx}/{total_batches}...")
            
            lines = [f'"{t["id"]}"\t"{t["masked_text"]}"' for t in batch]
            user_prompt = f"Translate these {len(batch)} entries:\n" + "\n".join(lines)
            
            success = False
            for attempt in range(1, max_retries + 1):
                if not self.is_running:
                    break
                try:
                    reply = ""
                    # --- NATIVE API ROUTING ---
                    if model.startswith("gemini"):
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                        payload = {
                            "systemInstruction": {"parts": [{"text": final_system_prompt}]},
                            "contents": [{"parts": [{"text": user_prompt}]}],
                            "generationConfig": {"temperature": 0.3}
                        }
                        res = requests.post(url, json=payload, timeout=120)
                        if res.status_code == 429:
                            self.log(f"[429] Rate Limit. Waiting... (Attempt {attempt}/{max_retries})", "WARN")
                            time.sleep(5)
                            continue
                        if res.status_code != 200:
                            self.log(f"Gemini API Error {res.status_code}: {res.text[:100]}", "ERROR")
                            time.sleep(5)
                            continue
                        reply = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

                    elif model.startswith("claude"):
                        url = "https://api.anthropic.com/v1/messages"
                        headers = {
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json"
                        }
                        payload = {
                            "model": model,
                            "max_tokens": 8192,
                            "temperature": 0.3,
                            "system": final_system_prompt,
                            "messages": [{"role": "user", "content": user_prompt}]
                        }
                        res = requests.post(url, json=payload, headers=headers, timeout=120)
                        if res.status_code == 429:
                            self.log(f"[429] Rate Limit. Waiting... (Attempt {attempt}/{max_retries})", "WARN")
                            time.sleep(5)
                            continue
                        if res.status_code != 200:
                            self.log(f"Claude API Error {res.status_code}: {res.text[:100]}", "ERROR")
                            time.sleep(5)
                            continue
                        reply = res.json()["content"][0]["text"].strip()

                    else:
                        # OpenAI / DeepSeek / Local LLM format
                        url = "https://api.openai.com/v1/chat/completions"
                        actual_model = model
                        
                        if model.startswith("deepseek"):
                            url = "https://api.deepseek.com/chat/completions"
                        elif model == "custom-local-llm":
                            url = config.get("base_url", "http://localhost:1234/v1/chat/completions")
                            actual_model = config.get("custom_model", "llama-3-8b")
                            
                        headers = {
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        }
                        # Local LLMs might not need Authorization, but passing it usually doesn't hurt.
                        if not api_key and model == "custom-local-llm":
                            headers["Authorization"] = "Bearer dummy_key"
                            
                        payload = {
                            "model": actual_model,
                            "messages": [
                                {"role": "system", "content": final_system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            "temperature": 0.3,
                        }
                        if model.startswith("gpt-4") or model.startswith("deepseek") or model == "custom-local-llm":
                            payload["max_tokens"] = 8192
                            
                        res = requests.post(url, json=payload, headers=headers, timeout=120)
                        if res.status_code == 429:
                            self.log(f"[429] Rate Limit. Waiting... (Attempt {attempt}/{max_retries})", "WARN")
                            time.sleep(5)
                            continue
                        if res.status_code == 401:
                            self.log("Unauthorized (401). Invalid API Key.", "ERROR")
                            self.is_running = False
                            break
                        if res.status_code != 200:
                            self.log(f"API Error {res.status_code}: {res.text[:100]}", "ERROR")
                            time.sleep(5)
                            continue
                        reply = res.json()['choices'][0]['message']['content'].strip()
                    # --- END ROUTING ---
                    
                    # Canary check
                    canary_hit = False
                    for cw in canary_words:
                        if cw.lower() in reply.lower():
                            self.log(f"Detected hallucinated word: {cw}. Rejecting batch.", "WARN")
                            canary_hit = True
                            break
                    if canary_hit:
                        time.sleep(2)
                        continue

                    reply = re.sub(r'^```[^\n]*\n?', '', reply, flags=re.MULTILINE)
                    reply = re.sub(r'\n?```$', '', reply, flags=re.MULTILINE)

                    results = {}
                    for line in reply.split('\n'):
                        line = line.strip()
                        if '\t' in line:
                            parts = line.split('\t', 1)
                            if len(parts) >= 2:
                                results[parts[0].strip().strip('"')] = parts[1].strip().strip('"')

                    for task in batch:
                        tid = task["id"]
                        if tid in results:
                            final_thai = self.unmask_tags(results[tid], task["placeholders"])
                            master_dict[task["raw_key"]] = final_thai
                            translated_count += 1
                        else:
                            failed_count += 1

                    success = True
                    break

                except Exception as e:
                    self.log(f"Request Error: {e}", "ERROR")
                    time.sleep(5)

            if not success and self.is_running:
                self.log(f"Batch {idx} failed after {max_retries} attempts.", "ERROR")
                failed_count += len(batch)

            self.save_checkpoint(master_dict, keys_order, output_csv, delimiter)
            if self.progress_callback:
                self.progress_callback(idx / total_batches)
            
            if self.is_running and idx < total_batches:
                time.sleep(1)

        self.log(f"Operation Finished! Translated: {translated_count}, Failed: {failed_count}")
        if self.progress_callback:
            self.progress_callback(1.0)
        self.is_running = False
