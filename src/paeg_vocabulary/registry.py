# -*- coding: utf-8 -*-
"""paeg_vocabulary.registry — 词汇表插件注册表（§3.116 ⭐ 生态可扩展）。

镜像 paeg-teaching-materials MaterialRegistry 模式：
- inject：宿主依赖注入（LLM/chat_fn）
- register：生成器/补全器/附件注册（可扩展）
- execute：统一执行入口
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional

from .protocols import DEFAULT_LLM, DEFAULT_READER, LLMCallable, PDFReader


class VocabularyRegistry:
    """词汇表插件注册表（类级全局单例）。"""

    # 宿主依赖
    llm: LLMCallable = DEFAULT_LLM
    reader: PDFReader = DEFAULT_READER

    # 可扩展注册表
    _generators: Dict[str, Callable] = {}      # 生成器（词汇表/附件）
    _enrichers: Dict[str, Callable] = {}       # 补全器（按字段）
    _languages: set = {"en", "de", "fr", "es"}  # 支持语种（可扩展）

    @classmethod
    def inject(cls, *, llm: Optional[LLMCallable] = None,
               reader: Optional[PDFReader] = None) -> None:
        """注入宿主实现（外部智能体接入点）。"""
        if llm is not None:
            cls.llm = llm
        if reader is not None:
            cls.reader = reader

    @classmethod
    def reset(cls) -> None:
        cls.llm = DEFAULT_LLM
        cls.reader = DEFAULT_READER

    @classmethod
    def register_generator(cls, name: str, fn: Callable) -> bool:
        """注册生成器（词汇表/附件——可扩展 ⭐）。"""
        cls._generators[name] = fn
        return True

    @classmethod
    def register_defaults(cls) -> None:
        """注册默认生成器（词汇表主流程——import 即注册）。"""
        cls._generators.setdefault("generate_vocabulary",
                                    VocabularyRegistry.generate_vocabulary)
        # 附件生成器（可扩展）
        try:
            from .accessories import generate_all_accessories
            cls._generators.setdefault("generate_accessories", generate_all_accessories)
        except Exception:
            pass

    @classmethod
    def register_language(cls, lang: str) -> bool:
        """注册新语种（生态扩展 ⭐）。"""
        cls._languages.add(lang)
        return True

    @classmethod
    def languages(cls) -> list:
        return sorted(cls._languages)

    @classmethod
    def available_generators(cls) -> list:
        return sorted(cls._generators.keys())

    @classmethod
    def generate_vocabulary(cls, pdf_path: str, lang: str = "en",
                            user_filter: Optional[Dict[str, Any]] = None,
                            chat_fn: Optional[Callable] = None) -> Dict[str, Any]:
        """主入口：PDF → 词汇表（全流程工作流引擎 ⭐）。

        5 阶段：ingest → clean → filter → enrich → render + accessories。
        §3.116 ⭐ user_filter 支持水平档位：
          {"exam": "kaoyan", "score": 70} 或 {"preset": "kaoyan-70"} → CEFR 阈值过滤
        """
        from .core.context import VocabularyContext
        from .pipeline import ingest_pdf, clean_corpus, filter_candidates, enrich_entries, render_html
        from .accessories import generate_all_accessories

        uf = user_filter or {}
        ctx = VocabularyContext(
            pdf_path=pdf_path,
            target_lang=lang,
            user_filter=uf,
        )

        # §3.116 ⭐ 解析水平档位 → 筛选阈值（CEFR + zipf 双轨）
        cefr_max = None
        zipf_thr = None
        try:
            from .level_matrix import select_cefr_max, resolve_preset
            from .pipeline.filter import zipf_threshold_for
            if uf.get("preset"):
                p = resolve_preset(uf["preset"])
                cefr_max = p.get("cefr_max")
                zipf_thr = zipf_threshold_for(p.get("exam", ""), float(p.get("score", 0)))
            elif uf.get("exam"):
                score = float(uf.get("score", 0))
                cefr_max = select_cefr_max(uf["exam"], score)
                zipf_thr = zipf_threshold_for(uf["exam"], score)
        except Exception:
            pass

        # 阶段1-5
        ctx = ingest_pdf(ctx, pdf_path)
        ctx = clean_corpus(ctx)
        # §3.116 ⭐ filter：zipf 阈值筛选需学习生词（量化标准——雅思 7.5 ≈ 2200 词）
        ctx = filter_candidates(ctx, cefr_max=cefr_max, zipf_threshold=zipf_thr,
                                filter_mode=uf.get("filter_mode", "learn"))

        # §3.116 ⭐ 提取书元数据（书名/作者）——用于"本书含义"义项标注
        book_title, book_author = _extract_book_meta(pdf_path, uf)

        ctx = enrich_entries(ctx, chat_fn=chat_fn or (cls.llm if cls.llm is not DEFAULT_LLM else None),
                             book_title=book_title, book_author=book_author)
        ctx = render_html(ctx, book_title=book_title, book_author=book_author)

        # 附件
        try:
            acc = generate_all_accessories(ctx)
            ctx.accessories = acc
        except Exception as e:
            ctx.errors.append(f"附件生成失败: {str(e)[:100]}")

        return {
            "ok": len(ctx.errors) == 0,
            "errors": ctx.errors,
            "html_path": str(ctx.html_path) if ctx.html_path else "",
            "pdf_path": str(ctx.pdf_path) if ctx.pdf_path else "",
            "accessories": {k: str(v) for k, v in ctx.accessories.items()},
            "entries_count": len(ctx.entries),
            "candidates_count": len(ctx.candidates),
            "completed_stages": sorted(ctx.completed_stages),
            "cefr_max": cefr_max or "C2",
        }


# 便捷别名（统一入口在 executor.execute——MCP 契约）
generate_vocabulary = VocabularyRegistry.generate_vocabulary


def _extract_book_meta(pdf_path: str, user_filter: Dict[str, Any]) -> tuple:
    """从 PDF 文件名/用户输入提取书名与作者（§3.116 ⭐ 本书含义义项）。

    优先级：用户提供（book_title/book_author）> 文件名解析。
    """
    # 1. 用户显式提供
    if user_filter.get("book_title"):
        return (str(user_filter["book_title"]),
                str(user_filter.get("book_author", "")))
    # 2. 文件名解析（"作者名_书名.pdf" 或 "书名 -- 作者" 模式）
    import re
    name = os.path.basename(pdf_path)
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    # 模式: "Author - Title" / "Title -- Author" / "Author_Title"
    m = re.match(r"^([^_\-]+)[_\-]+([^_\-]+)$", name)
    if m:
        a, t = m.group(1).strip(), m.group(2).strip()
        # 启发式：含大写词组更像书名
        return (t, a)
    return (name, "")
