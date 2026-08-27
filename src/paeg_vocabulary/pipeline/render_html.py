# -*- coding: utf-8 -*-
"""paeg_vocabulary.pipeline.render_html — 阶段5：渲染（§3.116 模块3 ⭐ 强约束）。

完整复用「英语学习」文件夹的 Bell Jar 精美 CSS 模板（禁止简化版）：
- 模板来源：D:\\团聚体\\桌面\\英语教学\\我的学习\\渲染资产\\
  - 模板_钟形罩_原版.html（B5/封面/章节头/词条布局）
  - 模板_生命现象_原版.html
  - render_vocab.py（渲染脚本）
  - render_html_to_pdf.py（HTML → PDF）

产出：HTML + PDF（Chrome 渲染）。
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import List, Optional

from ..core.context import VocabularyContext
from ..core.entry import VocabularyEntry

# Bell Jar 模板资产（从英语学习文件夹复制）
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates"


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_entry_html(entry: VocabularyEntry) -> str:
    """生成单个词条 HTML（对齐 Bell Jar 模板 .entry/.headword 结构）。"""
    head = _esc(entry.headword)
    ipa = ""
    if entry.ipa:
        ipa = ' <span class="ipa">' + _esc(" / ".join(entry.ipa.values())) + "</span>"
    pos = f' <span class="pos">{_esc(entry.pos)}</span>' if entry.pos else ""
    zh = _esc(entry.gloss_bilingual.get("zh", "")) if entry.gloss_bilingual else ""
    en = _esc(entry.gloss_bilingual.get("en", "")) if entry.gloss_bilingual else ""

    senses_html = ""
    if entry.senses:
        for s in entry.senses:
            # §3.116 ⭐ book_sense 带"本书含义"标注（如"在本书中，约纳斯的意思是…"）
            ctx_html = f'<span class="book-context">{_esc(s.book_context)}</span>' if s.book_context else ""
            senses_html += (
                f'<div class="sense">'
                f'<span class="sense-zh">{_esc(s.gloss_zh)}</span>'
                f'<span class="sense-en">{_esc(s.gloss_en)}</span>{ctx_html}</div>'
            )

    etymology = f'<div class="etymology">{_esc(entry.etymology)}</div>' if entry.etymology else ""

    # §3.116 ⭐ morpheme 词根词缀行（对齐 Bell Jar 模板蓝色构词行）
    morpheme_html = ""
    if entry.morpheme:
        parts = []
        if entry.morpheme.prefix:
            p = entry.morpheme.prefix
            parts.append(f'{p.get("p","")}「{p.get("meaning","")}」')
        for r in entry.morpheme.roots:
            parts.append(f'{r.get("root","")}({r.get("lang","")}「{r.get("meaning","")}」)')
        if entry.morpheme.suffix:
            s = entry.morpheme.suffix
            parts.append(f'{s.get("s","")}「{s.get("meaning","")}」')
        if parts:
            morpheme_html = f'<div class="morpheme">构词：{" + ".join(parts)}</div>'

    examples_html = ""
    for ex in entry.examples[:2]:
        examples_html += (
            f'<div class="example"><span class="example-en">{_esc(ex.get("en", ""))}</span>'
            f'<span class="example-zh">{_esc(ex.get("zh", ""))}</span></div>'
        )

    coll = ""
    if entry.collocations:
        coll = '<div class="collocations">' + " · ".join(
            _esc(c) for c in entry.collocations[:4]) + "</div>"

    # §3.116 ⭐ 语言现象标注（熟词生义/俚语/固定搭配——学习价值信号）
    phen_html = ""
    if entry.phenomena:
        _tags = []
        for _k, _label in (("polysemy", "熟词生义"), ("slang", "俚语"),
                           ("collocations", "固定搭配")):
            if entry.phenomena.get(_k):
                _tags.append(f'<span class="phen-tag">{_label}</span>')
        if _tags:
            phen_html = '<div class="phenomena">' + "".join(_tags) + "</div>"

    return f"""<div class="entry">
  <div class="headword">{head}{ipa}{pos}</div>
  <div class="gloss"><span class="gloss-zh">{zh}</span><span class="gloss-en">{en}</span></div>
  {senses_html}
  {etymology}
  {morpheme_html}
  {phen_html}
  {examples_html}
  {coll}
</div>"""


def _find_template(book_key: str = "bell_jar") -> Optional[Path]:
    """选择模板（钟形罩/生命现象）。"""
    candidates = [
        _TEMPLATES_DIR / "模板_钟形罩_原版.html",
        _TEMPLATES_DIR / "模板_生命现象_原版.html",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def render_html(ctx: VocabularyContext,
                out_dir: Optional[str] = None,
                book_key: str = "bell_jar",
                book_title: str = "",
                book_author: str = "") -> VocabularyContext:
    """阶段 5：entries → HTML（Bell Jar 模板）+ PDF（Chrome）。

    out_dir: 输出目录（默认插件 output/）。
    §3.116 ⭐ book_title/book_author：正确标题（内容一致性——防文件名错位）。
    """
    if not ctx.entries:
        ctx.errors.append("无词条（阶段4未执行）")
        return ctx

    tpl = _find_template(book_key)
    if tpl is None:
        # 兜底：无模板时生成极简 HTML（标记——不满足强约束，但保证可运行）
        ctx.errors.append("Bell Jar 模板缺失——使用兜底极简渲染")
        html = _minimal_html(ctx.entries)
        ctx.html_path = _save_html(html, out_dir, ctx, book_title)
        ctx.mark_completed("render")
        return ctx

    # 读取模板，替换词条部分
    tpl_text = tpl.read_text(encoding="utf-8")
    # §3.116 P6 ⭐ 切换 FIELD_RENDERERS 驱动 + L1 完整性门（过滤不完整词条）
    from ..render.entry_html import entries_to_html
    entries_html = entries_to_html(ctx.entries)

    # 模板含词条占位符（{{ENTRIES}} / div.entries / main.entries——Bell Jar 模板用 main）
    if "{{ENTRIES}}" in tpl_text:
        html = tpl_text.replace("{{ENTRIES}}", entries_html)
    else:
        # Bell Jar 模板：<main class="entries"><h2 class="alpha-header">A</h2><article class="entry">...</article>...</main>
        # 替换策略：找到 entries 容器开标签 → 清空容器内示例词条 → 注入新词条
        m = re.search(r'(<(?:main|div)\s+class="entries"[^>]*>)', tpl_text)
        if m:
            open_tag = m.group(1)
            # 清空容器内全部内容（示例词条）——从开标签后到容器结束
            container_end = re.search(r"</(?:main|div)>\s*</body>", tpl_text)
            if container_end:
                tail = tpl_text[container_end.start():]
                html = tpl_text[:m.end()] + "\n" + entries_html + "\n" + tail
            else:
                html = re.sub(r'(<(?:main|div)\s+class="entries"[^>]*>)[\s\S]*?(</(?:main|div)>)',
                              lambda mm: mm.group(1) + entries_html + mm.group(2),
                              tpl_text, count=1)
        else:
            # 模板无词条区——在 </body> 前插入
            html = tpl_text.replace("</body>", f'<div class="entries">{entries_html}</div></body>')

    # 标题替换（§3.116 ⭐ 内容一致性：优先 book_title，防文件名错位）
    title = book_title or "词汇表"
    if book_author:
        title = f"{title}（{book_author}）"
    html = html.replace("{{DOC_TITLE}}", _esc(title))
    # 也替换封面 h1（若模板用书名占位）
    html = re.sub(r"<h1[^>]*>.*?</h1>", f"<h1>{_esc(title)}</h1>", html, count=1)

    ctx.html_path = _save_html(html, out_dir, ctx, book_title)

    # PDF 渲染（Chrome）
    ctx.pdf_path = _render_pdf(ctx.html_path, out_dir, ctx)
    ctx.mark_completed("render")
    return ctx


def _save_html(html: str, out_dir: Optional[str], ctx: VocabularyContext,
               book_title: str = "") -> Path:
    out = Path(out_dir or _default_out_dir())
    out.mkdir(parents=True, exist_ok=True)
    stem = book_title or "vocabulary"
    if not stem or stem == "词汇表":
        stem = "vocabulary"
    # §3.116 ⭐ 档位后缀（区分不同水平档位输出）
    level = ""
    uf = getattr(ctx, "user_filter", None) or {}
    if uf.get("exam") and uf.get("score"):
        level = f"_{uf['exam']}{uf['score']}"
    name = stem + level + "_词汇表.html"
    p = out / name
    p.write_text(html, encoding="utf-8")
    return p


def _render_pdf(html_path: Path, out_dir: Optional[str], ctx: VocabularyContext) -> Optional[Path]:
    """用 Chrome 渲染 HTML → PDF。"""
    chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not os.path.isfile(chrome):
        return None
    pdf_path = html_path.with_suffix(".pdf")
    try:
        import subprocess
        cmd = [chrome, "--headless", "--disable-gpu",
               "--print-to-pdf=" + str(pdf_path),
               "file:///" + str(html_path).replace("\\", "/")]
        subprocess.run(cmd, capture_output=True, timeout=120)
        return pdf_path if pdf_path.exists() else None
    except Exception:
        return None


def _minimal_html(entries: List[VocabularyEntry]) -> str:
    """兜底极简 HTML（模板缺失时）。"""
    body = "\n".join(_build_entry_html(e) for e in entries)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>词汇表（兜底渲染）</title>
<style>body{{font-family:serif;max-width:800px;margin:auto;padding:2em}}
.entry{{margin-bottom:1.5em;page-break-inside:avoid}}
.headword{{font-size:1.2em;font-weight:bold}}</style></head>
<body><h1>词汇表</h1>{body}</body></html>"""


def _default_out_dir() -> Path:
    # 插件根 = src/.. 的上级 = paeg-vocabulary-plugin/output
    return Path(__file__).resolve().parent.parent.parent.parent / "output"
