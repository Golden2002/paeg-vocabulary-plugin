# test_artifacts — 外语词汇表工具测试产物

本目录是「外语词汇表工具」（`paeg-vocabulary-plugin` 14.3）**真实英文书**端到端测试的最终认可产物：
用真实英文书 PDF（`D:\wbo-workspace\vocab_trial\being_alive_p1-5.pdf`，《Being Alive: Essays on
Movement, Knowledge and Description》前 5 页）跑
`VocabularyRegistry.generate_vocabulary(lang="en", user_filter={"max_entries": 60})`，5 阶段管线
（ingest → clean → filter → enrich → render）+ 附件全链路产出。

**LLM 接入**：默认 `EnvLLM` 读 `~/.local/share/opencode/auth.json` 的 DeepSeek key（或
`DEEPSEEK_API_KEY`），书名/作者判定、批量补全（6 词/批）、渲染前审查三节点全部生效——
实测书名被正确识别为 "Being Alive"（而非文件名），词源/搭配/本书义均补全。

## 一、产物清单

| 文件 | 类型 | 说明 |
|---|---|---|
| `Being_Alive_词汇表.html` | 主产物 | Bell Jar 模板渲染，CEFR 徽章 + 频次徽章（×N）+ 多口音音标 + 词源/词素/例句/搭配 |
| `Being_Alive_词汇表.pdf` | 主产物 | Chrome headless 渲染（1.2 MB，`%PDF` 头） |
| `Being_Alive_词汇表.docx` | 主产物 | python-docx 导出（headword/pos/ipa/中英释义/词源/词素/例句/搭配/CEFR） |
| `语言学习价值说明.md` | 附件① | 基于原著的语言学习价值说明 |
| `词频统计报告.md` | 附件② | 全书实词词频统计（去虚词，Top 50） |
| `作者语言风格分析.md` | 附件③ | 词汇/句式特征风格画像 |
| `短语句式统计.md` | 附件④ | 高频短语（二元/三元 N-gram + PMI）+ 句式特征 |
| `SRS复习计划.md` | 附件⑤ | SM-2 遗忘曲线 14 天复习计划 |
| `高明词统计.html` | 附件⑥ | 高频实词独立 HTML 统计页 |
| `job轮询说明.md` | 文档 | 交互网页长任务 job_id + 轮询改造说明（Oracle §2.6-4） |

## 二、测试结果

- 5 阶段管线 + 附件生成全跑通：`ok=True`、`errors=[]`、`entries=60`、`candidates=60`。
- HTML/PDF/docx 三格式 + 6 类附件**全部产出**。
- 内容质量核验：
  - ✅ 词条字段完整（headword/pos/ipa/中英释义/词源/例句/搭配/CEFR/频次）
  - ✅ 排版无 `\n` 乱码（HTML 多义项转 `<br>`；docx 真实换行转 ` / `）
  - ✅ CEFR 难度徽章 + 本书频次徽章（×N）
  - ✅ 词元还原（`making→make`、`charging→charge`、`running→run`、`process→process`）
  - ✅ IPA 特殊字符（`/əˈlaɪv/`、`/ˌænθrəˈpɑːlədʒi/`、`/ˈmuːvmənt/`）
  - ✅ LLM 独立接入未破坏（书名识别、词源/搭配/本书义补全生效）
- 测试基线：`python -m pytest tests/ web/tests/ -q` → **206 passed 全绿**（Round 6 终态）。

## 三、本轮修复的问题

1. **长任务改造（Oracle §2.6-4）**：`web/web_api.py` `/api/generate` 由同步阻塞改为
   `job_id + 后台线程 + /api/jobs/<id> 轮询 + 前端进度条`，防浏览器断连丢任务。详见 `job轮询说明.md`。
2. **后台线程 NameError**：`_book_from_result` 原为 `create_app` 闭包内定义，后台线程调用抛
   `NameError` → 提升为模块级函数。
3. **entries_count 被预览覆盖**：`result["entries_count"]` 原被 `len(entries_preview)`（≤300）覆盖
   → 保留真实词条总数。
4. **审查 LLM 把 gloss/ipa 返回为字符串 → 渲染崩溃**：`review_entries` 回写时若 `gloss_bilingual`
   被整段返回为字符串，`_render_docx`/`_render_gloss`/预览会对 str 调 `.get` 抛 `AttributeError`。
   已三层兜底：registry 回写强转 dict + 渲染器/导出器防御式处理。
5. **词元还原缺陷**：`_rule_lemmatize` 的 `-ing/-ed` 去尾不还原 dropped-e（`making→mak`、
   `charging→charg`）与双写辅音（`running→runn`）；`-s` 误切 `-ss` 结尾词（`process→proces`）。
   新增 `_restore_stem`（用 ecdict 词频 rank 做信号）。
6. **docx 词素显示 dataclass repr**：`Morpheme(roots=[...])` → 可读构词链（`_morpheme_text`）。
7. **前端未接入轮询 + 进度**：`web/index.html` 新增轮询逻辑与进度条 UI。
8. **web 测试陈旧**：`test_generate_no_pdf`（200→400）、`test_index_page`（标题已改）更新，
   并新增 job 注册表/轮询测试。

## 四、风险与已知局限

1. **前端元噪声**：前 5 页以版权页/目录为主，出现 `isbn`、出版社/人名/地名（`routledge`、
   `stuart`、`minnesota`…）等词条。根因是专名过滤只覆盖出现 ≥2 次的大写词，单次专名未拦截；
   全本正文或 LLM 审查路径下会显著减轻，非本轮回归。
2. **`-s` 规则对专名**：`francis→franci`（-s 误切人名）。`_restore_stem` 覆盖 -ing/-ed/-ss，
   未覆盖「专名 -s」，需与专名过滤（cap_stats）配合，属遗留项。
3. **`_JOBS` 内存注册表无 TTL**：单进程单机可用，多 worker/重启即失效；生产化建议换
   Redis/持久化任务队列。
4. **词元化为规则级兜底**（spaCy 未装）：Round 4 已修复 `-ing/-ed` 误切（`spring→spr`、
   `string→str`、`during→dur`、`according→accord` 等，见「八、Round 4」）。Round 5 又补上
   `-ing` 实词 stoplist（`evening/building/meaning/interesting/meeting/engineering…` 等独立
   名词/形容词/领域名词保持原形，见「九、Round 5」），消除纯语义 false positive
   （`evening→even`、`building→build`）。剩余歧义（`reading/feeling` 这类动名词兼名词）已由
   Round 7 的 spaCy POS 路径消解并锁定（`tests/test_spacy_pos.py`，见「十一、Round 7」）——
   本机默认 Python 3.14 无 cp314 轮子仍走规则级兜底，安装 `[nlp]` 依赖（spaCy +
   `en_core_web_sm`）后 POS 消歧自动生效。
5. **IPA 重音位置**：CMU→IPA 转换的重音标注偶有偏位，不影响读音理解，属转换层精度项。

## 五、复现方式

```bash
cd D:\wbo-workspace
python vocab_test_run.py            # 离线（NullLLM）
# USE_LLM=1 python vocab_test_run.py  # 接入 DeepSeek LLM
cd paeg-vocabulary-plugin
python -m pytest tests/ web/tests/ -q
```

产物源目录：`paeg-vocabulary-plugin/output/`（生成后复制到本目录）。

> 注：仓库工作树还包含并行的 `paeg_lang_style`（14.1）L0 中文校对接入（`src/paeg_vocabulary/lang_style.py`、
> `tests/test_lang_style.py`）与前端内联 SVG 图标改动，均非本任务引入、与本任务改动不冲突
> （全量测试 194 绿）。本目录产物以**真实英文书 + DeepSeek LLM**为基准，是任务要求口径下的最终认可产物。

---

## 六、Round 2 · 真实 DeepSeek LLM 全量回归（2026-08-30）

复跑 `USE_LLM=1 python vocab_test_run.py`（`MAX_ENTRIES=60`，真实英文书 PDF → 5 阶段管线 +
LLM 三节点 + L0 校对 + 附件），完整摘要见 `round2_llm_regression.json`：

| 指标 | 结果 |
|---|---|
| `ok` | ✅ `True`（`errors=[]`，非弱模式空表） |
| `entries / candidates` | 60 / 60 |
| 5 阶段 `completed_stages` | `pdf_ingest / clean_dedup / filter / enrich / render` 全完成 |
| 主产物 | HTML / PDF / docx 三格式 + 6 附件全部产出 |
| 耗时 | 238.4s（含 LLM 三节点：关键术语 gate / 书名作者 / 批量补全 / 渲染前审查） |
| 书名识别 | ✅ 作者 Tim Ingold 语境进入搭配（`Tim Ingold` / `Tim's work`） |
| L0 校对 | ✅ 每词条经 `apply_l0_to_entry`（`gate_short`+`fix_known_gaffes`）+ 审查回写再 `apply_l0`；LLM 中文产出无已知病句，L0 为零改动安全网 |

**结论**：真实 DeepSeek 全 LLM 增强回归通过——LLM 三节点（关键术语 gate、书名/作者判定、
6 词/批批量补全、渲染前审查）与 L0 校对（`paeg_lang_style` 14.1）在真实数据下全链路生效，
无弱模式占位、无崩溃、无降级。

---

## 七、Round 3 · 交互网页浏览器端 E2E + 点击查词性能修复（2026-08-30）

补上前两轮缺口的「真实浏览器回归」：`web/tests/test_e2e_browser.py`（Playwright，6 用例）
在真实 chromium 里驱动 index.html / reader.html，覆盖翻页、点击查词、SRS 三态、阅读器查词。
详见 `round3_e2e_browser.md`。

| 指标 | 结果 |
|---|---|
| E2E 用例数 | 6（翻页 / 点词展开 / SRS 三态 / 阅读器查词 / SRS 过滤 Tab / 分页信息） |
| E2E 结果 | ✅ 6 passed（18.65s，chromium headless 真实渲染 + 真实 HTTP） |
| 浏览器探测 | 自装 chromium 优先，无则回退系统 Chrome/Edge（`executable_path`），三态降级 skip 不挂死套件 |
| 全量测试 | `python -m pytest tests/ web/tests/ -q` → **201 passed**（194 + 6 E2E + 1 health 状态用例） |

**本轮修复（真实性能缺陷）**：首次「点击查词」卡 15.7s —— 根因是 `WordBank` 懒加载
~285MB 本地词库（ecdict 63MB + kaikki 学科术语 ~218MB）落在用户第一次 `/api/lookup` 上。
修复：`web_api.create_app()` 启动时后台线程 `_prewarm_wordbank()` 预热词库，`/api/health`
暴露 `wordbank_warm` 状态；实测**预热前首查 15.66s → 预热后 <10ms**。单元测试
（`TESTING=True`）不触发预热，避免把 285MB 加载拖进核心用例。

---

## 八、Round 4 · 前端 job_id 轮询 E2E + 词元化 -ing 误切修复（2026-08-30）

两项遗留补齐：

| 项 | 结果 |
|---|---|
| 前端 `generate()` job_id 轮询浏览器端 E2E | ✅ `test_generate_job_polling_frontend`（E2E-7）：真实 HTTP 契约（upload→generate 202+job_id→轮询 `/api/jobs/<id>`→进度条活更新→done→词条列表加载），用「快速 mock 生成」驱动，7.5s |
| 词元化 `-ing/-ed` 误切修复 | ✅ `_rule_lemmatize` 增加频率信号：还原结果必须比原词更常见才保留，否则保持原词（`spring→spring`/`string→string`/`during→during`/`according→according`/`hundred→hundred`） |

全量 E2E 现为 **7 passed**（6 原有 + 1 长任务轮询），全量测试 **203 passed**（202 + 1
`test_rule_lemmatize_ing_base_word_not_miscut`）。详见 `round3_e2e_browser.md`（Round 4 段）。

---

## 九、Round 5 · 词元化 -ing 实词 stoplist（2026-08-30）

Round 4 的频率兜底只能挡「去尾后不是词典词」的误切（`spring→spr`），挡不住「去尾后是更常见
词」的**语义误切**。本轮在 `_rule_lemmatize` 增加 `_ING_REAL_WORDS` 实词 stoplist，把 `-ing`
结尾但语义已独立的词保持原形（不归并到 base 动词）：

| 类别 | 词例（`→` 修复后） |
|---|---|
| 时间/抽象名词 | `evening→evening`、`morning→morning`、`meaning→meaning`、`beginning→beginning`、`following→following` |
| 具体名词 | `building→building`、`wedding→wedding`、`meeting→meeting`、`opening→opening`、`ceiling→ceiling`、`offspring→offspring` |
| 形容词 | `interesting→interesting`、`surprising→surprising`、`amazing→amazing` |
| 领域/职业名词 | `engineering→engineering`、`marketing→marketing`、`accounting→accounting`、`consulting→consulting`、`training→training` |

**不回归**：真·动名词/动词仍正确还原（`making→make`/`running→run`/`walking→walk`/`worked→work`/
`charging→charge`/`living→live`/`learning→learn`/`reading→read`）。

新增回归用例：`tests/test_lemmatize_fix.py` 的 `test_rule_lemmatize_ing_real_words_stoplist` +
`test_rule_lemmatize_ing_verb_still_reduces`（2 用例）。全量测试 **205 passed**（203 + 2）。

---

## 十、Round 6 · 词元化不规则第三人称单数修复（2026-08-30）

`_rule_lemmatize` 的 `-s` 去尾规则会误切不规则第三人称单数（`goes→goe`、`does→doe`）——
`goe` 是词典外畸形词条，`doe` 是误切成的同形词（母鹿）。这两个是超高频英语词，词条污染面大。
本轮在 `_IRREGULAR_LEMMAS` 增加 `goes→go`、`does→do`、`has→have`（`does/has` 虽在停用词表
会被过滤，但补全保证 `_rule_lemmatize` 单点行为正确、不依赖调用方过滤）。

| 词 | 修复前 | 修复后 |
|---|---|---|
| `goes` | `goe`（畸形） | `go` |
| `does` | `doe`（误切同形词） | `do` |
| `has` | `has`（未归并） | `have` |

**不回归**：规则复数仍正确（`fees→fee`/`sees→see`/`shoes→shoe`/`lies→lie`/`dies→die`/`knees→knee`）。

新增回归用例：`tests/test_lemmatize_fix.py` 的 `test_rule_lemmatize_irregular_third_person`（1 用例）。
全量测试 **206 passed**（205 + 1）。

> 剩余歧义（`reading/feeling/drawing/writing` 这类动名词兼名词）仍无确定性规则可解（频率信号 +
> stoplist 已三层收敛），彻底消除需 spaCy `en_core_web_sm` POS；本机 Python 3.14 无 cp314 轮子，
> 列为已知局限（见「四、风险与已知局限」第 4 条），不影响验收。

---

## 十一、Round 7 · spaCy POS 词形还原路径生效（动名词/名词歧义消解，2026-08-31）

承接 Round 6 遗留 nextStep ①：规则级兜底无法彻底消除 `reading/feeling/drawing/writing/painting/
cooking` 这类动名词兼名词歧义。本轮在本机 py3.12 venv 安装 spaCy + en_core_web_sm，让
`_lemmatize_with_pos` 的 POS 感知路径真正生效，并用 `tests/test_spacy_pos.py`（8 用例，
`pytest.importorskip("spacy")` 自动降级）锁定行为。详见 `spacy_pos验证.md`。

| 词 | 动词上下文（VERB） | 名词上下文（NOUN） |
|---|---|---|
| `reading` | `I am reading a book` → lemma `read` | `the reading of the book` → lemma `reading` |

端到端验证：`clean_corpus("I am reading a book. The reading was beautiful.")` 产出 lemma 集合
`['read', 'book', 'reading', 'beautiful']`——动词 `reading` 折叠为 `read`，名词 `reading` 保留为
独立词条，停用词（`I/am/a/the/was`）正确过滤。

| 环境 | 结果 |
|---|---|
| py3.14（无 spaCy，规则兜底） | `206 passed, 1 skipped`（spaCy 测试自动跳过，全量 tests/ + web/tests/） |
| py3.12 venv（spaCy 3.8.16 + en_core_web_sm 3.8.0） | `198 passed`（tests/ 主套件 190 + 8 新 spaCy 测试） |

不规则三单（`goes/does/has → go/do/have`）在 spaCy 路径与规则兜底 `_IRREGULAR_LEMMAS`（Round 6）
结果一致，双路径收敛。
