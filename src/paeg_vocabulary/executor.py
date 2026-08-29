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

    # §3.116 ⭐ 标准化接口新工具（MCP 风格 schema）
    if name == "lookup_word":
        try:
            from .wordbank import WordBank
            wb = WordBank(domains=args.get("domains"))
            r = wb.lookup(args.get("word", ""))
            return json.dumps({"ok": True, **r}, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)[:200]},
                              ensure_ascii=False)

    if name == "extract_collocations":
        try:
            from .collocations import extract_collocations
            colls = extract_collocations(args.get("corpus") or [],
                                         n=int(args.get("n") or 2),
                                         min_count=int(args.get("min_count") or 2),
                                         top_n=int(args.get("top_n") or 30))
            return json.dumps({"ok": True, "collocations": colls},
                              ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)[:200]},
                              ensure_ascii=False)

    if name == "quantile_of":
        try:
            from .quantile_engine import compute_q
            q, meta = compute_q(args.get("word", ""),
                                cefr_hint=args.get("cefr_hint"),
                                with_meta=True)
            return json.dumps({"ok": True, "q": q, "meta": meta},
                              ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)[:200]},
                              ensure_ascii=False)

    if name == "bank_coverage":
        try:
            from .wordbank import WordBank
            wb = WordBank(domains=args.get("domains"))
            return json.dumps({"ok": True, "coverage": wb.coverage_stats()},
                              ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)[:200]},
                              ensure_ascii=False)

    if name == "srs_plan":
        from .srs import plan_schedule
        try:
            words = args.get("words", [])
            days = int(args.get("days", 7))
            r = plan_schedule(words, days)
            return json.dumps({"ok": True, **r}, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)[:200]},
                              ensure_ascii=False)

    if name == "srs_review":
        from .srs import sm2_review
        try:
            r = sm2_review(float(args.get("ef", 2.5)),
                           int(args.get("interval", 0)),
                           int(args.get("reps", 0)),
                           int(args.get("quality", 3)))
            return json.dumps({"ok": True, **r}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)[:200]},
                              ensure_ascii=False)

    return json.dumps({"ok": False, "error": f"未知工具: {name}（支持 generate_vocabulary/list_languages/list_generators）"},
                      ensure_ascii=False)
