# -*- coding: utf-8 -*-
"""HTML -> 精美 PDF (playwright + Chrome)"""
import os, sys, asyncio
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from playwright.async_api import async_playwright

OUT = r'D:\团聚体\桌面\英语教学\我的学习\output'
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

FOOTER = """
<div style="font-size:9pt; color:#888; width:100%; padding:0 16mm; box-sizing:border-box;
            display:flex; justify-content:space-between;
            font-family:'Cambria','Georgia',serif; font-style:italic;">
  <span>Vocabulary Review</span>
  <span><span class="pageNumber"></span> / <span class="totalPages"></span></span>
</div>
"""

async def render(html_path, pdf_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME,
            args=['--font-render-hinting=none', '--disable-gpu'],
        )
        page = await browser.new_page()
        await page.goto('file:///' + html_path.replace('\\', '/'))
        await page.evaluate('document.fonts.ready')
        await page.emulate_media(media='print')
        await page.pdf(
            path=pdf_path,
            print_background=True,
            prefer_css_page_size=True,
            display_header_footer=True,
            header_template='<div style="display:none"></div>',
            footer_template=FOOTER,
            margin={'top': '18mm', 'bottom': '22mm', 'left': '16mm', 'right': '16mm'},
        )
        await browser.close()
    print(f'PDF 生成: {pdf_path}')

async def main():
    htmls = sorted([f for f in os.listdir(OUT) if f.endswith('.html')])
    for html_name in htmls:
        html_path = os.path.join(OUT, html_name)
        pdf_path = os.path.join(OUT, html_name.replace('.html', '.pdf'))
        if os.path.exists(html_path):
            await render(html_path, pdf_path)
        else:
            print(f'缺失: {html_path}')

asyncio.run(main())
