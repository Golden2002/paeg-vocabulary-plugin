# -*- coding: utf-8 -*-
"""paeg_vocabulary.pipeline.pdf_ingest — 阶段1：PDF 提取（§3.116 ⭐）。

复用 PAEG lib/ingest/readers 的 pypdf 提取（若宿主可用）；
独立运行时用 pypdf/pdfplumber 兜底。
产出：raw_corpus（全书文本）+ pages_meta（页眉页脚坐标）。
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Set, Tuple

from ..core.context import PageMeta, VocabularyContext


# ═══════════════════════════════════════════════════════════
# 页眉页脚剥离（Oracle 方案：三信号取交集——坐标带 + 跨页重复 + 页码正则）
# ═══════════════════════════════════════════════════════════
_PAGE_NUM_RE = re.compile(
    r"^\s*(?:\d{1,4}|[ivxlcdmIVXLCDM]{1,8})\s*$"              # 纯数字 / 罗马数字
    r"|^\s*\d{1,4}\s*/\s*\d{1,4}\s*$"                          # 42 / 120
    r"|^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$"                      # -42-
    r"|^\s*page\s+\d{1,4}\s*$", re.IGNORECASE                 # Page 7
)


def _is_page_number(text: str) -> bool:
    """判断文本是否页码（纯数字/罗马数字/页码形式）。"""
    s = (text or "").strip()
    if not s:
        return False
    return bool(_PAGE_NUM_RE.match(s))


def _normalize_for_dup(text: str) -> str:
    """归一化用于重复检测（数字替换为 #，折叠空白）。"""
    return re.sub(r"\d+", "#", (text or "").lower()).strip()


def _strip_headers_footers(
    pages_meta: List[PageMeta],
) -> Tuple[List[Tuple[int, PageMeta]], Set[str]]:
    """跨页重复行检测：剥离页眉页脚。

    pages_meta 已含坐标带粗分（header/footer/body）。
    跨页重复检测：页眉/页脚中，归一化后出现 ≥ max(3, ceil(0.5*N)) 页的行 → 剥离。
    页码正则命中的 footer 直接剥离。

    返回：(清理后的 [(idx, PageMeta)], 被剥离字符串集合)
    """
    n = len(pages_meta)
    if n == 0:
        return [], set()

    # 1. 统计每页页眉/页脚的整块归一化文本 → 出现页数
    from collections import Counter
    header_occ: Counter = Counter()
    footer_occ: Counter = Counter()
    for m in pages_meta:
        if (m.header or "").strip():
            header_occ[_normalize_for_dup(m.header)] += 1
        if (m.footer or "").strip():
            footer_occ[_normalize_for_dup(m.footer)] += 1

    threshold = max(3, (n + 1) // 2)  # ≥ 半数页
    dropped: Set[str] = set()

    # 2. 逐页清理
    cleaned: List[Tuple[int, PageMeta]] = []
    for idx, m in enumerate(pages_meta):
        header = (m.header or "").strip()
        footer = (m.footer or "").strip()

        # 页眉：跨页重复 或 页码 → 剥离
        if header and (_is_page_number(header)
                       or header_occ.get(_normalize_for_dup(header), 0) >= threshold):
            dropped.add(header)
            header = ""
        # 页脚：页码 或 跨页重复 → 剥离
        if footer and (_is_page_number(footer)
                       or footer_occ.get(_normalize_for_dup(footer), 0) >= threshold):
            dropped.add(footer)
            footer = ""

        cleaned.append((idx, PageMeta(
            page_no=m.page_no, header=header, footer=footer, body=m.body,
        )))
    return cleaned, dropped


def _strip_repeated_lines(text: str) -> str:
    """纯文本兜底（pypdf/PAEG 无坐标路径）：按行重复率 + 页码模式剥离。"""
    if not text:
        return text
    lines = text.splitlines()
    n = len(lines)
    if n < 3:
        return text

    # 统计归一化行频次（只统计"疑似边缘行"——首尾 2 行的位置不重要，纯文本无坐标，
    # 故按全局重复 + 页码判定，保守起见仅剥除页码 + 全局高频短行）
    from collections import Counter
    norm_counter: Counter = Counter()
    for l in lines:
        s = l.strip()
        if s and len(s) <= 60:
            norm_counter[_normalize_for_dup(s)] += 1

    threshold = 3  # 固定下限：页眉页脚在每页出现，页数通常 ≥3
    kept = []
    for l in lines:
        s = l.strip()
        if not s:
            kept.append(l)
            continue
        if _is_page_number(s):
            continue  # 页码剥离
        if len(s) <= 60 and norm_counter.get(_normalize_for_dup(s), 0) >= threshold:
            continue  # 高频重复行（书名 running head）剥离
        kept.append(l)
    return "\n".join(kept)


def _try_paeg_reader(pdf_path: str) -> Optional[str]:
    """尝试复用 PAEG lib/ingest/readers（宿主可用时）。"""
    try:
        from lib.ingest.readers import _read_pdf_full
        return _read_pdf_full(pdf_path)
    except Exception:
        return None


def _try_pypdf(pdf_path: str) -> Optional[str]:
    """pypdf 兜底提取。"""
    try:
        from pypdf import PdfReader
        r = PdfReader(pdf_path)
        pages = []
        for i, page in enumerate(r.pages):
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
        return "\n\n".join(pages)
    except Exception:
        return None


def _try_pymupdf(pdf_path: str) -> Optional[dict]:
    """PyMuPDF 提取（含坐标——页眉页脚裁剪用）。"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        pages_meta = []
        full_texts = []
        for i, page in enumerate(doc):
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)
            # 分类：页眉（顶部 8%）、页脚（底部 8%）、正文
            h = page.rect.height
            header_blocks, footer_blocks, body_blocks = [], [], []
            for b in blocks.get("blocks", []):
                if "lines" not in b:
                    continue
                bbox = b.get("bbox", [0, 0, 0, 0])
                y0 = bbox[1]
                text = "".join(
                    span.get("text", "")
                    for line in b.get("lines", [])
                    for span in line.get("spans", [])
                ).strip()
                if not text:
                    continue
                if y0 < h * 0.08:
                    header_blocks.append(text)
                elif y0 > h * 0.92:
                    footer_blocks.append(text)
                else:
                    body_blocks.append(text)
            pages_meta.append(PageMeta(
                page_no=i + 1,
                header=" ".join(header_blocks),
                footer=" ".join(footer_blocks),
                body="\n".join(body_blocks),
            ))
        doc.close()
        # §3.116 ⭐ 页眉页脚剥离（Oracle 三信号）：跨页重复 + 页码正则
        cleaned, _dropped = _strip_headers_footers(pages_meta)
        cleaned.sort(key=lambda x: x[0])
        final_meta = [m for _, m in cleaned]
        full_texts = [m.body for m in final_meta]
        return {"text": "\n\n".join(full_texts), "pages_meta": final_meta}
    except Exception:
        return None


def ingest_pdf(ctx: VocabularyContext, pdf_path: str) -> VocabularyContext:
    """阶段 1：PDF → raw_corpus + pages_meta。

    优先级：PyMuPDF（坐标）→ PAEG readers → pypdf。
    """
    if not pdf_path or not os.path.isfile(pdf_path):
        ctx.errors.append(f"PDF 不存在: {pdf_path}")
        return ctx

    # 1. PyMuPDF（含坐标，首选）
    pm = _try_pymupdf(pdf_path)
    # §3.116 ⭐ 缺陷2修复：判文本非空（空文本 dict 也 truthy，此前不降级致 raw_corpus 空）
    if pm and str(pm.get("text", "")).strip():
        ctx.raw_corpus = pm["text"]
        ctx.pages_meta = pm["pages_meta"]
        ctx.mark_completed("pdf_ingest")
        return ctx

    # 2. PAEG readers
    paeg = _try_paeg_reader(pdf_path)
    if paeg and str(paeg).strip():
        # 纯文本兜底：页眉页脚重复行剥离
        ctx.raw_corpus = _strip_repeated_lines(str(paeg))
        ctx.mark_completed("pdf_ingest")
        return ctx

    # 3. pypdf
    pypdf_text = _try_pypdf(pdf_path)
    if pypdf_text and str(pypdf_text).strip():
        ctx.raw_corpus = _strip_repeated_lines(str(pypdf_text))
        ctx.mark_completed("pdf_ingest")
        return ctx

    ctx.errors.append("PDF 提取失败（PyMuPDF/PAEG/pypdf 均不可用）")
    return ctx
