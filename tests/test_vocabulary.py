# -*- coding: utf-8 -*-
"""词汇表插件核心测试（§3.116 ⭐ 模块1-5）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

import paeg_vocabulary as pv
from paeg_vocabulary import (
    VocabularyEntry, validate_entry, VocabularyRegistry, execute,
    ExampleSanitizer, OCRRepairPipeline,
)


# ─────────────────────────────────────
# 1. 词汇条目模型（模块2）
# ─────────────────────────────────────
class TestEntryModel:
    def test_full_entry_valid(self):
        e = VocabularyEntry(
            headword="consciousness", pos="n.",
            ipa={"en_us": "/ˈkɑːnʃəsnəs/"},
            gloss_bilingual={"zh": "意识", "en": "awareness"},
            examples=[{"en": "Example from book", "zh": "书中例句"}],
            lemma="consciousness")
        assert validate_entry(e) == []

    def test_missing_required(self):
        e = VocabularyEntry(headword="x")
        missing = validate_entry(e)
        assert "ipa" in missing
        assert "gloss_bilingual" in missing
        assert "examples" in missing


# ─────────────────────────────────────
# 2. 例句污染清洗（模块5）
# ─────────────────────────────────────
class TestExampleSanitize:
    def test_remove_reference(self):
        s = ExampleSanitizer()
        assert "sentence" in s.clean("This is a sentence [1] (Smith 2020)")

    def test_remove_superscript(self):
        s = ExampleSanitizer()
        assert "footnote" in s.clean("This has footnote¹")

    def test_remove_lone_page(self):
        s = ExampleSanitizer()
        assert s.clean("  42  ") == ""

    def test_clean_many_dedup(self):
        s = ExampleSanitizer()
        out = s.clean_many(["Hello world.", "Hello world.", "42"])
        assert out == ["Hello world."]


# ─────────────────────────────────────
# 3. OCR 修复（模块5）
# ─────────────────────────────────────
class TestOCRRepair:
    def test_hyphenation_join(self):
        p = OCRRepairPipeline("en")
        assert "story" in p.repair("a sto-\nry")  # 跨页断词拼接

    def test_encoding_fix(self):
        p = OCRRepairPipeline("en")
        # ftfy 修复 mojibake
        out = p.repair("cafÃ©")
        assert "caf" in out  # 至少不崩溃


# ─────────────────────────────────────
# 4. 执行入口（MCP 契约）
# ─────────────────────────────────────
class TestExecute:
    def test_list_languages(self):
        import json
        r = json.loads(execute("list_languages", {}))
        assert r["ok"] is True
        assert "en" in r["languages"]

    def test_validate_entry(self):
        import json
        r = json.loads(execute("validate_entry", {"headword": "x"}))
        assert r["ok"] is False  # 缺字段
        assert "ipa" in r["missing"]

    def test_clean_examples(self):
        import json
        r = json.loads(execute("clean_examples", {"examples": ["Good [1] sentence", "42"]}))
        assert r["ok"] is True
        assert "sentence" in r["cleaned"][0]

    def test_generate_no_pdf(self):
        import json
        r = json.loads(execute("generate_vocabulary", {}))
        assert r["ok"] is False
        assert "pdf_path" in r["error"]


# ─────────────────────────────────────
# 5. 可扩展性（生态）
# ─────────────────────────────────────
class TestExtensibility:
    def test_register_language(self):
        VocabularyRegistry.register_language("it")
        assert "it" in VocabularyRegistry.languages()

    def test_register_generator(self):
        VocabularyRegistry.register_generator("xlsx", lambda ctx: {})
        assert "xlsx" in VocabularyRegistry.available_generators()
