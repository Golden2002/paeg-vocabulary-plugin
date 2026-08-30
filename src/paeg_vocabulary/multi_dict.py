# -*- coding: utf-8 -*-
"""paeg_vocabulary.multi_dict — 多词典一次性查询 + 相同/近似义项去重合并（§3.116 ⭐）。

用户需求（§3.116 ⭐）：
  "同一个词可能在不同的本地词库查到不同的释义，那需要对它进行一个整合"——
  多词典对同一词的相同/近似义项去重合并，并保留来源标注（ecdict/CEFR/kaikki/WordNet
  各贡献了哪条义项）。

离线数据源（全部本地确定性，无网可跑）：
  - ECDICT（77 万词）：英文释义 definition_en + 中文释义 translation_zh（多义项按行拆分）
  - CEFR English Wordlist（2000+ 词）：基础英文释义 + 例句
  - kaikki Wiktionary 学科术语：英文 glosses（多义项）+ 词源
  - Oxford 3000 / CMU：分级 + 音标（由 WordBank 整合）
  - WordNet（可选）：NLTK wordnet 义项定义（未安装/未下载时自动降级为空）

合并策略（merge_senses）：
  - 归一化义项文本（小写/去词性前缀/去领域标签/折叠空白）→ 归一化 key + 词集
  - 完全一致 或 Jaccard 词集相似 ≥0.6 或 归一化文本互为子串（短者 ≥ 长者的 60%）→ 合并
  - 合并后保留更长（更完整）的义项文本，sources 追加贡献来源（去重）
  - 中文义项（仅 ECDICT 提供）与英文义项分列，各自合并

用法：
    from paeg_vocabulary.multi_dict import MultiDict, merge_senses
    md = MultiDict()
    r = md.query("phenomenon")
    # → {"word": ..., "senses_en": [{"text": ..., "sources": ["kaikki","ecdict"]}, ...],
    #     "senses_zh": [...], "ipa": ..., "pos": ..., "cefr": ..., "etymology": ...}
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .wordbank import (
    CefrGlossSource,
    DomainGlossary,
    EcdictSource,
    WordBank,
    clean_ecdict_gloss,
)

# ─────────────────────────────────────────────────────────────
# 义项归一化与合并
# ─────────────────────────────────────────────────────────────
# 词性前缀（ecdict 释义行首自带 n./vt./adj. 等）
_POS_PREFIX_RE = re.compile(
    r"^(?:n\.|v\.|vt\.|vi\.|adj\.|adv\.|ad\.|a\.|r\.|s\.|prep\.|conj\.|pron\.|"
    r"int\.|interj\.|num\.|art\.|abbr\.|aux\.|det\.|phr\.|comb\.|suf\.|pref\.)\s+",
    re.IGNORECASE)
# 领域标签（[计]/[法]/〔计〕 等——只影响归一化 key，不影响展示文本）
_BRACKET_RE = re.compile(r"[\[〔].*?[\]〕]")


def _normalize_sense(text: str) -> Tuple[str, set]:
    """归一化义项文本 → (归一化 key, 词集)。用于跨词典近似义项判定。"""
    if not text:
        return "", set()
    t = str(text).replace("\\n", "\n")
    t = _BRACKET_RE.sub(" ", t)
    t = _POS_PREFIX_RE.sub("", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = t.strip().lower().strip(" .,;:()'\"…")
    tokens = set(re.findall(r"[a-z]+", t))
    return t, tokens


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _near_identical(norm: str, tokens: set, other_norm: str, other_tokens: set) -> bool:
    """两个归一化义项是否近似（相同/包含/高词集重叠）。"""
    if norm == other_norm:
        return True
    if _jaccard(tokens, other_tokens) >= 0.6:
        return True
    # 子串包含（短者是长者的扩写子集）→ 近似。
    # 约束：短者长度 ≥ 长者的 40%，且短者 ≥3 个词——避免「to run」误并「to run a program」
    # （后者是不同义项）。「a natural phenomenon」⊂「a natural phenomenon that is observable」
    # 这类同义扩写则正确合并。
    if norm and other_norm:
        short, long, short_tok = (
            (norm, other_norm, tokens) if len(norm) <= len(other_norm)
            else (other_norm, norm, other_tokens))
        if short in long and len(short) >= 0.4 * len(long) and len(short_tok) >= 3:
            return True
    return False


def merge_senses(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """合并跨词典义项 → (英文义项列表, 中文义项列表)。

    items: [{text, source, lang(默认 "en")}]。
    每个合并结果：{"text": 义项文本, "sources": [来源1, 来源2, ...]}。
    相同/近似义项合并后 sources 累计贡献来源（去重），保留更长文本。
    """
    merged_en: List[Dict[str, Any]] = []
    merged_zh: List[Dict[str, Any]] = []
    for it in items:
        text = (it.get("text") or "").strip()
        src = (it.get("source") or "").strip()
        lang = it.get("lang", "en")
        if not text or not src:
            continue
        norm, tokens = _normalize_sense(text)
        if not norm:
            continue
        bucket = merged_zh if lang == "zh" else merged_en
        matched = None
        for m in bucket:
            if _near_identical(norm, tokens, m["_norm"], m["_tokens"]):
                matched = m
                break
        if matched is not None:
            if src not in matched["sources"]:
                matched["sources"].append(src)
            # 保留更长（更完整）的义项文本
            if len(norm) > len(matched["_norm"]):
                matched["text"] = text
                matched["_norm"] = norm
                matched["_tokens"] = tokens
        else:
            bucket.append({"text": text, "sources": [src],
                           "_norm": norm, "_tokens": tokens})
    for m in merged_en + merged_zh:
        m.pop("_norm", None)
        m.pop("_tokens", None)
    return merged_en, merged_zh


# ─────────────────────────────────────────────────────────────
# WordNet 可选离线源（NLTK wordnet——未安装/未下载时静默降级）
# ─────────────────────────────────────────────────────────────
class WordNetSource:
    """WordNet 义项源（可选离线，NLTK 数据）。

    未安装 nltk 或未下载 wordnet 数据时 definitions 返回空列表——不阻塞查询。
    下载：python scripts/download_wordnet.py（nltk.download('wordnet'/'omw-1.4')）。
    """

    def definitions(self, word: str, limit: int = 4) -> List[Tuple[str, str]]:
        """返回 [(definition, pos), ...]（NLTK 不可用时为空）。"""
        try:
            from nltk.corpus import wordnet as wn
        except Exception:
            return []
        out: List[Tuple[str, str]] = []
        try:
            for syn in wn.synsets(word.strip().lower())[:limit]:
                d = (syn.definition() or "").strip()
                if d:
                    out.append((d, syn.pos() or ""))
        except Exception:
            return []
        return out


# ─────────────────────────────────────────────────────────────
# 多词典统一查询入口
# ─────────────────────────────────────────────────────────────
class MultiDict:
    """多词典一次性查询（WordBank 整合 + 义项级跨源合并去重 + 来源标注）。"""

    def __init__(self, domains: Optional[List[str]] = None, use_wordnet: bool = True):
        self.wb = WordBank(domains=domains)
        self.ecdict = EcdictSource()
        self.cefr = CefrGlossSource()
        self.domain = DomainGlossary(domains)
        self.use_wordnet = use_wordnet

    def query(self, word: str) -> Dict[str, Any]:
        w = word.strip().lower()
        wb_r = self.wb.lookup(w)

        items: List[Dict[str, Any]] = []
        # 1. kaikki 学科术语 glosses（英文多义项）
        for g in (wb_r.get("senses") or []):
            if g:
                items.append({"text": g, "source": "kaikki", "lang": "en"})
        dt = wb_r.get("domain_term") or {}
        for g in (dt.get("glosses") or []):
            if g:
                items.append({"text": g, "source": "kaikki", "lang": "en"})
        # 2. ECDICT 英文释义 + 中文释义（多义项按行拆分）
        ec = self.ecdict.lookup(w)
        if ec:
            for line in clean_ecdict_gloss(ec.get("definition_en", "")).split("\n"):
                if line.strip():
                    items.append({"text": line.strip(), "source": "ecdict", "lang": "en"})
            for line in clean_ecdict_gloss(ec.get("translation_zh", "")).split("\n"):
                if line.strip():
                    items.append({"text": line.strip(), "source": "ecdict", "lang": "zh"})
        # 3. CEFR 基础英文释义
        cg = self.cefr.lookup(w)
        if cg and cg.get("gloss_en"):
            items.append({"text": cg["gloss_en"], "source": "cefr", "lang": "en"})
        # 4. WordNet（可选离线）
        if self.use_wordnet:
            for d, _pos in WordNetSource().definitions(w):
                items.append({"text": d, "source": "wordnet", "lang": "en"})

        senses_en, senses_zh = merge_senses(items)
        gloss_en = "；".join(s["text"] for s in senses_en) or wb_r.get("gloss_en") or ""
        gloss_zh = "；".join(s["text"] for s in senses_zh) or wb_r.get("gloss_zh") or ""

        return {
            "word": w,
            "ipa": wb_r.get("ipa"),
            "pos": wb_r.get("pos"),
            "cefr": wb_r.get("cefr"),
            "etymology": wb_r.get("etymology"),
            "gloss_en": gloss_en,
            "gloss_zh": gloss_zh,
            "senses_en": senses_en,
            "senses_zh": senses_zh,
            "sources": wb_r.get("sources", {}),
        }
