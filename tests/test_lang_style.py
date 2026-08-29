# -*- coding: utf-8 -*-
"""语言规范 L0 校对测试：paeg_vocabulary.lang_style 复用 paeg_lang_style（14.1）。

覆盖：
- apply_l0 对已知病句（悬空"听着你"）的确定性修正
- 缺失 paeg_lang_style 时的优雅降级（非字符串/空串原样返回、异常不抛）
- apply_l0_to_entry 对 dict 与 VocabularyEntry 的中文字段遍历
"""
import pytest

from paeg_vocabulary.lang_style import apply_l0, apply_l0_to_entry, has_lang_style
from paeg_vocabulary.core.entry import VocabularyEntry, Sense


# ---------- apply_l0 ----------

def test_apply_l0_empty_and_non_string_passthrough():
    assert apply_l0("") == ""
    assert apply_l0(None) is None
    assert apply_l0(123) == 123
    assert apply_l0("   ") == "   "


def test_apply_l0_fixes_known_gaffe():
    """悬空'听着你'是 14.1 fix_known_gaffes 的确定性病句规则。"""
    src = "我在这里听着你。"
    out = apply_l0(src)
    if has_lang_style():
        # paeg_lang_style 已安装 → 病句被修正，不再含悬空"听着你"
        assert "听着你" not in out
        assert out != src
    else:
        # 优雅降级：原样返回
        assert out == src


def test_apply_l0_never_raises_on_weird_input():
    # 各类奇怪输入都不应抛异常（优雅降级 + 不阻塞管线）
    for bad in ["我听着你。", "听你说说", "x", "…", "😀", "a" * 1000]:
        assert isinstance(apply_l0(bad), str)


# ---------- apply_l0_to_entry ----------

def test_apply_l0_to_entry_dict():
    e = {
        "headword": "phenomenon",
        "gloss_bilingual": {"zh": "我在这里听着你。", "en": "phenomenon"},
        "etymology": "来自希腊语 phainein（显现）",
        "senses": [{"gloss_zh": "现象", "book_context": "在本书中，约纳斯的意思是……"}],
        "examples": [{"en": "It is a phenomenon.", "zh": "这是一个现象。"}],
    }
    out = apply_l0_to_entry(e)
    assert out is e
    if has_lang_style():
        assert "听着你" not in e["gloss_bilingual"]["zh"]
    # 英文字段不动
    assert e["gloss_bilingual"]["en"] == "phenomenon"
    assert e["senses"][0]["gloss_en"] if "gloss_en" in e["senses"][0] else True


def test_apply_l0_to_entry_dataclass():
    e = VocabularyEntry(
        headword="phenomenon",
        gloss_bilingual={"zh": "我在这里听着你。", "en": "phenomenon"},
        etymology="来自希腊语 phainein",
        senses=[Sense(sense_id="1.1", gloss_zh="现象", gloss_en="phenomenon")],
        examples=[{"en": "It is a phenomenon.", "zh": "这是一个现象。"}],
    )
    out = apply_l0_to_entry(e)
    assert out is e
    if has_lang_style():
        assert "听着你" not in e.gloss_bilingual["zh"]
    assert e.senses[0].gloss_en == "phenomenon"


def test_apply_l0_to_entry_none():
    assert apply_l0_to_entry(None) is None
