# -*- coding: utf-8 -*-
"""paeg_vocabulary._noise — OCR 粘连词检测（P7 ⭐ 候选质量）。

常见词拼接（wouldhave / theword / sothat）——OCR 去空格噪声。
检测：8+ 字符词可拆分为两个常见英语词。
"""

from __future__ import annotations

# 常见功能词（用于拼接检测）
_FUNC = {
    "the", "of", "in", "on", "at", "to", "for", "and", "or", "but", "if",
    "then", "else", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "can",
    "could", "should", "may", "might", "must", "this", "that", "these",
    "those", "it", "its", "he", "she", "they", "we", "you", "i", "me",
    "him", "her", "them", "us", "my", "your", "his", "our", "their",
    "not", "no", "so", "very", "just", "about", "into", "which", "what",
    "who", "when", "where", "why", "how", "there", "here", "all", "only",
    "such", "more", "most", "much", "many", "some", "any", "each", "every",
    "one", "two", "upon", "within", "without", "through", "between",
    "then", "than", "as", "with", "from", "by",
    "a", "an",  # §3.116 短拼接检测：as+a / to+be 类 OCR 去空格噪声
}

# 常见实词（拼接检测第二段）
_CONTENT = {
    "have", "has", "had", "will", "would", "should", "could", "can",
    "say", "said", "see", "look", "know", "think", "want", "get", "go",
    "come", "make", "take", "give", "find", "feel", "become", "seem",
    "word", "words", "thing", "things", "time", "way", "man", "men",
    "woman", "women", "life", "world", "hand", "eye", "face", "head",
    "mother", "father", "name", "house", "heart", "mind", "day", "year",
    "back", "read", "write", "book", "page", "her", "him", "them",
    "one", "two", "three", "first", "every", "such", "same", "own",
    "other", "another", "never", "always", "often", "ever", "even",
    "still", "already", "yet", "now", "then", "here", "there",
    "skin", "nerve", "mother", "young", "readers", "women", "men",
    "nixon", "york", "yale", "penn", "harvard", "washington",
    "translate", "receive", "submit", "specify", "represent",
    "social", "sexual", "surprise", "talk", "tawton",
}

# 已确认的粘连噪声（书中实测）
_NOISE_KNOWN = {
    "wouldhave", "withher", "whatyou", "wayout", "tothis", "toread",
    "theword", "thetwo", "thereal", "talkingabout", "suchan", "sothat",
    "someother", "sheis", "seeu", "onthis", "ofhuman", "youwent",
    "youwear", "youshould", "yourskin", "yournerves", "yourmother",
    "yourcontested", "youbreak", "yetwhat", "yetshe", "yeteven",
    "yearsearlier", "yearsafter", "yorktimes", "wrongwith", "wrongnote",
    "zig-zagyet", "zippedup", "zippycollege", "zombievoice",
    "yourselfand", "youngadults", "youngreader", "youngreaders",
    "youngwomen", "youngwriter", "youngmen", "youngadult", "youngwoman",
    # 高频粘连（wordfreq 收录但属 OCR 噪声——硬编码拦截）
    "ofthe", "inthe", "bemore", "inher", "themiddle", "thesedays",
    "notthe", "ofhim", "herto", "halfan", "isno", "goback", "awoman",
    # §3.116 实测残留（wordfreq 误收录为合法词的 OCR 去空格噪声——硬编码拦截）
    "tobe", "asa", "lan-guage", "lan-guages",
}


def _is_common_word(w: str) -> bool:
    """判断是否为常见英语词（wordfreq zipf > 2.5 或已知内容词）。"""
    if w in _FUNC or w in _CONTENT:
        return True
    try:
        from wordfreq import zipf_frequency
        return zipf_frequency(w, "en") > 2.5
    except Exception:
        return False


def is_likely_noise(word: str) -> bool:
    """判断词是否 OCR 粘连噪声。

    1. 已知噪声表命中
    2. 可拆分为 [功能词] + [常见完整词] 拼接（整体非高频词——novel 不误伤）
    """
    w = word.strip().lower()
    if not w:
        return True
    if w in _NOISE_KNOWN:
        return True
    if len(w) < 5:
        return False
    # 整体是常见词（novel/femininity——zipf>2.5）→ 合法词不拆
    if _is_common_word(w):
        return False
    # 双词拼接检测：切分为 功能词+常见词（两侧都完整）
    for i in range(2, len(w) - 2):
        a, b = w[:i], w[i:]
        if a in _FUNC and _is_common_word(b):
            return True
        if b in _FUNC and _is_common_word(a):
            return True
    return False
