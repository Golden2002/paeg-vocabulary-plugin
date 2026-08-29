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


def _nl2br(s) -> str:
    """真实换行 → <br>（ecdict 释义清洗后为多行，渲染时逐行展示）。"""
    return str(s).replace("\n", "<br>")


# CEFR 等级徽章配色（与 make_high_freq_html 保持一致）
_CEFR_COLORS = {"A1": "#10b981", "A2": "#22c55e", "B1": "#eab308",
                "B2": "#f97316", "C1": "#ef4444", "C2": "#7c3aed"}

# 口音键 → 友好中文标签（en_us=美 / en_uk=英 / de=德 / fr=法 / es=西）
_ACCENT_LABELS = {"en_us": "美", "en_uk": "英", "de": "德", "fr": "法", "es": "西", "zh": "汉"}


@register_field("headword")
def _render_headword(e: VocabularyEntry) -> str:
    head = _esc(e.headword)
    pos = f'<span class="pos">{_esc(e.pos)}</span>' if e.pos else ""
    badges = ""
    cefr = (e.cefr_level or "").strip().upper()
    if cefr in _CEFR_COLORS:
        badges += f'<span class="badge-cefr" style="background:{_CEFR_COLORS[cefr]}">{cefr}</span>'
    if getattr(e, "freq_rank", 0) and int(e.freq_rank) > 0:
        badges += (f'<span class="badge-freq" title="本书出现 {e.freq_rank} 次">'
                   f'×{e.freq_rank}</span>')
    return f'<div class="headword"><span class="word">{head}</span>{pos}{badges}</div>'


@register_field("ipa")
def _render_ipa(e: VocabularyEntry) -> str:
    if not e.ipa:
        return ""
    ipa = e.ipa
    if isinstance(ipa, str):
        # §修复：LLM 偶发把 ipa 返回为字符串——兜底单口音展示
        ipa = {"en_us": ipa}
    parts = []
    for k, v in ipa.items():
        label = _ACCENT_LABELS.get(k, k)
        parts.append(f'<span class="ipa-accent">{label}</span> <span class="ipa-val">{_esc(v)}</span>')
    return '<div class="ipa-row">' + "　".join(parts) + "</div>"


@register_field("gloss")
def _render_gloss(e: VocabularyEntry) -> str:
    if not e.gloss_bilingual:
        return ""
    g = e.gloss_bilingual
    if isinstance(g, str):
        # §修复：审查 LLM 偶发把整段释义当字符串——兜底为中文释义
        zh, en = g, ""
    else:
        zh, en = g.get("zh", ""), g.get("en", "")
    zh = _nl2br(_esc(zh))
    en = _nl2br(_esc(en))
    parts = []
    if zh:
        parts.append(f'<span class="gloss-zh">{zh}</span>')
    if en:
        parts.append(f'<span class="gloss-en">{en}</span>')
    if not parts:
        return ""
    return '<div class="gloss">' + "".join(parts) + "</div>"


@register_field("senses")
def _render_senses(e: VocabularyEntry) -> str:
    if not e.senses:
        return ""
    parts = []
    for s in e.senses:
        ctx = (f'<span class="book-context">{_esc(s.book_context)}</span>'
               if s.book_context else "")
        parts.append(f'<div class="sense"><span class="sense-zh">{_nl2br(_esc(s.gloss_zh))}</span>'
                     f'<span class="sense-en">{_nl2br(_esc(s.gloss_en))}</span>{ctx}</div>')
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

    def _affix(item, key):
        """词缀段：只渲染非空内容，避免出现空「」。"""
        if isinstance(item, dict):
            seg = str(item.get(key, "")).strip()
            mean = str(item.get("meaning", "")).strip()
        else:
            seg = str(item or "").strip()
            mean = ""
        if not seg and not mean:
            return ""
        if seg and mean:
            return f'{seg}「{mean}」'
        return seg or f'「{mean}」'

    parts = []
    pre = e.morpheme.prefix
    if isinstance(pre, list):
        for item in pre:
            seg = _affix(item, "p")
            if seg:
                parts.append(seg)
    elif pre:
        seg = _affix(pre, "p")
        if seg:
            parts.append(seg)

    for r in e.morpheme.roots or []:
        if isinstance(r, dict):
            root = str(r.get("root", "")).strip()
            lang = str(r.get("lang", "")).strip()
            mean = str(r.get("meaning", "")).strip()
            if not (root or lang or mean):
                continue
            seg = root
            if lang or mean:
                seg += "(" + lang + ("「" + mean + "」" if mean else "") + ")"
            parts.append(seg)
        elif r:
            parts.append(str(r).strip())

    suf = e.morpheme.suffix
    if isinstance(suf, list):
        for item in suf:
            seg = _affix(item, "s")
            if seg:
                parts.append(seg)
    elif suf:
        seg = _affix(suf, "s")
        if seg:
            parts.append(seg)

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
