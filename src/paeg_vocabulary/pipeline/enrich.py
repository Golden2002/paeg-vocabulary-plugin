# -*- coding: utf-8 -*-
"""paeg_vocabulary.pipeline.enrich — 阶段4：信息补全（P5 ⭐ 重构）。

P5 架构（Oracle）：
1. **wordbank 离线优先**：音标（CMU 12.6万词）/ 释义 / CEFR 等级——确定性数据源直接查
2. **batch_llm 批量补全**：20 词/批 + JSON schema + 断点续跑（替代逐词调用）
3. **collocations 原著提取**：N-gram + PMI 从书中提取固定搭配
4. 逐词 LLM 仅作兜底（wordbank 无数据时）

词条 12 字段：headword/pos/ipa/gloss_bilingual/examples/lemma +
etymology/morpheme/senses/collocations + cefr_level/freq_rank + phenomena + book_sense
"""

from __future__ import annotations

from typing import List, Optional

from ..core.context import VocabularyContext
from ..core.entry import VocabularyEntry, Sense, Morpheme
from ..enrichers.ipa_enricher import IpaEnricher
# §3.116 ⭐ 语言现象识别（熟词生义/固定搭配/俚语）
from ..enrichers.idiom_enricher import detect_phenomena
# P5 ⭐ 本地专业词库（离线音标/释义/等级）
from ..wordbank import WordBank, clean_ecdict_gloss, normalize_pos
# P5 ⭐ LLM 批量补全（20 词/批）
from ..enrichers.batch_llm import batch_enrich
# P5 ⭐ 原著搭配提取（N-gram + PMI）
from ..collocations import extract_collocations, collocations_for_word


# §3.116 ⭐ ecdict 接线：离线中文释义兜底（修复弱模式空词汇表根因）
_ECDICT_CACHE = None


def _ecdict_zh(word: str) -> str:
    """查 ecdict.csv 中文释义（懒加载 word→translation 字典 + 模块级缓存）。

    62MB CSV（约 77 万词），首次调用加载 ~几秒，之后内存查询。
    加载失败 → 空缓存（不阻塞管线，回退到无 zh 释义）。
    """
    global _ECDICT_CACHE
    if _ECDICT_CACHE is None:
        import csv
        import os
        _ECDICT_CACHE = {}
        # __file__ = .../src/paeg_vocabulary/pipeline/enrich.py
        # dirname×2 = .../src/paeg_vocabulary → join data/ecdict.csv
        _path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "ecdict.csv")
        try:
            with open(_path, encoding="utf-8", errors="ignore") as _f:
                for _row in csv.reader(_f):
                    if len(_row) >= 4 and _row[0] and _row[3]:
                        _ECDICT_CACHE[_row[0].strip().lower()] = _row[3].strip()
        except Exception:
            _ECDICT_CACHE = {}
    return clean_ecdict_gloss(_ECDICT_CACHE.get(word.strip().lower(), ""))


# §3.116 ⭐ 词根词缀离线规则表（LLM 缺失时的兜底——常见前缀/后缀/词根）
_PREFIX_RULES = {
    "pre": "在前/预先（Latin prae）", "re": "再/重新（Latin re-）",
    "sub": "在下/次于（Latin sub）", "inter": "之间（Latin inter）",
    "trans": "跨越（Latin trans）", "super": "超过（Latin super）",
    "anti": "反对（Greek anti）", "auto": "自己（Greek autos）",
    "bio": "生命（Greek bios）", "geo": "地球（Greek ge）",
    "micro": "微小（Greek mikros）", "multi": "多（Latin multus）",
    "mono": "单一（Greek monos）", "poly": "多（Greek polys）",
    "tri": "三（Latin tres）", "uni": "一（Latin unus）",
    "di": "二（Greek dis）", "gen": "产生/起源（Greek genos）",
    "hetero": "异（Greek heteros）", "homo": "同（Greek homos）",
    "pheno": "显现（Greek phainein）", "proto": "最初（Greek protos）",
    "tele": "远（Greek tele）", "hyper": "超出（Greek hyper）",
    "hypo": "在下（Greek hypo）", "para": "旁边（Greek para）",
}
_SUFFIX_RULES = {
    "ology": "学科（Greek -logia）", "ism": "主义/状态（Greek -ismos）",
    "tion": "名词化（Latin -tio）", "ity": "性质（Latin -itas）",
    "ment": "行为/结果（Latin -mentum）", "ness": "状态（Old English -nes）",
    "able": "能够（Latin -abilis）", "ible": "能够（Latin -ibilis）",
    "ous": "充满（Latin -osus）", "ive": "倾向（Latin -ivus）",
    "ic": "属于（Greek -ikos）", "al": "相关（Latin -alis）",
    "ize": "使成为（Greek -izein）", "type": "类型（Greek typos）",
    "some": "具有（Old English -sum）", "like": "像（Old English -lic）",
}
_ROOT_RULES = {
    "gene": {"lang": "Greek", "meaning": "产生/基因（genos 起源）"},
    "pheno": {"lang": "Greek", "meaning": "显现/表现（phainein）"},
    "allel": {"lang": "Greek", "meaning": "相互（allelon 彼此的）"},
    "loc": {"lang": "Latin", "meaning": "位置（locus 地点）"},
    "morph": {"lang": "Greek", "meaning": "形态（morphe）"},
    "herit": {"lang": "Latin", "meaning": "继承（hereditas）"},
    "dom": {"lang": "Latin", "meaning": "统治/领域（dominus 主人）"},
    "part": {"lang": "Latin", "meaning": "部分（pars）"},
    "cess": {"lang": "Latin", "meaning": "行走/让步（cedere）"},
    "spect": {"lang": "Latin", "meaning": "看（specere）"},
    "struct": {"lang": "Latin", "meaning": "建造（struere）"},
}


def _rule_morpheme(word: str):
    """规则级词根词缀拆解（LLM 缺失时兜底）。"""
    w = word.strip().lower()
    if len(w) < 5:
        return None
    prefix = None
    suffix = None
    roots = []
    for p, meaning in _PREFIX_RULES.items():
        if w.startswith(p) and len(w) > len(p) + 2:
            prefix = {"p": p, "meaning": meaning}
            w = w[len(p):]
            break
    for s, meaning in _SUFFIX_RULES.items():
        if w.endswith(s) and len(w) > len(s) + 2:
            suffix = {"s": s, "meaning": meaning}
            w = w[:-len(s)]
            break
    for r, info in _ROOT_RULES.items():
        if r in w:
            roots.append({"root": r, "lang": info["lang"], "meaning": info["meaning"]})
    if not prefix and not suffix and not roots:
        return None
    return Morpheme(roots=roots, prefix=prefix, suffix=suffix)


def enrich_entries(ctx: VocabularyContext,
                   chat_fn: Optional[object] = None,
                   book_title: str = "",
                   book_author: str = "",
                   domains: Optional[List[str]] = None) -> VocabularyContext:
    """阶段 4：candidates → entries（12 字段补全，P5 离线优先 + 批量 LLM）。

    §3.116 ⭐ book_title/book_author：LLM 生成"本书含义"义项标注。
    §3.116 ⭐ domains：学科术语辞典（现象学/分子生物/物理/化学等）。
    """
    if not ctx.candidates:
        ctx.errors.append("无候选词（阶段3未执行）")
        return ctx

    # ── 0. 原著搭配提取（全书级——一次提取，按词检索）──
    corpus = getattr(ctx, "clean_sentences", None)
    if not corpus and getattr(ctx, "clean_corpus", None):
        # 从清洗词流重建句子（退化：按词流整体）
        try:
            corpus = [" ".join(getattr(t, "token", "") or getattr(t, "text", "") for t in ctx.clean_corpus[:200])]
        except Exception:
            corpus = []
    all_colls = extract_collocations(corpus or [], n=2, min_count=2, top_n=60) if corpus else []

    wb = WordBank(domains=domains)
    _ipa_fallback = IpaEnricher()

    # ── 1. 构建词条（wordbank 离线数据优先）──
    entries: List[VocabularyEntry] = []
    max_entries = getattr(ctx, "max_entries", 0) or len(ctx.candidates)
    for cand in ctx.candidates[:max_entries if max_entries > 0 else None]:
        wb_r = wb.lookup(cand.headword)

        entry = VocabularyEntry(
            headword=cand.headword,
            pos=normalize_pos(cand.pos or wb_r.get("pos") or ""),
            lemma=cand.lemma,
            freq_rank=cand.freq_count,
            cefr_level=cand.cefr_guess or wb_r.get("cefr") or "",
            source_book=book_title or str(ctx.pdf_path or ""),
        )
        # 音标：CMU 离线优先 → IpaEnricher 兜底
        entry.ipa = {}
        if wb_r.get("ipa"):
            entry.ipa["en_us"] = wb_r["ipa"]
        else:
            _fb = _ipa_fallback.enrich(cand.headword)
            if _fb:
                entry.ipa.update(_fb)
        # 释义：离线双轨——en（CEFR/kaikki/ECDICT 兜底链）+ zh（ECDICT）
        gloss_en = wb_r.get("gloss_en") or ""
        gloss_zh = wb_r.get("gloss_zh") or ""
        if not gloss_zh:
            _zh2 = _ecdict_zh(cand.headword)
            gloss_zh = _zh2
        entry.gloss_bilingual = {"en": gloss_en, "zh": gloss_zh}
        # 词源：kaikki 离线（LLM 批量阶段可精修）
        if wb_r.get("etymology"):
            entry.etymology = wb_r["etymology"]
        # 多义项：kaikki glosses 前 3 条 → Sense（词源.义项 双层编号）
        if wb_r.get("senses"):
            entry.senses = [
                Sense(sense_id=f"1.{i}", gloss_en=s[:200],
                      gloss_zh=entry.gloss_bilingual.get("zh", ""))
                for i, s in enumerate(wb_r["senses"], 1)
            ]
        # 词根词缀：离线规则表兜底（LLM 批量阶段可精修）
        _morph = _rule_morpheme(cand.headword)
        if _morph:
            entry.morpheme = _morph
        # 学科术语：domain 命中 → 标记术语（筛选豁免信号）
        if wb_r.get("domain_term"):
            entry.phenomena.setdefault(
                "domain_term",
                [wb_r["domain_term"].get("gloss_en", "")[:120]])
        # 原书例句（上下文优先）
        if cand.contexts:
            entry.examples = [{"en": c[:200], "zh": ""} for c in cand.contexts[:2]]
        # 语言现象识别
        _ctx_text = " ".join(cand.contexts[:3])
        entry.phenomena.update(detect_phenomena(cand.headword, _ctx_text))
        # 搭配：原著提取结果按词检索
        entry.collocations = [c["phrase"] for c in collocations_for_word(all_colls, cand.headword)][:4]

        entries.append(entry)

    # ── 2. LLM 批量补全（6 词/批——完整字段 JSON 防截断；断点续跑）──
    # P7 ⭐ 实测：10 词/批 max_tokens 4000 截断（completion_tokens=4000 达上限）
    # 6 词/批 × 每词 ~600 token ≈ 3600 < 4000 安全
    if chat_fn is not None and entries:
        entries = batch_enrich(entries, chat_fn, batch_size=6,
                               book_title=book_title, book_author=book_author)

    # §3.116 ⭐ 语言规范 L0 校对（复用 paeg_lang_style 14.1）：
    # 对生成的中文释义/词源/义项/例句翻译做 gate_short/fix_known_gaffes，
    # 缺失 paeg_lang_style 时 apply_l0 优雅降级为原文。
    try:
        from ..lang_style import apply_l0_to_entry
        for _e in entries:
            apply_l0_to_entry(_e)
    except Exception:
        pass

    ctx.entries = entries
    ctx.mark_completed("enrich")
    return ctx
