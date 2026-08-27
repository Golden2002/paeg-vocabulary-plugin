# -*- coding: utf-8 -*-
"""词汇难度分级矩阵测试（§3.116 ⭐：CEFR/雅思/四六级/考研/专四专八映射 + 档位过滤）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.level_matrix import (
    select_cefr_max, filter_by_level, guess_cefr_from_zipf,
    resolve_preset, user_presets, level_matrix_table, exam_systems, cefr_order,
)


# ─────────────────────────────────────
# 1. 档位 → CEFR 映射
# ─────────────────────────────────────
class TestSelectCefr:
    def test_kaoyan_70(self):
        """考研 70 分 → C1（用户核心场景）。"""
        assert select_cefr_max("kaoyan", 70) == "C1"

    def test_ielts_65(self):
        assert select_cefr_max("ielts", 6.5) == "C1"

    def test_cet4_425(self):
        """四级 425 过线 → B1。"""
        assert select_cefr_max("cet4", 425) == "B1"

    def test_cet6_520(self):
        assert select_cefr_max("cet6", 520) == "B2"

    def test_gaokao_130(self):
        assert select_cefr_max("gaokao", 130) == "B2"

    def test_tem4_pass(self):
        assert select_cefr_max("tem4", 60) == "B2"

    def test_unknown_exam(self):
        """未知体系 → C2（不限制）。"""
        assert select_cefr_max("unknown", 0) == "C2"


# ─────────────────────────────────────
# 2. Zipf → CEFR 桥接
# ─────────────────────────────────────
class TestZipfBridge:
    def test_high_freq(self):
        """§3.116 ⭐ 修正方向：zipf 高（常见）→ CEFR 低（A1）。"""
        assert guess_cefr_from_zipf(7.7) == "A1"  # the

    def test_low_freq(self):
        """zipf 低（稀有）→ CEFR 高（C2）。"""
        assert guess_cefr_from_zipf(2.0) == "C2"

    def test_mid(self):
        assert guess_cefr_from_zipf(4.0) == "B2"  # zipf 3.5-4.5 → B2

    def test_calibrated(self):
        """校准后桥接：zipf 4.23（雅思 7.5 阈值）→ B2（需学习——高于 B1 用户水平）。"""
        assert guess_cefr_from_zipf(4.23) in ("B1", "B2", "C1")


# ─────────────────────────────────────
# 3. 按档位过滤
# ─────────────────────────────────────
class TestFilterByLevel:
    def test_keep_below_cap(self):
        words = [
            {"lemma": "the", "cefr": "A1"},
            {"lemma": "ephemeral", "cefr": "C2"},
            {"lemma": "serendipity", "cefr": "C1"},
        ]
        kept = filter_by_level(words, "B2")
        lemmas = [w["lemma"] for w in kept]
        assert "the" in lemmas
        assert "ephemeral" not in lemmas  # C2 > B2 被过滤
        assert "serendipity" not in lemmas  # C1 > B2 被过滤

    def test_keep_all_c2(self):
        words = [{"lemma": "x", "cefr": "C2"}, {"lemma": "y", "cefr": "A1"}]
        assert len(filter_by_level(words, "C2")) == 2

    def test_zipf_fallback(self):
        """无 cefr 标签 → zipf 兜底（§3.116 修正：zipf 高=常见=A1）。"""
        words = [{"lemma": "the", "zipf": 7.7}]  # A1（常见词）
        kept = filter_by_level(words, "B2")
        assert len(kept) == 1  # A1 ≤ B2 保留

    def test_unknown_cefr_kept(self):
        words = [{"lemma": "x", "cefr": ""}]
        assert len(filter_by_level(words, "B1")) == 1  # 未知默认保留


# ─────────────────────────────────────
# 4. 用户预设
# ─────────────────────────────────────
class TestPresets:
    def test_presets_exist(self):
        presets = user_presets()
        assert len(presets) >= 8
        labels = [p["label"] for p in presets]
        assert "考研 70+" in labels
        assert "雅思 6.5+" in labels

    def test_resolve_preset(self):
        p = resolve_preset("kaoyan-70")
        assert p["cefr_max"] == "C1"
        assert p["label"] == "考研 70+"

    def test_resolve_all(self):
        p = resolve_preset("all")
        assert p["cefr_max"] == "C2"


# ─────────────────────────────────────
# 5. 展示内容（词汇对应表）
# ─────────────────────────────────────
class TestDisplay:
    def test_exam_systems_covered(self):
        systems = exam_systems()
        for k in ("ielts", "toefl", "cet4", "cet6", "kaoyan", "tem4", "tem8", "gaokao"):
            assert k in systems, f"缺 {k}"

    def test_table_generates(self):
        t = level_matrix_table()
        assert "考研英语" in t
        assert "雅思" in t
        assert "→" in t  # 分数段 → CEFR

    def test_cefr_order(self):
        assert cefr_order() == ["A1", "A2", "B1", "B2", "C1", "C2"]
