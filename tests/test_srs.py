# -*- coding: utf-8 -*-
"""SRS 间隔重复（SM-2）测试。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from paeg_vocabulary.srs import sm2_review, make_srs_state, due_words, plan_schedule


def test_sm2_interval_growth():
    """连续全对：间隔 1 → 6 → 递增。"""
    ef, interval, reps = 2.5, 0, 0
    intervals = []
    for q in (5, 5, 5, 5, 5):
        r = sm2_review(ef, interval, reps, q)
        ef, interval, reps = r["ef"], r["interval"], r["reps"]
        intervals.append(interval)
    assert intervals[0] == 1
    assert intervals[1] == 6
    assert intervals[2] >= 12  # 6 * EF(≥2.3) 递增
    assert intervals[3] > intervals[2]


def test_sm2_failure_reset():
    """评分 <3 失败：间隔重置为 1，reps 归零。"""
    r1 = sm2_review(2.5, 6, 2, 5)  # 先学两次到间隔 6
    r2 = sm2_review(r1["ef"], r1["interval"], r1["reps"], 2)  # 失败
    assert r2["interval"] == 1
    assert r2["reps"] == 0


def test_sm2_ef_bounds():
    """EF 不低于下限 1.3。"""
    ef = 2.5
    for _ in range(20):
        ef = sm2_review(ef, 1, 0, 0)["ef"]
    assert ef >= 1.3


def test_due_words():
    state = make_srs_state(["apple", "banana", "cherry"], "day0")
    state["apple"]["due"] = "day0"
    state["banana"]["due"] = "day5"
    due = due_words(state, "day2")
    assert "apple" in due
    assert "banana" not in due


def test_plan_schedule():
    r = plan_schedule(["a", "b", "c", "d", "e", "f"], days=7)
    assert r["words"] == 6
    assert r["total_reviews"] >= 6  # 每个词至少复习一次
    assert set(r["plan"].keys()) == {f"day{i}" for i in range(7)}
    # 首日应含全部词（初始 due=day0）
    assert len(r["plan"]["day0"]) == 6
