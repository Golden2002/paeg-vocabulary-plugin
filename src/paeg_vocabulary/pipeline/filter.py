# -*- coding: utf-8 -*-
"""paeg_vocabulary.pipeline.filter — 阶段3：单词筛选（§3.116 ⭐）。

支持用户自定义筛选维度：词频范围 / 难度等级 / 自定义条件。
产出：candidates（CandidateWord 列表）。

筛选策略（FilterStrategy 接口——可扩展）：
- frequency: 词频范围（书中出现次数）
- difficulty: 难度等级（CEFR 猜测）
- custom: 用户自定义
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Dict, List, Optional

from ..core.context import VocabularyContext
from ..core.entry import CandidateWord


class FilterStrategy:
    """筛选策略基类（可扩展 ⭐）。"""

    def should_keep(self, candidate: CandidateWord) -> bool:
        return True


class FrequencyFilter(FilterStrategy):
    """词频范围筛选。"""

    def __init__(self, min_count: int = 1, max_count: int = 10 ** 9):
        self.min_count = min_count
        self.max_count = max_count

    def should_keep(self, c: CandidateWord) -> bool:
        return self.min_count <= c.freq_count <= self.max_count


class CEFRFilter(FilterStrategy):
    """难度等级筛选（A1-C2；B2 以下 = 基础，C1+ = 高级）。"""

    _LEVELS = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}

    def __init__(self, min_level: str = "A1", max_level: str = "C2"):
        self.min = self._LEVELS.get(min_level.upper(), 1)
        self.max = self._LEVELS.get(max_level.upper(), 6)

    def should_keep(self, c: CandidateWord) -> bool:
        lv = self._LEVELS.get(c.cefr_guess.upper(), 0)
        if lv == 0:
            return True  # 未知难度默认保留
        return self.min <= lv <= self.max


class WordFreqFilter(FilterStrategy):
    """通用词频验证（wordfreq Zipf——剔除生造词/OCR 噪声）。"""

    def __init__(self, min_zipf: float = 0.0):
        self.min_zipf = min_zipf

    def should_keep(self, c: CandidateWord) -> bool:
        # zipf 过低 = 生造词/OCR 噪声
        return c.global_zipf >= self.min_zipf


class FunctionWordFilter(FilterStrategy):
    """§3.116 ⭐ 虚词过滤（冠词/介词/连词/代词/助动词——保留实词）。

    用户要求：词频统计去虚词保留实词（accessory 同样适用主筛选）。
    """

    _FUNC_WORDS = {
        "the", "a", "an", "of", "in", "on", "at", "to", "for", "with",
        "by", "from", "as", "and", "or", "but", "if", "then", "else",
        "is", "are", "was", "were", "be", "been", "being", "have", "has",
        "had", "do", "does", "did", "will", "would", "can", "could",
        "should", "may", "might", "must", "this", "that", "these",
        "those", "it", "its", "he", "she", "they", "we", "you", "i",
        "me", "him", "her", "them", "us", "my", "your", "his", "our",
        "their", "not", "no", "yes", "so", "very", "just", "about",
        "into", "which", "what", "who", "whom", "whose", "when", "where",
        "why", "how", "there", "here", "all", "only", "such", "more",
        "most", "much", "many", "some", "any", "each", "every", "own",
        "one", "two", "upon", "within", "without", "through", "between",
        "among", "itself", "himself", "herself", "themselves", "myself",
        "ourselves", "thus", "hence", "therefore", "however", "though",
        "although", "since", "while", "until", "before", "after", "man",
    }

    def should_keep(self, c: CandidateWord) -> bool:
        return c.headword.lower() not in self._FUNC_WORDS


def guess_cefr(word: str) -> str:
    """CEFR 难度猜测（基于 wordfreq zipf——高频=低难度）。
    §3.116 ⭐ 统一用 level_matrix 的 zipf_bridge。"""
    try:
        from wordfreq import zipf_frequency
        z = zipf_frequency(word, "en")
        from ..level_matrix import guess_cefr_from_zipf
        return guess_cefr_from_zipf(z)
    except Exception:
        return "B1"  # 未知默认


def _get_zipf(word: str) -> float:
    try:
        from wordfreq import zipf_frequency
        return zipf_frequency(word, "en")
    except Exception:
        return 0.0


def _build_candidates(ctx: VocabularyContext) -> List[CandidateWord]:
    """从 clean_corpus 构建候选词（词频统计 + 通用词频 + CEFR 猜测）。"""
    counts = Counter(t.lemma for t in ctx.clean_corpus)
    cands = []
    # 短词（≤3 字符）词典校验：无音标且无释义 → 断词残片/噪声，过滤
    _wb = None
    for lemma, count in counts.items():
        if len(lemma) <= 3:
            if _wb is None:
                try:
                    from ..wordbank import WordBank
                    _wb = WordBank()
                except Exception:
                    _wb = False
            if _wb:
                r = _wb.lookup(lemma)
                if not r.get("ipa") and not r.get("gloss_zh") and not r.get("gloss_en"):
                    continue  # 词典无此词 → 残片
        c = CandidateWord(
            headword=lemma,
            lemma=lemma,
            freq_count=count,
            global_zipf=_get_zipf(lemma),
            cefr_guess=guess_cefr(lemma),
        )
        cands.append(c)
    return cands


class LevelFilter(FilterStrategy):
    """§3.116 ⭐ 用户水平档位筛选（词汇对应表）。

    双模式：
    - mode="learn"（默认）：筛选**需学习的生词**（难度 ≥ 用户水平对应阈值——
      雅思 7.5 用户需学习约 2200 个生词）
    - mode="master"：筛选**能掌握的词**（CEFR ≤ 用户水平）
    """

    def __init__(self, cefr_max: str = "C1", mode: str = "learn"):
        self.cefr_max = cefr_max.upper()
        self.mode = mode
        from ..level_matrix import cefr_order
        self._order = cefr_order()
        self._level_idx = self._order.index(self.cefr_max) if self.cefr_max in self._order else 4

    def should_keep(self, c: CandidateWord) -> bool:
        lv = c.cefr_guess.upper()
        if lv not in self._order:
            return False  # 未知难度不保留（learn 模式）
        idx = self._order.index(lv)
        if self.mode == "learn":
            # 需学习的生词：难度 ≥ 用户水平（对 C1 用户，C1/C2 是生词）
            return idx >= self._level_idx
        # master：能掌握的词：难度 ≤ 用户水平
        return idx <= self._level_idx


class ZipfLearnFilter(FilterStrategy):
    """§3.116 ⭐ Zipf 阈值筛选需学习生词（量化标准校准）。

    雅思 7.5 用户需学习约 2200 个生词 → 对应 zipf ≥ 4.23
    （《生命现象》实测：第 2200 词的 zipf = 4.23）。
    比 CEFR 桥接更精确——直接按词频稀有度筛选生词。
    """

    def __init__(self, min_zipf: float = 4.23):
        self.min_zipf = min_zipf

    def should_keep(self, c: CandidateWord) -> bool:
        # 需学习的生词 = 稀有词（zipf 低于用户词汇量水平）
        return c.global_zipf >= self.min_zipf


# 各考试体系 → zipf 阈值（§3.116 ⭐ 修正：水平低 → 阈值低 → 更多生词）
# 含义：zipf ≥ 阈值的词视为"生词"（需学习）。
# 雅思 6.5（低水平）→ 阈值低（如 3.8）→ 含更多低频生词
# 雅思 8.0（高水平）→ 阈值高（如 4.5）→ 只含极高难度生词
EXAM_ZIPF_THRESHOLDS = {
    "ielts": {6.5: 3.8, 7.0: 4.0, 7.5: 4.23, 8.0: 4.5},
    "toefl": {80: 3.9, 100: 4.2, 110: 4.5},
    "cet4": {425: 3.6, 550: 3.9},
    "cet6": {425: 3.8, 520: 4.1, 600: 4.4},
    "kaoyan": {40: 3.7, 55: 4.0, 70: 4.23, 85: 4.5},
    "tem4": {60: 3.8},
    "tem8": {60: 4.2},
    "gaokao": {90: 3.5, 120: 3.8, 135: 4.1},
}


def zipf_threshold_for(exam: str, score: float) -> float:
    """查考试分数 → zipf 阈值（需学习的生词=zipf≥阈值）。

    修正（§3.116）：水平低 → 阈值低 → 更多生词；水平高 → 阈值高 → 更少生词。
    未精确匹配 → 取最近的档位。
    """
    table = EXAM_ZIPF_THRESHOLDS.get(exam, {})
    if not table:
        return 4.0  # 默认
    scores = sorted(table.keys())
    # 找到 ≤ score 的最大档位
    best = scores[0]
    for s in scores:
        if s <= score:
            best = s
    return table[best]


def filter_candidates(ctx: VocabularyContext,
                      strategies: Optional[List[FilterStrategy]] = None,
                      cefr_max: Optional[str] = None,
                      zipf_threshold: Optional[float] = None,
                      filter_mode: str = "learn") -> VocabularyContext:
    """阶段 3：clean_corpus → candidates（应用筛选策略）。

    §3.116 ⭐ cefr_max: 用户水平档位 CEFR 上限（如 "C1"——雅思 7.5）。
    zipf_threshold: zipf 阈值（量化标准——雅思 7.5 ≈ zipf 4.23，筛出约 2200 生词）。
    filter_mode: "learn"（需学习的生词——难度≥阈值）/ "master"（能掌握的词）。
    §3.116 ⭐ 语言现象豁免：熟词生义/固定搭配/俚语 = 学习价值信号，
    即使 zipf 不达标也保留（phenomenon_keep 集合）。
    """
    if not ctx.clean_corpus:
        ctx.errors.append("无清洗词流（阶段2未执行）")
        return ctx

    all_cands = _build_candidates(ctx)

    # 默认策略：虚词过滤 + 频率 ≥ 2 + 用户水平档位（若指定）
    if strategies is None:
        strategies = [
            FunctionWordFilter(),
            FrequencyFilter(min_count=2),
            WordFreqFilter(min_zipf=0.0),
        ]
    if zipf_threshold is not None:
        strategies.append(ZipfLearnFilter(zipf_threshold))
    elif cefr_max:
        strategies.append(LevelFilter(cefr_max, mode=filter_mode))

    # §3.116 ⭐ 语言现象豁免：先识别语境信号（熟词生义/俚语/固定搭配）
    _phenomenon_keep = set()
    try:
        from ..enrichers.idiom_enricher import is_important_phenomenon
        for _c in all_cands:
            _ctx_txt = " ".join(_c.contexts[:3])
            if is_important_phenomenon(_c.headword, _ctx_txt):
                _phenomenon_keep.add(_c.lemma.lower())
    except Exception:
        pass

    kept = []
    for c in all_cands:
        if all(s.should_keep(c) for s in strategies):
            kept.append(c)
        elif c.lemma.lower() in _phenomenon_keep:
            # 语言现象豁免（zipf 不达标但熟词生义/俚语 → 保留）
            kept.append(c)
    # 按频率降序
    kept.sort(key=lambda c: -c.freq_count)
    ctx.candidates = kept
    ctx.mark_completed("filter")
    return ctx
