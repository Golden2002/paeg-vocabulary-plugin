# -*- coding: utf-8 -*-
"""paeg_vocabulary.quantile_filter — P4 ⭐ 统一分位筛选（Q≥U OR is_important）。

用户设计原则（§3.116 ⭐）：
1. 标准化过滤阈值 0.10-0.95 递进——词分不同层级
2. 双标准互为补充：难度分位 Q + 本书重要性（学术术语等）
3. 考试/自述 → 统一分位 U
4. 与词形归一化联动（独立词条判定后参与筛选）

筛选决策：keep if Q ≥ U OR is_important（第二标准互补）。
防失控三道闸（Oracle）：频率地板（频次≥2）/ 难度地板（family_q≥0.15）/
占比上限（important 救回 ≤25%）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .core.context import VocabularyContext
from .core.entry import CandidateWord


@dataclass
class AntiRunawayConfig:
    """防失控三道闸配置（可按书目类型调节）。"""
    min_freq: int = 2                 # 频率地板：is_important 豁免要求全书频次 ≥2
    exclude_function_words: bool = True  # 难度地板：纯虚词（the/of）不可被豁免
    max_important_ratio: float = 0.25 # 占比上限：important 救回占总保留 ≤25%


@dataclass
class QuantileCandidate:
    """带分位的候选词（筛选中间产物）。"""
    candidate: CandidateWord
    q: float = 0.5                    # 难度分位（0-1，越高越难）
    is_important: bool = False        # 本书重要性（第二标准）
    kept_by: str = "q"                # q / important / both


def _compute_candidate_q(cand: CandidateWord) -> float:
    """候选词难度分位 Q（P1 分位引擎）。"""
    from .quantile_engine import compute_q
    try:
        q = compute_q(cand.headword, cefr_hint=cand.cefr_guess)
        return float(q)
    except Exception:
        return 0.5


def _is_important_word(cand: CandidateWord,
                       important_words: Optional[Set[str]],
                       min_freq: int) -> bool:
    """候选词是否本书重要（第二标准）——频率地板闸。

    important_words: 外部传入的重要词集合（学术术语/熟词生义/俚语等）。
    §3.116 P7 ⭐ 语义显著词（moonlighting 类）自动纳入 important。
    """
    if important_words and cand.headword.lower() in important_words:
        if cand.freq_count >= min_freq:   # 闸 1：频率地板
            return True
    # P7 ⭐ moonlighting 类：语义显著词（隐喻/文化含义）即使高频低难度也保留
    try:
        from .notable_words import is_semantically_notable
        if is_semantically_notable(cand.headword):
            if cand.freq_count >= min_freq:
                return True
    except Exception:
        pass
    return False


def quantile_filter_candidates(ctx: VocabularyContext,
                               u_level: Optional[float] = None,
                               important_words: Optional[Set[str]] = None,
                               config: Optional[AntiRunawayConfig] = None,
                               max_entries: int = 2500,
                               ) -> VocabularyContext:
    """P4 统一分位筛选：keep if Q ≥ U OR is_important。

    Args:
        u_level: 用户水平分位 U（0-1）。None → 默认 0.60。
        important_words: 本书重要词集合（术语/熟词生义——第二标准）。
        config: 防失控三道闸配置。
        max_entries: 硬上限（防爆）。

    Returns:
        更新后的 ctx（candidates 带 q/is_important/kept_by）。
    """
    if not ctx.clean_corpus:
        ctx.errors.append("无清洗词流（阶段2未执行）")
        return ctx

    if u_level is None:
        u_level = 0.60
    cfg = config or AntiRunawayConfig()

    # 1. 构建候选（复用旧 filter 的候选构建 + 虚词过滤 + 专名/粘连过滤）
    from .pipeline.filter import _build_candidates, FunctionWordFilter
    all_cands = _build_candidates(ctx)
    fw = FunctionWordFilter()
    cap_stats = getattr(ctx, "capitalized_stats", None) or {}
    cands = [c for c in all_cands
             if fw.should_keep(c)
             and _is_clean_word(c.headword)
             and not _is_proper_noun(c.headword, cap_stats)]

    # 2. 逐词算分位 + 重要性
    enriched: List[QuantileCandidate] = []
    for c in cands:
        q = _compute_candidate_q(c)
        imp = _is_important_word(c, important_words, cfg.min_freq)
        enriched.append(QuantileCandidate(candidate=c, q=q, is_important=imp))

    # 3. 筛选决策：Q ≥ U OR is_important
    kept: List[QuantileCandidate] = []
    important_saved = 0
    for qc in enriched:
        q_ok = qc.q >= u_level
        imp_ok = qc.is_important and _passes_exclusion_gate(qc.candidate, cfg)
        if q_ok and qc.is_important:
            qc.kept_by = "both"
            kept.append(qc)
        elif q_ok:
            qc.kept_by = "q"
            kept.append(qc)
        elif imp_ok:
            qc.kept_by = "important"
            important_saved += 1
            kept.append(qc)

    # 4. 三道闸——占比上限（important 救回 ≤ max_ratio）
    if kept and important_saved > 0:
        total = len(kept)
        max_saved = max(1, int(total * cfg.max_important_ratio))
        if important_saved > max_saved:
            # 超限：按 Q 降序补刀（优先保留难词）
            kept.sort(key=lambda qc: (-qc.q, qc.kept_by != "q"))
            cut = 0
            result = []
            imp_used = 0
            for qc in kept:
                if qc.kept_by == "important":
                    if imp_used >= max_saved:
                        continue
                    imp_used += 1
                result.append(qc)
            kept = result

    # 5. 硬上限
    kept.sort(key=lambda qc: -qc.candidate.freq_count)
    if len(kept) > max_entries:
        kept = kept[:max_entries]

    # 6. 写回（保留 q/important 元数据）
    for qc in kept:
        qc.candidate.q = qc.q
        qc.candidate.is_important = qc.is_important
        qc.candidate.kept_by = qc.kept_by
    ctx.candidates = [qc.candidate for qc in kept]
    ctx.mark_completed("filter")
    return ctx


def _passes_exclusion_gate(cand: CandidateWord, cfg: AntiRunawayConfig) -> bool:
    """闸 2：难度/虚词地板——纯虚词不可被 is_important 救回。

    语义（Oracle）：熟词生义（spring/life 等实词）应可被救回；
    纯虚词（the/of/which）即使书中高频也不值得作为学习词条。
    """
    if not cfg.exclude_function_words:
        return True
    try:
        from .pipeline.filter import FunctionWordFilter
        fw = FunctionWordFilter()
        return fw.should_keep(cand)   # True=实词（可救回）；False=虚词（不可）
    except Exception:
        return True


def _is_proper_noun(word: str, cap_stats: Dict) -> bool:
    """专名检测：非句首大写比例高 → 人名/地名（非学习词条）。

    cap_stats: {lemma_lower: {"upper": n, "total": n}}——clean_dedup 阶段统计。
    比例 > 60% 且出现 ≥2 次 → 专名。
    """
    w = word.strip().lower()
    s = cap_stats.get(w)
    if not s or s.get("total", 0) < 2:
        return False
    ratio = s.get("upper", 0) / s.get("total", 1)
    return ratio > 0.6


def _is_clean_word(word: str) -> bool:
    """过滤专名/粘连 token/OCR 噪声（P7 ⭐ 提升候选质量）。

    - OCR 断裂（连字符拆分 transla-tion / 常见词拼接 wouldhave）
    - 数字/过短/过长噪声
    - 异常撇号
    - 词典外词（zipf=0 且不在学科辞典/CEFR——OCR 噪声）
    """
    import re
    w = word.strip().lower()
    if not w or len(w) < 3 or len(w) > 30:
        return False
    if re.search(r"\d", w):
        return False
    # 连字符断裂（OCR：transla-tion / re-ceived / up-dike's）
    if "-" in w:
        parts = w.split("-")
        # 合法连字符词（well-known/self-made）罕见于扫描书——除非两侧都是词典完整词
        try:
            from wordfreq import zipf_frequency
            if len(parts) == 2:
                a_ok = zipf_frequency(parts[0], "en") > 2.0
                b_ok = zipf_frequency(parts[1], "en") > 2.0
                if not (a_ok and b_ok):
                    return False  # 一侧不完整 → OCR 断裂
            else:
                return False  # 多连字符 → 噪声
        except Exception:
            return False
    # 撇号所有格（esther's/plath's——残余）
    if "'" in w and not w.endswith("'s"):
        return False
    if w.endswith("'s") and len(w) > 10:
        return False
    # 常见词拼接（wouldhave/theword/sothat/tothis——OCR 去空格噪声）
    if len(w) >= 5:
        from ._noise import is_likely_noise
        if is_likely_noise(w):
            return False
    # 词典外词校验（zipf=0 且不在离线词库 → OCR 噪声）
    try:
        from wordfreq import zipf_frequency
        z = zipf_frequency(w, "en")
        if z <= 0:
            # 查离线词库（CMU/CEFR/Oxford/学科辞典）——合法词放行
            try:
                from .wordbank import WordBank
                wb = WordBank()
                r = wb.lookup(w)
                if r.get("ipa") or r.get("gloss_en") or r.get("domain_term"):
                    return True  # 词典词
            except Exception:
                pass
            return False  # 词典外 → OCR 噪声
    except Exception:
        pass
    return True


# 便捷别名（registry 兼容）
filter_candidates_quantile = quantile_filter_candidates
