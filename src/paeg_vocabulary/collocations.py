# -*- coding: utf-8 -*-
"""paeg_vocabulary.collocations — P5 ⭐ 原著固定搭配提取（N-gram 显著性）。

需求（§3.116 模块2 第5条）："短语/固定搭配：提取该词在原著中的固定搭配、常用短语"

算法：
1. 从原著语料生成 N-gram（2/3 元）
2. PMI（点互信息）显著性打分——过滤"of the"类无信息组合
3. 虚词过滤（FunctionWordFilter 复用）
4. 频率下限（min_count）防噪声

与词汇表联动：按词检索搭配（entry.collocations）。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

# 虚词集合（搭配必须含至少一个实词）
_FUNCTION_WORDS = {
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
    "although", "since", "while", "until", "before", "after",
}

# 已过滤的纯虚词搭配（防止 of the / in the 类返回）
COLLOCATION_FILTER = {
    "of the", "in the", "on the", "to the", "for the", "with the",
    "by the", "from the", "at the", "and the", "is the", "was the",
    "are the", "were the", "be the", "has the", "have the", "it is",
    "this is", "that is", "there is", "there are", "in a", "of a",
}

_TOKEN_RE = re.compile(r"[A-Za-z']+")


def _tokenize(text: str) -> List[str]:
    """文本 → 小写 token 列表。"""
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _ngrams(tokens: List[str], n: int) -> List[Tuple[str, ...]]:
    """生成 n-gram。"""
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def score_bigram(freq_ab: int, freq_a: int, freq_b: int,
                 total: int = 100000) -> Optional[float]:
    """二元搭配 PMI 打分（对数点互信息）。

    PMI = log2(P(ab) / (P(a)·P(b)))
    高频无信息组合（of the）PMI 低；罕见共现 PMI 高。
    Returns: PMI 或 None（无效）。
    """
    if freq_ab <= 0 or freq_a <= 0 or freq_b <= 0 or total <= 0:
        return None
    p_ab = freq_ab / total
    p_a = freq_a / total
    p_b = freq_b / total
    if p_a * p_b <= 0:
        return None
    return math.log2(p_ab / (p_a * p_b))


def score_trigram(freq_abc: int, freq_ab: int, freq_bc: int,
                  total: int = 100000) -> Optional[float]:
    """三元搭配 PMI。"""
    if freq_abc <= 0 or freq_ab <= 0 or freq_bc <= 0:
        return None
    # 简化为组合概率
    return math.log2(max(1.0, freq_abc) / max(1.0, freq_ab) * 2)


def _is_meaningful(phrase: str) -> bool:
    """搭配是否有意义（含至少一个实词 + 非纯虚词组合）。"""
    words = phrase.split()
    if len(words) < 2:
        return False
    if phrase in COLLOCATION_FILTER:
        return False
    # 至少一个实词
    has_content = any(w not in _FUNCTION_WORDS for w in words)
    return has_content


def extract_collocations(corpus: List[str], n: int = 2,
                         min_count: int = 2, top_n: int = 30) -> List[Dict]:
    """从语料提取固定搭配（N-gram + PMI + 频率 + 实词过滤）。

    Args:
        corpus: 原著句子/段落列表。
        n: n-gram 阶（2=二元，3=三元）。
        min_count: 最低出现次数（防噪声）。
        top_n: 返回数量（按 PMI 降序）。

    Returns:
        [{"phrase": "cell membrane", "count": 5, "pmi": 3.2, "words": [...]}]
    """
    if not corpus:
        return []

    # 1. 全部 token + n-gram 计数
    all_tokens: List[str] = []
    ngram_counts: Counter = Counter()
    bigram_counts: Counter = Counter()   # 三元 PMI 需要二元支撑
    token_counts: Counter = Counter()
    for text in corpus:
        tokens = _tokenize(text)
        if len(tokens) < n:
            continue
        all_tokens.extend(tokens)
        for ng in _ngrams(tokens, n):
            ngram_counts[ng] += 1
        if n == 3:
            for bg in _ngrams(tokens, 2):
                bigram_counts[bg] += 1
    for t in all_tokens:
        token_counts[t] += 1
    total_tokens = len(all_tokens)

    # 2. 频率过滤 + PMI 打分
    results = []
    for ng, count in ngram_counts.items():
        if count < min_count:
            continue
        phrase = " ".join(ng)
        if not _is_meaningful(phrase):
            continue
        if n == 2:
            pmi = score_bigram(count, token_counts.get(ng[0], 0),
                               token_counts.get(ng[1], 0), total_tokens)
        else:
            # 三元：用前后二元近似（需 bigram_counts 支撑）
            pmi = score_trigram(count, bigram_counts.get(tuple(ng[:2]), 0),
                                bigram_counts.get(tuple(ng[1:]), 0), total_tokens)
        if pmi is None or pmi <= 0:
            continue
        results.append({
            "phrase": phrase, "count": count, "pmi": round(pmi, 2),
            "words": list(ng),
        })

    # 3. PMI 降序 + top_n
    results.sort(key=lambda x: (-x["pmi"], -x["count"]))
    return results[:top_n]


def collocations_for_word(collocations: List[Dict], word: str) -> List[Dict]:
    """按词检索搭配（词汇表联动——entry.collocations）。"""
    w = word.strip().lower()
    return [c for c in collocations if w in c["words"]]
