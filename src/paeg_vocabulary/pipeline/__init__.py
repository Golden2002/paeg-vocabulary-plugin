# -*- coding: utf-8 -*-
"""paeg_vocabulary.pipeline — 5 模块全流程工作流引擎（§3.116 模块1 ⭐）。

流程：PDF 提取 → 清洗去重 → 筛选 → 信息补全 → 渲染。
每阶段中间产物落盘（断点续跑 + 可检查）。

输入：用户上传 PDF + 目标语言 + 单词筛选规则
输出：词汇表 HTML/PDF + 4 附件（价值说明/词频报告/风格分析）
"""

from __future__ import annotations

from .pdf_ingest import ingest_pdf
from .clean_dedup import clean_corpus
from .filter import filter_candidates
from .enrich import enrich_entries
from .render_html import render_html

__all__ = ["ingest_pdf", "clean_corpus", "filter_candidates",
           "enrich_entries", "render_html"]
