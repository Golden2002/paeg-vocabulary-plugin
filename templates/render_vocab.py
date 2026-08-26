# -*- coding: utf-8 -*-
"""词汇表渲染脚本（复用包版）——原版模板 + 新数据 → 新 HTML → PDF。

用法：
  1. 把词条数据放到本目录 data.json（格式见 README）
  2. 把原版 HTML 模板放到本目录（模板_XXX_原版.html）
  3. 修改 BOOKS 配置
  4. python render_vocab.py
"""
import io, sys, json, os, re, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── 路径（相对本目录，可整体拷贝复用）──
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "..", "output")          # PDF/HTML 输出
IN = os.path.join(BASE, "数据_优化词条.json")       # 词条数据（可替换）
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def morpheme_str(m):
    if not isinstance(m, dict):
        return ""
    parts = []
    pre = m.get("prefix")
    if isinstance(pre, dict):
        parts.append(f"{pre.get('p','')}「{pre.get('meaning','')}」")
    elif isinstance(pre, str) and pre:
        parts.append(pre)
    for r in (m.get("roots") or []):
        if isinstance(r, dict):
            parts.append(f"{r.get('root','')}({r.get('lang','')}「{r.get('meaning','')}」)")
        elif isinstance(r, str) and r:
            parts.append(r)
    suf = m.get("suffix")
    if isinstance(suf, dict):
        parts.append(f"{suf.get('s','')}「{suf.get('meaning','')}」")
    elif isinstance(suf, str) and suf:
        parts.append(suf)
    return " + ".join(parts) if parts else ""

def build_entries(items):
    items = sorted(items, key=lambda x: str(x.get("word", "")).lower())
    out = []
    cur = ""
    for it in items:
        w = str(it.get("word", ""))
        if not w:
            continue
        letter = w[0].upper()
        if letter != cur:
            cur = letter
            out.append(f'<h2 class="alpha-header">{letter}</h2>')
        mstr = morpheme_str(it.get("morpheme"))
        e = ['<article class="entry">']
        e.append(f'  <header class="headword"><span class="word">{esc(w)}</span><span class="pos">{esc(it.get("pos",""))}</span></header>')
        if it.get("zh"):
            e.append(f'  <div class="zh-def">{esc(it.get("zh"))}</div>')
        if it.get("en"):
            e.append(f'  <div class="en-def">{esc(it.get("en"))}</div>')
        ety = str(it.get("etymology", ""))
        if ety:
            e.append(f'  <div class="etymology">{esc(ety)}</div>')
        if mstr:
            e.append(f'  <div class="morpheme">构词：{esc(mstr)}</div>')
        ex = str(it.get("example", ""))
        if ex:
            e.append(f'  <div class="example">{esc(ex)}</div>')
        elif it.get("example_source") == "needs_manual":
            e.append('  <div class="example">（例句待人工补充）</div>')
        e.append("</article>")
        out.append("\n".join(e))
    return "\n".join(out)

def build(orig_html_name, key, meta):
    orig = open(os.path.join(BASE, orig_html_name), encoding="utf-8-sig", errors="ignore").read()
    m = re.search(r'<main class="entries">', orig)
    if not m:
        print(f"❌ 模板未找到 main.entries: {orig_html_name}")
        return None
    prefix = orig[:m.end()]
    suffix = "</main>" if "</main>" in orig[m.end():] else "</body>"
    data = json.load(open(IN, encoding="utf-8"))
    items = data[key] if isinstance(data, dict) else data
    entries_html = build_entries(items)
    new_html = prefix + "\n" + entries_html + "\n" + suffix
    new_html = re.sub(r'共\s*[\d,]+\s*词', f"共 {len(items)} 词", new_html)
    os.makedirs(OUT, exist_ok=True)
    out_path = os.path.join(OUT, meta["html_file"])
    with open(out_path, "w", encoding="utf-8-sig") as f:
        f.write(new_html)
    print(f"✅ HTML: {meta['html_file']}（{len(items)} 词）")
    return out_path

FOOTER = """
<div style="font-size:9pt; color:#888; width:100%; padding:0 16mm; box-sizing:border-box;
            display:flex; justify-content:space-between;
            font-family:'Cambria','Georgia',serif; font-style:italic;">
  <span>Vocabulary Review</span>
  <span><span class="pageNumber"></span> / <span class="totalPages"></span></span>
</div>
"""

async def render(html_path, pdf_path):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME,
            args=["--font-render-hinting=none", "--disable-gpu"],
        )
        page = await browser.new_page()
        await page.goto("file:///" + html_path.replace("\\", "/"))
        await page.evaluate("document.fonts.ready")
        await page.emulate_media(media="print")
        await page.pdf(
            path=pdf_path,
            print_background=True,
            prefer_css_page_size=True,
            display_header_footer=True,
            header_template='<div style="display:none"></div>',
            footer_template=FOOTER,
            margin={"top": "18mm", "bottom": "22mm", "left": "16mm", "right": "16mm"},
        )
        await browser.close()
    print(f"✅ PDF: {os.path.basename(pdf_path)}")

# ── 配置：书 → 模板/数据 key/输出名 ──
BOOKS = [
    ("模板_生命现象_原版.html", "phenomenon_of_life",
     {"html_file": "《生命现象》词汇表_渲染版.html", "pdf_file": "《生命现象》词汇表_渲染版.pdf"}),
    ("模板_钟形罩_原版.html", "bell_jar_criticism",
     {"html_file": "《钟形罩》词汇表_渲染版.html", "pdf_file": "《钟形罩》词汇表_渲染版.pdf"}),
]

async def main():
    for orig_html, key, meta in BOOKS:
        html_path = build(orig_html, key, meta)
        if html_path:
            await render(html_path, os.path.join(OUT, meta["pdf_file"]))

if __name__ == "__main__":
    asyncio.run(main())
