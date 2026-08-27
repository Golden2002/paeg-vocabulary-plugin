# -*- coding: utf-8 -*-
"""paeg_vocabulary.quantile_engine — P1 ⭐ 统一词汇分位引擎。

用户设计原则（§3.116 ⭐）："一个标准化的过滤阈值，如 0.10 0.15 0.20 0.25 直到
0.90 0.95，然后他会把词分为不同的层级"——把每个词映射到统一的 0-1 难度分位空间。

混合分位 Q（Oracle 验证方案）：
- zipf_q   = 1 - sigmoid((zipf - 5.5) / 1.5)     # 语料客观分布（wordfreq）
- family_q = nation_band / 10                     # Nation BNC/COCA 词族档位
- cefr_q   = lookup → {A1:0.05, A2:0.20, B1:0.40, B2:0.60, C1:0.80, C2:0.95}
- if cefr 已知: Q = 0.5·cefr_q + 0.3·family_q + 0.2·zipf_q
- else:         Q = 0.6·family_q + 0.4·zipf_q

用户映射（考试/自述 → U 分位）：
- U = clamp((vocab - 1500) / 8500, 0.10, 0.95)    # 自述词汇量桥梁
- 已知考试（雅思/托福/考研等）→ CEFR → 词汇量 → U（level_matrix 配置）

普适性：任意词都有分位（zipf 保底）；考试体系可扩展（数据驱动配置）。
"""

from __future__ import annotations

import json
import math
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ═══════════════════════════════════════════════════════════
# CEFR 等级 → 分位（教学真值锚点）
# ═══════════════════════════════════════════════════════════
CEFR_QUANTILES = {
    "A1": 0.05, "A2": 0.20, "B1": 0.40,
    "B2": 0.60, "C1": 0.80, "C2": 0.95,
}

# 混合权重（教学侧权重高——锚定习得顺序）
DEFAULT_WEIGHTS = {
    "cefr": 0.5, "family": 0.3, "zipf": 0.2,   # CEFR 已知时
    "family_no_cefr": 0.6, "zipf_no_cefr": 0.4,  # CEFR 未知时
}

# Nation 词族数据目录（10000-headwords 10 档——注意序数词后缀不统一：1st/2nd/3rd/4th...）
_DATA_DIR = Path(__file__).resolve().parent / "data"
_NATION_FILE_NAMES = [
    "headwords 1st 1000.txt",
    "headwords 2nd 1000.txt",
    "headwords 3rd 1000.txt",
] + [f"headwords {n}th 1000.txt" for n in range(4, 11)]


# ═══════════════════════════════════════════════════════════
# 词族档位（Nation BNC/COCA 10000 词族——第 1 档最常用）
# ═══════════════════════════════════════════════════════════
@lru_cache(maxsize=1)
def _load_family_map() -> Dict[str, int]:
    """加载 Nation 词族表 → {headword_lower: band(1-10)}。

    注意：第 10 档含重音词（latin-1 编码），其余 UTF-8——逐文件探测编码。
    """
    fam: Dict[str, int] = {}
    for band in range(1, 11):
        p = _DATA_DIR / _NATION_FILE_NAMES[band - 1]
        if not p.exists():
            continue
        try:
            raw = p.read_bytes()
            try:
                text = raw.decode("utf-8")
            except Exception:
                text = raw.decode("latin-1")
            for line in text.splitlines():
                w = line.strip().lower()
                if w:
                    fam[w] = band
        except Exception:
            continue
    return fam


def family_band(word: str) -> Optional[int]:
    """词在 Nation 词族表中的档位（1-10）；不在 → None。"""
    fam = _load_family_map()
    if not fam:
        return None
    w = word.strip().lower()
    if w in fam:
        return fam[w]
    # 词族头词通常是原形——尝试去屈折后缀
    for suf in ("s", "es", "ed", "ing", "er", "est"):
        if len(w) > len(suf) + 2 and w.endswith(suf) and w[:-len(suf)] in fam:
            return fam[w[:-len(suf)]]
    return None


def family_to_quantile(band: Optional[int]) -> Optional[float]:
    """词族档位 → 分位（band 1 → 0.10 最易；band 10 → 0.95 最难）。"""
    if band is None:
        return None
    return min(0.95, 0.05 + (band - 1) * 0.10)


# ═══════════════════════════════════════════════════════════
# zipf → 分位（语料客观分布——wordfreq）
# ═══════════════════════════════════════════════════════════
def zipf_to_quantile(zipf: float) -> float:
    """zipf → 难度分位（越高越常见 → Q 越低）。

    公式（Oracle 验证）：Q = 1 - sigmoid((zipf - 5.5) / 1.5)
    zipf=5.5 中点 → Q≈0.5；zipf=7.7（the）→ Q≈0.08；zipf=3.4 → Q≈0.82。

    §3.116 P7 ⭐ zipf=0 表示"无词频数据"（词典外词）而非"极稀有"——
    返回中性 0.5（避免 OCR 噪声词被误判为最高难度）。
    """
    if zipf is None or zipf <= 0:
        return 0.5
    return 1.0 - 1.0 / (1.0 + math.exp(-(zipf - 5.5) / 1.5))


def _get_zipf(word: str) -> Optional[float]:
    """wordfreq zipf 值（不可用返回 None）。"""
    try:
        from wordfreq import zipf_frequency
        return zipf_frequency(word, "en")
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
# CEFR → 分位
# ═══════════════════════════════════════════════════════════
def cefr_to_quantile(cefr: str) -> Optional[float]:
    """CEFR 等级 → 分位（未知等级返回 None）。"""
    c = (cefr or "").strip().upper()
    return CEFR_QUANTILES.get(c)


# ═══════════════════════════════════════════════════════════
# 混合分位计算（核心）
# ═══════════════════════════════════════════════════════════
def compute_q(word: str, cefr_hint: Optional[str] = None,
              with_meta: bool = False) -> Any:
    """计算词的统一难度分位 Q（0-1，越高越难）。

    Args:
        word: 词（lemma 形）。
        cefr_hint: 已知 CEFR 等级（来自词表/LLM），None 则自动推断。
        with_meta: True 返回 (q, meta_dict) 供调试/渲染。

    Returns:
        q: float 或 (q, meta)。
    """
    w = (word or "").strip().lower()
    meta: Dict[str, Any] = {}

    # 信号 1：zipf
    zipf = _get_zipf(w)
    zipf_q = zipf_to_quantile(zipf) if zipf is not None else 0.5
    meta["zipf"] = zipf
    meta["zipf_q"] = round(zipf_q, 4)

    # 信号 2：Nation 词族档位
    band = family_band(w)
    family_q = family_to_quantile(band)
    meta["family_band"] = band
    meta["family_q"] = round(family_q, 4) if family_q is not None else None

    # 信号 3：CEFR
    cefr = (cefr_hint or "").strip().upper()
    if not cefr:
        # 自动推断（zipf → CEFR 桥接）
        try:
            from .level_matrix import guess_cefr_from_zipf
            if zipf is not None:
                cefr = guess_cefr_from_zipf(zipf)
        except Exception:
            pass
    cefr_q = cefr_to_quantile(cefr)
    meta["cefr"] = cefr or ""
    meta["cefr_q"] = round(cefr_q, 4) if cefr_q is not None else None

    # 组合
    if cefr_q is not None:
        # CEFR 已知：0.5·cefr + 0.3·family + 0.2·zipf
        fq = family_q if family_q is not None else zipf_q
        q = (DEFAULT_WEIGHTS["cefr"] * cefr_q
             + DEFAULT_WEIGHTS["family"] * fq
             + DEFAULT_WEIGHTS["zipf"] * zipf_q)
    elif family_q is not None:
        # CEFR 未知但有词族：0.6·family + 0.4·zipf
        q = (DEFAULT_WEIGHTS["family_no_cefr"] * family_q
             + DEFAULT_WEIGHTS["zipf_no_cefr"] * zipf_q)
    else:
        # 全兜底：纯 zipf
        q = zipf_q

    q = min(0.95, max(0.05, q))
    meta["q"] = round(q, 4)

    if with_meta:
        return q, meta
    return q


# ═══════════════════════════════════════════════════════════
# 用户水平 → U 分位（考试/自述映射）
# ═══════════════════════════════════════════════════════════
def user_level_to_u(vocab_size: float = 0, exam: str = "",
                    score: float = 0, preset: str = "") -> float:
    """用户英语水平 → 统一分位 U（0.10-0.95）。

    优先级：preset > exam+score > vocab_size。
    - preset: 从 level_matrix user_presets 查（数据驱动）
    - exam+score: 查考试体系 → CEFR → 词汇量 → U
    - vocab_size: 自述词汇量 → U = clamp((V-1500)/8500, 0.10, 0.95)
    """
    # 1. preset（数据驱动配置）
    if preset:
        try:
            from .level_matrix import resolve_preset
            p = resolve_preset(preset)
            if p.get("exam"):
                exam, score = p["exam"], float(p.get("score") or 0)
        except Exception:
            pass

    # 2. exam + score → 学习语义 CEFR（已掌握上限）→ 词族分位 U
    if exam:
        try:
            cefr = select_learn_cefr(exam, score)
            if cefr in CEFR_NATION_QUANTILE:
                return CEFR_NATION_QUANTILE[cefr]
            vocab = cefr_to_vocab_size(cefr)
            if vocab:
                return _vocab_to_u(vocab)
        except Exception:
            pass

    # 3. 自述词汇量
    if vocab_size > 0:
        return _vocab_to_u(vocab_size)

    return 0.60  # 默认 B2（安全中性）


# CEFR → 词汇量（业界共识桥梁——Cambridge/ETS）
CEFR_VOCAB_SIZE = {
    "A1": 800, "A2": 1800, "B1": 3500, "B2": 5500, "C1": 6500, "C2": 10000,
}

# CEFR → Nation 词族分位（词汇量 / 10000 词族——雅思 7.5 掌握 6500 族 → 0.65）
# P7 ⭐ 校准：U 基于词族分位（与 compute_q 的 family_q 对齐），
# 而非 zipf 线性映射——雅思 7.5 → U≈0.65 产出 ~2200 词（钟形罩实测 0.826 稍高，
# 因文学书稀有词多；0.65 为通用保守值）
CEFR_NATION_QUANTILE = {
    "A1": 0.10, "A2": 0.25, "B1": 0.40, "B2": 0.55, "C1": 0.70, "C2": 0.85,
}

# 考试 → 学习语义 CEFR 上限（用户已掌握的水平——学习"之上"的词汇）
# 官方映射 7.5→C2 是"能力描述"；学习语义取"已掌握上限"= 官方映射降一档：
# 雅思 7.5 已掌握 C1 → 需学 C1 以上（C1+C2）的词
EXAM_LEARN_CEFR = {
    "ielts": {5.5: "B1", 6.0: "B1", 6.5: "B2", 7.0: "B2", 7.5: "C1", 8.0: "C1", 8.5: "C2", 9.0: "C2"},
    "toefl": {60: "B1", 80: "B2", 90: "B2", 100: "C1", 110: "C1", 120: "C2"},
    "cet4": {425: "B1", 550: "B1", 600: "B2"},
    "cet6": {425: "B1", 520: "B2", 600: "C1"},
    "kaoyan": {40: "B1", 55: "B2", 70: "B2", 85: "C1"},
    "tem4": {60: "B2", 80: "C1"},
    "tem8": {60: "C1", 80: "C2"},
    "gaokao": {90: "A2", 120: "B1", 135: "B2"},
}


def select_learn_cefr(exam: str, score: float) -> str:
    """考试分数 → 学习语义 CEFR 上限（用户已掌握水平）。"""
    table = EXAM_LEARN_CEFR.get(exam, {})
    if not table:
        return "C2"
    best = "A1"
    for s in sorted(table.keys()):
        if s <= score:
            best = table[s]
    return best


def cefr_to_vocab_size(cefr: str) -> Optional[float]:
    """CEFR → 词汇量（近似桥梁）。"""
    return CEFR_VOCAB_SIZE.get((cefr or "").strip().upper())


def _vocab_to_u(vocab: float) -> float:
    """词汇量 → U：U = clamp((V-1500)/8500, 0.10, 0.95)。"""
    u = (vocab - 1500) / 8500
    return min(0.95, max(0.10, u))


# ═══════════════════════════════════════════════════════════
# 分档（内部 18 档 / 展示 9 档）
# ═══════════════════════════════════════════════════════════
def quantile_to_tier(q: float, n_tiers: int = 9) -> int:
    """分位 → 档位（9 档：每 0.10；18 档：每 0.05）。"""
    q = min(0.95, max(0.05, q))
    step = 1.0 / n_tiers
    tier = int(math.ceil(q / step))
    return min(n_tiers, max(1, tier))


def tier_color(q: float) -> str:
    """分位 → 颜色（Hue 220 蓝 → 0 红，9 档等距）。"""
    tier = quantile_to_tier(q, 9)
    hue = 220 - (tier - 1) * (220 / 9)
    return f"hsl({hue:.0f}, 65%, 45%)"
