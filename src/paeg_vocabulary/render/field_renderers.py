# -*- coding: utf-8 -*-
"""paeg_vocabulary.render.field_renderers — P6 ⭐ 字段渲染注册表。

Oracle 方案（§3.116）：FIELD_RENDERERS 注册表——每个字段一个渲染器，
新增字段 = 注册新渲染器（生态可扩展）。缺失字段渲染器 → 抛错（防静默丢失）。
"""

from __future__ import annotations

from typing import Callable, Dict

from ..core.entry import VocabularyEntry

# 字段 → 渲染器注册表
FIELD_RENDERERS: Dict[str, Callable[[VocabularyEntry], str]] = {}


def register_field(name: str):
    """字段渲染器注册装饰器（生态扩展点 ⭐）。"""
    def _wrap(fn: Callable[[VocabularyEntry], str]):
        FIELD_RENDERERS[name] = fn
        return fn
    return _wrap


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@register_field("headword")
def _render_headword(e: VocabularyEntry) -> str:
    head = _esc(e.headword)
    ipa = ""
    if e.ipa:
        ipa = ' <span class="ipa">' + _esc(" / ".join(e.ipa.values())) + "</span>"
    pos = f' <span class="pos">{_esc(e.pos)}</span>' if e.pos else ""
    return f'<div class="headword">{head}{ipa}{pos}</div>'


@register_field("ipa")
def _render_ipa(e: VocabularyEntry) -> str:
    if not e.ipa:
        return ""
    return '<div class="ipa-row">' + " ".join(
        f'<span class="ipa-accent">{k}</span> <span class="ipa-val">{_esc(v)}</span>'
        for k, v in e.ipa.items()) + "</div>"


@register_field("gloss")
def _render_gloss(e: VocabularyEntry) -> str:
    if not e.gloss_bilingual:
        return ""
    zh = _esc(e.gloss_bilingual.get("zh", ""))
    en = _esc(e.gloss_bilingual.get("en", ""))
    return (f'<div class="gloss"><span class="gloss-zh">{zh}</span>'
            f'<span class="gloss-en">{en}</span></div>')


@register_field("senses")
def _render_senses(e: VocabularyEntry) -> str:
    if not e.senses:
        return ""
    parts = []
    for s in e.senses:
        ctx = (f'<span class="book-context">{_esc(s.book_context)}</span>'
               if s.book_context else "")
        parts.append(f'<div class="sense"><span class="sense-zh">{_esc(s.gloss_zh)}</span>'
                     f'<span class="sense-en">{_esc(s.gloss_en)}</span>{ctx}</div>')
    return '<div class="senses">' + "".join(parts) + "</div>"


@register_field("etymology")
def _render_etymology(e: VocabularyEntry) -> str:
    if not e.etymology:
        return ""
    return f'<div class="etymology">{_esc(e.etymology)}</div>'


@register_field("morpheme")
def _render_morpheme(e: VocabularyEntry) -> str:
    if not e.morpheme:
        return ""
    parts = []
    if e.morpheme.prefix:
        p = e.morpheme.prefix
        parts.append(f'{p.get("p", "")}「{p.get("meaning", "")}」')
    for r in e.morpheme.roots:
        parts.append(f'{r.get("root", "")}({r.get("lang", "")}「{r.get("meaning", "")}」)')
    if e.morpheme.suffix:
        s = e.morpheme.suffix
        parts.append(f'{s.get("s", "")}「{s.get("meaning", "")}」')
    if not parts:
        return ""
    return f'<div class="morpheme">构词：{" + ".join(parts)}</div>'


@register_field("phenomena")
def _render_phenomena(e: VocabularyEntry) -> str:
    if not e.phenomena:
        return ""
    tags = []
    for key, label in (("polysemy", "熟词生义"), ("slang", "俚语"),
                       ("collocations", "固定搭配"), ("domain_term", "学科术语")):
        if e.phenomena.get(key):
            tags.append(f'<span class="phen-tag">{label}</span>')
    if not tags:
        return ""
    return '<div class="phenomena">' + "".join(tags) + "</div>"


@register_field("examples")
def _render_examples(e: VocabularyEntry) -> str:
    if not e.examples:
        return ""
    parts = []
    for ex in e.examples[:2]:
        parts.append(f'<div class="example"><span class="example-en">{_esc(ex.get("en", ""))}</span>'
                     f'<span class="example-zh">{_esc(ex.get("zh", ""))}</span></div>')
    return "".join(parts)


@register_field("collocations")
def _render_collocations(e: VocabularyEntry) -> str:
    if not e.collocations:
        return ""
    return '<div class="collocations">' + " · ".join(
        _esc(c) for c in e.collocations[:4]) + "</div>"


# L1 必填字段（完整性门——Oracle：headword/ipa/gloss/lemma；examples 降 L2）
L1_FIELDS = ["headword", "ipa", "gloss_bilingual", "lemma"]


def l1_missing_fields(e: VocabularyEntry) -> list:
    """L1 必填字段缺失清单（渲染前校验）。

    §3.116 P6 ⭐ examples 降为 L2：例句来自原书 contexts 或 LLM 补全，
    若两者皆空但释义完整 → 不拦截（好词条不因缺例句被丢弃）。
    """
    missing = []
    if not e.headword:
        missing.append("headword")
    if not e.ipa:
        missing.append("ipa")
    if not e.gloss_bilingual:
        missing.append("gloss_bilingual")
    return missing


def validate_l1_complete(e: VocabularyEntry) -> bool:
    """L1 完整性校验。"""
    return not l1_missing_fields(e)


def render_entry(field: str, e: VocabularyEntry) -> str:
    """渲染单个字段（未注册 → 抛错防静默丢失）。"""
    if field not in FIELD_RENDERERS:
        raise KeyError(f"字段渲染器未注册: {field}（可 register_field 扩展）")
    return FIELD_RENDERERS[field](e)
