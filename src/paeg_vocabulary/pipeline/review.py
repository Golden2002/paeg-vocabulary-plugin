# -*- coding: utf-8 -*-
"""paeg_vocabulary.pipeline.review — 渲染前 LLM 审查（LLM 第三节点 ⭐）。

设计（用户 2026-08-28）：在准备渲染词库文件时，把结构化词条交给 LLM 审查——
用户的输入（水平档位/需求描述）作为上下文提示词，与系统提示词一并发送；
LLM 根据系统提示词和用户需求，对即将渲染的数据逐条审查（纠错/补漏/降噪），
返回修正后的结构化数据。
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional


def review_entries(
    entries: List[Dict[str, Any]],
    chat_fn: Callable,
    user_context: str = "",
    batch_size: int = 8,
) -> List[Dict[str, Any]]:
    """LLM 审查即将渲染的词条（批量，返回修正后的 entries）。

    entries: 待渲染词条字典列表（to_dict 后）
    user_context: 用户输入（水平档位/学习目标/需求描述——作为上下文提示词）
    返回：审查修正后的词条列表（与原列表等长，逐条修正字段）。
    """
    if not chat_fn or not entries:
        return entries

    sys_p = (
        "你是词汇表质检官。用户即将使用一份外语学习词汇表，"
        "请你根据【用户需求】对词条数据逐条审查，指出并修正以下问题：\n"
        "1. 释义错误或不准确（含中英释义不符）\n"
        "2. 词性标注错误\n"
        "3. 音标明显错误\n"
        "4. 例句与词义不匹配\n"
        "5. 不重要的噪声词（可标记 remove）\n"
        "6. 缺字段（词源/词根词缀/释义）需要补全的\n"
        "输出 JSON：{\"fixes\": [{\"word\": \"...\", \"field\": \"字段名\", "
        "\"before\": \"...\", \"after\": \"...\", \"action\": \"replace|remove|add\", "
        "\"reason\": \"...\"}]}，只列需要修正的词条，无问题的词条不列。"
    )

    all_fixes: Dict[str, List[Dict[str, Any]]] = {}
    for i in range(0, len(entries), batch_size):
        batch = entries[i:i + batch_size]
        usr_p = (f"用户需求：{user_context or '通用词汇学习'}\n\n"
                 f"词条数据：{json.dumps(batch, ensure_ascii=False)[:6000]}")
        raw = chat_fn(sys_p, usr_p)
        if not raw:
            continue
        try:
            import re
            m = re.search(r"\{.*\}", raw, re.S)
            data = json.loads(m.group(0)) if m else {}
            for fix in data.get("fixes", []):
                w = (fix.get("word") or "").strip().lower()
                if w:
                    all_fixes.setdefault(w, []).append(fix)
        except Exception:
            continue

    # 应用修正
    for e in entries:
        w = (e.get("headword") or "").strip().lower()
        for fix in all_fixes.get(w, []):
            _apply_fix(e, fix)
    return entries


def _apply_fix(entry: Dict[str, Any], fix: Dict[str, Any]) -> None:
    action = fix.get("action", "replace")
    field = fix.get("field", "")
    after = fix.get("after", "")
    if action == "remove":
        entry["_removed"] = True
        return
    if not field or not after:
        return
    # 顶层字段
    if field in entry:
        entry[field] = after
        return
    # 嵌套字段（gloss_bilingual.zh / gloss_bilingual.en / ipa.en_us 等）
    if "." in field:
        parts = field.split(".")
        cur = entry
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
            if not isinstance(cur, dict):
                cur = {}
        cur[parts[-1]] = after
