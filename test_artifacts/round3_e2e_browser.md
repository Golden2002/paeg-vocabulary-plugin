# Round 3 · 交互网页浏览器端 E2E 回归（Playwright）

> 验收项「交互网页长任务 job_id 轮询」此前仅覆盖 Flask `test_client` 后端契约
> （`web/tests/test_web.py` 的 `test_job_registry_lifecycle`），缺**真实浏览器**回归。
> 本轮补上 `web/tests/test_e2e_browser.py`：真实 chromium headless 驱动 index.html /
> reader.html，覆盖翻页 · 点击查词 · SRS 三态 · 阅读器查词 · SRS 过滤 Tab。

## 一、覆盖矩阵

| 用例 | 前端页面 | 验证内容 |
|---|---|---|
| `test_index_loads_and_reports_pagination` | index.html | 首页渲染满 20 条；首词 word000；分页信息「第 1 / 3 页 · 共 45 词」；上一页禁用/下一页可用 |
| `test_pagination_next_prev` | index.html | 下一页→第 2/3 页（首词 word020/word040），末页 5 条；上一页回退 |
| `test_click_toggles_entry_detail` | index.html | 点词条展开 `.open`（词源/例句/搭配/SRS 按钮可见），再点收起 |
| `test_srs_three_state_cycle` | index.html | SRS 三态 new→learning→mastered→new，`.entry`/`.srs-dot` 类名与配色同步 |
| `test_reader_lookup` | reader.html | 渲染文本→点单词 "Being"→离线词库查词面板（gloss/词源/标记按钮） |
| `test_srs_filter_tabs` | index.html | 标记「学习中」后 Tab 过滤只剩 1 条，切回「全部」恢复 20 条 |

## 二、运行结果

```
web/tests/test_e2e_browser.py::test_index_loads_and_reports_pagination PASSED
web/tests/test_e2e_browser.py::test_pagination_next_prev          PASSED
web/tests/test_e2e_browser.py::test_click_toggles_entry_detail    PASSED
web/tests/test_e2e_browser.py::test_srs_three_state_cycle         PASSED
web/tests/test_e2e_browser.py::test_reader_lookup                 PASSED
web/tests/test_e2e_browser.py::test_srs_filter_tabs               PASSED
============================= 6 passed in 18.65s =============================
```

全量回归：`python -m pytest tests/ web/tests/ -q` → **201 passed**（194 原有 + 6 E2E + 1 health 状态用例）。

## 三、本轮发现并修复的性能缺陷（点击查词首查 15.7s）

**症状**：阅读器首次「点击查词」卡 ~15s 无响应，之后才正常。

**根因**：`WordBank.lookup` 首次调用懒加载 ~285MB 本地词库——
`ecdict.csv` 63MB + kaikki 学科术语 JSONL（philosophy/biology/physics/chemistry ~218MB）
+ CMU 3.4MB + CEFR/Oxford。实测：

```
import execute:        0.44 s
first lookup_word:    15.66 s   ← 懒加载全部词库
second lookup_word:    0.00 s   ← 缓存命中
```

**修复**（`web/web_api.py`）：

1. 新增模块级 `_WORD_BANK_WARM = threading.Event()` + `_prewarm_wordbank()`：
   服务启动时后台 daemon 线程 `WordBank().coverage_stats()` 触发全部词库缓存加载。
2. `create_app()` 启动即 spawn 预热线程（进程内只预热一次），把开销从「用户首查」移到「启动期」。
3. `/api/health` 暴露 `wordbank_warm` / `wordbank_error` 状态，供前端/测试感知。
4. 单元测试（`create_app({"TESTING": True})`）不触发预热，避免 285MB 加载拖进核心用例。

**修复后实测**（服务端 `test_client`）：

```
warm after 11.37 s        ← 启动后台预热完成
lookup POST took 0.00 s   ← 首查即命中缓存（<10ms）
```

## 四、测试基建要点

- **E2E 服务器**：`make_server(..., threaded=True)` —— 对齐 `web_api.py` 的
  `app.run()` 默认（Flask 生产式并发）。`threaded=False`（werkzeug 默认）会让浏览器
  keep-alive 连接上的后续请求排队，查词出现 8~13s 级延迟（曾误导为前端 bug）。
- **浏览器探测**：`_browser_executable()` 依序找 playwright 自装 chromium → 系统 Chrome
  → 系统 Edge（`executable_path`）；找不到则整模块 `pytest.mark.skipif` 跳过，不挂死无浏览器环境。
- **种子词条**：`_seed_entries(45)` 注入 `web_api._LAST_ENTRIES`（不跑真实 PDF 生成），
  纯前端交互回归，秒级完成；`_reset_state` autouse fixture 保证用例独立。

## 五、复现方式

```bash
cd D:\wbo-workspace\paeg-vocabulary-plugin
python -m pytest web/tests/test_e2e_browser.py -v    # 单独 E2E
python -m pytest tests/ web/tests/ -q                 # 全量 201
```

> 依赖：`pip install playwright`（chromium 未装时自动回退系统 Chrome/Edge，本机已装）。

---

## Round 4 · 长任务 job_id 轮询的浏览器端回归（E2E-7）

Round 3 已补真实浏览器 E2E，但「制作词汇表」的前端 `generate()` 轮询闭环仍只有
`test_web.py` 的后端契约覆盖（`test_job_registry_lifecycle`）——浏览器端的
进度条 + 轮询推进尚未回归。本轮新增 `test_generate_job_polling_frontend`：

| 验证点 | 手段 |
|---|---|
| `/api/generate` 立即返回 202 + job_id（不再同步卡 1-3 分钟） | 点击「制作词汇表」后 note 即出现「任务已提交」，服务端 `_JOBS` 生成 job |
| 前端 `while(true)` 轮询 `/api/jobs/<id>` | `page.on("response")` 计数 `/api/jobs/` 请求 ≥2 次 |
| 进度条活更新（数据源有中间 running 态） | spy `_update_job` 记录 `running(10%) → running(55%) → done(100%)` |
| 完成态契约 | 进度标签「完成 · 100%」、note「生成完成：45 词条」、词条列表加载满 20 条、下载按钮可见、书名更新为 `Being_Alive` |

**实现**：用「快速 mock 生成」替换后台 `_run_generate_job`（走真实 HTTP 契约：
upload → generate → jobs 轮询 → done），不跑真实 PDF 生成，单用例 7.5s。mock 用
`time.sleep(2.0)+sleep(1.5)` 拉开中间态，让前端 1.5s 轮询能观测到 running。

运行结果：

```
web/tests/test_e2e_browser.py::test_generate_job_polling_frontend PASSED
============================= 7 passed in 17.33s =============================
```

全量 E2E 现为 **7 passed**（6 原有 + 1 长任务轮询）。
