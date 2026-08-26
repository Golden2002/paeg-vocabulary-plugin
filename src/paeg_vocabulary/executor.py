# -*- coding: utf-8 -*-
"""paeg_vocabulary.executor — 统一执行入口（§3.116 ⭐ MCP 契约）。

对标 paeg-teaching-materials executor——返回 JSON 字符串，绝不抛异常。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .registry import VocabularyRegistry


def execute(name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
    """统一执行入口。

    支持：
    - generate_vocabulary（主流程：PDF → 词汇表）
    - list_languages / list_generators（自省）
    - validate_entry（条目校验）
    """
    args = arguments or {}

    if name == "list_languages":
        return json.dumps({"ok": True, "languages": VocabularyRegistry.languages()},
                          ensure_ascii=False)

    if name == "list_generators":
        return json.dumps({"ok": True,
                           "generators": VocabularyRegistry.available_generators()},
                          ensure_ascii=False)

    if name == "validate_entry":
        from .core.entry import VocabularyEntry, validate_entry
        entry = VocabularyEntry(
            headword=args.get("headword", ""),
            pos=args.get("pos", ""),
            ipa=args.get("ipa", {}),
            gloss_bilingual=args.get("gloss_bilingual", {}),
        )
        missing = validate_entry(entry)
        return json.dumps({"ok": len(missing) == 0, "missing": missing},
                          ensure_ascii=False)

    if name == "clean_examples":
        from .cleaners.example_sanitize import sanitize_examples
        cleaned = sanitize_examples(args.get("examples", []))
        return json.dumps({"ok": True, "cleaned": cleaned}, ensure_ascii=False)

    if name == "generate_vocabulary":
        pdf = args.get("pdf_path", "")
        lang = args.get("lang", "en")
        if not pdf:
            return json.dumps({"ok": False, "error": "缺少 pdf_path"},
                              ensure_ascii=False)
        try:
            result = VocabularyRegistry.generate_vocabulary(
                pdf, lang, user_filter=args.get("user_filter"),
                chat_fn=args.get("chat_fn"))
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)[:300]},
                              ensure_ascii=False)

    return json.dumps({"ok": False, "error": f"未知工具: {name}（支持 generate_vocabulary/list_languages/list_generators）"},
                      ensure_ascii=False)
