# -*- coding: utf-8 -*-
"""paeg_vocabulary.pipeline.clean_dedup — 阶段2：清洗去重（§3.116 ⭐）。

清洗（OCR 5 层）→ 分词 → 词元化（lemma）→ 去重。
产出：clean_corpus（TokenSpan 列表）。
"""

from __future__ import annotations

import re
from typing import List

from ..core.context import TokenSpan, VocabularyContext
from ..cleaners.ocr_repair import OCRRepairPipeline

# 英文分词（简单 tokenize；有 spaCy 时用 spaCy）
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*|[ÄÖÜäöüß][a-zäöüß]*")


def _simple_tokenize(text: str, lang: str = "en") -> List[str]:
    """基础分词（英文/德文等拉丁字母语言）。"""
    return _WORD_RE.findall(text)


def _lemmatize_spacy(tokens: List[str], lang: str = "en") -> List[str]:
    """用 spaCy 词元化（可用时）。"""
    try:
        import spacy
        lang_map = {"en": "en_core_web_sm", "de": "de_core_news_sm",
                    "fr": "fr_core_news_sm", "es": "es_core_news_sm"}
        model = lang_map.get(lang, "en_core_web_sm")
        try:
            nlp = spacy.load(model)
        except Exception:
            return tokens
        doc = nlp(" ".join(tokens))
        return [t.lemma_.lower() for t in doc]
    except Exception:
        return [t.lower() for t in tokens]


def _lemmatize_with_pos(tokens: List[str], lang: str = "en") -> List[dict]:
    """spaCy 词元化 + 词性（§3.116 词形归一化需要 POS 判断）。"""
    try:
        import spacy
        lang_map = {"en": "en_core_web_sm", "de": "de_core_news_sm",
                    "fr": "fr_core_news_sm", "es": "es_core_news_sm"}
        model = lang_map.get(lang, "en_core_web_sm")
        nlp = spacy.load(model)
        doc = nlp(" ".join(tokens))
        return [{"lemma": t.lemma_.lower(), "pos": t.pos_,
                 "lemma_pos": _pos_to_map(t.tag_)} for t in doc]
    except Exception:
        # §3.116 ⭐ V-R8：spaCy 缺失降级——规则级词形还原（不再 lemma=表面形）
        return [{"lemma": _rule_lemmatize(t), "pos": "NOUN", "lemma_pos": "NOUN"}
                for t in tokens]


def _pos_to_map(tag: str) -> str:
    """spaCy tag → 简化 POS（NOUN/VERB/ADJ/ADV）。"""
    if tag.startswith("NN"):
        return "NOUN"
    if tag.startswith("VB"):
        return "VERB"
    if tag.startswith("JJ"):
        return "ADJ"
    if tag.startswith("RB"):
        return "ADV"
    return "X"


# §3.116 ⭐ V-R8 范本超越：规则级英文词形还原（spaCy 缺失时的兜底）
# 范本核心方法论"词形还原聚合"（-s/-ed/-ing/-es 归并到词元）——spaCy 未安装时
# 降级路径 lemma=表面形导致 housewife/housewives 都成独立词条，本表兜底还原。
_IRREGULAR_LEMMAS = {
    # 不规则复数（-f/-fe → -ves）
    "housewives": "housewife", "wives": "wife", "lives": "life",
    "knives": "knife", "leaves": "leaf", "thieves": "thief",
    "selves": "self", "halves": "half", "shelves": "shelf",
    # 不规则复数（-y → -ies / 其他）
    "studies": "study", "bodies": "body", "parties": "party",
    "men": "man", "women": "woman", "children": "child",
    "feet": "foot", "teeth": "tooth", "mice": "mouse",
    # 不规则过去式
    "went": "go", "meant": "mean", "said": "say", "made": "make",
    "took": "take", "came": "come", "became": "become", "gave": "give",
    "found": "find", "thought": "think", "brought": "bring",
}

# §3.116 ⭐ -s 结尾但非复数的词（不可数/单复同形）——不还原，防 news→new 误伤
_S_SUFFIX_SAFE = {
    "news", "maths", "means", "series", "species", "politics",
    "physics", "economics", "ethics", "logistics", "aesthetics",
    "scissors", "trousers", "glasses", "headquarters",
}


def _rule_lemmatize(word: str) -> str:
    """规则级英文词形还原（无 spaCy 时兜底）：不规则表 + 安全规则还原。"""
    low = word.strip().lower()
    if not low:
        return low
    if low in _IRREGULAR_LEMMAS:
        return _IRREGULAR_LEMMAS[low]
    if low in _S_SUFFIX_SAFE:
        return low  # -s 结尾但非复数，不还原
    # 规则屈折：-ies→-y / -es / -ed / -ing / -s（还原后长度 ≥3，避免误伤）
    for suf, strip in (("ies", "y"), ("es", ""), ("ed", ""), ("ing", ""), ("s", "")):
        if low.endswith(suf) and len(low) > len(suf) + 2:
            base = low[:-len(suf)] + strip
            if base != low and len(base) >= 3:
                return base
    return low


# 英文停用词（基础集；spaCy 可用时用 spaCy）
_EN_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "for",
    "of", "in", "on", "at", "to", "from", "by", "with", "without",
    "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "can", "could",
    "should", "may", "might", "must", "this", "that", "these", "those",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "us", "them", "my", "your", "his", "its", "our", "their",
    "not", "no", "yes", "so", "very", "just", "about", "as", "into",
}


def clean_corpus(ctx: VocabularyContext, repair: bool = True) -> VocabularyContext:
    """阶段 2：raw_corpus → clean_corpus（清洗 + 分词 + 词元 + 去停用词）。

    §3.116 ⭐ 词形归一化策略：用 should_preserve_form 判断——
    - 屈折变化（POS 不变）→ 归一化 lemma
    - 派生变化（POS 改变/后缀）→ 保留原形为独立词条（abandonment ≠ abandon）
    - 学术术语 → 标记 is_book_term
    """
    if not ctx.raw_corpus:
        ctx.errors.append("无原文（阶段1未执行）")
        return ctx

    text = ctx.raw_corpus
    # 1. OCR 修复
    if repair:
        text = OCRRepairPipeline(ctx.target_lang).repair(text)

    # 2. 分词
    tokens = _simple_tokenize(text, ctx.target_lang)

    # 3. 词元化 + 词性（§3.116 需 POS 判断派生）
    if ctx.target_lang == "en":
        lemmas_info = _lemmatize_with_pos(tokens, "en")
    else:
        lemmas = _lemmatize_spacy(tokens, ctx.target_lang)
        lemmas_info = [{"lemma": l, "pos": "NOUN", "lemma_pos": "NOUN"}
                       for l in lemmas]

    # 4. 去停用词 + 词形归一化决策
    clean = []
    preserved_surfaces = set()  # 已保留的独立派生词条
    # §3.116 P7 ⭐ 专名统计：{lemma_lower: {"upper": n, "total": n}}
    # 非句首大写比例高 → 专名（人名/地名——不构成学习词条）
    cap_stats: dict = {}
    prev_tok = ""  # 判断句首（前一 token 以句末标点结尾）
    for tok, info in zip(tokens, lemmas_info):
        low = info["lemma"].lower()
        if low in _EN_STOPWORDS or len(low) < 2:
            prev_tok = tok
            continue
        # 大写统计：非句首位置的大写（句子开头大写不算专名信号）
        is_sentence_start = (not prev_tok or prev_tok.endswith((".", "!", "?", "…")))
        if not is_sentence_start and tok[:1].isupper():
            s = cap_stats.setdefault(low, {"upper": 0, "total": 0})
            s["upper"] += 1
            s["total"] += 1
        elif tok[:1].islower():
            s = cap_stats.setdefault(low, {"upper": 0, "total": 0})
            s["total"] += 1
        # §3.116 ⭐ 词形归一化决策
        try:
            from ..normalization import should_preserve_form
            decision = should_preserve_form(
                surface=tok, lemma=info["lemma"], pos=info["pos"],
                lemma_pos=info["lemma_pos"],
                ctx={"freq": 1})  # 频率在 filter 阶段统计
            if decision.is_lexically_independent:
                # 保留表面形为独立词条（派生/术语）
                key = tok.lower()
                if key not in preserved_surfaces:
                    preserved_surfaces.add(key)
                    clean.append(TokenSpan(
                        token=tok, lemma=tok.lower(), pos=info["pos"],
                        page_no=(len(clean) // 500) + 1,
                        context=decision.reason,
                    ))
                prev_tok = tok
                continue
            low = decision.lemma
        except Exception:
            pass
        if low in _EN_STOPWORDS or len(low) < 2:
            prev_tok = tok
            continue
        clean.append(TokenSpan(
            token=tok, lemma=low,
            page_no=(len(clean) // 500) + 1,
            context="",
        ))
        prev_tok = tok
    ctx.clean_corpus = clean
    # P7 ⭐ 专名统计存入 ctx（filter 阶段用大写比例过滤专名）
    ctx.capitalized_stats = {k: v for k, v in cap_stats.items()
                             if v["total"] >= 2}
    ctx.mark_completed("clean_dedup")
    return ctx
