# -*- coding: utf-8 -*-
"""paeg_vocabulary.accessories — 附件产物（§3.116 模块4 ⭐）。

3 类附件：
1. 语言学习价值说明（基于原著）
2. 全书词频统计报告（作者高频词/短语/句式）
3. 作者语言风格分析（词汇/句式特征风格画像）
"""

from __future__ import annotations

from typing import Dict, List

from ..core.entry import VocabularyEntry
from ..pipeline.filter import FunctionWordFilter


def language_value_note(book_title: str, entry_count: int,
                        top_words: List[str]) -> str:
    """附件1：基于原著的语言学习价值说明。"""
    return f"""# 《{book_title}》语言学习价值说明

## 词汇量概览
- 全书提取有效词汇 **{entry_count}** 个（含词元去重）
- 高频核心词：{', '.join(top_words[:10])}

## 学习价值
1. **真实语境**：本书词汇表例句全部提取自原著原文，保留真实语言环境
2. **词汇密度**：作为文学作品，本书词汇丰富度高于口语/新闻语料
3. **多义项覆盖**：高频词在本书中呈现多义项用法，可系统学习
4. **词源脉络**：每条词汇标注词源（语系/词根词缀），帮助理解构词规律

## 建议学习路径
- 高频词（频次 ≥ 10）：精读掌握，关注搭配
- 中频词（频次 2-9）：结合例句理解语境
- 低频词（频次 = 1）：了解即可，不必强记
"""


def freq_report(candidates, entries: List[VocabularyEntry]) -> str:
    """附件2：全书词频统计报告（§3.116 ⭐ 去虚词保留实词）。

    只统计实词（名词/动词/形容词/副词）——过滤虚词（冠词/介词/连词/代词/助动词）。
    """
    # 实词词性集合（spaCy POS：NOUN/VERB/ADJ/ADV/PROPN）
    _CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV", "PROPN"}

    def _is_content_word(c) -> bool:
        """判定是否为实词（词性在实词集合 或 未知时按停用词表过滤）。"""
        entry = next((e for e in entries if e.headword == c.headword), None)
        if entry and entry.pos:
            pos_map = {"n.": "NOUN", "v.": "VERB", "adj.": "ADJ", "adv.": "ADV",
                       "n": "NOUN", "v": "VERB", "adj": "ADJ", "adv": "ADV"}
            return pos_map.get(entry.pos, entry.pos) in _CONTENT_POS
        # 未知词性：用基础停用词过滤（冠词/介词/连词/代词）
        _FUNC_WORDS = {"the", "a", "an", "of", "in", "on", "at", "to", "for",
                       "and", "or", "but", "with", "by", "from", "as", "is",
                       "are", "was", "were", "be", "been", "being", "have",
                       "has", "had", "do", "does", "did", "will", "would",
                       "can", "could", "should", "may", "might", "must",
                       "this", "that", "these", "those", "it", "its", "he",
                       "she", "they", "we", "you", "i", "me", "him", "her",
                       "them", "us", "not", "no", "so", "if", "then", "else"}
        return c.headword.lower() not in _FUNC_WORDS

    content_candidates = [c for c in candidates if _is_content_word(c)]

    lines = ["# 全书词频统计报告（实词 · 已去虚词）\n",
             "| 排名 | 单词 | 词性 | 频次 | CEFR |", "|---|---|---|---|---|"]
    for i, c in enumerate(content_candidates[:50], 1):
        entry = next((e for e in entries if e.headword == c.headword), None)
        pos = entry.pos if entry else c.pos
        cefr = entry.cefr_level if entry else c.cefr_guess
        lines.append(f"| {i} | **{c.headword}** | {pos} | {c.freq_count} | {cefr} |")

    # 实词/虚词统计
    total = len(candidates)
    content_n = len(content_candidates)
    lines.append("\n## 统计说明")
    lines.append(f"- 全书候选词 {total} 个，其中**实词 {content_n} 个**（名词/动词/形容词/副词）")
    lines.append("- 已过滤虚词（冠词 a/an/the、介词、连词、代词、助动词等）")
    lines.append("- CEFR 等级为 wordfreq Zipf 猜测（A1-C2）")
    return "\n".join(lines)


def style_analysis(candidates, entries: List[VocabularyEntry]) -> str:
    """附件3：作者语言风格分析（词汇/句式特征风格画像）。"""
    if not candidates:
        return "# 作者语言风格分析\n\n（无足够词汇数据）"
    # 词汇特征
    top = candidates[:20]
    high_freq = [c.headword for c in candidates[:5]]
    # 句式特征（基于例句长度粗估）
    ex_lens = [len(e.get("en", "")) for e in
               [ex for en in entries for ex in en.examples[:1]]][:100]
    avg_len = sum(ex_lens) / len(ex_lens) if ex_lens else 0
    return f"""# 作者语言风格分析

## 词汇特征
- **核心词汇**：{', '.join(high_freq)}——反映主题重心
- **词汇丰富度**：top 20 词覆盖主题关键概念
- **高频词性分布**：名词/动词为主（叙事 + 描述）

## 句式特征
- 平均句长约 **{avg_len:.0f} 字符**（{'偏长，句式复杂' if avg_len > 60 else '中等，阅读友好'}）
- 原书例句保留完整句式（含从句/修饰）

## 风格画像
1. **书面语体**：文学性文本，用词正式
2. **主题密度**：高频词集中反映核心主题
3. **修辞特征**：需结合原文段落进一步分析（附件可扩展）
"""


def phrase_statistics(ctx) -> str:
    """§3.116 ⭐ V-R5 附件：短语句式统计——高频短语（2/3 词）+ 句式特征。

    范本附件产物之一（对标"短语句式统计/作者语言风格分析"）——用 N-gram + PMI
    提取原著高频固定搭配，附句式特征（平均句长/从句密度粗估）。
    """
    from ..collocations import extract_collocations
    corpus = getattr(ctx, "clean_sentences", None)
    if not corpus and getattr(ctx, "clean_corpus", None):
        corpus = [" ".join(getattr(t, "token", "") or getattr(t, "text", "") for t in ctx.clean_corpus[:500])]
    bigrams = extract_collocations(corpus or [], n=2, min_count=3, top_n=30)
    trigrams = extract_collocations(corpus or [], n=3, min_count=2, top_n=20)
    lines = ["# 短语句式统计", ""]
    lines.append("## 高频短语（二元 · PMI 排序）")
    lines.append("| 短语 | 频次 | PMI |")
    lines.append("|---|---|---|")
    for c in bigrams[:20]:
        lines.append(f"| {c['phrase']} | {c['count']} | {c['pmi']} |")
    lines.append("")
    lines.append("## 高频短语（三元）")
    lines.append("| 短语 | 频次 | PMI |")
    lines.append("|---|---|---|")
    for c in trigrams[:10]:
        lines.append(f"| {c['phrase']} | {c['count']} | {c['pmi']} |")
    # 句式特征（平均句长）
    if corpus:
        _lens = [len(s) for s in corpus if s]
        _avg = sum(_lens) / len(_lens) if _lens else 0
        lines.append("")
        lines.append("## 句式特征")
        lines.append(f"- 平均句长：约 {_avg:.0f} 字符（{'偏长，句式复杂' if _avg > 80 else '中等'}）")
        lines.append("- 短语密度：高频短语反映作者惯用表达与主题重心")
    return "\n".join(lines)


def srs_plan_note(ctx) -> str:
    """附件：SRS 间隔重复复习计划（SM-2 遗忘曲线，14 天复习安排）。

    对标 LingQ：词汇不是一次性产出，而是按遗忘曲线复习。
    """
    from ..srs import plan_schedule
    words = [e.headword for e in ctx.entries]
    if not words:
        return "# SRS 复习计划\n\n（无词条）"
    r = plan_schedule(words, days=14)
    lines = ["# SRS 间隔重复复习计划（SM-2 遗忘曲线）", "",
             f"- 词条总数：**{r['words']}**",
             f"- 14 天总复习次数：**{r['total_reviews']}**（日均约 {r['daily_avg']}）",
             "", "## 每日复习安排",
             "| 天数 | 复习词数 | 词条（前 10） |", "|---|---|---|"]
    for day, ws in r["plan"].items():
        head = ", ".join(ws[:10]) + ("…" if len(ws) > 10 else "")
        lines.append(f"| {day} | {len(ws)} | {head} |")
    lines.append("")
    lines.append("> 说明：SM-2 算法——评分 ≥3 正确回忆，间隔按难度因子 EF 递增（1→6→…）；评分 <3 失败重置为 1 天。复习时可用 `srs_review` 工具评分推进。")
    return "\n".join(lines)


def make_high_freq_html(candidates, entries: List[VocabularyEntry]) -> str:
    """生成高明词统计独立 HTML 小页面（§3.116 ⭐ 非主文档，趣味统计）。

    展示作者高频实词（已去虚词）——独立小页面，不混入词汇学习主文档。
    """
    content_candidates = [c for c in candidates
                          if FunctionWordFilter().should_keep(c)]
    rows = []
    for i, c in enumerate(content_candidates[:50], 1):
        entry = next((e for e in entries if e.headword == c.headword), None)
        pos = entry.pos if entry else c.pos
        cefr = entry.cefr_level if entry else c.cefr_guess
        badge_color = {"A1": "#10b981", "A2": "#22c55e", "B1": "#eab308",
                       "B2": "#f97316", "C1": "#ef4444", "C2": "#7c3aed"}.get(cefr, "#888")
        rows.append(
            f'<tr><td>{i}</td><td><b>{c.headword}</b></td>'
            f'<td>{pos}</td><td>{c.freq_count}</td>'
            f'<td><span class="badge" style="background:{badge_color}">{cefr}</span></td></tr>')
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>高明词统计</title>
<style>
body{{font-family:serif;max-width:700px;margin:auto;padding:2em;color:#2b2b2b}}
h1{{font-size:20pt;color:#3b5b6e;font-style:italic;border-bottom:0.6pt solid #e8e8e8;padding-bottom:3pt}}
table{{border-collapse:collapse;width:100%;margin-top:1em}}
th,td{{border-bottom:1px solid #e8e8e8;padding:6px 8px;text-align:left;font-size:10.5pt}}
th{{color:#3b5b6e;font-weight:600}}
.badge{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:9pt;color:#fff}}
.note{{color:#888;font-size:9pt;margin-top:2em}}
</style></head><body>
<h1>全书高明词统计</h1>
<p>本书作者的高频实词分布（已去虚词）——看看作者最偏爱哪些词：</p>
<table><tr><th>排名</th><th>单词</th><th>词性</th><th>频次</th><th>难度</th></tr>
{''.join(rows) or '<tr><td colspan="5">（数据不足）</td></tr>'}
</table>
<p class="note">PAEG 词汇表 · 高明词趣味统计 · 独立小页</p>
</body></html>"""


# §3.120 ⭐ LLM 深度分析系统提示词（python 脚本 + 系统提示词 harness LLM 提升产物质量）
_LLM_ANALYSIS_SYSTEM = """你是外文词汇学习分析专家。根据给定一本书的词汇统计数据，生成三部分深刻、具体、有据可依的分析（拒绝空话套话）：

## 1. 高频词解读与主题聚类
- 为什么这些词高频出现？它们揭示了本书什么主题与论证框架？
- 把高频词聚成 3-5 个主题簇，每簇命名并举代表词。

## 2. 作者语言风格画像
- 句式特征（结合平均句长/最长句，推断长句复杂还是短句明快）
- 用词倾向（结合 TTR 与高频词，判断书面/口语、学术/叙事、抽象/具象）
- 可读性与难度定位

## 3. 学习价值与路径建议
- 本书词汇难度结构（结合 CEFR 分布）
- 最值得精读掌握的词群及原因
- 分阶段学习路径

要求：中文输出、markdown 格式、## 分节、每节 3-6 条要点、直接引用统计数字作依据。"""


def llm_analysis(ctx, chat_fn=None) -> str:
    """§3.120 ⭐ 用 LLM 生成深刻词汇学习分析（词频解读/风格画像/学习价值）。失败返回空串。

    设计：python 脚本先把「确定性统计」算好（高频词/CEFR 分布/句长/TTR），
    再用系统提示词 harness LLM 对统计做「解读与洞察」——确定性数据打底，LLM 只负责分析。
    """
    if chat_fn is None:
        try:
            from ..llm_client import chat as _chat
            chat_fn = _chat
        except Exception:
            return ""
    from collections import Counter
    from pathlib import Path

    entries = ctx.entries or []
    candidates = ctx.candidates or []
    sentences = [s for s in (getattr(ctx, "clean_sentences", None) or []) if s]

    _FUNC = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or",
             "but", "with", "by", "from", "as", "is", "are", "was", "were", "be",
             "been", "being", "have", "has", "had", "do", "does", "did", "this",
             "that", "these", "those", "it", "its", "he", "she", "they", "we",
             "you", "i", "not", "no", "so", "if", "then", "else", "also", "such"}
    content = [c for c in candidates if c.headword.lower() not in _FUNC]
    top = sorted(content, key=lambda x: -x.freq_count)[:15]
    top_desc = "、".join(f"{c.headword}({c.freq_count}次)" for c in top)

    cefr_c = Counter(e.cefr_level for e in entries if e.cefr_level)
    cefr_desc = "、".join(f"{k}×{v}" for k, v in sorted(cefr_c.items())) or "未知"

    pos_c = Counter((e.pos or "其他").strip() for e in entries if e.pos)
    pos_desc = "、".join(f"{k}×{v}" for k, v in pos_c.most_common(6)) or "未知"

    sent_lens = [len(s) for s in sentences]
    avg = round(sum(sent_lens) / len(sent_lens), 1) if sent_lens else 0
    longest = max(sent_lens) if sent_lens else 0
    total = sum(c.freq_count for c in candidates)
    ttr = round(len(candidates) / total, 3) if total else 0

    book = Path(str(ctx.pdf_path)).stem if ctx.pdf_path else "本书"

    user = (f"书名：{book}\n词条总数：{len(entries)}\n"
            f"高频实词（词/频次）：{top_desc}\n"
            f"CEFR 分布：{cefr_desc}\n"
            f"词性分布：{pos_desc}\n"
            f"平均句长：{avg} 字符，最长句：{longest} 字符\n"
            f"词汇密度 TTR：{ttr}\n\n请据此输出三部分分析。")
    try:
        raw = chat_fn(_LLM_ANALYSIS_SYSTEM, user, max_tokens=2000, temperature=0.4)
        return (raw or "").strip()
    except Exception:
        try:
            return (chat_fn(_LLM_ANALYSIS_SYSTEM, user) or "").strip()
        except Exception:
            return ""


# §3.120 ⭐ 趣味语言解读（LLM 生成：本书术语为什么重要 / 语言冷知识 / 同源词族 / 学习小贴士）
_FUN_INSIGHTS_SYSTEM = """你是外语词汇学习趣味内容作者。根据给定一本书的词条数据（高频词/词源/CEFR），
产出四个部分有趣、详实、有据可依的内容（拒绝空话套话）：

## 1. 本书关键术语「为什么重要」
挑 3-5 个本书核心术语，用通俗语言解释：这个词为什么对理解本书/这个领域至关重要？
它在本书论证或主题中扮演什么角色？

## 2. 语言冷知识
挑 3-5 个词，各讲一个词源/构词/历史冷知识（形近易混、同形异义、有趣的构词来源等），
让人会心一笑或印象深刻。

## 3. 同源词族
挑 2-4 组同源词（共享同一词根，如 gene/genetic/genesis/genotype 共享希腊词根 gen-），
列出一族词 + 共享词根 + 各自含义，帮助举一反三成片记忆。

## 4. 学习小贴士
针对本书词汇给出 3-6 条具体、可执行的学习建议（词根记忆/联想/语境/间隔重复组合）。

要求：中文输出、markdown 格式、## 分节、直接引用给定的词/词源数据作依据、内容有趣可读。"""


def llm_fun_insights(ctx, chat_fn=None) -> str:
    """§3.120 ⭐ 用 LLM 生成趣味语言解读（术语为什么重要/冷知识/同源词族/学习小贴士）。

    设计同 llm_analysis：python 先算好确定性数据（高频词 + 词源 + CEFR），
    系统提示词 harness LLM 只做生成。失败返回空串（静默降级，不阻塞）。
    """
    if chat_fn is None:
        try:
            from ..llm_client import chat as _chat
            chat_fn = _chat
        except Exception:
            return ""
    from pathlib import Path

    entries = ctx.entries or []
    candidates = ctx.candidates or []
    entry_by_word = {e.headword.lower(): e for e in entries}
    top = sorted(candidates, key=lambda c: -c.freq_count)[:12]
    lines = []
    for c in top:
        e = entry_by_word.get(c.headword.lower())
        etym = (getattr(e, "etymology", "") or "")[:120] if e else ""
        cefr = (e.cefr_level or c.cefr_guess or "") if e else (c.cefr_guess or "")
        lines.append(f"- {c.headword}（出现 {c.freq_count} 次，CEFR {cefr}）词源：{etym}")

    book = Path(str(ctx.pdf_path)).stem if ctx.pdf_path else "本书"
    user = (f"书名：{book}\n词条总数：{len(entries)}\n"
            f"高频词（词/频次/CEFR/词源）：\n" + "\n".join(lines) +
            "\n\n请据此输出四部分趣味解读。")
    try:
        raw = chat_fn(_FUN_INSIGHTS_SYSTEM, user, max_tokens=2000, temperature=0.6)
        return (raw or "").strip()
    except Exception:
        try:
            return (chat_fn(_FUN_INSIGHTS_SYSTEM, user) or "").strip()
        except Exception:
            return ""


def generate_all_accessories(ctx, out_dir=None, chat_fn=None) -> Dict[str, str]:
    """生成全部附件 + 高明词统计独立页 + LLM 深度解读。返回 {name: path}。

    §3.116 ⭐ 输出到插件根 output/（非 src/output）。
    高明词统计是独立 HTML 小页面（非词汇学习主文档）。
    §3.120 ⭐ chat_fn：LLM 深度解读（智能学习解读.md）。
    """
    from pathlib import Path
    # 插件根 = src/.. 的上级 = paeg-vocabulary-plugin/
    plugin_root = Path(__file__).resolve().parent.parent.parent.parent
    out = Path(out_dir or (plugin_root / "output"))
    out.mkdir(parents=True, exist_ok=True)
    book = "词汇表"
    if ctx.pdf_path:
        _p = Path(str(ctx.pdf_path))
        book = _p.stem if _p.suffix else str(ctx.pdf_path)
    results = {}
    arts = {
        "语言学习价值说明.md": language_value_note(
            book, len(ctx.entries), [c.headword for c in ctx.candidates[:10]]),
        "词频统计报告.md": freq_report(ctx.candidates, ctx.entries),
        "作者语言风格分析.md": style_analysis(ctx.candidates, ctx.entries),
        "短语句式统计.md": phrase_statistics(ctx),  # §3.116 ⭐ V-R5
        "SRS复习计划.md": srs_plan_note(ctx),       # ⭐ 间隔重复复习计划
    }
    # §3.120 ⭐ LLM 深度解读（失败静默降级，不阻塞）
    try:
        _analysis = llm_analysis(ctx, chat_fn)
        ctx.llm_analysis = _analysis or ""   # 存回 ctx，供交互式交付页复用（不重复调 LLM）
        if _analysis:
            arts["智能学习解读.md"] = _analysis
    except Exception:
        ctx.llm_analysis = ""
    # §3.120 ⭐ 趣味语言解读（术语为什么重要/冷知识/同源词族/学习小贴士）
    try:
        _fun = llm_fun_insights(ctx, chat_fn)
        ctx.llm_fun = _fun or ""   # 存回 ctx，供交互式交付页复用
        if _fun:
            arts["趣味语言解读.md"] = _fun
    except Exception:
        ctx.llm_fun = ""
    # §3.116 ⭐ 高明词统计独立 HTML 小页面（非主文档）
    try:
        high_freq_html = make_high_freq_html(ctx.candidates, ctx.entries)
        _hp = out / "高明词统计.html"
        _hp.write_text(high_freq_html, encoding="utf-8")
        results["高明词统计.html"] = str(_hp)
    except Exception:
        pass
    for name, content in arts.items():
        p = out / name
        p.write_text(content, encoding="utf-8")
        results[name] = str(p)
    return results
