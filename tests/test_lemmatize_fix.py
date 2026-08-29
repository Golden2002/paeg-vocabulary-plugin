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
    # §3.116 ⭐ -ing/-ed dropped-e 还原：making→make（不再 mak）
    assert _rule_lemmatize("making") == "make"
    assert _rule_lemmatize("worked") == "work"


def test_rule_lemmatize_ing_ed_restore():
    """-ing/-ed 去尾后还原 dropped-e 与双写辅音（ecdict 校验）。"""
    assert _rule_lemmatize("charging") == "charge"
    assert _rule_lemmatize("living") == "live"
    assert _rule_lemmatize("taking") == "take"
    assert _rule_lemmatize("running") == "run"
    assert _rule_lemmatize("stopping") == "stop"
    # 词干本身是合法词 → 不动（walk/work/call）
    assert _rule_lemmatize("walking") == "walk"
    assert _rule_lemmatize("calling") == "call"
    # -ss 结尾非复数 → 不还原（process 不误切 proces）
    assert _rule_lemmatize("process") == "process"


def test_rule_lemmatize_safe():
    """-s 结尾但非复数（news/maths）不还原。"""
    assert _rule_lemmatize("news") == "news"
    assert _rule_lemmatize("maths") == "maths"


def test_rule_lemmatize_ing_base_word_not_miscut():
    """-ing/-ed 结尾的实词不被误切（spring→spr / string→str / during→dur 等）。

    §3.116 ⭐ Round 4：规则级兜底在「还原结果不比原词更常见」时保持原词，
    修复 -ing 规则把 spring/string/during/according 等实词与功能词切成
    spr/str/dur/accord 的缺陷（这些词干是 ecdict 里的缩写/生僻词，frq=0）。
    """
    assert _rule_lemmatize("spring") == "spring"
    assert _rule_lemmatize("string") == "string"
    assert _rule_lemmatize("during") == "during"
    assert _rule_lemmatize("according") == "according"
    assert _rule_lemmatize("hundred") == "hundred"
    assert _rule_lemmatize("sacred") == "sacred"
    assert _rule_lemmatize("wicked") == "wicked"


def test_rule_lemmatize_ing_real_words_stoplist():
    """-ing 结尾但为独立名词/形容词的词保持原形（Round 5 ⭐）。

    频率兜底（Round 4）挡得住 spring→spr（去尾后非词典词），但挡不住
    evening→even / building→build / meaning→mean 这类「去尾后是更常见词」的
    语义误切——这些 -ing 词形是独立词（傍晚/建筑/意义/有趣的），非 base 动词屈折。
    """
    # 时间/抽象名词
    assert _rule_lemmatize("evening") == "evening"
    assert _rule_lemmatize("morning") == "morning"
    assert _rule_lemmatize("meaning") == "meaning"
    assert _rule_lemmatize("beginning") == "beginning"
    assert _rule_lemmatize("following") == "following"
    # 具体名词
    assert _rule_lemmatize("building") == "building"
    assert _rule_lemmatize("wedding") == "wedding"
    assert _rule_lemmatize("meeting") == "meeting"
    assert _rule_lemmatize("opening") == "opening"
    assert _rule_lemmatize("ceiling") == "ceiling"
    assert _rule_lemmatize("offspring") == "offspring"
    # 形容词
    assert _rule_lemmatize("interesting") == "interesting"
    assert _rule_lemmatize("surprising") == "surprising"
    assert _rule_lemmatize("amazing") == "amazing"
    # 领域/职业名词
    assert _rule_lemmatize("engineering") == "engineering"
    assert _rule_lemmatize("marketing") == "marketing"
    assert _rule_lemmatize("accounting") == "accounting"
    assert _rule_lemmatize("consulting") == "consulting"
    assert _rule_lemmatize("training") == "training"


def test_rule_lemmatize_ing_verb_still_reduces():
    """stoplist 不误伤真·动名词/动词：仍正确还原到 base 动词（Round 5 回归）。"""
    assert _rule_lemmatize("making") == "make"
    assert _rule_lemmatize("running") == "run"
    assert _rule_lemmatize("walking") == "walk"
    assert _rule_lemmatize("worked") == "work"
    assert _rule_lemmatize("charging") == "charge"
    assert _rule_lemmatize("living") == "live"
    assert _rule_lemmatize("learning") == "learn"
    assert _rule_lemmatize("reading") == "read"


def test_rule_lemmatize_irregular_third_person():
    """不规则第三人称单数不误切（goes→goe / does→doe，Round 6 ⭐）。

    -s 规则会把 goes→goe、does→doe（词尾丢失畸形词条）；这三词属不规则屈折，
    必须走不规则表直接映射 base 动词，而非 -s 去尾。
    """
    assert _rule_lemmatize("goes") == "go"
    assert _rule_lemmatize("does") == "do"
    assert _rule_lemmatize("has") == "have"


def test_recover_truncated():
    """词尾丢失恢复（ecdict 词典校验，需 ecdict 可用）。"""
    import pytest
    pytest.importorskip("paeg_vocabulary.wordbank")
    assert _recover_truncated("science") == "science"  # 合法词不恢复
    assert _recover_truncated("use") == "use"  # 合法词不误伤 used
