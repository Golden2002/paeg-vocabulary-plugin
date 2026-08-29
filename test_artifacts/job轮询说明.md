# 交互网页长任务 job_id + 轮询说明（Oracle §2.6-4）

> 对应 Oracle 论证记录 §2.6-4：「补 SSE 实现要点：Flask 实现约束（生成器响应 + 线程/任务隔离 + 断连处理），并约定长任务统一返回 `job_id` + 轮询兜底，防浏览器断连丢任务」。

## 1. 改造前后对比

| | 改造前 | 改造后 |
|---|---|---|
| `/api/generate` 行为 | 同步阻塞 1–3 分钟，直到生成完才返回 | 立即返回 `job_id`（HTTP 202），后台线程跑生成 |
| 浏览器断连/刷新 | 请求中断 → 任务丢失 | 服务端后台线程继续跑完并保存结果，不丢任务 |
| 进度可见性 | 无（页面一直转圈） | 前端轮询 `/api/jobs/<id>` 显示阶段 + 百分比进度条 |

## 2. API 契约

### `POST /api/generate`
请求体：`{"pdf_path": "...", "preset": "ielts-7.5", "lang": "en"}`

- PDF 不存在 → `400 {"ok": false, "error": "PDF 不存在——请先上传"}`
- 成功 → `202 {"ok": true, "job_id": "<uuid32>", "status": "pending"}`

### `GET /api/jobs/<job_id>`（轮询）
返回：

```json
{
  "ok": true,
  "job_id": "…",
  "status": "pending | running | done | error",
  "progress": 0,            // 0-100
  "stage": "排队中",        // 中文阶段名
  "result": { ... },        // 仅 status=done 时返回（html_path/pdf_path/docx_path/accessories/entries_preview 等）
  "error": ""               // 仅 status=error 时返回
}
```

- 未知 `job_id` → `404 {"ok": false, "error": "未知 job_id"}`

## 3. 状态机与进度阶段

```
pending → running → done
                 └→ error（异常回写，绝不静默丢任务）
```

`generate_vocabulary` 的 `progress_cb(stage, pct)` 在 5 阶段边界回调，进度大致映射：

| pct | stage |
|---|---|
| 1 | 准备 |
| 8 | 解析 PDF |
| 15 | 清洗语料 |
| 25 | 识别关键术语 |
| 35 | 分位筛选 |
| 45 | 提取书名/作者 |
| 70 | 批量补全词条 |
| 88 | 审查词条 |
| 96 | 渲染 HTML |
| 99 | 生成附件 |
| 100 | 完成 |

## 4. 前端轮询流程（web/index.html）

1. `/api/upload` 上传 PDF → 拿 `pdf_path`
2. `/api/generate` → 拿 `job_id`（立即返回）
3. 每 1.5s `fetch('/api/jobs/'+job_id)`，更新进度条（`.progress-bar` 宽度 = pct）
4. `status=done` → 读 `result`，载入词条（`/api/entries`），显示下载按钮
5. `status=error` → 显示 `error`

关键点：**断连/刷新后任务不丢**——服务端后台线程仍在跑，用户重新打开页面后可用同一 `job_id` 继续轮询（`_JOBS` 为进程内内存注册表）。

## 5. 实现要点（线程安全 + 可逆）

- `_JOBS`（dict）+ `_JOBS_LOCK`（threading.Lock）保护并发读写；`_new_job`/`_update_job` 均为线程安全。
- 后台线程 `daemon=True`，`try/except` 包裹整个生成流程，异常回写 `status=error`（不静默）。
- `progress_cb` 异常被 `generate_vocabulary` 内部吞掉，绝不阻断主流程。
- 修复：`_book_from_result` 提升为模块级函数（原为 `create_app` 闭包内定义，后台线程调用会 `NameError`）。
- 修复：不再用 `entries_preview`（≤300 条预览）覆盖真实 `entries_count`。

## 6. 测试证据

- `web/tests/test_web.py::test_generate_no_pdf`（缺失 PDF → 400）
- `web/tests/test_web.py::test_job_status_unknown`（未知 job → 404）
- `web/tests/test_web.py::test_job_registry_lifecycle`（pending→running→done 逐步可见）

端到端实测（真实书 `being_alive_p1-5.pdf`，离线模式）：`/api/generate` → 后台线程跑完 → `status=done`、`entries_count` 正确、`_LAST_ENTRIES` 载入、无 `NameError`。
