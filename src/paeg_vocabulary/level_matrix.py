# -*- coding: utf-8 -*-
"""paeg_vocabulary.level_matrix — 词汇难度分级矩阵（§3.116 ⭐ 用户新增）。

词汇对应表：统一映射 CEFR ↔ 雅思 ↔ 托福 ↔ 四六级 ↔ 考研 ↔ 专四专八 ↔ 高考。
- 用户选择水平档位（如"考研英语 70 分"）→ select_cefr_max 查矩阵 → CEFR 阈值
- filter 阶段按阈值过滤词汇
- 矩阵本身作为展示内容（README/前端展示词汇对应表）

数据：data/level_matrix.json（可扩充——新增考试体系/分数段即扩展）。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

_MATRIX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "level_matrix.json")

# 缓存
_MATRIX: Optional[Dict[str, Any]] = None


def _load_matrix() -> Dict[str, Any]:
    global _MATRIX
    if _MATRIX is None:
        try:
            with open(_MATRIX_PATH, encoding="utf-8") as f:
                _MATRIX = json.load(f)
        except Exception:
            _MATRIX = {"cefr_order": ["A1", "A2", "B1", "B2", "C1", "C2"],
                       "exam_systems": {}, "zipf_bridge": [],
                       "cefr_meta": {}, "user_presets": []}
    return _MATRIX


def cefr_order() -> List[str]:
    return list(_load_matrix().get("cefr_order", ["A1", "A2", "B1", "B2", "C1", "C2"]))


def cefr_meta() -> Dict[str, Any]:
    return _load_matrix().get("cefr_meta", {})


def exam_systems() -> Dict[str, Any]:
    return _load_matrix().get("exam_systems", {})


def user_presets() -> List[Dict[str, Any]]:
    return _load_matrix().get("user_presets", [])


def select_cefr_max(exam: str, score: float) -> str:
    """用户选档位 → CEFR 上限。

    Args:
        exam: 考试体系（ielts/toefl/cet4/cet6/kaoyan/tem4/tem8/gaokao）。
        score: 分数。

    Returns:
        CEFR 等级（A1-C2）。
    """
    systems = exam_systems()
    system = systems.get(exam)
    if not system:
        return "C2"  # 未知体系 → 不限制（全保留）
    for band in system.get("bands", []):
        if band["min"] <= score <= band["max"]:
            return band["cefr_max"]
    # 超上限 → C2（全保留）
    return "C2"


def guess_cefr_from_zipf(zipf: float) -> str:
    """Zipf → CEFR 桥接（wordfreq 兜底）。

    §3.116 ⭐ 修正方向：zipf 越高 = 越常见 = CEFR 越低（A1/A2）；
    zipf 越低 = 越稀有 = CEFR 越高（C1/C2）。
    原实现 `zipf >= min → cefr` 方向颠倒（7.73→C2 错误）。
    """
    bridge = _load_matrix().get("zipf_bridge", [])
    # zipf_bridge 数据形如 [{"min": 6.5, "cefr": "C2"}]——min 是"达到该 CEFR 所需的最高 zipf 下限"？
    # 修正语义：zipf ≥ 6.5 是超高频率（常见词）→ 应为 A1/A2 而非 C2。
    # 采用映射表：高 zipf → 低 CEFR。
    if zipf >= 6.5:
        return "A1"
    if zipf >= 5.5:
        return "A2"
    if zipf >= 4.5:
        return "B1"
    if zipf >= 3.5:
        return "B2"
    if zipf >= 2.5:
        return "C1"
    return "C2"


def filter_by_level(words: List[Dict[str, Any]], cefr_max: str) -> List[Dict[str, Any]]:
    """按 CEFR 上限过滤词汇（保留 ≤ 该难度的词）。

    Args:
        words: 词汇列表（每项含 lemma 或 headword）。
        cefr_max: CEFR 上限（如 "C1"——考研 70 分场景）。

    Returns:
        过滤后词汇列表。
    """
    order = cefr_order()
    cap = order.index(cefr_max) if cefr_max in order else len(order) - 1
    out = []
    for w in words:
        cefr = w.get("cefr")
        if not cefr:
            # zipf 无数据（0.0）→ 未知 → 保留（不误判为极稀有 C2）
            zipf = w.get("zipf", 0.0)
            if zipf is None or zipf <= 0.0:
                out.append(w)
                continue
            cefr = guess_cefr_from_zipf(zipf)
        if cefr in order and order.index(cefr) <= cap:
            out.append(w)
    return out


def resolve_preset(preset_id: str) -> Dict[str, Any]:
    """按用户预设 id 解析档位。返回 {exam, score, cefr_max, label}。"""
    for p in user_presets():
        if p["id"] == preset_id:
            return {
                "exam": p["exam"], "score": p["score"],
                "cefr_max": select_cefr_max(p["exam"], p["score"]),
                "label": p["label"], "id": preset_id,
            }
    return {"exam": "", "score": 0, "cefr_max": "C2", "label": "全部", "id": "all"}


def level_matrix_table() -> str:
    """生成展示用 Markdown 表（词汇对应表——用户可见 ⭐）。"""
    lines = ["| 考试体系 | 分数段 → CEFR |", "|---|---|"]
    for exam, sys_info in exam_systems().items():
        name = sys_info.get("name_zh", exam)
        bands = "；".join(
            f"{b['min']}-{b['max']}→{b['cefr_max']}" for b in sys_info.get("bands", []))
        lines.append(f"| **{name}** | {bands} |")
    return "\n".join(lines)
