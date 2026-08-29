# -*- coding: utf-8 -*-
"""词形还原修复测试：-es 规则误伤（sciences→scienc）+ 停用词绕过（this→thi）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from paeg_vocabulary.pipeline.clean_dedup import _rule_lemmatize, _recover_truncated


def test_rule_lemmatize_es_not_miscut():
    """普通 -s 复数不应被 -es 规则误切（sciences→science 而非 scienc）。"""
    assert _rule_lemmatize("sciences") == "science"
    assert _rule_lemmatize("includes") == "include"
    assert _rule_lemmatize("decades") == "decade"
    assert _rule_lemmatize("voices") == "voice"


def test_rule_lemmatize_true_es():
    """真·es 复数（-ches/-shes/-xes/-zes/-sses）正确去掉 es。"""
    assert _rule_lemmatize("boxes") == "box"
    assert _rule_lemmatize("churches") == "church"
    assert _rule_lemmatize("watches") == "watch"


def test_rule_lemmatize_ies_ing_ed():
    assert _rule_lemmatize("studies") == "study"
    assert _rule_lemmatize("making") == "mak"
    assert _rule_lemmatize("worked") == "work"


def test_rule_lemmatize_safe():
    """-s 结尾但非复数（news/maths）不还原。"""
    assert _rule_lemmatize("news") == "news"
    assert _rule_lemmatize("maths") == "maths"


def test_recover_truncated():
    """词尾丢失恢复（ecdict 词典校验，需 ecdict 可用）。"""
    import pytest
    pytest.importorskip("paeg_vocabulary.wordbank")
    assert _recover_truncated("science") == "science"  # 合法词不恢复
    assert _recover_truncated("use") == "use"  # 合法词不误伤 used
