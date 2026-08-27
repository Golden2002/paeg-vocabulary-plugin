# -*- coding: utf-8 -*-
"""paeg_vocabulary.enrichers.llm_enricher — LLM 信息补全 sub-agent（§3.116 ⭐）。

词汇补全 sub-agent：对候选词生成 12 字段（双语释义/词源/例句/短语）。
注入式 chat_fn（零宿主依赖——外部智能体可注入自己的 LLM）。

sub-agent 插件化：可独立扩展语种/字段/数据源（生态要求）。
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Optional

from ..core.entry import VocabularyEntry

# 补全系统提示词（词汇补全 sub-agent 角色）
ENRICHER_SYSTEM_PROMPT = """你是语言学习词汇补全专家。为给定单词生成结构化词汇信息。

输出 JSON，字段：
{
  "headword": 原词,
  "pos": 词性(n./v./adj./adv.),
  "gloss_bilingual": {"zh": "中文释义", "en": "英文释义"},
  "ipa": {"en_us": "/美式音标/", "en_uk": "/英式音标/"},
  "etymology": "词源（语系归属 + 词根词缀拆解 + 演变路径，etymonline 风格）",
  "morpheme": {"roots": [{"root": "词根", "lang": "语言", "meaning": "含义"}],
               "prefix": {"p": "前缀", "meaning": "含义"},
               "suffix": {"s": "后缀", "meaning": "含义"}},
  "senses": [{"zh": "义项1释义", "en": "sense 1 gloss"},
             {"zh": "义项2释义", "en": "sense 2 gloss"}],
  "book_sense": {"zh": "本书特定含义", "en": "meaning in this book",
                 "context": "在本书中，作者（作者名）的意思是…"},
  "examples": [{"zh": "中文翻译", "en": "英文例句"}],
  "collocations": ["短语搭配1", "短语搭配2"]
}

要求：
- 多义词按义项拆分（Etymology1/2 + Sense1/2 编号）
- **book_sense 必须给出**：这个词在本书（{book_title}，作者 {book_author}）中的特定含义，
  作为义项之一；context 字段标注"在本书中，{book_author}的意思是…"
- 词源标注语系（印欧/拉丁/希腊等）+ 词根词缀拆解（roots/prefix/suffix 各含语言与含义）
- 音标必须给出（IPA 格式，美式 en_us + 英式 en_uk）
- 例句自然、教学友好
- 只输出 JSON，不要其他文字"""


def enrich_entry_with_llm(entry: VocabularyEntry,
                          chat_fn: Optional[Callable] = None,
                          book_title: str = "",
                          book_author: str = "") -> VocabularyEntry:
    """LLM 补全条目（chat_fn 注入；None 时弱模式保留已有字段）。

    §3.116 ⭐ book_title/book_author：用于生成"本书含义"义项（book_sense）。
    """
    if chat_fn is None:
        return entry  # 弱模式：不补全
    try:
        user = (f"单词: {entry.headword}\n"
                f"已知词性: {entry.pos or '未知'}\n"
                f"已知释义: {entry.gloss_bilingual or '无'}\n"
                f"来源书籍: {book_title or '未知'}（作者: {book_author or '未知'}）\n"
                f"请补全完整词汇信息。")
        _sys = (ENRICHER_SYSTEM_PROMPT
                .replace("{book_title}", book_title or "本书")
                .replace("{book_author}", book_author or "作者"))
        # §3.116 ⭐ 安全调用：宿主 chat_fn 签名可能是 (sys_p, usr_p) 两参——
        # 传 max_tokens 关键字会 TypeError 被吞导致补全失败。逐级降级调用。
        _raw = None
        try:
            _raw = chat_fn(_sys, user, max_tokens=100000)
        except TypeError:
            try:
                _raw = chat_fn(_sys, user)
            except Exception:
                _raw = None
        except Exception:
            _raw = None
        if not _raw:
            return entry
        # 提取 JSON
        m = re.search(r"\{.*\}", _raw, re.S)
        if not m:
            return entry
        data = json.loads(m.group(0))

        # 合并到条目
        if data.get("pos"):
            entry.pos = data["pos"]
        if data.get("gloss_bilingual"):
            entry.gloss_bilingual = data["gloss_bilingual"]
        if data.get("ipa"):
            entry.ipa.update(data["ipa"])
        if data.get("etymology"):
            entry.etymology = data["etymology"]
        # §3.116 ⭐ morpheme（词根词缀——roots/prefix/suffix）
        if data.get("morpheme"):
            from ..core.entry import Morpheme
            m_data = data["morpheme"]
            entry.morpheme = Morpheme(
                roots=[dict(r) for r in m_data.get("roots", []) if isinstance(r, dict)],
                prefix=m_data.get("prefix"),
                suffix=m_data.get("suffix"),
            )
        # senses（多义项）
        if data.get("senses"):
            from ..core.entry import Sense
            entry.senses = [
                Sense(sense_id=f"1.{i+1}", gloss_zh=s.get("zh", ""), gloss_en=s.get("en", ""))
                for i, s in enumerate(data["senses"]) if isinstance(s, dict)
            ]
        # §3.116 ⭐ book_sense（本书含义义项——标注作者）
        if data.get("book_sense"):
            from ..core.entry import Sense
            bs = data["book_sense"]
            ctx = bs.get("context") or f"在本书中，{book_author or '作者'}的意思是"
            entry.senses.append(Sense(
                sense_id="book",
                gloss_zh=bs.get("zh", ""),
                gloss_en=bs.get("en", ""),
                book_context=ctx,
            ))
        if data.get("examples"):
            entry.examples = [{"en": e.get("en", ""), "zh": e.get("zh", "")}
                              for e in data["examples"] if isinstance(e, dict)]
        if data.get("collocations"):
            entry.collocations = data["collocations"]
        return entry
    except Exception:
        return entry


class LLMEnricher:
    """词汇补全 sub-agent（可独立扩展语种/字段）。"""

    def __init__(self, chat_fn: Optional[Callable] = None):
        self.chat_fn = chat_fn

    def enrich(self, entry: VocabularyEntry) -> VocabularyEntry:
        return enrich_entry_with_llm(entry, self.chat_fn)
