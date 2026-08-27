# -*- coding: utf-8 -*-
"""P7 ⭐ 语义显著词识别（moonlighting 类——隐喻/文化含义词保护）。

用户需求："对，moonlighting也很重要"——moonlighting（兼职）这类词
虽然罕见但语义价值高，应受 is_important 保护（第二标准）。

识别：
1. 语义显著词表（常见文化/隐喻含义词）
2. 隐喻构词检测（复合词：常见词根组合，词义非字面——moon+light → 兼职）
"""

from __future__ import annotations

import re
from typing import Set

# 语义显著词（文化/隐喻含义——moonlight 已归入熟词生义 polysemy，此处不再重复）
SEMANTICALLY_NOTABLE = {
    "watershed",                           # 分水岭/转折点
    "breakthrough",                        # 突破
    "mainstream",                          # 主流
    "groundbreaking",                      # 开创性的
    "blueprint",                           # 蓝图/方案
    "landmark",                            # 里程碑
    "milestone",                           # 里程碑
    "cornerstone",                         # 基石
    "hallmark",                            # 标志特征
    "trademark",                           # 标志性特征
    "linchpin",                            # 关键
    "lynchpin",                            # 关键
    "bedrock",                             # 基石/基岩
    "underpinning",                        # 支撑/基础
    "touchstone",                          # 试金石/标准
    "litmus",                              # 试金石
    "flashpoint",                          # 爆发点
    "crossroads",                          # 十字路口/关键时刻
    "turningpoint",                        # 转折点
    "foothold",                            # 立足点
    "springboard",                         # 跳板
    "stumblingblock",                      # 障碍
    "steppingstone",                       # 垫脚石
    "whitewash",                           # 粉饰
    "backdrop",                            # 背景
    "showcase",                            # 展示/橱窗
    "flagship",                            # 旗舰
    "powerhouse",                          # 强权/动力源
    "heavyweight",                         # 重量级/要员
    "lightweight",                         # 无足轻重
    "watchdog",                            # 监督者
    "gatekeeper",                          # 守门人
    "frontrunner",                         # 领先者
    "trailblazer",                         # 先驱
    "pathfinder",                          # 开拓者
    "trendsetter",                         # 引领潮流者
    "gamechanger",                         # 改变格局者
    "eyeopener",                           # 令人大开眼界的事物
    "headturner",                          # 引人注目者
    "heartthrob",                          # 万人迷
    "soulmate",                            # 灵魂伴侣
    "scapegoat",                           # 替罪羊
    "whippingboy",                         # 替罪羊
    "fallguy",                             # 替罪羊
    "laughingstock",                       # 笑柄
    "goldmine",                            # 金矿/宝库
    "moneyspinner",                        # 摇钱树
    "cashcow",                             # 摇钱树
    "gravy",                               # 意外之财
    "windfall",                            # 意外之财
    "jackpot",                             # 头奖
    "bonanza",                             # 富矿/好运
    "paydirt",                             # 成功/发现宝矿
    "motherlode",                          # 母矿脉/宝库
    "skeletonkey",                         # 万能钥匙
    "masterkey",                           # 万能钥匙
    "passkey",                             # 万能钥匙
    "opensesame",                          # 敲门砖/万能法
    "shortcut",                            # 捷径
    "cuttingedge",                         # 前沿
    "bleedingedge",                        # 最前沿
    "leadingedge",                         # 领先地位
    "stateoftheart",                       # 最先进的
    "silverlining",                        # 一线希望
    "brightside",                          # 光明面
    "darkhorse",                           # 黑马
    "longshot",                            # 冷门
    "surefire",                            # 必成的
    "triedandtrue",                        # 久经考验的
    "householdname",                       # 家喻户晓的名字
    "bigwig",                              # 大人物
    "bigshot",                             # 大人物
    "hotshot",                             # 能人
    "whizkid",                             # 神童
    "prodigy",                             # 神童
    "wunderkind",                          # 神童
    "risingstar",                          # 新星
    "shootingstar",                        # 流星/新星
}

# 隐喻构词词根（复合词检测——常见词根组合；moon 已归熟词生义不在此列）
_METAPHOR_ROOTS = {"star", "sun", "earth", "fire", "water", "stone",
                   "rock", "ground", "sky", "light", "dark", "gold", "silver",
                   "iron", "steel", "heart", "blood", "bone", "hand", "foot",
                   "head", "eye", "ear", "face", "finger", "key", "door",
                   "gate", "road", "path", "bridge", "ship", "horse", "dog",
                   "cat", "bird", "wolf", "lion", "tiger", "bear", "fox"}


def is_semantically_notable(word: str) -> bool:
    """词是否语义显著（moonlighting 类——文化/隐喻含义）。

    1. 语义显著词表命中
    2. 隐喻构词：含隐喻词根（moon/star/water 等）且整体罕见（zipf 低）
    """
    w = word.strip().lower()
    if not w:
        return False
    if w in SEMANTICALLY_NOTABLE:
        return True
    # 隐喻构词检测：含隐喻词根 + 整体非高频（字面组合但语义可能隐喻）
    if len(w) >= 8 and not w.startswith(("un", "re", "in", "dis", "mis", "over", "under")):
        for root in _METAPHOR_ROOTS:
            if root in w:
                try:
                    from wordfreq import zipf_frequency
                    if zipf_frequency(w, "en") < 4.5:
                        return True
                except Exception:
                    return True
    return False


def notable_words() -> Set[str]:
    """语义显著词表（供渲染标注）。"""
    return set(SEMANTICALLY_NOTABLE)
