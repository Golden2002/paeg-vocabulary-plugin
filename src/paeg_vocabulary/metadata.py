# -*- coding: utf-8 -*-
"""paeg_vocabulary.metadata — 书籍元数据 LLM 判定（§3.116 ⭐ 用户新方案）。

用户明确："不应该用书名提取文件路径提取，而应该直接用LLM给出这一份词汇表的标题，还有页脚"
"读者上传的其他作品的文件名、文件格式绝对与这一次不同，所以最好的方案就是根据标题页或者前几页的信息让LLM直接给"

实现：读 PDF 前 1-3 页文本 → LLM 判定书名/作者（结构化 JSON）。
优先级：用户提供 > LLM 判定 > 文件名兜底（LLM 不可用时）。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, Optional

# 元数据判定系统提示词（LLM 直接读标题页判定——不依赖文件名）
META_SYSTEM_PROMPT = """你是书籍元数据识别专家。根据提供的书籍开头若干页文本，识别这本书的【书名】和【作者】。

规则：
1. 书名：优先取标题页/扉页/版权页上的正式书名——标题页可能出现在任一页（第 1 页或更靠后，
   前面可能是出版社广告、系列页、目录、前言）；无标题页时从正文开篇/版权信息推断。
2. 作者：标题页/版权页的作者姓名；无则留空。
3. 书名/作者必须干净——不要含出版社、出版年份、ISBN、系列名、译者、文件来源、书名号外的副标题等。
4. 严禁直接输出文件名或目录文本——必须从文本中识别真正的书名与作者。
5. 只输出 JSON，不要其他文字：
{"book_title": "书名", "book_author": "作者"}"""


def _extract_first_pages(pdf_path: str, n_pages: int = 15) -> str:
    """提取 PDF 开头若干页文本（带页码标记——标题页可能在任意一页）。

    §3.116 ⭐ 用户反馈"3 页过于刚性"、"前 15 页"：不同书籍标题页位置不同
    （有的第 1 页就是标题页，有的前十几页是广告/系列页/目录/前言/献词页）。
    扫描前 15 页，每页取开头 300 字符（标题页文本通常靠前）——太长会稀释 LLM 注意力。
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        texts = []
        for i in range(min(n_pages, doc.page_count)):
            t = (doc[i].get_text() or "").strip()[:300]  # 每页取开头 300 字符
            if t:
                texts.append(f"【第 {i+1} 页】\n{t}")
        doc.close()
        return "\n\n".join(texts)[:6000]
    except Exception:
        pass
    try:
        from pypdf import PdfReader
        r = PdfReader(pdf_path)
        texts = []
        for i in range(min(n_pages, len(r.pages))):
            try:
                t = (r.pages[i].extract_text() or "").strip()[:300]
                if t:
                    texts.append(f"【第 {i+1} 页】\n{t}")
            except Exception:
                pass
        return "\n\n".join(texts)[:6000]
    except Exception:
        return ""


def extract_book_meta_llm(pdf_path: str,
                          chat_fn: Optional[Callable] = None,
                          user_filter: Optional[Dict[str, Any]] = None) -> tuple:
    """用 LLM 判定书名/作者（§3.116 ⭐ 用户方案——不依赖文件名）。

    优先级：用户提供 > LLM 判定（读前几页）> 文件名兜底。
    Returns: (book_title, book_author)
    """
    uf = user_filter or {}

    # 1. 用户显式提供（最高优先级）
    if uf.get("book_title"):
        return (str(uf["book_title"]), str(uf.get("book_author", "")))

    # 2. LLM 判定（读前几页）
    if chat_fn is not None:
        _first_pages = _extract_first_pages(pdf_path, 15)
        if _first_pages.strip():
            _usr = (f"以下是《书籍》开头若干页文本（标题页可能在任意一页，请自行定位）。"
                    f"注意：文件名不可靠，完全以文本内容为准：\n\n{_first_pages}")
            # §3.116 ⭐ 多轮重试（LLM 偶发输出文件名——失败重试 2 次）
            for _attempt in range(3):
                try:
                    _raw = chat_fn(META_SYSTEM_PROMPT, _usr)
                    if isinstance(_raw, str) and _raw.strip():
                        _m = re.search(r"\{.*\}", _raw, re.S)
                        if _m:
                            _d = json.loads(_m.group(0))
                            _t = str(_d.get("book_title", "")).strip()
                            _a = str(_d.get("book_author", "")).strip()
                            # 校验：书名不像文件名（不含下划线连串/Archive/libgen/年份）
                            if _t and len(_t) <= 80 and not _looks_like_filename(_t):
                                return (_t, _a)
                except Exception:
                    pass
            # 重试耗尽：再次尝试但放宽校验（保底返回）
            try:
                _raw = chat_fn(META_SYSTEM_PROMPT, _usr)
                if isinstance(_raw, str) and _raw.strip():
                    _m = re.search(r"\{.*\}", _raw, re.S)
                    if _m:
                        _d = json.loads(_m.group(0))
                        _t = str(_d.get("book_title", "")).strip()
                        _a = str(_d.get("book_author", "")).strip()
                        if _t and len(_t) <= 120:
                            return (_t, _a)
            except Exception:
                pass

    # 3. 文件名兜底（LLM 不可用）
    return _extract_book_meta_fallback(pdf_path)


def _looks_like_filename(title: str) -> bool:
    """书名像文件名（LLM 误输出文件名时的启发式拦截）。"""
    t = title.strip()
    if not t:
        return True
    # 含安娜档案/libgen 标记
    low = t.lower()
    if "archive" in low or "libgen" in low or "anna" in low:
        return True
    # 连续下划线 / 连续双横线（文件名特征）
    if "__" in t or " -- " in t or re.search(r"[_-]{2,}", t):
        return True
    # 含 (年, 出版社) 或 ISBN
    if re.search(r"\(\d{4},", t) or re.search(r"\bISBN\b", t, re.I):
        return True
    return False


def _extract_book_meta_fallback(pdf_path: str) -> tuple:
    """文件名兜底提取（仅 LLM 不可用时）——尽力剥离扩展名。"""
    name = os.path.basename(pdf_path)
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    # 剥离常见来源后缀（Anna's Archive / libgen 等）
    name = re.sub(r"\s*[-_]\s*(Anna'?s Archive|libgen\.[a-z]+|Anna's Archive)$", "", name, flags=re.I)
    return (name.strip(), "")


# 兼容旧引用（registry 已用 _extract_book_meta）
extract_book_meta = extract_book_meta_llm
