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


def _recover_truncated(word: str) -> str:
    """词尾丢失恢复：scienc→science / includ→include / decad→decade / voic→voice。

    根因：PDF 提取/OCR 时词尾字母（尤其 e）丢失。用 ecdict 词典校验——
    词本身不在词典，但加尾字母（e/es/ed/d）后在词典 → 恢复为完整词。
    词本身在词典时直接返回（不误伤 use→used 等合法词）。
    """
    low = word.strip().lower()
    if not low or len(low) < 4:
        return low
    try:
        from ..wordbank import EcdictSource
        ec = EcdictSource()
        if ec.lookup(low) is not None:
            return low  # 词本身合法，不恢复
        for suffix in ("e", "es", "ed", "d"):
            cand = low + suffix
            if ec.lookup(cand) is not None:
                return cand
    except Exception:
        pass
    return low


def _ecdict_freq(word: str) -> int:
    """ecdict 词频 rank：-1=词典外；0=在词典但无 frq；正整数=BNC 频次 rank（越小越常见）。

    用于 -ing/-ed 误切防护：spring→spr 这类「去尾后非词典词」的判定信号。
    EcdictSource 用类级 `_CACHE` 懒加载 63MB CSV，首次调用后均命中内存缓存。
    """
    try:
        from ..wordbank import EcdictSource
        r = EcdictSource().lookup(word)
    except Exception:
        return -1
    if r is None:
        return -1
    try:
        return int(str(r.get("frq") or "0") or "0")
    except Exception:
        return 0


def _more_common_word(cand: str, other: str) -> bool:
    """cand 是否比 other 严格更常见（cand 有正 frq 且 other 非正 frq 或 cand rank 更小）。

    用于 -ing/-ed 误切防护：只在该还原比原词更常见时保留还原，否则保持原词——
    spring(901)→spr(0) 这类「去尾后是缩写/生僻词」的场景不会误切。
    """
    cf = _ecdict_freq(cand)
    of = _ecdict_freq(other)
    return cf > 0 and (of <= 0 or cf < of)


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
    # 不规则第三人称单数（-s 规则会误切成 goe/doe，§3.116 Round 6）
    "goes": "go", "does": "do", "has": "have",
}

# §3.116 ⭐ -s 结尾但非复数的词（不可数/单复同形）——不还原，防 news→new 误伤
_S_SUFFIX_SAFE = {
    "news", "maths", "means", "series", "species", "politics",
    "physics", "economics", "ethics", "logistics", "aesthetics",
    "scissors", "trousers", "glasses", "headquarters",
}

# §3.116 ⭐ -ing 实词 stoplist（Round 5）：独立名词/形容词/领域名词，非 base 动词屈折。
# 频率兜底（Round 4）只能挡「去尾后不是词典词」的误切（spring→spr），挡不住
# 「去尾后是更常见词」的语义误切：evening→even、building→build、meaning→mean、
# interesting→interest、surprising→surprise、meeting→meet…。
# spaCy POS 缺失时，本表确定性兜底，保持这些词形为独立词条（不归并到 base 动词）。
_ING_REAL_WORDS = {
    # 时间/抽象名词
    "evening", "morning", "meaning", "beginning", "following",
    # 具体名词
    "building", "wedding", "meeting", "opening", "ceiling", "offspring",
    # 形容词（词干是常见动词但语义已独立）
    "interesting", "surprising", "amazing",
    # 领域/职业名词（简历高频，避免误归并到动词：market/account/consult/engineer）
    "engineering", "marketing", "accounting", "consulting", "training",
}


def _restore_stem(base: str) -> str:
    """还原 -ing/-ed 去尾后的词干（dropped-e 与双写辅音 ⭐）。

    - making→mak→make（去 e 动词：mak+e）
    - charging→charg→charge
    - living→liv→live
    - running→runn→run（双写辅音：runn→run）
    - walking→walk（worke/walke 为 ecdict 古拼写，frq=0，不采用）
    - calling→call（call 本身高频，不误删双写 l）

    用 ecdict 词频 rank（frq，越小越常见）做信号：只在候选词比词干更常见时还原，
    避免被 ecdict 里的古拼写（worke）与缩写（mak/cal）误导。
    """
    if not base or len(base) < 2:
        return base
    try:
        from ..wordbank import EcdictSource
        ec = EcdictSource()
    except Exception:
        return base

    def _freq(w: str) -> int:
        """词频 rank：-1=词典外；0=在词典但无 frq；正整数=BNC 频次 rank（越小越常见）。"""
        try:
            r = ec.lookup(w)
        except Exception:
            return -1
        if r is None:
            return -1
        try:
            return int(str(r.get("frq") or "0") or "0")
        except Exception:
            return 0

    def _more_common(cand: str, other: int) -> bool:
        """候选词 cand 是否比 other 频次更常见（正整数 frq 且 strictly 更靠前）。"""
        cf = _freq(cand)
        if cf < 0:
            return False  # 词典外
        return cf > 0 and (other <= 0 or cf < other)

    base_f = _freq(base)
    # dropped-e：base+e 更常见 → 还原（making→make / charging→charge / living→live）
    if base[-1] not in "aeiouy":
        cand = base + "e"
        if _more_common(cand, base_f):
            return cand
    # 双写辅音：去重后更常见 → 还原（runn→run / stopp→stop）
    if len(base) >= 3 and base[-1] == base[-2] and base[-1] not in "aeiouy":
        single = base[:-1]
        if _more_common(single, base_f):
            return single
    return base


def _rule_lemmatize(word: str) -> str:
    """规则级英文词形还原（无 spaCy 时兜底）：不规则表 + 安全规则还原。

    §3.116 ⭐ 修复：-es 规则只匹配真·es 复数（-ches/-shes/-xes/-zes/-sses），
    否则 sciences→(误切es)→scienc。普通 -s 复数（sciences→science）走 -s 规则。
    §3.116 ⭐ 修复：-ing/-ed 去尾后用 _restore_stem 还原 dropped-e 与双写辅音
    （making→make / charging→charge / running→run），避免 mak/charg 畸形词条。
    """
    low = word.strip().lower()
    if not low:
        return low
    if low in _IRREGULAR_LEMMAS:
        return _IRREGULAR_LEMMAS[low]
    if low in _S_SUFFIX_SAFE:
        return low  # -s 结尾但非复数，不还原
    # 规则屈折：-ies→-y（还原后长度 ≥3，避免误伤）
    if low.endswith("ies") and len(low) > 5:
        base = low[:-3] + "y"
        if base != low and len(base) >= 3:
            return base
    # §3.116 ⭐ 实词 stoplist：独立 -ing 名词/形容词保持原形（不还原 base 动词）
    if low in _ING_REAL_WORDS:
        return low
    # -ing / -ed：去尾后还原 dropped-e 与双写辅音
    for suf in ("ing", "ed"):
        if low.endswith(suf) and len(low) > len(suf) + 2:
            base = low[:-len(suf)]
            if base != low and len(base) >= 3:
                cand = _restore_stem(base)
                # §3.116 ⭐ 误切防护：还原结果必须比原词更常见才保留，否则保持原词
                # （spring→spr / string→str / during→dur / according→accord /
                #  hundred→hundr / sacred→sacr 等 -ing/-ed 结尾实词与功能词不误切）。
                if _more_common_word(cand, low):
                    return cand
                return low
    # -es 只在特定结尾（-ches/-shes/-xes/-zes/-sses）去掉 es（boxes→box）
    if low.endswith("es") and len(low) > 4 and low.endswith(
            ("ches", "shes", "xes", "zes", "sses")):
        return low[:-2]
    # -s（普通复数，最后兜底）——排除 -ss 结尾（process/class/glass 非复数）
    if low.endswith("s") and not low.endswith("ss") and len(low) > 3:
        base = low[:-1]
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


def _is_noise_word(word: str) -> bool:
    """噪声词判定（OCR 污染/重复字符/断词残片）。

    - 同一字符重复 ≥3 次（ggggg/aaaaa）
    - 交替重复模式（abababab）
    """
    low = word.lower()
    if len(low) < 2:
        return True
    if re.match(r"^([a-z])\1{2,}$", low):
        return True
    if re.match(r"^([a-z]{2})\1{2,}$", low):
        return True
    # 3 字符内同字符占 2/3 以上
    if len(low) <= 3 and max(low.count(ch) for ch in set(low)) >= 2:
        return True
    return False


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

    # 2. 分词 + 词尾丢失恢复（scienc→science / includ→include，ecdict 词典校验）
    tokens = [_recover_truncated(t) for t in _simple_tokenize(text, ctx.target_lang)]

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
        # §3.116 ⭐ 修复：停用词过滤用「原始 token」+「词元」双重检查——
        # 否则 this→(lemmatize)→thi 绕过停用词过滤，产生畸形词条 thi
        tok_low = tok.lower()
        low = info["lemma"].lower()
        if tok_low in _EN_STOPWORDS or low in _EN_STOPWORDS or len(low) < 2 or _is_noise_word(low):
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
