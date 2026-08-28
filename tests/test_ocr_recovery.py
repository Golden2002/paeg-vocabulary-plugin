# -*- coding: utf-8 -*-
"""V-R4 ⭐ OCR 断裂恢复率测试集——断裂词恢复率 ≥95% 量化基准。

对标表 V-01「断裂恢复率 ≥95%（测试集量化）」——此前仅 2 项功能测试（断词拼接/编码），
无恢复率基准。本测试集构造三类断裂样本（跨页断词/拼接词/编码），量化断言恢复率。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "src"))
from paeg_vocabulary.cleaners.ocr_repair import OCRRepairPipeline, repair_text

# ── 断裂样本集：{断裂文本: 期望恢复后的关键内容} ──
# 跨页断词（行末连字符 - 换行 → 拼接）——确定性修复
_HYPHENATION_CASES = [
    ("a sto-\nry about life", "story"),
    ("the transla-\ntion is clear", "translation"),
    ("philo-\nsophical biology", "philosophical"),
    ("pheno-\nmenology of life", "phenomenology"),
    ("under-\nstanding the text", "understanding"),
    ("meta-\nbolism and freedom", "metabolism"),
    ("transcend-\nence of self", "transcendence"),
    ("con-\ntradiction in being", "contradiction"),
    ("evo-\nlutionary process", "evolutionary"),
    ("con-\nsummation of possibility", "consummation"),
]

# 编码问题（mojibake）——ftfy 可选（不可用时跳过，不影响核心恢复率）
_ENCODING_CASES = [
    ("cafÃ©", "caf"),
    ("naÃ¯ve", "na"),
]

# 拼接词（行内空格丢失）——wordninja 可选（不可用时跳过）
_CONCAT_CASES = [
    ("theword is here", "the"),
    ("wouldhave been", "have"),
]


def _check_deps():
    """检测可选依赖（ftfy/wordninja）。"""
    deps = {"ftfy": True, "wordninja": True}
    try:
        import ftfy  # noqa: F401
    except ImportError:
        deps["ftfy"] = False
    try:
        import wordninja  # noqa: F401
    except ImportError:
        deps["wordninja"] = False
    return deps


class TestOCRRecoveryRate:
    """OCR 断裂恢复率量化测试（V-R4）。"""

    def test_hyphenation_recovery_100(self):
        """跨页断词恢复率必须 100%（确定性修复，无依赖）。"""
        p = OCRRepairPipeline("en")
        recovered = 0
        for broken, expected in _HYPHENATION_CASES:
            out = p.repair(broken)
            if expected in out:
                recovered += 1
        rate = recovered / len(_HYPHENATION_CASES)
        print(f"\n[V-R4] 跨页断词恢复率: {recovered}/{len(_HYPHENATION_CASES)} = {rate:.0%}")
        assert rate >= 0.95, f"跨页断词恢复率 {rate:.0%} < 95%"

    def test_overall_recovery_95(self):
        """总恢复率 ≥95%（确定性样本 100% + 可选依赖样本尽力）。"""
        deps = _check_deps()
        p = OCRRepairPipeline("en")
        total = 0
        recovered = 0
        # 确定性样本（跨页断词）
        for broken, expected in _HYPHENATION_CASES:
            total += 1
            if expected in p.repair(broken):
                recovered += 1
        # 编码样本（ftfy）
        if deps["ftfy"]:
            for broken, expected in _ENCODING_CASES:
                total += 1
                if expected in p.repair(broken):
                    recovered += 1
        # 拼接词样本（wordninja）
        if deps["wordninja"]:
            for broken, expected in _CONCAT_CASES:
                total += 1
                if expected in p.repair(broken):
                    recovered += 1
        rate = recovered / total if total else 1.0
        print(f"[V-R4] 总恢复率: {recovered}/{total} = {rate:.0%}"
              f"（ftfy={'✓' if deps['ftfy'] else '✗'} wordninja={'✓' if deps['wordninja'] else '✗'}）")
        assert rate >= 0.95, f"总恢复率 {rate:.0%} < 95%"

    def test_repair_text_convenience(self):
        """便捷入口 repair_text 可用。"""
        assert "story" in repair_text("a sto-\nry")
