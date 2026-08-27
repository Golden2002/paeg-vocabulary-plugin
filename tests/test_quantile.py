# -*- coding: utf-8 -*-
"""P1 ⭐ 统一分位引擎测试（混合分位 Q 计算——zipf_q + family_q + cefr_q）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import pytest

from paeg_vocabulary.quantile_engine import (
    zipf_to_quantile, family_band, cefr_to_quantile,
    compute_q, user_level_to_u, DEFAULT_WEIGHTS,
)


# ── R1: zipf → 分位（越高越常见 → Q 越低）──
def test_zipf_quantile_direction():
    """常见词 zipf 高 → Q 低；稀有词 zipf 低 → Q 高。"""
    q_the = zipf_to_quantile(7.73)       # the
    q_abandonment = zipf_to_quantile(3.4)  # abandonment
    assert q_the < q_abandonment, "常见词分位应低于稀有词"
    assert 0.0 <= q_the <= 1.0
    assert 0.0 <= q_abandonment <= 1.0


def test_zipf_quantile_midpoint():
    """zipf=5.5（中点）→ Q≈0.5。"""
    q = zipf_to_quantile(5.5)
    assert 0.4 <= q <= 0.6


# ── R2: Nation 词族档位 ──
def test_family_band_known_words():
    """第 1 档词（the/able）→ band 1。"""
    assert family_band("the") == 1, f"the 应在第 1 档"
    assert family_band("able") == 1, f"able 应在第 1 档"


def test_family_band_unknown():
    """不在词族表的词 → None（走 zipf 兜底）。"""
    assert family_band("zzzqqq_nonexistent_xyz") is None


# ── R3: CEFR → 分位 ──
def test_cefr_to_quantile():
    assert cefr_to_quantile("A1") == pytest.approx(0.05)
    assert cefr_to_quantile("C2") == pytest.approx(0.95)
    assert cefr_to_quantile("B1") == pytest.approx(0.40)


def test_cefr_unknown_returns_none():
    assert cefr_to_quantile("") is None
    assert cefr_to_quantile("X9") is None


# ── R4: compute_q 混合 ──
def test_compute_q_direction():
    """常见词 Q 低，稀有词 Q 高。"""
    q_common = compute_q("the")
    q_rare = compute_q("abandonment")
    assert 0.0 <= q_common <= 1.0
    assert 0.0 <= q_rare <= 1.0
    assert q_common < q_rare, f"the({q_common:.3f}) 应比 abandonment({q_rare:.3f}) 简单"


def test_compute_q_with_cefr_hint():
    """提供 CEFR 提示时走 cefr 权重路径。"""
    q = compute_q("run", cefr_hint="B1")
    assert 0.0 <= q <= 1.0


def test_compute_q_returns_dict():
    """compute_q 返回 (q, meta) 结构——含分量信号供调试。"""
    q, meta = compute_q("life", with_meta=True)
    assert 0.0 <= q <= 1.0
    assert "zipf_q" in meta or "family_q" in meta or "cefr_q" in meta


# ── R5: 用户水平 → U ──
def test_user_level_to_u():
    """自述词汇量 → U（clamp 0.10-0.95）。公式 U=(V-1500)/8500。"""
    assert user_level_to_u(3000) == pytest.approx((3000 - 1500) / 8500, abs=0.02)
    assert user_level_to_u(6500) == pytest.approx((6500 - 1500) / 8500, abs=0.02)
    assert user_level_to_u(100000) <= 0.95  # 上限 clamp
    assert user_level_to_u(0) >= 0.10       # 下限 clamp


def test_user_level_to_u_known_exams():
    """已知考试 → U（CEFR→词族分位：雅思 7.5 已掌握 C1 → 0.70）。"""
    assert user_level_to_u(500, exam="ielts", score=7.5) == pytest.approx(0.70, abs=0.02)
    assert user_level_to_u(500, exam="toefl", score=100) == pytest.approx(0.70, abs=0.02)
    # 雅思 6.5 已掌握 B2 → 0.55 → 更低 U
    u65 = user_level_to_u(500, exam="ielts", score=6.5)
    u75 = user_level_to_u(500, exam="ielts", score=7.5)
    assert u65 < u75, "雅思 6.5 的 U 应低于 7.5"


# ── R6: 分档 ──
def test_tier_rounding():
    """Q → 9 档 / 18 档。"""
    from paeg_vocabulary.quantile_engine import quantile_to_tier
    assert quantile_to_tier(0.05) == 1
    assert quantile_to_tier(0.95) == 9
    assert quantile_to_tier(0.50) == 5
