# -*- coding: utf-8 -*-
"""paeg_vocabulary.core.context — 工作流上下文（VocabularyContext blackboard ⭐）。

借鉴 paeg-teaching-materials MaterialContext 模式——5 阶段中间产物传递。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .entry import CandidateWord, VocabularyEntry


@dataclass
class PageMeta:
    """页面元信息（污染处理用）。"""
    page_no: int = 0
    header: str = ""          # 页眉
    footer: str = ""          # 页脚/页码
    body: str = ""            # 正文


@dataclass
class TokenSpan:
    """清洗后词流中的词元。"""
    token: str = ""
    lemma: str = ""
    pos: str = ""
    page_no: int = 0
    context: str = ""         # 所在句/上下文


@dataclass
class VocabularyContext:
    """词汇表工作流共享上下文（blackboard）。"""

    # 输入
    pdf_path: Optional[Path] = None
    target_lang: str = "en"
    user_filter: Dict[str, Any] = field(default_factory=dict)  # 自定义筛选规则

    # 阶段 1: PDF 提取
    raw_corpus: str = ""
    pages_meta: List[PageMeta] = field(default_factory=list)

    # 阶段 2: 清洗去重
    clean_corpus: List[TokenSpan] = field(default_factory=list)
    clean_corpus_path: Optional[Path] = None
    # P7 ⭐ 专名统计：{lemma_lower: {"upper": n, "total": n}}——大写比例过滤专名
    capitalized_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # 阶段 3: 筛选
    candidates: List[CandidateWord] = field(default_factory=list)
    candidates_path: Optional[Path] = None

    # 阶段 4: 信息补全
    entries: List[VocabularyEntry] = field(default_factory=list)
    entries_path: Optional[Path] = None

    # 阶段 5: 渲染
    html_path: Optional[Path] = None
    pdf_path: Optional[Path] = None
    docx_path: Optional[Path] = None  # §3.116 ⭐ V-R3 Word 导出
    accessories: Dict[str, Path] = field(default_factory=dict)

    # 元数据
    completed_stages: Set[str] = field(default_factory=set)
    errors: List[str] = field(default_factory=list)

    def mark_completed(self, stage: str) -> None:
        self.completed_stages.add(stage)

    def is_completed(self, stage: str) -> bool:
        return stage in self.completed_stages
