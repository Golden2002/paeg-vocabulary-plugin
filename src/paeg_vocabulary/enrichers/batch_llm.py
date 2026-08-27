# -*- coding: utf-8 -*-
"""paeg_vocabulary.enrichers.batch_llm — P5 ⭐ LLM 批量补全（20 词/批）。

Oracle 架构（§3.116）：
- 逐词调用 3819 次 API（2 小时）→ 批量 20 词/批（191 次，10 分钟）
- JSON schema 强校验 + 行号前缀防截断 + headword 防串味
- 断点续跑：每批独立 try/except，失败不阻塞后续
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional, Sequence

# 批量补全系统提示词（20 词/批，JSON 数组）
BATCH_SYSTEM_PROMPT = """你是语言学习词汇补全专家。为给定的一批单词批量生成结构化词汇信息。

输出 JSON 数组（不要 Markdown 代码块包裹，不要其他文字）：
[
  {
    "headword": "原词（必须与输入完全一致）",
    "pos": "词性(n./v./adj./adv.)",
    "gloss_zh": "中文释义",
    "gloss_en": "英文释义",
    "ipa": {"en_us": "/美式/", "en_uk": "/英式/"},
    "etymology": "词源（语系归属+词根词缀+演变路径，etymonline 风格）",
    "morpheme": {"roots": [{"root": "词根", "lang": "语言", "meaning": "含义"}],
                 "prefix": {"p": "前缀", "meaning": "含义"},
                 "suffix": {"s": "后缀", "meaning": "含义"}},
    "senses": [{"zh": "义项1", "en": "sense1"}, {"zh": "义项2", "en": "sense2"}],
    "book_sense": {"zh": "本书义", "en": "book sense", "context": "在本书中的含义说明"},
    "examples": [{"en": "英文例句", "zh": "中文翻译"}],
    "collocations": ["短语搭配1", "短语搭配2"]
  }
]

要求：
- 数组长度必须与输入词数一致，顺序一致
- headword 必须与输入词完全一致（校验防串味）
- 多义词按义项拆分 senses
- 每个字段尽量给出；无法确定可留空但字段名保留
- 只输出 JSON，不要其他文字"""


def chunk_words(words: Sequence[str], batch_size: int = 20) -> List[List[str]]:
    """词列表分块（默认 20 词/批）。"""
    if not words:
        return []
    return [list(words[i:i + batch_size]) for i in range(0, len(words), batch_size)]


def build_batch_prompt(words: Sequence[str],
                       book_title: str = "", book_author: str = "") -> str:
    """构造批量补全用户提示词。"""
    word_list = "\n".join(f"{i + 1}. {w}" for i, w in enumerate(words))
    book_ctx = f"（来源书籍：{book_title}，作者：{book_author}）" if book_title else ""
    return (f"请为以下 {len(words)} 个单词批量生成词汇信息{book_ctx}：\n\n{word_list}\n\n"
            f"按序号顺序输出 JSON 数组，每个元素 headword 必须与输入一致。")


def parse_batch_response(raw: str,
                         expected: Optional[set] = None) -> List[Dict[str, Any]]:
    """解析批量 JSON 响应（含容错）。

    策略：完整 JSON 数组 → 正则提取首个 [...] → headword 校验（防串味）。
    """
    if not raw or not isinstance(raw, str):
        return []
    # 1. 完整解析
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return _validate_batch(data, expected)
    except Exception:
        pass
    # 2. 正则提取首个 [...]（含前缀/截断容错）
    m = re.search(r"\[.*\]", raw, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return _validate_batch(data, expected)
        except Exception:
            pass
    return []


def _validate_batch(data: List[Any], expected: Optional[set]) -> List[Dict[str, Any]]:
    """校验：元素为 dict + headword 匹配（大小写不敏感——LLM 可能改大小写）。"""
    exp_lower = {w.lower() for w in expected} if expected else None
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        hw = str(item.get("headword", "")).strip()
        if not hw:
            continue
        if exp_lower is not None and hw.lower() not in exp_lower:
            continue  # headword 与请求词不匹配 → 丢弃
        out.append(item)
    return out


def _merge_to_entry(entry, data: Dict[str, Any]) -> None:
    """批量结果合并到条目（与 llm_enricher 单批逻辑一致）。"""
    from ..core.entry import Morpheme, Sense

    if data.get("pos"):
        entry.pos = data["pos"]
    if data.get("gloss_zh") or data.get("gloss_en"):
        entry.gloss_bilingual = {
            "zh": data.get("gloss_zh", ""),
            "en": data.get("gloss_en", ""),
        }
    if data.get("ipa"):
        entry.ipa.update(data["ipa"])
    if data.get("etymology"):
        entry.etymology = data["etymology"]
    if data.get("morpheme"):
        m_data = data["morpheme"]
        if isinstance(m_data, dict):
            prefix = m_data.get("prefix")
            if isinstance(prefix, list):
                prefix = prefix[0] if prefix else None
            suffix = m_data.get("suffix")
            if isinstance(suffix, list):
                suffix = suffix[0] if suffix else None
            entry.morpheme = Morpheme(
                roots=[dict(r) for r in m_data.get("roots", []) if isinstance(r, dict)],
                prefix=prefix if isinstance(prefix, dict) else None,
                suffix=suffix if isinstance(suffix, dict) else None,
            )
    if data.get("senses"):
        entry.senses = [
            Sense(sense_id=f"1.{i + 1}", gloss_zh=s.get("zh", ""),
                  gloss_en=s.get("en", ""))
            for i, s in enumerate(data["senses"]) if isinstance(s, dict)
        ]
    if data.get("book_sense"):
        bs = data["book_sense"]
        ctx = bs.get("context") or "在本书中的含义"
        entry.senses.append(Sense(sense_id="book", gloss_zh=bs.get("zh", ""),
                                  gloss_en=bs.get("en", ""), book_context=ctx))
    if data.get("examples"):
        entry.examples = [{"en": e.get("en", ""), "zh": e.get("zh", "")}
                          for e in data["examples"] if isinstance(e, dict)]
    if data.get("collocations"):
        entry.collocations = data["collocations"]


def batch_enrich(entries: List[VocabularyEntry],
                 chat_fn: Callable,
                 batch_size: int = 20,
                 book_title: str = "", book_author: str = "") -> List[VocabularyEntry]:
    """批量补全条目（20 词/批 + 断点续跑）。

    - 每批独立 try/except——失败不阻塞后续
    - 返回原 entries 列表（原地更新）
    """
    from ..core.entry import VocabularyEntry  # noqa: F401

    words = [e.headword for e in entries]
    batches = chunk_words(words, batch_size)
    entry_by_word = {e.headword.lower(): e for e in entries}

    for batch in batches:
        try:
            sys_p = BATCH_SYSTEM_PROMPT
            usr_p = build_batch_prompt(batch, book_title, book_author)
            raw = None
            try:
                raw = chat_fn(sys_p, usr_p, max_tokens=8000)
            except TypeError:
                try:
                    raw = chat_fn(sys_p, usr_p)
                except Exception:
                    raw = None
            except Exception:
                raw = None
            if not raw:
                continue  # 批失败 → 跳过（断点续跑）
            parsed = parse_batch_response(raw, expected=set(batch))
            for item in parsed:
                hw = str(item.get("headword", "")).strip()
                if hw.lower() in entry_by_word:
                    _merge_to_entry(entry_by_word[hw.lower()], item)
        except Exception:
            continue  # 单批异常不阻塞

    return entries


def enrich_with_batch(entries: List[VocabularyEntry],
                      chat_fn: Callable,
                      batch_size: int = 20,
                      book_title: str = "", book_author: str = "") -> List[VocabularyEntry]:
    """便捷入口（registry 兼容）。"""
    return batch_enrich(entries, chat_fn, batch_size, book_title, book_author)
