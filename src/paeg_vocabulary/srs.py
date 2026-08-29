# -*- coding: utf-8 -*-
"""paeg_vocabulary.srs —— SRS 间隔重复复习（SM-2 算法，对标 LingQ/Anki）。

LingQ 核心经验：词汇不是"一次性产出"，而是"状态化 + 按遗忘曲线复习"。
本模块为词汇表产物提供复习调度：SM-2 遗忘曲线 + 到期判断 + 今日复习清单。

SM-2 算法（SuperMemo-2）：
- 每个词条维护 EF（难度因子，初始 2.5）+ 间隔 interval + 重复次数 reps
- 复习评分 q∈0-5：q≥3 正确（间隔按 EF 递增），q<3 失败（重置为 1 天）
"""
from __future__ import annotations

from typing import Any, Dict, List

DEFAULT_EF = 2.5
MIN_EF = 1.3

# 正确回忆的间隔序列（前两次固定，之后按 EF 递增）
_INTERVALS = (1, 6)


def status_from_reps(reps: int) -> str:
    """重复次数 → 词汇三态（对标 LingQ 蓝/黄/白）。

    reps 0 → new（生词/蓝）；reps 1-2 → learning（学习中/黄）；reps ≥3 → mastered（已掌握/白）。
    """
    if reps <= 0:
        return "new"
    if reps < 3:
        return "learning"
    return "mastered"


def sm2_review(ef: float, interval: int, reps: int, quality: int) -> Dict[str, Any]:
    """SM-2 单次复习：根据评分更新 EF/间隔/次数。

    返回：{ef, interval, reps, status}
    """
    q = max(0, min(5, int(quality)))
    if q >= 3:
        if reps == 0:
            interval = _INTERVALS[0]
        elif reps == 1:
            interval = _INTERVALS[1]
        else:
            interval = max(1, round(interval * ef))
        reps += 1
    else:
        reps = 0
        interval = _INTERVALS[0]
    ef = ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    if ef < MIN_EF:
        ef = MIN_EF
    return {
        "ef": round(ef, 2),
        "interval": interval,
        "reps": reps,
        "status": "learned" if q >= 4 else ("reviewing" if q == 3 else "forgot"),
    }


def make_srs_state(words: List[str], start_day: str = "day0") -> Dict[str, Dict[str, Any]]:
    """初始化 SRS 状态：每个词 EF=2.5 / interval=0 / reps=0 / due=start_day。

    产出的状态可作为词汇表附件的「复习计划」起点。
    """
    return {
        w: {"ef": DEFAULT_EF, "interval": 0, "reps": 0, "due": start_day}
        for w in words
    }


def due_words(state: Dict[str, Dict[str, Any]], day: str) -> List[str]:
    """到期词清单（due ≤ day）。"""
    return sorted(w for w, it in state.items() if str(it.get("due", "")) <= str(day))


def review_word(state: Dict[str, Dict[str, Any]], word: str, quality: int,
                day: str) -> Dict[str, Any]:
    """复习一个词，更新状态并返回结果。"""
    it = state.get(word)
    if it is None:
        return {"ok": False, "error": f"词不在状态中: {word}"}
    r = sm2_review(it.get("ef", DEFAULT_EF), it.get("interval", 0),
                   it.get("reps", 0), quality)
    state[word] = {
        "ef": r["ef"], "interval": r["interval"], "reps": r["reps"],
        "due": f"day{int(day.replace('day', '')) + r['interval']}" if day.startswith("day") else str(day + r["interval"]),
    }
    return {"ok": True, "word": word, **r}


def plan_schedule(words: List[str], days: int = 7) -> Dict[str, Any]:
    """为词汇表产出 N 天复习计划（模拟 SM-2 全对路径，供展示/规划）。

    返回：{day0: [...], day1: [...], ...} 每天应复习的词 + 总量统计。
    """
    state = make_srs_state(words)
    plan: Dict[str, List[str]] = {}
    # 模拟：每天复习到期词，全对（quality=5），推进间隔
    day_labels = [f"day{i}" for i in range(days)]
    total = 0
    for i, day in enumerate(day_labels):
        due = due_words(state, day)
        plan[day] = due
        total += len(due)
        for w in due:
            r = sm2_review(state[w]["ef"], state[w]["interval"],
                           state[w]["reps"], 5)
            state[w] = {**r, "due": f"day{i + r['interval']}"}
    return {
        "plan": plan,
        "total_reviews": total,
        "words": len(words),
        "daily_avg": round(total / max(1, days), 1),
    }
