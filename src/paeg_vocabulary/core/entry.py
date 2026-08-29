# -*- coding: utf-8 -*-
"""paeg_vocabulary.core.entry — 词汇条目强制信息标准（§3.116 模块2 ⭐）。

基于调研（librarian §3.116）：Wiktionary/Anki/OALD/TEI 标准 → 12 字段。

词汇条目强制字段（L1 必填 + L2 增强 + L3 元数据）：
- L1 必填: headword, pos, ipa[多口音], gloss_bilingual, examples[原书优先], lemma
- L2 增强: etymology, senses[多义项编号], collocations, audio
- L3 元数据: cefr_level, freq_rank

多义项标准：Wiktionary 风格 Etymology1/2 + Sense 1/2 双层编号（同形异源 → 词源编号）。
IPA 多口音：{en_us, en_uk, de, fr...}，CMU dict + espeak-ng 兜底。
词源：etymonline 散文式（italic 源语言 + bold 关键节点）。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class Sense:
    """一个义项（多义词分义项）。

    §3.116 ⭐ book_context: 本书特定含义标注（如"在本书中，约纳斯的意思是…"）。
    """
    sense_id: str = ""            # "1.1" / "1.2"（词源.义项 双层编号）
    gloss_zh: str = ""            # 中文释义
    gloss_en: str = ""            # 英文释义
    book_context: str = ""        # 本书含义标注（"在本书中，作者的意思是…"）
    examples: List[Dict[str, str]] = field(default_factory=list)  # [{src, trans, ref}]
    collocations: List[str] = field(default_factory=list)


@dataclass
class Morpheme:
    """词根词缀拆解（§3.116 ⭐ 词源学上的词根词缀）。

    对齐英语学习已有词条数据格式：roots/prefix/suffix + 语言 + 含义。
    """
    roots: List[Dict[str, str]] = field(default_factory=list)   # [{"root", "lang", "meaning"}]
    prefix: Optional[Dict[str, str]] = None                     # {"p", "meaning"}
    suffix: Optional[Dict[str, str]] = None                     # {"s", "meaning"}

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VocabularyEntry:
    """词汇条目（12 字段强制标准）。"""
    # L1 核心（必填）
    headword: str = ""            # 词目（lemma 形，单数原形）
    pos: str = ""                 # 词性（n./v./adj./adv./prep.）
    ipa: Dict[str, str] = field(default_factory=dict)  # 多口音 {en_us, en_uk, de...}
    gloss_bilingual: Dict[str, str] = field(default_factory=dict)  # {zh, en}
    examples: List[Dict[str, str]] = field(default_factory=list)   # 原书优先
    lemma: str = ""               # 词元（lemmatization 结果）

    # L2 增强
    etymology: str = ""           # 词源（语系/词根词缀/演变路径）
    morpheme: Optional[Morpheme] = None  # 词根词缀拆解（roots/prefix/suffix）
    senses: List[Sense] = field(default_factory=list)  # 多义项（词源编号）
    collocations: List[str] = field(default_factory=list)  # 短语搭配
    audio: List[str] = field(default_factory=list)     # 发音 URL
    # §3.116 ⭐ 语言现象信号（熟词生义/固定搭配/俚语——筛选豁免依据）
    phenomena: Dict[str, List[str]] = field(default_factory=dict)  # {polysemy, collocations, slang}

    # L3 元数据
    cefr_level: str = ""          # A1-C2
    freq_rank: int = 0            # 全书频次排名

    # 来源追踪
    source_book: str = ""         # 来源书籍
    source_page: int = 0          # 首次出现页码

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateWord:
    """候选词（阶段 3 产物：筛选后待补全）。"""
    headword: str = ""
    lemma: str = ""
    pos: str = ""
    freq_count: int = 0           # 书中出现次数
    global_zipf: float = 0.0      # 通用词频（wordfreq）
    cefr_guess: str = ""          # 难度猜测
    source_pages: List[int] = field(default_factory=list)
    contexts: List[str] = field(default_factory=list)  # 原书上下文（例句候选）
    must_keep: bool = False  # §3.116 ⭐ 本书关键术语（LLM 判断，豁免筛选）


def entry_required_fields() -> List[str]:
    """L1 必填字段清单（校验用）。"""
    return ["headword", "pos", "ipa", "gloss_bilingual", "examples", "lemma"]


def validate_entry(entry: VocabularyEntry) -> List[str]:
    """校验条目是否满足 L1 必填。返回缺失字段列表。"""
    missing = []
    if not entry.headword:
        missing.append("headword")
    if not entry.pos:
        missing.append("pos")
    if not entry.ipa:
        missing.append("ipa")
    if not entry.gloss_bilingual:
        missing.append("gloss_bilingual")
    if not entry.examples:
        missing.append("examples")
    return missing
