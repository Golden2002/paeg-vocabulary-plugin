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
        from .pipeline import ingest_pdf, clean_corpus, enrich_entries, render_html
        from .accessories import generate_all_accessories

        uf = user_filter or {}
        ctx = VocabularyContext(
            pdf_path=pdf_path,
            target_lang=lang,
            user_filter=uf,
        )

        # P3/P4 ⭐ 解析用户水平 → 统一分位 U（考试/自述 → U 分位）
        u_level = None
        try:
            from .quantile_engine import user_level_to_u
            u_level = user_level_to_u(
                vocab_size=float(uf.get("vocab_size") or 0),
                exam=uf.get("exam", ""), score=float(uf.get("score") or 0),
                preset=uf.get("preset", ""))
        except Exception:
            pass

        # 学科术语辞典（按书学科——用户可指定 domains）
        domains = uf.get("domains") or _guess_domains(pdf_path)

        # 阶段1-5（P4 分位筛选）
        ctx = ingest_pdf(ctx, pdf_path)
        ctx = clean_corpus(ctx)
        # P4 ⭐ 统一分位筛选：Q ≥ U OR is_important（替代旧 zipf/CEFR 双轨）
        try:
            from .quantile_filter import quantile_filter_candidates
            ctx = quantile_filter_candidates(
                ctx, u_level=u_level,
                max_entries=int(uf.get("max_entries") or 2500))
        except Exception:
            # 兜底：旧筛选（保证可用）
            from .pipeline.filter import filter_candidates
            ctx = filter_candidates(ctx, filter_mode=uf.get("filter_mode", "learn"))

        # §3.116 ⭐ 提取书元数据（书名/作者）——用 LLM 读前几页判定（用户方案，
        # 不依赖文件名——文件名格式随上传作品而异无法泛化）
        _chat_for_meta = chat_fn or (cls.llm if cls.llm is not DEFAULT_LLM else None)
        from .metadata import extract_book_meta_llm
        book_title, book_author = extract_book_meta_llm(
            pdf_path, chat_fn=_chat_for_meta, user_filter=uf)

        # P5 ⭐ enrich：wordbank 离线优先 + batch_llm 批量补全 + collocations
        ctx = enrich_entries(ctx,
                             chat_fn=chat_fn or (cls.llm if cls.llm is not DEFAULT_LLM else None),
                             book_title=book_title, book_author=book_author,
                             domains=domains)
        # P6 ⭐ 渲染（FIELD_RENDERERS + L1 门）
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
            "cefr_max": "C2",
            "u_level": u_level,
        }


def _guess_domains(pdf_path: str) -> list:
    """按书名/文件名猜测学科领域（用于学科辞典加载）。"""
    import re
    name = os.path.basename(str(pdf_path)).lower()
    rules = [
        (r"phenomen|husserl|heidegger|merleau|jonas|existential|conscious", ["philosophy", "phenomenology"]),
        (r"bell jar|plath|novel|fiction|poetry|literature", ["philosophy"]),
        (r"biolog|life|cell|gene|organism|molecular", ["biology", "biochemistry", "genetics"]),
        (r"physic|quantum|mechanics|thermo|relativit", ["physics"]),
        (r"chem|molecule|acid|reaction", ["chemistry"]),
    ]
    for pattern, domains in rules:
        if re.search(pattern, name):
            return domains
    return ["philosophy", "biology", "physics", "chemistry"]


# 便捷别名（统一入口在 executor.execute——MCP 契约）
generate_vocabulary = VocabularyRegistry.generate_vocabulary


def _extract_book_meta(pdf_path: str, user_filter: Dict[str, Any]) -> tuple:
    """从 PDF 文件名/用户输入提取书名与作者（§3.116 ⭐ 本书含义义项）。

    优先级：用户提供（book_title/book_author）> 文件名解析。
    支持安娜档案（Anna's Archive）命名："[系列] 作者, 作者 - 书名 -- 作者 -- 年份 -- ... -- Anna's Archive.pdf"
    以及常见 "作者 - 书名.pdf" / "书名 -- 作者.pdf"。
    """
    # 1. 用户显式提供
    if user_filter.get("book_title"):
        return (str(user_filter["book_title"]),
                str(user_filter.get("book_author", "")))
    # 2. 文件名解析
    import re
    name = os.path.basename(pdf_path)
    name = re.sub(r"\.pdf$", "", name, flags=re.I)

    # 2.1 安娜档案格式：... -- Title -- Author -- ... -- Anna's Archive
    #     生命现象："The phenomenon of life- toward a philosophical biology -- Jonas..." 书名在首个 " -- " 前
    #     钟形罩："Plath, Sylvia McCann, Janet - The bell jar, by Sylvia Plath (2012, Salem Press) - libgen.li"
    #             书名是单横线后的 "The bell jar"（年份括号前的部分）
    # 策略 A：首个 " -- " 前若含 "- " 形如 "xxx- title" 则取 title 部分
    parts = re.split(r"\s*--\s*", name)
    if len(parts) >= 2:
        _head = parts[0]
        # 生命现象式："The phenomenon of life- toward a philosophical biology"
        m = re.search(r"-\s*([A-Z][A-Za-z0-9'& ]{2,60})$", _head)
        if m:
            return (m.group(1).strip(), "")
        # 若首段是纯作者/系列（无 "- "），取第二个 " -- " 段（跳过作者/年份）
        if len(parts) >= 3 and not re.search(r"\d{4}", parts[1]):
            return (parts[1].strip(), "")
    # 策略 B：钟形罩式 "[系列] 作者, 作者 - 书名, 副题 (年份, 出版社) - 来源"
    #     年份括号 "(2012," 是书名结束锚点——取它之前最后一个 "- " 之后的部分
    clean2 = re.sub(r"^\[[^\]]*\]\s*", "", name)
    _yr = re.search(r"\((\d{4})[,)]", clean2)
    if _yr:
        _pre = clean2[:_yr.start()]
        m = re.search(r"[-_]\s*([A-Z][A-Za-z0-9'&, ]{2,80})$", _pre)
        if m:
            _t = m.group(1).strip()
            if len(_t) < 60:
                return (_t, "")
    # 策略 C：剥离方括号系列前缀后通用解析
    clean = clean2
    m = re.search(r"-\s*([A-Z][A-Za-z0-9' ]{2,60})$", clean)
    if m:
        _t = m.group(1).strip()
        if _t.lower() not in ("archive", "anna s archive"):
            return (_t, "")
    m = re.match(r"^([^_\-]+)[_\-]+([^_\-]+)$", clean)
    if m:
        a, t = m.group(1).strip(), m.group(2).strip()
        return (t, a)
    return (clean, "")
