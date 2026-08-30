# -*- coding: utf-8 -*-
"""paeg_vocabulary.enrichers.ocr_llm_cleaner — OCR 词库清理/判别/修复（LLM 判别 ⭐）。

用户需求（§3.116 ⭐）：「对清洗后的候选词用 LLM 判别 OCR 断裂词、专名、非词噪声，
修复词形、提取拼写错误——接入 clean/filter 阶段，失败降级到规则层」。

设计（python 脚本算确定性数据 + 系统提示词 harness LLM 做判别/生成）：
  1. 确定性打标（collect_suspects）：从 clean_corpus 统计词频 + 大写比例，
     找出「离线词典外词」（ecdict/CMU/CEFR/Oxford/wordfreq 均不认识）——
     这些是 LLM 需要判别的嫌疑词（断裂词/拼写错误/专名/非词噪声都可能落在这里）。
  2. LLM 判别（llm_classify）：分批把嫌疑词 + 频次/大写比例发送给 LLM，输出
     {word, action, replacement, reason}，action ∈ repair|spelling|proper|noise|keep。
  3. 应用（apply_llm_clean）：repair/spelling → 改写 clean_corpus 词形；
     proper/noise → 从 clean_corpus 移除；keep → 保留。
  4. 失败降级：无 chat_fn / LLM 空响应 / 任何异常 → 返回原 ctx（规则层
     _is_clean_word/_is_proper_noun 继续兜底，不阻塞管线）。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

# LLM 判别系统提示词（只判别，不生成整条词条）
OCR_CLEAN_SYSTEM_PROMPT = """你是 OCR 词库清理专家。给定一批从书籍扫描/OCR 提取的候选词及其
出现次数与大写比例，判别每个词属于哪一类并给出处理建议。

判别类别（action）：
- "repair"：OCR 断裂词/词尾丢失（如 scienc→science、includ→include、recieve→receive），
  replacement 给出修复后的正确词形（必须是小写英文单词）。
- "spelling"：拼写错误（replacement 给出正确拼写）。
- "proper"：专有名词（人名/地名/机构名，如 Plath/Esther/France），replacement 留空。
- "noise"：非词噪声/断词残片/重复字符（如 gggg/ababab/th），replacement 留空。
- "keep"：看起来是合法的罕见词/专业术语/正常单词，无需处理，replacement 留空。

规则：
- 只输出 JSON，不要其他文字，格式：
{"decisions": [{"word": "scienc", "action": "repair", "replacement": "science", "reason": "词尾 e 丢失"}]}
- 每个输入词都必须给出一条 decision（顺序无关）。
- 不确定时判 "keep"（宁可不改，不误删、不误改合法词）。
- 大写比例高的词优先考虑是专名（proper）。
- replacement 只填小写英文单词，不含标点。"""

# 只清洗一次最多多少嫌疑词（成本闸——按频次取前 N）
_DEFAULT_LIMIT = 200
_DEFAULT_BATCH = 40


def _known_word(word: str) -> bool:
    """确定性判断：词是否被离线词库（ecdict/CMU/CEFR/Oxford/wordfreq）认识。"""
    w = word.strip().lower()
    if not w:
        return False
    try:
        from ..wordbank import CefrGlossSource, CmuIpaSource, EcdictSource, OxfordLevelSource
        if EcdictSource().lookup(w) is not None:
            return True
        if CmuIpaSource().lookup(w):
            return True
        if CefrGlossSource().lookup(w):
            return True
        if OxfordLevelSource().lookup(w):
            return True
    except Exception:
        pass
    try:
        from wordfreq import zipf_frequency
        # wordfreq 有平滑下限（几乎不为 0），需较高阈值（≥4.0 才算"确信常见词"），
        # 否则 scienc(1.28)/plath(2.52)/gggg(1.14) 这类畸形/专名/噪声会被误判为认识。
        if zipf_frequency(w, "en") >= 4.0:
            return True
    except Exception:
        pass
    return False


def collect_suspects(ctx, limit: int = _DEFAULT_LIMIT) -> List[Dict[str, Any]]:
    """确定性打标：从 clean_corpus 找出「词典外」嫌疑词 + 频次/大写比例。"""
    from ..core.context import VocabularyContext
    if not isinstance(ctx, VocabularyContext) or not ctx.clean_corpus:
        return []
    counts = Counter(t.lemma.lower() for t in ctx.clean_corpus)
    cap_stats = getattr(ctx, "capitalized_stats", None) or {}
    out = []
    for lemma, freq in counts.most_common():
        if _known_word(lemma):
            continue  # 词典认识 → 无需 LLM 判别
        cs = cap_stats.get(lemma, {})
        total = cs.get("total", 0) or 0
        upper = cs.get("upper", 0) or 0
        cap_ratio = round(upper / total, 2) if total else 0.0
        out.append({"word": lemma, "freq": freq, "cap_ratio": cap_ratio})
        if len(out) >= limit:
            break
    return out


def build_clean_prompt(suspects: List[Dict[str, Any]]) -> str:
    """构造判别用户提示词（确定性数据打底：词/频次/大写比例）。"""
    lines = [f"- {s['word']}（出现 {s['freq']} 次，大写比例 {s['cap_ratio']}）"
             for s in suspects]
    return ("请判别以下候选词（依次给出 decision）：\n\n" + "\n".join(lines))


def parse_clean_response(raw: str) -> Dict[str, Dict[str, Any]]:
    """解析 LLM 判别响应 → {word: {action, replacement, reason}}。"""
    if not raw or not isinstance(raw, str):
        return {}
    data = None
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                return {}
    if not isinstance(data, dict):
        return {}
    decisions = data.get("decisions") or []
    out: Dict[str, Dict[str, Any]] = {}
    for d in decisions:
        if not isinstance(d, dict):
            continue
        w = str(d.get("word", "")).strip().lower()
        if not w:
            continue
        action = str(d.get("action", "")).strip().lower()
        replacement = str(d.get("replacement", "")).strip().lower()
        reason = str(d.get("reason", "")).strip()[:200]
        if action not in ("repair", "spelling", "proper", "noise", "keep"):
            action = "keep"
        out[w] = {"action": action, "replacement": replacement, "reason": reason}
    return out


def llm_classify(suspects: List[Dict[str, Any]], chat_fn,
                 batch_size: int = _DEFAULT_BATCH) -> Dict[str, Dict[str, Any]]:
    """分批调用 LLM 判别嫌疑词（每批独立 try/except——失败不阻塞）。"""
    if not suspects or chat_fn is None:
        return {}
    merged: Dict[str, Dict[str, Any]] = {}
    for i in range(0, len(suspects), batch_size):
        batch = suspects[i:i + batch_size]
        try:
            raw = None
            try:
                raw = chat_fn(OCR_CLEAN_SYSTEM_PROMPT, build_clean_prompt(batch),
                              max_tokens=4000)
            except TypeError:
                try:
                    raw = chat_fn(OCR_CLEAN_SYSTEM_PROMPT, build_clean_prompt(batch))
                except Exception:
                    raw = None
            except Exception:
                raw = None
            if not raw:
                continue
            merged.update(parse_clean_response(raw))
        except Exception:
            continue
    return merged


def apply_llm_clean(ctx, chat_fn=None, limit: int = _DEFAULT_LIMIT) -> Any:
    """接入 clean/filter 阶段：LLM 判别 + 修复/剔除嫌疑词（失败降级到规则层）。

    - repair/spelling：改写 clean_corpus 中该词的 token/lemma 为 replacement
    - proper/noise：从 clean_corpus 移除该词
    - keep：保留
    任何失败/无 LLM → 返回原 ctx（规则层继续兜底）。
    """
    if chat_fn is None or ctx is None or not getattr(ctx, "clean_corpus", None):
        return ctx
    suspects = collect_suspects(ctx, limit=limit)
    if not suspects:
        ctx.llm_ocr_clean = {"suspects": 0, "decisions": {}, "repaired": [], "dropped": []}
        return ctx
    try:
        decisions = llm_classify(suspects, chat_fn)
    except Exception:
        decisions = {}

    repaired: List[str] = []
    dropped: List[str] = []
    repair_map: Dict[str, str] = {}
    drop_set: set = set()
    for w, d in decisions.items():
        if d["action"] in ("repair", "spelling") and d.get("replacement") and d["replacement"] != w:
            repair_map[w] = d["replacement"]
            repaired.append(w)
        elif d["action"] in ("proper", "noise"):
            drop_set.add(w)
            dropped.append(w)

    if not repair_map and not drop_set:
        ctx.llm_ocr_clean = {"suspects": len(suspects), "decisions": decisions,
                             "repaired": [], "dropped": []}
        return ctx

    # 应用：改写 + 移除
    new_corpus = []
    for t in ctx.clean_corpus:
        low = (t.lemma or "").lower()
        if low in drop_set:
            continue
        if low in repair_map:
            repl = repair_map[low]
            try:
                t.lemma = repl
                t.token = repl
            except Exception:
                pass
        new_corpus.append(t)
    ctx.clean_corpus = new_corpus
    ctx.llm_ocr_clean = {"suspects": len(suspects), "decisions": decisions,
                         "repaired": repaired, "dropped": dropped}
    return ctx
