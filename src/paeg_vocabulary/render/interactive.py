# -*- coding: utf-8 -*-
"""paeg_vocabulary.render.interactive — 词汇表交互式交付单页（§3.119 ⭐ 自包含、可公网部署）。

用户反馈（2026-08-31）：
1. 附件（词频/风格/学习价值）内容少、质量差、只有 markdown 交付。
2. 想要「一个按钮 + 好听的名字 + 点击展开的美化卡片（有趣统计/分析）」的 HTML 交付 + PDF。
3. 词汇表网页本身：能否公网部署？视觉/交互差？无点击展开/跳转到附加有趣信息。

交付形态：单个自包含 HTML 文件（数据 + CSS + JS 全内联，无后端依赖）——
- 可静态部署（GitHub Pages / 任意静态托管）或直接双击打开
- 顶部标签页：词汇表 / 词频统计 / 作者风格 / 学习价值 / 短语句式 / 高明词 / SRS 计划
- 词汇表：分页 + 搜索 + CEFR 筛选 + 点击展开词条详情 + SRS 三态（localStorage 记忆）
- 附件：卡片式、点击展开/收起、含 CSS 柱状图（CEFR 分布/POS 分布）、排名表
- 「导出 PDF」按钮：window.print() + @media print 打印样式
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.context import VocabularyContext

_CONTENT_POS = {"n.", "v.", "adj.", "adv.", "noun", "verb", "adjective", "adverb"}
_FUNC_WORDS = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or",
               "but", "with", "by", "from", "as", "is", "are", "was", "were", "be",
               "been", "being", "have", "has", "had", "do", "does", "did", "will",
               "would", "can", "could", "should", "may", "might", "must", "this",
               "that", "these", "those", "it", "its", "he", "she", "they", "we",
               "you", "i", "me", "him", "her", "them", "us", "not", "no", "so",
               "if", "then", "else", "also", "such", "there", "here", "what",
               "which", "who", "whom", "when", "where", "how", "why"}

_CEFR_COLORS = {"A1": "#10b981", "A2": "#22c55e", "B1": "#eab308",
                "B2": "#f97316", "C1": "#ef4444", "C2": "#7c3aed"}


def _norm_pos(pos: str) -> str:
    p = (pos or "").strip().lower().rstrip(".")
    m = {"n": "n.", "noun": "n.", "v": "v.", "verb": "v.", "vt": "v.", "vi": "v.",
         "adj": "adj.", "a": "adj.", "adjective": "adj.", "adv": "adv.", "r": "adv.",
         "adverb": "adv."}
    return m.get(p, pos or "其他")


def _is_content(c) -> bool:
    return c.headword.lower() not in _FUNC_WORDS


def _entry_dict(e) -> Dict[str, Any]:
    g = e.gloss_bilingual or {}
    return {
        "w": e.headword, "pos": _norm_pos(e.pos), "ipa": (e.ipa or {}).get("en_us", ""),
        "zh": g.get("zh", ""), "en": g.get("en", ""),
        "cefr": e.cefr_level or "", "freq": getattr(e, "freq_rank", 0) or 0,
        "etym": getattr(e, "etymology", "") or "",
        "ex": (e.examples or [])[:2], "col": (e.collocations or [])[:4],
    }


def _compute_stats(ctx: VocabularyContext) -> Dict[str, Any]:
    entries = ctx.entries or []
    candidates = ctx.candidates or []
    sentences = [s for s in (getattr(ctx, "clean_sentences", None) or []) if s]

    # 实词候选（去虚词）
    content = [c for c in candidates if _is_content(c)]

    # 词频 Top（候选 freq_count 排序）
    top_words = []
    for i, c in enumerate(sorted(content, key=lambda x: -x.freq_count)[:30], 1):
        e = next((x for x in entries if x.headword == c.headword), None)
        top_words.append({
            "rank": i, "w": c.headword,
            "pos": _norm_pos(e.pos) if e else _norm_pos(c.pos),
            "freq": c.freq_count,
            "cefr": (e.cefr_level if e else c.cefr_guess) or "",
        })

    # POS 分布（词条）
    pos_counter = Counter(_norm_pos(e.pos) for e in entries if e.pos)
    pos_total = sum(pos_counter.values()) or 1
    pos_dist = [{"pos": k, "n": v, "pct": round(v / pos_total * 100)} for k, v in
                pos_counter.most_common(6)]

    # CEFR 分布（词条）
    cefr_counter = Counter(e.cefr_level for e in entries if e.cefr_level)
    cefr_total = sum(cefr_counter.values()) or 1
    order = ["A1", "A2", "B1", "B2", "C1", "C2"]
    cefr_dist = [{"lv": lv, "n": cefr_counter.get(lv, 0),
                  "pct": round(cefr_counter.get(lv, 0) / cefr_total * 100),
                  "color": _CEFR_COLORS.get(lv, "#888")} for lv in order
                 if cefr_counter.get(lv, 0) > 0]

    # 全书统计
    total_tokens = sum(c.freq_count for c in candidates)
    unique = len(candidates)
    ttr = round(unique / total_tokens, 3) if total_tokens else 0
    avg_sent = round(sum(len(s) for s in sentences) / len(sentences), 1) if sentences else 0
    longest = max((len(s) for s in sentences), default=0)

    # 短语（二元）
    try:
        from ..collocations import extract_collocations
        bigrams = extract_collocations(sentences, n=2, min_count=2, top_n=12)
    except Exception:
        bigrams = []

    # SRS 计划
    try:
        from ..srs import plan_schedule
        srs = plan_schedule([e.headword for e in entries], days=14)
    except Exception:
        srs = {"plan": {}, "total_reviews": 0, "words": len(entries), "daily_avg": 0}

    # 学习价值：高频/中频/低频分段
    high = sum(1 for c in content if c.freq_count >= 10)
    mid = sum(1 for c in content if 2 <= c.freq_count < 10)
    low = sum(1 for c in content if c.freq_count == 1)

    return {
        "entries": [_entry_dict(e) for e in entries[:300]],
        "total": len(entries),
        "top_words": top_words,
        "pos_dist": pos_dist,
        "cefr_dist": cefr_dist,
        "total_tokens": total_tokens,
        "unique": unique,
        "ttr": ttr,
        "avg_sent": avg_sent,
        "longest": longest,
        "bigrams": [{"p": b["phrase"], "n": b["count"], "pmi": b["pmi"]} for b in bigrams],
        "high": high, "mid": mid, "low": low,
        "srs": {"plan": srs.get("plan", {}), "total_reviews": srs.get("total_reviews", 0),
                "daily_avg": srs.get("daily_avg", 0)},
        "book": str(ctx.pdf_path or ""),
    }


def render_interactive_html(ctx: VocabularyContext, out_dir: Optional[str] = None,
                            book_title: str = "") -> Optional[str]:
    """生成自包含交互式交付单页，返回文件路径。"""
    if not ctx.entries:
        return None
    stats = _compute_stats(ctx)
    title = book_title or Path(str(ctx.pdf_path or "词汇表")).stem

    # 数据注入（转义 </script> 防注入破坏）
    data_json = json.dumps(stats, ensure_ascii=False).replace("</", "<\\/")

    html = _HTML_TEMPLATE.replace("__TITLE__", _esc(title)).replace("__DATA__", data_json)

    out = Path(out_dir or _default_out_dir())
    out.mkdir(parents=True, exist_ok=True)
    name = _safe_name(title) + "_词汇表_交互版.html"
    p = out / name
    p.write_text(html, encoding="utf-8")
    return str(p)


def _safe_name(s: str) -> str:
    keep = "".join(ch for ch in s if ch.isalnum() or ch in " _-()（）")
    return (keep.strip() or "vocabulary")[:60]


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _default_out_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent / "output"


# ═══════════════════════════════════════════════════════════════
# 自包含 HTML 模板（__TITLE__ / __DATA__ 占位符）
# ═══════════════════════════════════════════════════════════════
_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__ · 词汇表</title>
<style>
:root{--bg:#f7f8fa;--card:#fff;--ink:#1a1a1a;--mut:#6b7280;--brand:#2563eb;--line:#e5e7eb;
--new:#3b82f6;--learning:#f59e0b;--mastered:#10b981}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);line-height:1.65}
.cover{background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);color:#fff;padding:44px 28px 36px;text-align:center}
.cover h1{font-size:28px;font-weight:700;letter-spacing:.01em}
.cover .sub{opacity:.85;margin-top:8px;font-size:14px}
.cover .stats{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:20px}
.cover .stat{background:rgba(255,255,255,.14);border-radius:12px;padding:10px 18px;min-width:96px}
.cover .stat b{display:block;font-size:20px}
.cover .stat span{font-size:12px;opacity:.85}
nav{position:sticky;top:0;z-index:20;background:var(--card);border-bottom:1px solid var(--line);display:flex;overflow-x:auto;gap:2px;padding:0 12px}
nav button{flex:0 0 auto;border:none;background:none;padding:13px 16px;font-size:14px;color:var(--mut);cursor:pointer;border-bottom:2.5px solid transparent;white-space:nowrap}
nav button:hover{color:var(--ink)}
nav button.active{color:var(--brand);border-bottom-color:var(--brand);font-weight:600}
.wrap{max-width:960px;margin:0 auto;padding:22px 16px 80px}
section{display:none}
section.active{display:block}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
.toolbar input{flex:1;min-width:180px;padding:9px 12px;border:1px solid var(--line);border-radius:9px;font-size:13px}
.toolbar .filters{display:flex;gap:6px;flex-wrap:wrap}
.chip{padding:6px 13px;border:1px solid var(--line);border-radius:999px;font-size:12.5px;cursor:pointer;background:var(--card);color:var(--mut)}
.chip.active{background:var(--ink);color:#fff;border-color:var(--ink)}
.entry{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin-bottom:8px;cursor:pointer;border-left:4px solid var(--new);transition:.15s}
.entry:hover{box-shadow:0 3px 12px rgba(0,0,0,.07)}
.entry.learning{border-left-color:var(--learning)}.entry.mastered{border-left-color:var(--mastered)}
.entry .top{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.entry .w{font-size:17px;font-weight:700}
.entry .pos{font-size:12px;color:var(--brand);font-weight:600}
.entry .ipa{font-family:Consolas,monospace;font-size:12.5px;color:var(--mut)}
.entry .zh{font-size:13.5px;color:#374151;margin-top:4px}
.entry .meta{display:flex;gap:6px;align-items:center;margin-left:auto}
.cefr{font-size:10.5px;font-weight:700;color:#fff;padding:1px 7px;border-radius:4px}
.freq{font-size:10.5px;color:var(--mut);border:1px solid var(--line);padding:1px 7px;border-radius:4px}
.detail{display:none;border-top:1px solid var(--line);margin-top:10px;padding-top:10px;font-size:13px}
.entry.open .detail{display:block}
.detail .row{margin:6px 0}.detail .lab{font-weight:600;color:var(--brand);font-size:12px}
.detail .ex{font-style:italic;color:#374151;margin:3px 0 3px 8px;border-left:2px solid var(--line);padding-left:8px}
.detail .ex .z{font-style:normal;color:var(--mut)}
.srs{display:flex;gap:8px;margin-top:8px}
.srs button{font-size:12px;padding:4px 12px;border-radius:999px;border:1px solid var(--line);cursor:pointer;background:#fff}
.srs button.on-new{background:var(--new);color:#fff;border-color:var(--new)}
.srs button.on-learning{background:var(--learning);color:#fff;border-color:var(--learning)}
.srs button.on-mastered{background:var(--mastered);color:#fff;border-color:var(--mastered)}
.pager{display:flex;gap:8px;justify-content:center;align-items:center;margin-top:16px}
.pager button{padding:7px 15px;border:1px solid var(--line);border-radius:8px;background:var(--card);cursor:pointer;font-size:13px}
.pager button:disabled{opacity:.4;cursor:not-allowed}
.pager .info{font-size:13px;color:var(--mut)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;margin-bottom:12px;overflow:hidden}
.card>summary{list-style:none;cursor:pointer;padding:16px 20px;display:flex;align-items:center;gap:10px;font-size:15.5px;font-weight:600}
.card>summary::-webkit-details-marker{display:none}
.card>summary .ic{font-size:20px}
.card>summary .hint{font-size:12px;color:var(--mut);font-weight:400;margin-left:auto}
.card>summary .chev{margin-left:8px;transition:.2s}
.card[open]>summary .chev{transform:rotate(90deg)}
.card .body{padding:0 20px 20px}
table{width:100%;border-collapse:collapse;font-size:13px;margin:10px 0}
th,td{border-bottom:1px solid var(--line);padding:7px 10px;text-align:left}
th{color:var(--brand);font-weight:600;font-size:12px}
.bar-row{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:13px}
.bar-row .lb{width:44px;color:var(--mut)}
.bar-row .track{flex:1;height:16px;background:#f1f3f5;border-radius:8px;overflow:hidden}
.bar-row .fill{height:100%;border-radius:8px;transition:.4s}
.bar-row .val{width:52px;text-align:right;color:var(--mut);font-size:12px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:720px){.grid2{grid-template-columns:1fr}}
.stat-line{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px dashed var(--line);font-size:13.5px}
.stat-line span:first-child{color:var(--mut)}
.badge-row{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
.note{font-size:12.5px;color:var(--mut);background:#f8f9fb;border-left:3px solid var(--brand);padding:10px 14px;border-radius:0 8px 8px 0;margin:10px 0}
.print-btn{position:fixed;right:22px;bottom:22px;z-index:30;background:var(--brand);color:#fff;border:none;border-radius:999px;padding:12px 20px;font-size:14px;font-weight:600;cursor:pointer;box-shadow:0 4px 14px rgba(37,99,235,.35)}
.print-btn:hover{opacity:.92}
.empty{color:#c0c5cd;text-align:center;padding:50px 0}
@media print{
  nav,.print-btn,.toolbar,.pager{display:none!important}
  body{background:#fff}
  section{display:block!important}
  .card{border:none;page-break-inside:avoid}
  .entry{page-break-inside:avoid}
  .cover{background:#fff;color:#000;padding:20px 0}
  .cover .stat{background:#f1f3f5;color:#000}
}
</style>
</head>
<body>
<div class="cover">
  <h1>__TITLE__</h1>
  <div class="sub">交互式词汇学习表 · 词源助记 · 语境释义 · 间隔重复</div>
  <div class="stats" id="coverStats"></div>
</div>
<nav id="nav">
  <button data-t="vocab" class="active">词汇表</button>
  <button data-t="freq">词频统计</button>
  <button data-t="style">作者风格</button>
  <button data-t="value">学习价值</button>
  <button data-t="phrase">短语句式</button>
  <button data-t="highfreq">高明词</button>
  <button data-t="srs">SRS 计划</button>
</nav>
<div class="wrap">
  <section id="vocab" class="active">
    <div class="toolbar">
      <input id="q" placeholder="搜索单词 / 释义…" oninput="debLoad()">
      <div class="filters" id="filters">
        <span class="chip active" data-f="">全部</span>
        <span class="chip" data-f="new">生词</span>
        <span class="chip" data-f="learning">学习中</span>
        <span class="chip" data-f="mastered">已掌握</span>
      </div>
    </div>
    <div id="list"></div>
    <div class="pager">
      <button id="prev">← 上一页</button><span class="info" id="pi"></span><button id="next">下一页 →</button>
    </div>
  </section>
  <section id="freq"></section>
  <section id="style"></section>
  <section id="value"></section>
  <section id="phrase"></section>
  <section id="highfreq"></section>
  <section id="srs"></section>
</div>
<button class="print-btn" onclick="window.print()"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect width="12" height="8" x="6" y="14"/></svg> 导出 PDF</button>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const CEFR={A1:'#10b981',A2:'#22c55e',B1:'#eab308',B2:'#f97316',C1:'#ef4444',C2:'#7c3aed'};
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const ICONS={
 chart:'<line x1="12" x2="12" y1="20" y2="10"/><line x1="18" x2="18" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="16"/>',
 trend:'<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
 calc:'<rect width="16" height="20" x="4" y="2" rx="2"/><line x1="8" x2="16" y1="6" y2="6"/><line x1="16" x2="16" y1="14" y2="18"/><path d="M16 10h.01"/><path d="M12 10h.01"/><path d="M8 10h.01"/><path d="M12 14h.01"/><path d="M8 14h.01"/><path d="M12 18h.01"/><path d="M8 18h.01"/>',
 pen:'<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
 key:'<path d="m21 2-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/>',
 target:'<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
 map:'<polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"/><line x1="9" x2="9" y1="3" y2="18"/><line x1="15" x2="15" y1="6" y2="21"/>',
 link:'<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
 star:'<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
 repeat:'<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
 chevron:'<polyline points="9 18 15 12 9 6"/>'
};
function ic(n,s){return '<svg width="'+(s||18)+'" height="'+(s||18)+'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+(ICONS[n]||'')+'</svg>'}
const srsOf=w=>localStorage.getItem('srs_'+w)||'new';
const setSrs=(w,s)=>{localStorage.setItem('srs_'+w,s);renderList();};

// 封面统计
document.getElementById('coverStats').innerHTML=[
 ['词条总数',D.total],['全书词次',D.total_tokens],['去重词数',D.unique],['词汇密度 TTR',D.ttr]
].map(x=>`<div class="stat"><b>${x[1]}</b><span>${x[0]}</span></div>`).join('');

// 标签切换
document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('#nav button').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  document.querySelectorAll('section').forEach(s=>s.classList.remove('active'));
  document.getElementById(b.dataset.t).classList.add('active');
});

// 词汇表分页
let page=1,ps=20,q='',f='';
document.querySelectorAll('#filters .chip').forEach(c=>c.onclick=()=>{
  document.querySelectorAll('#filters .chip').forEach(x=>x.classList.remove('active'));
  c.classList.add('active');f=c.dataset.f;page=1;renderList();
});
let tmr;const debLoad=()=>{clearTimeout(tmr);tmr=setTimeout(()=>{q=document.getElementById('q').value.trim();page=1;renderList();},300)};

function renderList(){
  let arr=D.entries.slice();
  if(q)arr=arr.filter(e=>(e.w+' '+e.zh+' '+e.en).toLowerCase().includes(q.toLowerCase()));
  if(f)arr=arr.filter(e=>srsOf(e.w)===f);
  const pages=Math.max(1,Math.ceil(arr.length/ps));
  if(page>pages)page=pages;
  const chunk=arr.slice((page-1)*ps,page*ps);
  document.getElementById('list').innerHTML=chunk.length?chunk.map(e=>{
    const s=srsOf(e.w),c=(e.cefr||'').toUpperCase();
    const cefrHtml=c?`<span class="cefr" style="background:${CEFR[c]||'#888'}">${c}</span>`:'';
    const freqHtml=e.freq>0?`<span class="freq">频 ${e.freq}</span>`:'';
    const ex=(e.ex||[]).map(x=>`<div class="ex">${esc(x.en)}<div class="z">${esc(x.zh||'')}</div></div>`).join('');
    const col=(e.col||[]).map(esc).join(' · ');
    return `<div class="entry ${s}" onclick="this.classList.toggle('open')" data-w="${esc(e.w)}">
      <div class="top"><span class="w">${esc(e.w)}</span>${e.pos?`<span class="pos">${esc(e.pos)}</span>`:''}${e.ipa?`<span class="ipa">/${esc(e.ipa)}/</span>`:''}
      <span class="meta">${cefrHtml}${freqHtml}</span></div>
      <div class="zh">${esc(e.zh)}</div>
      <div class="detail">
        ${e.en?`<div class="row"><span class="lab">英文释义</span> ${esc(e.en)}</div>`:''}
        ${e.etym?`<div class="row"><span class="lab">词源</span> ${esc(e.etym)}</div>`:''}
        ${ex?`<div class="row"><span class="lab">例句</span>${ex}</div>`:''}
        ${col?`<div class="row"><span class="lab">搭配</span> ${col}</div>`:''}
        <div class="srs" onclick="event.stopPropagation()">
          <button class="${s==='new'?'on-new':''}" onclick="setSrs('${esc(e.w)}','new')">生词</button>
          <button class="${s==='learning'?'on-learning':''}" onclick="setSrs('${esc(e.w)}','learning')">学习中</button>
          <button class="${s==='mastered'?'on-mastered':''}" onclick="setSrs('${esc(e.w)}','mastered')">已掌握</button>
        </div>
      </div></div>`;
  }).join(''):'<div class="empty">没有匹配的词条</div>';
  document.getElementById('pi').textContent=`第 ${page} / ${pages} 页 · 共 ${arr.length} 词`;
  document.getElementById('prev').disabled=page<=1;
  document.getElementById('next').disabled=page>=pages;
}
document.getElementById('prev').onclick=()=>{page--;renderList()};
document.getElementById('next').onclick=()=>{page++;renderList()};

// 词频统计
document.getElementById('freq').innerHTML=`
  <div class="grid2">
    <details class="card"><summary><span class="ic">${ic('chart',18)}</span>高频实词 TOP 30<span class="hint">去虚词</span><span class="chev">${ic('chevron',14)}</span></summary><div class="body">
      <table><tr><th>#</th><th>单词</th><th>词性</th><th>频次</th><th>难度</th></tr>
      ${D.top_words.map(x=>`<tr><td>${x.rank}</td><td><b>${esc(x.w)}</b></td><td>${esc(x.pos)}</td><td>${x.freq}</td><td>${x.cefr?`<span class="cefr" style="background:${CEFR[x.cefr]||'#888'}">${x.cefr}</span>`:''}</td></tr>`).join('')}
      </table></div></details>
    <details class="card"><summary><span class="ic">${ic('trend',18)}</span>词性分布<span class="hint">${D.pos_dist.length} 类</span><span class="chev">${ic('chevron',14)}</span></summary><div class="body">
      ${D.pos_dist.map(x=>`<div class="bar-row"><span class="lb">${esc(x.pos)}</span><span class="track"><span class="fill" style="width:${x.pct}%;background:var(--brand)"></span></span><span class="val">${x.n} · ${x.pct}%</span></div>`).join('')}
    </div></details>
  </div>
  <details class="card"><summary><span class="ic">${ic('calc',18)}</span>全书词汇统计<span class="chev">${ic('chevron',14)}</span></summary><div class="body">
    <div class="stat-line"><span>全书总词次（token）</span><b>${D.total_tokens}</b></div>
    <div class="stat-line"><span>去重词数（unique）</span><b>${D.unique}</b></div>
    <div class="stat-line"><span>词汇密度 TTR（type-token ratio）</span><b>${D.ttr}</b></div>
    <div class="stat-line"><span>平均句长（字符）</span><b>${D.avg_sent}</b></div>
    <div class="stat-line"><span>最长句（字符）</span><b>${D.longest}</b></div>
    <div class="note">TTR 越高词汇越丰富：0.2 以下口语化，0.3–0.5 书面化，0.5 以上词汇非常多样。</div>
  </div></details>`;

// 作者风格
document.getElementById('style').innerHTML=`
  <details class="card"><summary><span class="ic">${ic('pen',18)}</span>风格画像<span class="chev">${ic('chevron',14)}</span></summary><div class="body">
    <div class="stat-line"><span>平均句长</span><b>${D.avg_sent} 字符（${D.avg_sent>80?'偏长，句式复杂、书面性强':D.avg_sent>50?'中等，阅读友好':'偏短，节奏明快'}）</b></div>
    <div class="stat-line"><span>词汇密度 TTR</span><b>${D.ttr}（${D.ttr>0.45?'词汇非常多样':D.ttr>0.3?'书面化、用词较丰富':'口语化、词汇集中'}）</b></div>
    <div class="stat-line"><span>最长句</span><b>${D.longest} 字符</b></div>
    <div class="note">高频词反映主题重心：<b>${D.top_words.slice(0,8).map(x=>esc(x.w)).join('、')}</b></div>
  </div></details>
  <details class="card"><summary><span class="ic">${ic('key',18)}</span>作者偏爱词（高频实词）<span class="chev">${ic('chevron',14)}</span></summary><div class="body">
    <div class="badge-row">${D.top_words.slice(0,15).map(x=>`<span class="freq">${esc(x.w)} ×${x.freq}</span>`).join('')}</div>
  </div></details>`;

// 学习价值
document.getElementById('value').innerHTML=`
  <details class="card"><summary><span class="ic">${ic('target',18)}</span>难度分布（CEFR）<span class="chev">${ic('chevron',14)}</span></summary><div class="body">
    ${D.cefr_dist.map(x=>`<div class="bar-row"><span class="lb">${x.lv}</span><span class="track"><span class="fill" style="width:${x.pct}%;background:${x.color}"></span></span><span class="val">${x.n} · ${x.pct}%</span></div>`).join('')||'<div class="empty">暂无 CEFR 分级数据</div>'}
  </div></details>
  <details class="card"><summary><span class="ic">${ic('map',18)}</span>建议学习路径<span class="chev">${ic('chevron',14)}</span></summary><div class="body">
    <div class="stat-line"><span>高频词（频次 ≥10，精读掌握）</span><b>${D.high} 个</b></div>
    <div class="stat-line"><span>中频词（2–9 次，结合语境）</span><b>${D.mid} 个</b></div>
    <div class="stat-line"><span>低频词（1 次，了解即可）</span><b>${D.low} 个</b></div>
    <div class="note">建议每日 30–50 词，先高频后低频；搭配 <b>SRS 计划</b> 标签页按遗忘曲线复习。</div>
  </div></details>`;

// 短语句式
document.getElementById('phrase').innerHTML=`
  <details class="card"><summary><span class="ic">${ic('link',18)}</span>高频短语（二元 · PMI 排序）<span class="chev">${ic('chevron',14)}</span></summary><div class="body">
    <table><tr><th>短语</th><th>频次</th><th>PMI</th></tr>
    ${D.bigrams.map(x=>`<tr><td>${esc(x.p)}</td><td>${x.n}</td><td>${x.pmi}</td></tr>`).join('')||'<tr><td colspan=3>（样本过短，无高频短语）</td></tr>'}
    </table>
    <div class="note">PMI 越高越像固定搭配；这些是作者惯用表达，值得整块记忆。</div>
  </div></details>`;

// 高明词
document.getElementById('highfreq').innerHTML=`
  <details class="card"><summary><span class="ic">${ic('star',18)}</span>全书高明词统计<span class="hint">高频实词</span><span class="chev">${ic('chevron',14)}</span></summary><div class="body">
    <table><tr><th>#</th><th>单词</th><th>词性</th><th>频次</th><th>难度</th></tr>
    ${D.top_words.map(x=>`<tr><td>${x.rank}</td><td><b>${esc(x.w)}</b></td><td>${esc(x.pos)}</td><td>${x.freq}</td><td>${x.cefr?`<span class="cefr" style="background:${CEFR[x.cefr]||'#888'}">${x.cefr}</span>`:''}</td></tr>`).join('')}
    </table></div></details>`;

// SRS 计划
const srsDays=Object.entries(D.srs.plan||{});
document.getElementById('srs').innerHTML=`
  <details class="card"><summary><span class="ic">${ic('repeat',18)}</span>间隔重复复习计划（SM-2 遗忘曲线）<span class="chev">${ic('chevron',14)}</span></summary><div class="body">
    <div class="stat-line"><span>词条总数</span><b>${D.total}</b></div>
    <div class="stat-line"><span>14 天总复习次数</span><b>${D.srs.total_reviews}（日均 ${D.srs.daily_avg}）</b></div>
    <table><tr><th>天数</th><th>复习词数</th><th>词条（前 10）</th></tr>
    ${srsDays.map(([d,ws])=>`<tr><td>${d.replace('day','第 ')} 天</td><td>${ws.length}</td><td>${ws.slice(0,10).map(esc).join(', ')}${ws.length>10?' …':''}</td></tr>`).join('')}
    </table>
    <div class="note">评分 ≥3 正确回忆、间隔按 EF 递增；评分 <3 失败重置 1 天。在词汇表标签页给词条标记「生词/学习中/已掌握」，进度自动保存在本机。</div>
  </div></details>`;

renderList();
</script>
</body>
</html>
"""
