import csv
import json
import os
import sys
import tempfile
from translator_engine import TranslatorEngine


def make_engine():
    return TranslatorEngine()


class TestMaskTags:
    def test_html_tags(self):
        engine = make_engine()
        text = '<font color="red">Hello</font>'
        masked, placeholders = engine.mask_tags(text)
        assert "[TAG_0]" in masked
        assert "[TAG_1]" in masked
        assert placeholders["[TAG_0]"] == '<font color="red">'
        assert placeholders["[TAG_1]"] == '</font>'

    def test_format_specifiers(self):
        engine = make_engine()
        text = "Damage: %d, Name: %s"
        masked, placeholders = engine.mask_tags(text)
        assert placeholders["[TAG_0]"] == "%d"
        assert placeholders["[TAG_1]"] == "%s"

    def test_brace_placeholders(self):
        engine = make_engine()
        text = "You have {0} gold and {1} items"
        masked, placeholders = engine.mask_tags(text)
        assert placeholders["[TAG_0]"] == "{0}"
        assert placeholders["[TAG_1]"] == "{1}"

    def test_bracket_tags(self):
        engine = make_engine()
        text = "[Action] Attack the enemy"
        masked, placeholders = engine.mask_tags(text)
        assert placeholders["[TAG_0]"] == "[Action]"

    def test_pipe_tags(self):
        engine = make_engine()
        text = "Press |A| to jump and |B| to attack"
        masked, placeholders = engine.mask_tags(text)
        assert placeholders["[TAG_0]"] == "|A|"
        assert placeholders["[TAG_1]"] == "|B|"
        assert "|A|" not in masked
        assert "|B|" not in masked

    def test_pipe_tag_with_preserved_text(self):
        engine = make_engine()
        text = "Use |Left Stick| to move"
        masked, placeholders = engine.mask_tags(text)
        assert placeholders["[TAG_0]"] == "|Left Stick|"
        assert "Use [TAG_0] to move" == masked

    def test_newlines(self):
        engine = make_engine()
        text = "Line1\nLine2\rLine3"
        masked, placeholders = engine.mask_tags(text)
        assert "\n" not in masked
        assert "\r" not in masked
        assert len(placeholders) == 2

    def test_no_tags(self):
        engine = make_engine()
        text = "Plain text with no special markers"
        masked, placeholders = engine.mask_tags(text)
        assert masked == text
        assert placeholders == {}

    def test_multiple_same_tags(self):
        engine = make_engine()
        text = "{0} apples and {0} oranges"
        masked, placeholders = engine.mask_tags(text)
        assert "[TAG_0]" in masked
        assert "[TAG_1]" in masked
        assert placeholders["[TAG_0]"] == "{0}"
        assert placeholders["[TAG_1]"] == "{0}"


class TestUnmaskTags:
    def test_restores_tags(self):
        engine = make_engine()
        text = '<font>Hello</font> %s'
        masked, placeholders = engine.mask_tags(text)
        translated = '<font>สวัสดี</font> %s'
        restored = engine.unmask_tags(translated, placeholders)
        assert restored == translated

    def test_preserves_thai_content(self):
        engine = make_engine()
        text = "[Quest] Find the sword"
        masked, placeholders = engine.mask_tags(text)
        translated = "[Quest] ตามหาดาบ"
        restored = engine.unmask_tags(translated, placeholders)
        assert restored == translated


class TestSaveCheckpoint:
    def test_writes_valid_csv(self):
        engine = make_engine()
        master_dict = {"ID_001": "สวัสดี", "ID_002": "ลาก่อน"}
        keys_order = ["ID_001", "ID_002"]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
            tmp_path = f.name

        try:
            engine.save_checkpoint(master_dict, keys_order, tmp_path)
            with open(tmp_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
            assert len(rows) == 2
            assert rows[0] == ["ID_001", "สวัสดี"]
            assert rows[1] == ["ID_002", "ลาก่อน"]
        finally:
            os.unlink(tmp_path)

    def test_key_with_special_chars(self):
        engine = make_engine()
        master_dict = {"ID,with,commas": "value", 'ID"with"quotes': "value2"}
        keys_order = ["ID,with,commas", 'ID"with"quotes']

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
            tmp_path = f.name

        try:
            engine.save_checkpoint(master_dict, keys_order, tmp_path)
            with open(tmp_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
            assert len(rows) == 2
            assert rows[0][0] == "ID,with,commas"
            assert rows[1][0] == 'ID"with"quotes'
        finally:
            os.unlink(tmp_path)

    def test_empty_value(self):
        engine = make_engine()
        master_dict = {"ID_001": ""}
        keys_order = ["ID_001"]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
            tmp_path = f.name

        try:
            engine.save_checkpoint(master_dict, keys_order, tmp_path)
            with open(tmp_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
            assert rows[0] == ["ID_001", ""]
        finally:
            os.unlink(tmp_path)

    def test_creates_output_dir(self):
        engine = make_engine()
        master_dict = {"k": "v"}
        keys_order = ["k"]
        tmp_dir = tempfile.mkdtemp()
        nested_path = os.path.join(tmp_dir, "subdir", "out.csv")
        try:
            engine.save_checkpoint(master_dict, keys_order, nested_path)
            assert os.path.exists(nested_path)
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_tab_delimiter(self):
        engine = make_engine()
        master_dict = {"Barret": "Ha! Bring it on!", "Cloud": "Not interested."}
        keys_order = ["Barret", "Cloud"]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False, encoding="utf-8", newline="") as f:
            tmp_path = f.name

        try:
            engine.save_checkpoint(master_dict, keys_order, tmp_path, delimiter='\t')
            with open(tmp_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f, delimiter='\t')
                rows = list(reader)
            assert len(rows) == 2
            assert rows[0] == ["Barret", "Ha! Bring it on!"]
            assert rows[1] == ["Cloud", "Not interested."]
        finally:
            os.unlink(tmp_path)

    def test_pipe_delimiter(self):
        engine = make_engine()
        master_dict = {"ID_001": "hello", "ID_002": "world"}
        keys_order = ["ID_001", "ID_002"]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
            tmp_path = f.name

        try:
            engine.save_checkpoint(master_dict, keys_order, tmp_path, delimiter='|')
            with open(tmp_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f, delimiter='|')
                rows = list(reader)
            assert len(rows) == 2
            assert rows[0] == ["ID_001", "hello"]
            assert rows[1] == ["ID_002", "world"]
        finally:
            os.unlink(tmp_path)


class TestDelimiterDetection:
    def test_detects_tab(self):
        engine = make_engine()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False, encoding="utf-8", newline="") as f:
            f.write("Barret\tHa! Bring it on!\n")
            f.write("Cloud\tNot interested.\n")
            tmp_path = f.name
        try:
            delim = engine.detect_delimiter(tmp_path)
            assert delim == '\t'
        finally:
            os.unlink(tmp_path)

    def test_detects_pipe(self):
        engine = make_engine()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
            f.write("ID_001|Hello World\n")
            f.write("ID_002|Goodbye\n")
            tmp_path = f.name
        try:
            delim = engine.detect_delimiter(tmp_path)
            assert delim == '|'
        finally:
            os.unlink(tmp_path)

    def test_detects_comma(self):
        engine = make_engine()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
            f.write('ID_001,"Hello World"\n')
            f.write('ID_002,"Goodbye"\n')
            tmp_path = f.name
        try:
            delim = engine.detect_delimiter(tmp_path)
            assert delim == ','
        finally:
            os.unlink(tmp_path)


class TestHeaderDetection:
    def test_detects_header_with_do_not_delete(self):
        engine = make_engine()
        assert engine._looks_like_header(["Character's name", "DO NOT DELETE '|' Text"])

    def test_detects_header_with_name(self):
        engine = make_engine()
        assert engine._looks_like_header(["Name", "Dialogue"])

    def test_rejects_data_row(self):
        engine = make_engine()
        assert not engine._looks_like_header(["Barret", "Ha! Bring it on!"])

    def test_rejects_short_row(self):
        engine = make_engine()
        assert not engine._looks_like_header(["single_column"])


class TestCanary:
    def test_canary_check_case_insensitive(self):
        """Simulate what _process_translation does for canary check."""
        canary_words = ["death", "HELL"]
        reply1 = "This contains DEATH in uppercase"
        reply2 = "This contains death in lowercase"
        reply3 = "No canary hits here"
        reply4 = "This mentions hell in lowercase"

        assert any(cw.lower() in reply1.lower() for cw in canary_words)
        assert any(cw.lower() in reply2.lower() for cw in canary_words)
        assert not any(cw.lower() in reply3.lower() for cw in canary_words)
        assert any(cw.lower() in reply4.lower() for cw in canary_words)


class TestThaiDetection:
    def test_detects_thai(self):
        import re
        assert bool(re.search(r'[฀-๿]', "สวัสดี"))
        assert not bool(re.search(r'[฀-๿]', "Hello"))


class TestConvertRestore:
    def test_convert_tab_file(self):
        engine = make_engine()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False, encoding="utf-8", newline="") as f:
            f.write("Character's name\t... DO NOT DELETE '|'\tText\n")
            f.write("Barret\tHa! Bring it on!\n")
            f.write("Cloud\tNot interested.\n")
            tmp_path = f.name
        try:
            std_path, mapping_path = engine.convert_to_standard(tmp_path)
            assert std_path is not None
            assert os.path.exists(std_path)
            assert os.path.exists(mapping_path)

            with open(std_path, "r", encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
            assert len(rows) == 2
            assert rows[0][0] == "ID_00001"
            assert rows[0][1] == "Ha! Bring it on!"
            assert rows[1][0] == "ID_00002"
            assert rows[1][1] == "Not interested."

            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            assert mapping["has_header"] is True
            assert mapping["mapping"]["ID_00001"] == "Barret"
            assert mapping["mapping"]["ID_00002"] == "Cloud"
        finally:
            for p in [tmp_path, std_path, mapping_path]:
                try:
                    os.unlink(p)
                except Exception:
                    pass

    def test_round_trip_tab(self):
        engine = make_engine()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False, encoding="utf-8", newline="") as f:
            f.write("Name\tDialogue\n")
            f.write("Tifa\tLet's go!\n")
            f.write("Aerith\tWait for me.\n")
            orig = f.name
        try:
            std_path, mapping_path = engine.convert_to_standard(orig)

            # Simulate translation
            with open(std_path, "r", encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
            with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                for r in rows:
                    w.writerow([r[0], f"[TH] {r[1]}"])
                translated_path = f.name

            restored = engine.restore_from_standard(translated_path, mapping_path)
            assert restored is not None

            with open(restored, "r", encoding="utf-8", newline="") as f:
                restored_rows = list(csv.reader(f, delimiter="\t"))
            assert restored_rows[0] == ["Name", "Dialogue"]
            assert restored_rows[1] == ["Tifa", "[TH] Let's go!"]
            assert restored_rows[2] == ["Aerith", "[TH] Wait for me."]
        finally:
            for p in [orig, std_path, mapping_path, translated_path, restored]:
                try:
                    os.unlink(p)
                except Exception:
                    pass

    def test_convert_no_header(self):
        engine = make_engine()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
            f.write('ID_001,"Hello World"\n')
            f.write('ID_002,"Goodbye"\n')
            tmp_path = f.name
        try:
            std_path, mapping_path = engine.convert_to_standard(tmp_path)
            assert std_path is not None
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            assert mapping["has_header"] is False
            assert mapping["mapping"]["ID_00001"] == "ID_001"
        finally:
            for p in [tmp_path, std_path, mapping_path]:
                try:
                    os.unlink(p)
                except Exception:
                    pass

    def test_try_parse_rows_whitespace_fallback(self):
        engine = make_engine()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8", newline="") as f:
            f.write("Name    Text\n")
            f.write("Key1    Value One\n")
            f.write("Key2    Value Two\n")
            tmp_path = f.name
        try:
            rows, delim, has_header = engine._try_parse_rows(tmp_path)
            assert len(rows) >= 2
            assert has_header
            data_rows = rows[1:] if has_header else rows
            assert len(data_rows) == 2
            assert data_rows[0][0] == "Key1"
            assert data_rows[0][1] == "Value One"
        finally:
            os.unlink(tmp_path)

    def test_convert_newline_txt(self):
        engine = make_engine()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8", newline="") as f:
            f.write("Slow Motion\n")
            f.write("Press |L3| to mark enemies\n")
            f.write("Get to the Car\n")
            tmp_path = f.name
        try:
            std_path, mapping_path = engine.convert_to_standard(tmp_path, force_delim='newline')
            assert std_path is not None
            assert os.path.exists(std_path)

            with open(std_path, "r", encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
            assert len(rows) == 3
            assert rows[0] == ["ID_00001", "Slow Motion"]
            assert rows[1] == ["ID_00002", "Press |L3| to mark enemies"]
            assert rows[2] == ["ID_00003", "Get to the Car"]

            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            assert mapping["delimiter"] == "newline"
            assert mapping["has_header"] is False
            assert mapping["mapping"]["ID_00001"] == "0"
            assert mapping["mapping"]["ID_00002"] == "1"
            assert mapping["mapping"]["ID_00003"] == "2"
        finally:
            for p in [tmp_path, std_path, mapping_path]:
                try:
                    os.unlink(p)
                except Exception:
                    pass

    def test_round_trip_newline(self):
        engine = make_engine()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8", newline="") as f:
            f.write("Line one\n")
            f.write("Line two |X| tag\n")
            f.write("Line three\n")
            orig = f.name
        try:
            std_path, mapping_path = engine.convert_to_standard(orig, force_delim='newline')

            # Simulate translation
            with open(std_path, "r", encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
            with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                for r in rows:
                    w.writerow([r[0], f"[TH] {r[1]}"])
                translated_path = f.name

            restored = engine.restore_from_standard(translated_path, mapping_path)
            assert restored is not None
            assert restored.endswith('.txt')

            with open(restored, "r", encoding="utf-8") as f:
                restored_lines = [l.rstrip('\n\r') for l in f.readlines()]
            assert restored_lines == ["[TH] Line one", "[TH] Line two |X| tag", "[TH] Line three"]
        finally:
            for p in [orig, std_path, mapping_path, translated_path, restored]:
                try:
                    os.unlink(p)
                except Exception:
                    pass

    def test_auto_detect_newline_with_pipe_tags(self):
        engine = make_engine()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8", newline="") as f:
            f.write("Plain text line\n")
            f.write("Press |L3| to mark\n")
            f.write("|R| Rotate\\|L| Navigate\n")
            f.write("Another plain line\n")
            tmp_path = f.name
        try:
            rows, delim, has_header = engine._try_parse_rows(tmp_path)
            assert delim == 'newline'
            assert len(rows) == 4
            assert rows[0] == ["Plain text line"]
            assert rows[1] == ["Press |L3| to mark"]
            assert rows[2] == ["|R| Rotate\\|L| Navigate"]
            assert not has_header
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
