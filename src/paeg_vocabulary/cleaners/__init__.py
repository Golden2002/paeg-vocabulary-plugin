# -*- coding: utf-8 -*-
"""paeg_vocabulary.cleaners — 污染处理机制（§3.116 模块5 ⭐）。

基于调研（librarian §3.116）：OCR 5 层管道 + 例句去污染 7 条规则。
"""

from .ocr_repair import OCRRepairPipeline, repair_text
from .example_sanitize import ExampleSanitizer, sanitize_examples

__all__ = ["OCRRepairPipeline", "repair_text", "ExampleSanitizer", "sanitize_examples"]
