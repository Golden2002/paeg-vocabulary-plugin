# -*- coding: utf-8 -*-
"""paeg_vocabulary.lang_style — 语言规范 L0 校对（复用 paeg_lang_style 若可用）。

§3.116 ⭐ 工具生态联通：词汇表工具（14.3）注册并使用 paeg_lang_style（14.1）
对【生成的中文文本】做 L0 确定性校对（gate_short + fix_known_gaffes）。

接入点（中文文本生成链路）：
- batch_llm 批量补全产出的 gloss_zh / etymology / senses[].gloss_zh / examples[].zh
- review 渲染前 LLM 审查回写的 zh 字段

缺失 paeg_lang_style 时优雅降级：apply_l0 原样返回，不抛异常、不阻塞管线。
"""

from __future__ import annotations

from typing import Any

_HAS_LANG_STYLE = False
_gate_short = None
_fix_known_gaffes = None

try:  # pragma: no cover - 依赖环境，非测试分支
    from paeg_lang_style import gate_short as _gate_short
    from paeg_lang_style import fix_known_gaffes as _fix_known_gaffes
    _HAS_LANG_STYLE = True
except Exception:
    _HAS_LANG_STYLE = False


def has_lang_style() -> bool:
    """是否已接入 paeg_lang_style（14.1）。"""
    return _HAS_LANG_STYLE


def apply_l0(text: str, context: str = "") -> str:
    """对一段中文文本做 L0 校对（gate_short + fix_known_gaffes 兜底）。

    - paeg_lang_style 缺失 → 原样返回（优雅降级）
    - 非字符串 / 空串 → 原样返回
    - 任一步骤异常 → 回退原文（绝不抛异常、绝不阻塞生成管线）
    """
    if not text or not isinstance(text, str) or not text.strip():
        return text
    if not _HAS_LANG_STYLE:
        return text
    try:
        out = _gate_short(text, context=context)
        if not isinstance(out, str):
            out = text
        # gate_short 已内置 fix_known_gaffes（首尾各一次）；再跑一次兜底，
        # 与 14.1 gate_content 的"最终收口"策略一致，确保输出永不含已知病句。
        out = _fix_known_gaffes(out)
        return out if isinstance(out, str) else text
    except Exception:
        return text


# 中文文本字段清单（VocabularyEntry → 渲染输出中的中文内容）
# 仅处理【生成的中文】，英文释义/例句/词头不动。
def apply_l0_to_entry(entry: Any) -> Any:
    """对词条内生成的中文文本字段做 L0 校对（原地更新，返回原对象）。

    entry 为 VocabularyEntry（或 dict），含：
    - gloss_bilingual.zh（双语释义中文）
    - etymology（词源——LLM 生成的中文散文）
    - senses[].gloss_zh / book_context（义项中文 / 本书含义）
    - examples[].zh（例句中文翻译）
    """
    if entry is None:
        return entry

    def _clean(value: str) -> str:
        return apply_l0(value) if isinstance(value, str) else value

    # 兼容 dict（review 阶段以 dict 回写）与 VocabularyEntry（dataclass）
    if isinstance(entry, dict):
        gb = entry.get("gloss_bilingual")
        if isinstance(gb, dict) and gb.get("zh"):
            gb["zh"] = _clean(gb["zh"])
        if entry.get("etymology"):
            entry["etymology"] = _clean(entry["etymology"])
        for s in entry.get("senses") or []:
            if isinstance(s, dict):
                if s.get("gloss_zh"):
                    s["gloss_zh"] = _clean(s["gloss_zh"])
                if s.get("book_context"):
                    s["book_context"] = _clean(s["book_context"])
        for ex in entry.get("examples") or []:
            if isinstance(ex, dict) and ex.get("zh"):
                ex["zh"] = _clean(ex["zh"])
        return entry

    # VocabularyEntry（dataclass）
    try:
        gb = getattr(entry, "gloss_bilingual", None)
        if isinstance(gb, dict) and gb.get("zh"):
            gb["zh"] = _clean(gb["zh"])
        if getattr(entry, "etymology", ""):
            entry.etymology = _clean(entry.etymology)
        for s in getattr(entry, "senses", None) or []:
            if getattr(s, "gloss_zh", ""):
                s.gloss_zh = _clean(s.gloss_zh)
            if getattr(s, "book_context", ""):
                s.book_context = _clean(s.book_context)
        for ex in getattr(entry, "examples", None) or []:
            if isinstance(ex, dict) and ex.get("zh"):
                ex["zh"] = _clean(ex["zh"])
    except Exception:
        pass
    return entry


__all__ = ["has_lang_style", "apply_l0", "apply_l0_to_entry"]
