# -*- coding: utf-8 -*-
"""paeg_vocabulary.wordbank — P5 ⭐ 本地专业词库（离线音标/释义/分级 + 多词库整合消歧）。

用户需求（§3.116 ⭐）：
1. "联网下载一个专业词库到本地，这样来减少LLM的负担，让词汇表流更快，因为音标可以直接查"
2. "同一个词可能在不同的本地词库查到不同的释义，那需要对它进行一个整合，需要识别书中是哪个意思"
3. "现象学辞典，分子生物学辞典，物理学辞典，化学辞典等等"——学科术语辞典

词库体系：
- CmuIpaSource：CMU Pronouncing Dictionary（13 万词，ARPAbet → IPA）——音标权威
- CefrGlossSource：CEFR English Wordlist（2000+ 词，释义+例句+等级）——基础释义
- OxfordLevelSource：Oxford 3000（CEFR 分级 + 词性）——分级权威
- DomainGlossary：学科术语辞典（现象学/分子生物/物理/化学等）——学术术语

冲突消歧策略（多词库整合）：
- 音标：CMU 权威优先（espeak/LLM 兜底）
- 释义：词库基础义 + LLM 本书义（book_sense）双轨
- 等级：取最难（保守学习——防高估用户）
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA_DIR = Path(__file__).resolve().parent / "data"


# ═══════════════════════════════════════════════════════════
# CMU 音标（ARPAbet → IPA 映射）
# ═══════════════════════════════════════════════════════════
_ARPABET_TO_IPA = {
    # 元音（base 无重音数字——重音由 _arpabet_to_ipa 处理）
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ",
    "AW": "aʊ", "AY": "aɪ", "EH": "ɛ", "ER": "ɜr",
    "EY": "eɪ", "IH": "ɪ", "IY": "i", "OW": "oʊ",
    "OY": "ɔɪ", "UH": "ʊ", "UW": "u",
    # 辅音
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f",
    "G": "ɡ", "HH": "h", "JH": "dʒ", "K": "k", "L": "l",
    "M": "m", "N": "n", "NG": "ŋ", "P": "p", "R": "r",
    "S": "s", "SH": "ʃ", "T": "t", "TH": "θ", "V": "v",
    "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}


@lru_cache(maxsize=1)
def _load_cmu() -> Dict[str, List[str]]:
    """加载 CMU dict → {word_lower: [ARPAbet phones]}。"""
    p = _DATA_DIR / "cmudict.dict"
    if not p.exists():
        return {}
    out: Dict[str, List[str]] = {}
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith(";;;"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            word = parts[0].lower()
            # 去数字后缀（word(2) 多音词变体）
            word = re.sub(r"\(\d+\)$", "", word)
            out[word] = parts[1:]
    except Exception:
        pass
    return out


def _arpabet_to_ipa(phones: List[str]) -> str:
    """ARPAbet → IPA 字符串（重音标注在音节开头）。

    CMU 音节 = 元音 + 其前辅音串（如 L AY1 F → /laɪf/，重音在 l 前）。
    """
    ipa_parts: List[str] = []
    pending_stress: Optional[str] = None  # 待标注的重音（遇到辅音时前置）
    for ph in phones:
        if len(ph) >= 3 and ph[-1].isdigit():
            # 带重音的元音——先输出前面积累的辅音（无重音），重音挂在下个音节
            stress = ph[-1]
            base = ph[:-1]
            ipa = _ARPABET_TO_IPA.get(base, base)
            if stress == "1":
                # 重音放在当前音节前——若前有辅音串则标记需加在音节首
                pending_stress = "ˈ" + ipa
            elif stress == "2":
                pending_stress = "ˌ" + ipa
            else:
                pending_stress = ipa
        else:
            cons = _ARPABET_TO_IPA.get(ph, ph)
            if pending_stress is not None:
                # 音节开始（辅音前）——重音在此前置
                ipa_parts.append(pending_stress)
                ipa_parts.append(cons)
                pending_stress = None
            else:
                ipa_parts.append(cons)
    # 结尾残留重音（无后续辅音——如元音结尾词）
    if pending_stress is not None:
        ipa_parts.append(pending_stress)
    return "/" + "".join(ipa_parts) + "/"


class CmuIpaSource:
    """CMU 音标源（离线，13 万词）。"""

    def lookup(self, word: str) -> Optional[str]:
        cmu = _load_cmu()
        if not cmu:
            return None
        w = word.strip().lower()
        phones = cmu.get(w)
        if not phones:
            return None
        return _arpabet_to_ipa(phones)


# ═══════════════════════════════════════════════════════════
# CEFR 词表（释义 + 等级 + 例句）
# ═══════════════════════════════════════════════════════════
@lru_cache(maxsize=1)
def _load_cefr_gloss() -> Dict[str, Dict[str, str]]:
    """加载 CEFR English Wordlist → {word_lower: {gloss, cefr, pos, example}}。"""
    p = _DATA_DIR / "cefr_words.csv"
    if not p.exists():
        return {}
    out: Dict[str, Dict[str, str]] = {}
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
            parts = line.split(",")
            if len(parts) < 4:
                continue
            word = parts[0].strip().lower()
            if not word:
                continue
            out[word] = {
                "pos": parts[1].strip(),
                "cefr": parts[2].strip().upper(),
                "gloss_en": parts[3].strip(),
                "example": parts[4].strip() if len(parts) > 4 else "",
            }
    except Exception:
        pass
    return out


class CefrGlossSource:
    """CEFR 词表源（离线释义 + 等级）。"""

    def lookup(self, word: str) -> Optional[Dict[str, str]]:
        gloss = _load_cefr_gloss()
        if not gloss:
            return None
        return gloss.get(word.strip().lower())


# ═══════════════════════════════════════════════════════════
# Oxford 3000 分级
# ═══════════════════════════════════════════════════════════
@lru_cache(maxsize=1)
def _load_oxford() -> Dict[str, Dict[str, str]]:
    """加载 Oxford 3000 → {word_lower: {cefr, pos}}。"""
    p = _DATA_DIR / "oxford3000.tsv"
    if not p.exists():
        return {}
    out: Dict[str, Dict[str, str]] = {}
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            word = parts[0].strip().lower()
            if not word:
                continue
            out[word] = {"cefr": parts[4].strip().upper(), "pos": parts[3].strip()}
    except Exception:
        pass
    return out


class OxfordLevelSource:
    """Oxford 3000 分级源。"""

    def lookup(self, word: str) -> Optional[str]:
        ox = _load_oxford()
        if not ox:
            return None
        r = ox.get(word.strip().lower())
        return r.get("cefr") if r else None


class EcdictSource:
    """ECDICT 双语词典（skywind3000/ECDICT，77 万词全列）⭐。

    列：word, phonetic(1), definition(2), translation(3), pos(4),
        collins(5), oxford(6), tag(7), bnc(8), frq(9), ...
    懒加载 word → 字段映射（模块级缓存，内存查询，只存所需字段）。
    """

    _CACHE: Optional[Dict[str, Dict[str, str]]] = None

    @classmethod
    def _load(cls) -> Dict[str, Dict[str, str]]:
        if cls._CACHE is not None:
            return cls._CACHE
        import csv
        cache: Dict[str, Dict[str, str]] = {}
        p = _DATA_DIR / "ecdict.csv"
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                for row in csv.reader(f):
                    if len(row) < 5 or not row[0]:
                        continue
                    w = row[0].strip().lower()
                    pos = row[4].strip() if len(row) > 4 else ""
                    if not pos:
                        # pos 列常空——从释义前缀提取（n./v./adj. 等）
                        for src_col in (2, 3):
                            if len(row) > src_col:
                                m = re.match(r"([a-z]+\.)\s", row[src_col].strip())
                                if m:
                                    pos = m.group(1)
                                    break
                    cache[w] = {
                        "phonetic": row[1].strip() if len(row) > 1 else "",
                        "definition_en": row[2].strip() if len(row) > 2 else "",
                        "translation_zh": row[3].strip() if len(row) > 3 else "",
                        "pos": pos,
                        "collins": row[5].strip() if len(row) > 5 else "",
                        "oxford": row[6].strip() if len(row) > 6 else "",
                        "frq": row[9].strip() if len(row) > 9 else "",
                    }
        except Exception:
            pass
        cls._CACHE = cache
        return cache

    def lookup(self, word: str) -> Optional[Dict[str, str]]:
        return self._load().get(word.strip().lower())


# ═══════════════════════════════════════════════════════════
# 学科术语辞典（kaikki Wiktionary topic 分片——真实下载数据）
# 数据源：kaikki.org（CC BY-SA + GFDL），7 个学科 topic JSONL
#   philosophy/physics/biology/chemistry/biochemistry/genetics/anatomy
# ═══════════════════════════════════════════════════════════
_KAIKKI_TOPIC_FILES = {
    "phenomenology": "kaikki_topic_philosophy.jsonl",
    "philosophy": "kaikki_topic_philosophy.jsonl",
    "physics": "kaikki_topic_physics.jsonl",
    "chemistry": "kaikki_topic_chemistry.jsonl",
    "biology": "kaikki_topic_biology.jsonl",
    "biochemistry": "kaikki_topic_biochemistry.jsonl",
    "genetics": "kaikki_topic_genetics.jsonl",
    "anatomy": "kaikki_topic_anatomy.jsonl",
}


@lru_cache(maxsize=1)
def _load_kaikki(domains_key: str = "") -> Dict[str, Dict[str, Any]]:
    """加载 kaikki 学科术语 → {term_lower: {gloss_en, pos, topics, ipa, etymology}}。

    domains_key: 逗号分隔的学科列表（空 = 全部已下载学科）。
    """
    import json as _json
    domains = [d.strip() for d in domains_key.split(",") if d.strip()] if domains_key else []
    files = set()
    for d in domains:
        if d in _KAIKKI_TOPIC_FILES:
            files.add(_KAIKKI_TOPIC_FILES[d])
    if not files:
        files = set(_KAIKKI_TOPIC_FILES.values())

    out: Dict[str, Dict[str, Any]] = {}
    for fname in files:
        p = _DATA_DIR / fname
        if not p.exists():
            continue
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        d = _json.loads(line)
                    except Exception:
                        continue
                    word = str(d.get("word", "")).strip().lower()
                    if not word or len(word) > 40:
                        continue
                    senses = d.get("senses", [])
                    glosses = []
                    topics = set()
                    ipa = ""
                    for s in senses[:5]:
                        g = s.get("glosses") or []
                        if g:
                            glosses.extend(g)
                        topics.update(s.get("topics") or [])
                        # IPA（词条级 sounds）
                    sounds = d.get("sounds") or []
                    for sd in sounds:
                        if sd.get("ipa"):
                            ipa = sd["ipa"]
                            break
                    if not glosses:
                        continue
                    out[word] = {
                        "gloss_en": glosses[0][:300],
                        "glosses": glosses[:3],
                        "pos": str(d.get("pos", "")),
                        "topics": sorted(topics)[:8],
                        "ipa": ipa,
                        "etymology": str(d.get("etymology_text", ""))[:300],
                    }
        except Exception:
            continue
    return out


class DomainGlossary:
    """学科术语辞典（kaikki 真实数据——现象学/分子生物/物理/化学等按学科查询）。

    用法：DomainGlossary(["phenomenology", "biology"]) 只加载相关学科。
    """

    def __init__(self, domains: Optional[List[str]] = None):
        # 别名映射：phenomenology → philosophy 文件；分子生物 → biology/biochemistry
        self.domains = domains or ["philosophy", "biology", "physics", "chemistry"]
        self._cache_key = ",".join(self.domains)

    def available_domains(self) -> List[str]:
        return sorted(_KAIKKI_TOPIC_FILES.keys())

    def lookup(self, term: str) -> Optional[Dict[str, str]]:
        """查询术语（跨学科，返回含 domain 标注）。"""
        gloss = _load_kaikki(self._cache_key)
        if not gloss:
            return None
        t = term.strip().lower()
        hit = gloss.get(t)
        if hit:
            return {**hit, "domain": ",".join(hit.get("topics", [])[:3])}
        return None

    def coverage(self) -> int:
        """当前学科加载的词条数。"""
        return len(_load_kaikki(self._cache_key))


# ═══════════════════════════════════════════════════════════
# 多词库冲突整合消歧
# ═══════════════════════════════════════════════════════════
def resolve_ipa_conflict(sources: Dict[str, str], primary: str = "cmu") -> Optional[str]:
    """多音标源冲突消歧：CMU 权威优先，espeak/LLM 兜底。"""
    if sources.get(primary):
        return sources[primary]
    for v in sources.values():
        if v:
            return v
    return None


def resolve_gloss_conflict(bank_gloss: Optional[str], llm_gloss: Optional[str],
                           strategy: str = "bank_first") -> Optional[str]:
    """释义冲突整合：
    - bank_first：词库基础义优先（确定性）
    - llm_first：LLM 义优先（本书语境）
    - both：两者合并（基础义 + 本书义）
    """
    if strategy == "bank_first":
        return bank_gloss or llm_gloss
    if strategy == "llm_first":
        return llm_gloss or bank_gloss
    if strategy == "both" and bank_gloss and llm_gloss:
        return f"{bank_gloss}；本书义：{llm_gloss}"
    return bank_gloss or llm_gloss


def resolve_level_conflict(levels: Dict[str, Optional[str]],
                           strategy: str = "hardest") -> Optional[str]:
    """等级冲突整合：
    - hardest：取最难（保守学习——防高估用户）
    - easiest：取最易
    - majority：多数一致
    """
    order = ["A1", "A2", "B1", "B2", "C1", "C2"]
    known = [lv for lv in levels.values()
             if lv and lv.upper() in order]
    if not known:
        return None
    if strategy == "hardest":
        return max(known, key=lambda lv: order.index(lv.upper()))
    if strategy == "easiest":
        return min(known, key=lambda lv: order.index(lv.upper()))
    # majority：取众数
    from collections import Counter
    return Counter(known).most_common(1)[0][0]


# ═══════════════════════════════════════════════════════════
# ecdict 释义 / 词性清洗（§3.116 ⭐ 排版修复：去字面 \n、去词性前缀、规整领域标签）
# ═══════════════════════════════════════════════════════════
# ecdict 词性代码 → 标准词性（ecdict 用 r./s./a. 等非常规缩写；CEFR 词表用全词）
_POS_ALIAS = {
    "n": "n.", "v": "v.", "vt": "v.", "vi": "v.", "aux": "v.",
    "a": "adj.", "s": "adj.", "adj": "adj.",
    "r": "adv.", "ad": "adv.", "adv": "adv.",
    "prep": "prep.", "conj": "conj.", "pron": "pron.",
    "int": "int.", "interj": "int.", "num": "num.",
    "art": "art.", "abbr": "abbr.", "det": "det.",
    "phr": "phr.", "comb": "comb.", "suf": "suf.", "pref": "pref.",
    # CEFR/Oxford 词表全词词性 → 短代码（统一渲染风格）
    "noun": "n.", "verb": "v.", "adjective": "adj.", "adverb": "adv.",
    "preposition": "prep.", "conjunction": "conj.", "pronoun": "pron.",
    "interjection": "int.", "numeral": "num.", "article": "art.",
    "auxiliary": "v.", "determiner": "det.", "abbreviation": "abbr.",
}

# ecdict 释义行首词性前缀（n./vt./vi./adj./adv./a./r./s./prep. …）
_GLOSS_POS_PREFIX_RE = re.compile(
    r"^(?:n\.|v\.|vt\.|vi\.|adj\.|adv\.|ad\.|a\.|r\.|s\.|prep\.|conj\.|pron\.|"
    r"int\.|interj\.|num\.|art\.|abbr\.|aux\.|det\.|phr\.|comb\.|suf\.|pref\.)\s+",
    re.IGNORECASE)

# ecdict 罕见的无点词性码（如 "r in a systematic manner" 的 r=副词、s=形容词）
_GLOSS_BARE_POS_RE = re.compile(r"^[rs]\s+", re.IGNORECASE)


def normalize_pos(pos: str) -> str:
    """词性代码标准化（ecdict 的 r./s./a. → 通用 adv./adj. 等）。"""
    if not pos:
        return ""
    key = str(pos).strip().lower().rstrip(".")
    return _POS_ALIAS.get(key, str(pos).strip())


def clean_ecdict_gloss(text: str) -> str:
    """清理 ecdict 释义：字面 \\n → 换行；去行首词性前缀；领域标签 [x] → 〔x〕。

    ecdict translation/definition 字段用字面 \\n 分隔义项、且每行自带词性前缀
    （如 "n. 商标\\n[法] 商标"），直接渲染会出现 "\n" 乱码与词性重复。
    清洗后交给渲染层，渲染层再把真实换行转成 <br>。
    """
    if not text:
        return ""
    t = str(text).replace("\\n", "\n")
    lines = []
    for raw in t.split("\n"):
        line = raw.strip()
        if not line:
            continue
        # 去行首词性前缀（n./vt./a./r. …），避免与 headword 的 pos 徽章重复
        line = _GLOSS_POS_PREFIX_RE.sub("", line)
        # 再去无点词性码（r=副词/s=形容词），如 "r in a systematic manner"
        line = _GLOSS_BARE_POS_RE.sub("", line)
        # 领域标签规整：[计]/[法]/[医] → 〔计〕/〔法〕/〔医〕
        line = re.sub(r"\[([^\]]+)\]", r"〔\1〕", line)
        # 折叠内部多余空格
        line = re.sub(r"[ \t]{2,}", " ", line)
        if line:
            lines.append(line)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# WordBank 统一入口
# ═══════════════════════════════════════════════════════════
class WordBank:
    """本地专业词库统一查询（多源整合 + 冲突消歧）。

    用法：
        wb = WordBank(domains=["phenomenology", "biology"])
        r = wb.lookup("phenomenon")
        # → {"ipa": "/fɪˈnɑːmɪnɑːn/", "gloss_en": "...", "cefr": "B2",
        #    "domain_term": {...}, "sources": {...}}
    """

    def __init__(self, domains: Optional[List[str]] = None,
                 level_strategy: str = "hardest"):
        self.cmu = CmuIpaSource()
        self.cefr = CefrGlossSource()
        self.oxford = OxfordLevelSource()
        self.ecdict = EcdictSource()
        self.domain = DomainGlossary(domains)
        self.level_strategy = level_strategy

    def lookup(self, word: str) -> Dict[str, Any]:
        w = word.strip().lower()
        result: Dict[str, Any] = {
            "word": w, "ipa": None, "gloss_en": None, "gloss_zh": None,
            "cefr": None, "pos": None, "domain_term": None, "etymology": None,
            "senses": [], "sources": {},
        }

        # 1. 音标（CMU 权威，ECDICT 兜底）
        result["ipa"] = self.cmu.lookup(w)
        if result["ipa"]:
            result["sources"]["ipa"] = "cmu"

        # 2. CEFR 词表（基础释义）
        cg = self.cefr.lookup(w)
        if cg:
            result["gloss_en"] = cg.get("gloss_en")
            result["cefr"] = cg.get("cefr")
            result["pos"] = cg.get("pos")
            result["sources"]["gloss"] = "cefr_wordlist"

        # 3. Oxford 分级（等级冲突消歧）
        ox_lv = self.oxford.lookup(w)
        levels = {"oxford": ox_lv, "cefr_wordlist": result["cefr"]}
        resolved_lv = resolve_level_conflict(levels, self.level_strategy)
        if resolved_lv:
            result["cefr"] = resolved_lv
            result["sources"]["level"] = "|".join(
                k for k, v in levels.items() if v)

        # 4. 学科术语辞典（kaikki：gloss_en/pos/词源/多义项）
        dt = self.domain.lookup(w)
        if dt:
            result["domain_term"] = dt
            result["sources"]["domain"] = dt.get("domain", "")
            if not result["gloss_en"] and dt.get("gloss_en"):
                result["gloss_en"] = dt["gloss_en"]
            if not result["pos"] and dt.get("pos"):
                result["pos"] = dt["pos"]
            if dt.get("etymology"):
                result["etymology"] = dt["etymology"]
                result["sources"]["etymology"] = "kaikki"
            # 多义项（kaikki glosses 前 3 条 → senses）
            glosses = dt.get("glosses") or []
            result["senses"] = glosses[:3]

        # 5. ECDICT 双语（全列接线 ⭐：zh 释义/英文兜底/音标兜底/词性兜底）
        ec = self.ecdict.lookup(w)
        if ec:
            result["sources"]["ecdict"] = True
            if ec.get("translation_zh"):
                result["gloss_zh"] = clean_ecdict_gloss(ec["translation_zh"])
            if not result["gloss_en"] and ec.get("definition_en"):
                result["gloss_en"] = clean_ecdict_gloss(ec["definition_en"])
            if not result["ipa"] and ec.get("phonetic"):
                result["ipa"] = ec["phonetic"]
                result["sources"]["ipa"] = "ecdict"
            if not result["pos"] and ec.get("pos"):
                result["pos"] = normalize_pos(ec["pos"])

        return result

    def coverage_stats(self) -> Dict[str, int]:
        """词库覆盖统计（自检用）。"""
        kaikki = _load_kaikki(self.domain._cache_key)
        return {
            "cmu_words": len(_load_cmu()),
            "cefr_words": len(_load_cefr_gloss()),
            "oxford_words": len(_load_oxford()),
            "domain_terms": len(kaikki),
            "ecdict_words": len(self.ecdict._load()),
        }
