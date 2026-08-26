# -*- coding: utf-8 -*-
"""paeg_vocabulary.pipeline.pdf_ingest — 阶段1：PDF 提取（§3.116 ⭐）。

复用 PAEG lib/ingest/readers 的 pypdf 提取（若宿主可用）；
独立运行时用 pypdf/pdfplumber 兜底。
产出：raw_corpus（全书文本）+ pages_meta（页眉页脚坐标）。
"""

from __future__ import annotations

import os
from typing import Optional

from ..core.context import PageMeta, VocabularyContext


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
            full_texts.append("\n".join(body_blocks))
        doc.close()
        return {"text": "\n\n".join(full_texts), "pages_meta": pages_meta}
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
    if pm:
        ctx.raw_corpus = pm["text"]
        ctx.pages_meta = pm["pages_meta"]
        ctx.mark_completed("pdf_ingest")
        return ctx

    # 2. PAEG readers
    paeg = _try_paeg_reader(pdf_path)
    if paeg:
        ctx.raw_corpus = paeg
        ctx.mark_completed("pdf_ingest")
        return ctx

    # 3. pypdf
    pypdf_text = _try_pypdf(pdf_path)
    if pypdf_text:
        ctx.raw_corpus = pypdf_text
        ctx.mark_completed("pdf_ingest")
        return ctx

    ctx.errors.append("PDF 提取失败（PyMuPDF/PAEG/pypdf 均不可用）")
    return ctx
