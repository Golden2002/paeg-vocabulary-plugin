# -*- coding: utf-8 -*-
"""paeg_vocabulary.cleaners.ocr_repair — OCR 断裂修复（§3.116 模块5 ⭐）。

5 层管道（librarian 调研）：
1. 编码修复：ftfy + Unicode NFC
2. 页面去污染：页眉页脚坐标裁剪（已在 pdf_ingest 处理）
3. 跨页断词：行末 `-\n` → 拼接
4. 拼接词拆分：wordninja
5. 词级校验：wordfreq 频率验证（剔除生造词）

零依赖弱模式：缺 ftfy/wordninja 时静默跳过（核心正则仍生效）。
"""

from __future__ import annotations

import re
from typing import List, Optional


class OCRRepairPipeline:
    """OCR 文本修复管道（5 层）。"""

    def __init__(self, lang: str = "en"):
        self.lang = lang

    def _fix_encoding(self, text: str) -> str:
        """Layer 1: 编码修复（ftfy + NFC）。"""
        try:
            import ftfy
            text = ftfy.fix_text(text, normalization="NFC")
        except Exception:
            pass
        return text

    def _fix_hyphenation(self, text: str) -> str:
        """Layer 3: 跨页断词 `-\n` → 拼接（英文）。"""
        if self.lang == "en":
            text = re.sub(r"-\n", "", text)  # 行末连字符 + 换行 → 直接拼接
        return text

    def _split_concatenated(self, text: str) -> str:
        """Layer 4: 拼接词拆分（wordninja——OCR 行内空格丢失）。"""
        try:
            import wordninja
            # 只处理明显的拼接词（无空格的长词）
            def _split(match):
                word = match.group(0)
                if len(word) < 8:
                    return word
                parts = wordninja.split(word)
                if len(parts) > 1:
                    return " ".join(parts)
                return word
            # 对连续小写字母串尝试拆分
            text = re.sub(r"[a-z]{8,}", _split, text)
        except Exception:
            pass
        return text

    def repair(self, text: str) -> str:
        """执行 5 层修复（页眉页脚已由 pdf_ingest 裁剪）。"""
        if not text:
            return text
        text = self._fix_encoding(text)
        text = self._fix_hyphenation(text)
        text = self._split_concatenated(text)
        # Layer 5: wordfreq 验证（此处不做全量过滤——留到 filter 阶段按频率筛选）
        return text


def repair_text(text: str, lang: str = "en") -> str:
    """便捷入口：单段文本 OCR 修复。"""
    return OCRRepairPipeline(lang).repair(text)


def _repair_corpus(text: str, lang: str = "en") -> str:
    """批量语料修复（供 pipeline/clean_dedup 调用）。"""
    return repair_text(text, lang)
