# -*- coding: utf-8 -*-
"""paeg_vocabulary.cleaners.example_sanitize — 例句污染清洗（§3.116 模块5）。

例句去污染 7 条规则（librarian 调研）：
1. 参考文献编号 [1] / (Author2020) 剔除
2. 上标脚注字符（¹ * †）剔除
3. 跨页断词 `-\n` 合并
4. 注释括号 (see page42) 剔除
5. 目录条目（连续点号行）剔除
6. 页码/孤立数字剔除
7. 页眉页脚关键词剔除（Chapter/Page 等）
"""

from __future__ import annotations

import re
from typing import List, Optional

# 参考文献编号： [1] / (Smith 2020) / [12]
_REF_PATTERN = re.compile(r"\s*[\[\(]\s*\d+\s*[\]\)]\s*|\s*[\[\(][A-Z][A-Za-z]+\s+\d{4}[\]\)]\s*")
# 上标脚注字符
_SUPERSCRIPT_PATTERN = re.compile(r"[\u00B9-\u00BF\u2070-\u209F†*]")
# 注释括号
_NOTE_PATTERN = re.compile(r"\s*\((?:see|cf\.|emphasis|trans\.|note)[^)]*\)\s*", re.I)
# 目录条目
_TOC_PATTERN = re.compile(r"^.*\.{3,}\s*\d+\s*$", re.M)
# 孤立页码/数字
_LONE_NUM_PATTERN = re.compile(r"^\s*\d{1,4}\s*$")
# 页眉页脚关键词
_HEADER_FOOTER_KW = re.compile(r"^\s*(chapter|part|page|contents|index)\b.*$", re.I)


class ExampleSanitizer:
    """例句清洗器（7 条规则）。"""

    def clean(self, example: str) -> str:
        """清洗单条例句。返回干净文本；污染严重返回空。"""
        if not example:
            return ""
        e = example.strip()
        # 规则 6: 孤立页码
        if _LONE_NUM_PATTERN.match(e):
            return ""
        # 规则 7: 页眉页脚关键词
        if _HEADER_FOOTER_KW.match(e) and len(e) < 40:
            return ""
        # 规则 5: 目录条目
        if _TOC_PATTERN.match(e):
            return ""
        # 规则 1: 参考文献编号
        e = _REF_PATTERN.sub("", e)
        # 规则 2: 上标脚注
        e = _SUPERSCRIPT_PATTERN.sub("", e)
        # 规则 4: 注释括号
        e = _NOTE_PATTERN.sub("", e)
        # 规则 3: 跨页断词（已在 OCR 层处理，此处兜底）
        e = e.replace("-\n", "")
        return e.strip()

    def clean_many(self, examples: List[str]) -> List[str]:
        """批量清洗，去除污染严重的空结果。"""
        out = []
        for ex in examples:
            c = self.clean(ex)
            if c and c not in out:
                out.append(c)
        return out


def sanitize_examples(examples: List[str]) -> List[str]:
    """便捷入口：批量清洗例句。"""
    return ExampleSanitizer().clean_many(examples)


def sanitize_single(example: str) -> str:
    """便捷入口：清洗单条例句。"""
    return ExampleSanitizer().clean(example)
