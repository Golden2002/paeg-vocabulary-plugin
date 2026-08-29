# -*- coding: utf-8 -*-
"""交互网页浏览器端 E2E（Playwright）—— 翻页 / 点击查词 / SRS 三态。

覆盖 web/index.html（词条浏览：翻页 + 点击展开详情 + SRS 三态标记）
与 web/reader.html（点击查词阅读器：渲染文本 → 点击单词 → 查词面板）。

后端复用 Flask 内存态（web_api._LAST_ENTRIES 注入种子词条），不跑真实 PDF 生成，
因此本用例是纯前端交互回归（浏览器真实渲染 + 真实 HTTP fetch），秒级完成。

运行：`python -m pytest web/tests/test_e2e_browser.py -v`
（未安装 playwright 或 chromium 时自动跳过，不影响其余 194 用例。）
"""

from __future__ import annotations

import glob
import os
import re
import sys
import threading
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_WEB = os.path.dirname(_HERE)  # web 目录
if _WEB not in sys.path:
    sys.path.insert(0, _WEB)

from werkzeug.serving import make_server  # noqa: E402

from web_api import create_app  # noqa: E402
import web_api  # noqa: E402

playwright_sync = pytest.importorskip(
    "playwright.sync_api", reason="需要 playwright（pip install playwright）")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

PAGE_SIZE = 20
TOTAL = 45
EXPECTED_PAGES = 3


def _seed_entries(n: int) -> list:
    """构造确定性种子词条（字段对齐前端 render 与后端 /api/entries）。"""
    cefrs = ["A1", "A2", "B1", "B2", "C1"]
    out = []
    for i in range(n):
        out.append({
            "headword": f"word{i:03d}",
            "pos": "n.",
            "ipa": "wɜːd",
            "gloss_zh": f"测试词条 {i} 的中文释义",
            "gloss_en": f"test entry number {i}",
            "cefr": cefrs[i % len(cefrs)],
            "freq": i + 1,
            "etymology": f"来自测试语料 {i}",
            "examples": [{"en": f"This is example sentence {i}.",
                          "zh": f"这是例句 {i} 的翻译。"}],
            "collocations": [f"colloc-{i}", f"搭配{i}"],
        })
    return out


def _browser_executable() -> str | None:
    """定位一个可用的 Chromium/Chrome/Edge 二进制（自装 chromium 优先，系统浏览器兜底）。

    返回可执行文件绝对路径；找不到则返回 None（用于 skip，不把测试套件挂死在无浏览器环境）。
    """
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        for pat in (
            os.path.join(local, "ms-playwright", "chromium-*", "chrome-win64", "chrome.exe"),
            os.path.join(local, "ms-playwright", "chromium-*", "chrome-win", "chrome.exe"),
        ):
            for exe in glob.glob(pat):
                if os.path.exists(exe):
                    return exe
    for pth in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ):
        if os.path.exists(pth):
            return pth
    return None


pytestmark = pytest.mark.skipif(
    _browser_executable() is None,
    reason="无可用浏览器（playwright install chromium 或安装 Chrome/Edge）")


@pytest.fixture(scope="module")
def live_url():
    """模块级：后台线程启动一次 Flask 真实 HTTP 服务（临时端口）。"""
    web_api._LAST_ENTRIES = _seed_entries(TOTAL)
    web_api._LAST_BOOK = "Being Alive"
    web_api._SRS_STATE.clear()
    app = create_app()
    # threaded=True 对齐 web_api.py 的 app.run() 默认（Flask 生产式并发），
    # 否则单线程 + HTTP keep-alive 会让浏览器并发/后续请求排队，触发查词 12s 级延迟。
    server = make_server("127.0.0.1", 0, app, threaded=True)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    t.join(timeout=5)


@pytest.fixture(autouse=True)
def _reset_state():
    """每个用例前重置内存态，保证用例彼此独立。"""
    web_api._LAST_ENTRIES = _seed_entries(TOTAL)
    web_api._LAST_BOOK = "Being Alive"
    web_api._SRS_STATE.clear()
    yield


@pytest.fixture(scope="module")
def browser():
    """模块级：一个 chromium/chrome 实例（headless），函数级 page 各自独立上下文。"""
    p = sync_playwright().start()
    exe = _browser_executable()
    b = p.chromium.launch(headless=True, executable_path=exe)
    try:
        yield b
    finally:
        b.close()
        p.stop()


@pytest.fixture()
def page(browser, live_url):
    pg = browser.new_page()
    pg.set_default_timeout(10000)
    yield pg
    pg.close()


def _load_entries(page):
    """触发词条列表加载：点击「全部」Tab（等价真实用户交互，驱动 loadEntries）。"""
    page.click(".tab[data-s='']")
    page.wait_for_selector(".entry")


def _wait_warm(timeout: float = 45.0):
    """等待后台词库预热完成（测试与服务器同进程，直接读模块级 Event）。"""
    t0 = time.time()
    while not web_api._WORD_BANK_WARM.is_set():
        if time.time() - t0 > timeout:
            raise AssertionError(f"词库预热超时: {web_api._WORD_BANK_ERROR}")
        time.sleep(0.5)


# ── E2E-1：词条列表加载 + 分页信息 ────────────────────────────────
def test_index_loads_and_reports_pagination(page, live_url):
    page.goto(live_url + "/")
    _load_entries(page)
    # 首页应渲染满一页（20 条）
    expect(page.locator(".entry")).to_have_count(PAGE_SIZE)
    # 首页首词为 word000（种子顺序）
    expect(page.locator(".entry .word").first).to_have_text("word000")
    # 分页信息：第 1 / 3 页 · 共 45 词
    info = page.locator("#pageInfo").inner_text()
    assert f"第 1 / {EXPECTED_PAGES} 页" in info
    assert f"共 {TOTAL} 词" in info
    # 首页「上一页」禁用、「下一页」可用
    expect(page.locator("#prev")).to_be_disabled()
    expect(page.locator("#next")).to_be_enabled()


# ── E2E-2：翻页（下一页 / 上一页）──────────────────────────────
def test_pagination_next_prev(page, live_url):
    page.goto(live_url + "/")
    _load_entries(page)

    # 第 1 页 → 第 2 页（首词 word020）
    page.click("#next")
    expect(page.locator(".entry .word").first).to_have_text("word020")
    expect(page.locator("#pageInfo")).to_contain_text("第 2 / 3 页")

    # 第 2 页 → 第 3 页（首词 word040，末页仅 5 条）
    page.click("#next")
    expect(page.locator(".entry .word").first).to_have_text("word040")
    expect(page.locator(".entry")).to_have_count(TOTAL % PAGE_SIZE)
    expect(page.locator("#pageInfo")).to_contain_text("第 3 / 3 页")
    expect(page.locator("#next")).to_be_disabled()

    # 第 3 页 → 第 2 页（上一页）
    page.click("#prev")
    expect(page.locator(".entry .word").first).to_have_text("word020")
    expect(page.locator("#pageInfo")).to_contain_text("第 2 / 3 页")


# ── E2E-3：点击词条展开/收起详情（点击查词）────────────────────
def test_click_toggles_entry_detail(page, live_url):
    page.goto(live_url + "/")
    _load_entries(page)
    entry = page.locator(".entry").first
    # 初始详情折叠（无 .open）
    expect(entry).not_to_have_class(re.compile(r"\bopen\b"))
    # 点击展开
    entry.click()
    expect(entry).to_have_class(re.compile(r"\bopen\b"))
    # 详情含词源 / 例句 / 搭配 / SRS 按钮
    detail = entry.locator(".detail")
    expect(detail).to_be_visible()
    assert "词源" in detail.inner_text()
    assert "例句" in detail.inner_text()
    assert "搭配" in detail.inner_text()
    # 再点收起
    entry.click()
    expect(entry).not_to_have_class(re.compile(r"\bopen\b"))


# ── E2E-4：SRS 三态标记（生词→学习中→已掌握）─────────────────
def test_srs_three_state_cycle(page, live_url):
    page.goto(live_url + "/")
    _load_entries(page)

    def open_first():
        e = page.locator(".entry").first
        e.click()
        expect(e).to_have_class(re.compile(r"\bopen\b"))
        return e

    # 初始：生词（默认 new）
    expect(page.locator(".entry").first).to_have_class(re.compile(r"\bnew\b"))
    expect(page.locator(".entry .srs-dot").first).to_have_class(re.compile(r"\bnew\b"))

    # 标记「学习中」
    open_first().locator(".srs-btn.learning").click()
    expect(page.locator(".entry").first).to_have_class(re.compile(r"\blearning\b"))
    expect(page.locator(".entry .srs-dot").first).to_have_class(re.compile(r"\blearning\b"))

    # 标记「已掌握」
    open_first().locator(".srs-btn.mastered").click()
    expect(page.locator(".entry").first).to_have_class(re.compile(r"\bmastered\b"))
    expect(page.locator(".entry .srs-dot").first).to_have_class(re.compile(r"\bmastered\b"))

    # 标记回「生词」
    open_first().locator(".srs-btn.new").click()
    expect(page.locator(".entry").first).to_have_class(re.compile(r"\bnew\b"))


# ── E2E-5：点击查词阅读器（渲染文本 → 点词 → 查词面板）───────
def test_reader_lookup(page, live_url):
    # 等待后台词库预热完成（首查 15s 懒加载 → 预热后 <10ms）。
    _wait_warm()
    page.goto(live_url + "/reader")
    page.fill("#source", "The phenomenon of life is not reducible to physics. Being alive matters.")
    page.click("button.side-btn")
    page.wait_for_selector(".article .w")
    # 点击单词 "Being"（data-word 为小写 being）
    page.locator(".article .w", has_text="Being").first.click()
    page.wait_for_selector("#side .word")
    side_word = page.locator("#side .word").inner_text().strip()
    assert "being" in side_word
    # 离线词库查词成功 → 侧栏出现释义 / 词源 / SRS 标记按钮
    side_text = page.locator("#side").inner_text()
    assert ("存在" in side_text) or ("无释义" in side_text) or ("查词失败" not in side_text)
    assert "标记：学习中" in side_text
    assert "标记：已掌握" in side_text


# ── E2E-6：SRS 过滤 Tab（三态筛选后端契约在真实浏览器生效）───
def test_srs_filter_tabs(page, live_url):
    page.goto(live_url + "/")
    _load_entries(page)
    # 先把首词标记为「学习中」
    e = page.locator(".entry").first
    e.click()
    e.locator(".srs-btn.learning").click()
    expect(page.locator(".entry").first).to_have_class(re.compile(r"\blearning\b"))
    # 点「学习中」Tab → 仅剩 1 条（word000）
    page.locator(".tab[data-s='learning']").click()
    expect(page.locator(".entry")).to_have_count(1)
    expect(page.locator(".entry .word").first).to_have_text("word000")
    # 点「全部」Tab → 恢复 20 条
    page.locator(".tab[data-s='']").click()
    expect(page.locator(".entry")).to_have_count(PAGE_SIZE)


# ── E2E-7：长任务生成 job_id 轮询（真实 HTTP 契约 + 前端进度条活更新）──
def test_generate_job_polling_frontend(page, live_url, tmp_path, monkeypatch):
    """前端 generate() 的 job_id 轮询闭环（§2.6-4 ⭐）。

    用「快速 mock 生成」替换后台 _run_generate_job（走真实 HTTP 契约：
    upload → /api/generate 202 + job_id → 前端 while(true) 轮询 /api/jobs/<id>
    → 进度条活更新 → done → 词条列表加载），不跑真实 PDF 生成（秒级完成）。
    """
    pdf = tmp_path / "fake_book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")

    web_api._JOBS.clear()  # 干净起点（模块级作业注册表）

    # mock：running(10%) → running(55%) → done(100%)，总时长 ~3.5s，
    # 让前端 1.5s 轮询能观测到至少一个「中间 running 态」。
    def _mock_run(job_id, pdf_path, preset, lang):
        web_api._update_job(job_id, status="running", stage="解析 PDF", progress=10)
        time.sleep(2.0)
        web_api._update_job(job_id, status="running", stage="提取词元", progress=55)
        time.sleep(1.5)
        web_api._LAST_ENTRIES = _seed_entries(TOTAL)
        web_api._LAST_BOOK = "Being Alive"
        result = {
            "entries_count": TOTAL,
            "html_path": "Being_Alive_词汇表.html",
            "pdf_path": "Being_Alive_词汇表.pdf",
            "completed_stages": ["解析", "词元", "释义"],
            "entries_preview": _seed_entries(TOTAL),
        }
        web_api._update_job(job_id, status="done", progress=100,
                            stage="完成", result=result)

    # spy _update_job：记录服务端进度历史（pending→running→done 的中间态数据源）
    seen = []
    orig_update = web_api._update_job

    def _spy_update(job_id, **fields):
        if "progress" in fields:
            seen.append((fields.get("status", "?"), fields["progress"]))
        return orig_update(job_id, **fields)

    monkeypatch.setattr(web_api, "_run_generate_job", _mock_run)
    monkeypatch.setattr(web_api, "_update_job", _spy_update)

    # 计数浏览器对 /api/jobs/<id> 的轮询请求（每次轮询 = 一次真实 fetch）
    poll_count = {"n": 0}

    def _on_response(resp):
        if "/api/jobs/" in resp.url and resp.status == 200:
            poll_count["n"] += 1

    page.on("response", _on_response)
    page.goto(live_url + "/")
    page.set_input_files("#file", str(pdf))
    page.click("#genBtn")

    # 立即拿到 job_id（202 不阻塞，不再同步卡 1-3 分钟）
    expect(page.locator("#genNote")).to_contain_text("任务已提交")
    with web_api._JOBS_LOCK:
        job_id = next(iter(web_api._JOBS))
    assert job_id, "服务端作业注册表未生成 job"

    # 前端轮询推进 → 进度条最终完成（100%）
    page.wait_for_function(
        "document.getElementById('progressLabel').textContent.includes('完成 · 100%')",
        timeout=15000)

    # 完成态契约：note 词条数 / 词条列表加载 / 下载按钮可见 / 书名更新
    expect(page.locator("#genNote")).to_contain_text("生成完成")
    expect(page.locator("#genNote")).to_contain_text(f"{TOTAL} 词条")
    expect(page.locator(".entry")).to_have_count(PAGE_SIZE)
    expect(page.locator("#dlBtn")).to_be_visible()
    expect(page.locator("#bookTitle")).to_have_text("Being_Alive")

    # 前端确实做了多次轮询（≥2 次 /api/jobs 请求），而非一次性同步等待
    assert poll_count["n"] >= 2, f"前端轮询 /api/jobs 次数过少: {poll_count['n']}"

    # 服务端进度确实经历了 0-100 之间的「中间 running 态」（进度条活更新的数据源）
    running = [p for s, p in seen if s == "running"]
    assert running and any(0 < p < 100 for p in running), \
        f"缺中间 running 态（进度应经历 0<p<100）: {seen}"
