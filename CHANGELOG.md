# CHANGELOG — paeg-vocabulary-plugin（PAEG 工具生态 14.3 词汇表）

## v0.1.8 (2026-08-31) — PDF 页眉页脚美观化（去时间戳/URL，页眉书名 + 页脚页码）

**更新路径**：src/paeg_vocabulary/pipeline/render_html.py + templates/{模板_钟形罩_原版.html, 模板_生命现象_原版.html}

- **问题**：Chrome `--print-to-pdf` 默认页眉页脚含「生成时间戳（2026/8/30 02:19）」与「file:/// 本地 URL」，信息错误且不美观。
- **修复**：
  - `_render_pdf` 加 `--print-to-pdf-no-header` 关闭 Chrome 默认页眉页脚
  - 模板 CSS `@page` 边距盒：`@top-center` 显示书名（`{{DOC_TITLE}}` 运行时替换）、`@bottom-center` 显示 `第 X / 共 Y 页`（`counter(page)/counter(pages)`）
- 实测：页眉=「Being Alive（Tim Ingold）」、页脚=「3 / 13」，无时间戳、无 URL

## v0.1.7 (2026-08-31) — spaCy POS 词形还原路径生效（动名词/名词歧义消解）

**更新路径**：tests/test_spacy_pos.py（新增）+ README.md（测试说明同步）

- 规则级兜底（`_rule_lemmatize` 频率信号 + `_ING_REAL_WORDS` stoplist）无法彻底消除
  动名词兼名词歧义：`reading/feeling/drawing/writing/painting/cooking` 既是动名词
  （VERB，应还原 base 动词）又是独立名词（NOUN，应保持原形为独立词条）。
- 补上 spaCy POS 感知路径的测试锁定：`_lemmatize_with_pos` 在 spaCy + en_core_web_sm
  可用时按上下文 POS 消歧——
  - 动词上下文 `I am reading a book` → `reading` 判 VERB，lemma=`read`（折叠）
  - 名词上下文 `the reading of the book` → `reading` 判 NOUN，lemma=`reading`（保留）
  - 不规则三单 `goes/does/has` → `go/do/have`（与 `_IRREGULAR_LEMMAS` 兜底一致）
- 端到端验证：`clean_corpus("I am reading a book. The reading was beautiful.")` 产出
  lemma 集合同时含 `read`（动词折叠）与 `reading`（名词保留），停用词过滤不回归
- 测试 +8（test_spacy_pos.py：`pytest.importorskip("spacy")` 自动降级）——
  - 本机默认 py3.14（无 spaCy）：`206 passed, 1 skipped`（全量 tests/ + web/tests/；spaCy 测试自动跳过）
  - py3.12 venv（spaCy 3.8 + en_core_web_sm 3.8.0）：`198 passed`（tests/ 主套件 190 + 8 新 spaCy 测试）
- 复现环境：`py -3.12 -m venv .venv-spacy312 && pip install "spacy>=3.7" pytest &&
  python -m spacy download en_core_web_sm && python -m pytest tests/test_spacy_pos.py -v`

## v0.1.6 (2026-08-30) — 词元化不规则第三人称单数（修复 goes→goe / does→doe）

**更新路径**：src/paeg_vocabulary/pipeline/clean_dedup.py + tests/test_lemmatize_fix.py

- `_IRREGULAR_LEMMAS` 新增 `goes→go`、`does→do`、`has→have`：修复 `-s` 去尾规则误切超高频
  不规则第三人称单数（`goes→goe` 词典外畸形词条、`does→doe` 误切同形词）
- 不回归：规则复数仍正确（`fees→fee`/`sees→see`/`shoes→shoe`/`lies→lie`/`dies→die`）
- 测试 +1（test_lemmatize_fix.py：`test_rule_lemmatize_irregular_third_person`），全量 205 → 206 passed

## v0.1.5 (2026-08-30) — 词元化 -ing 实词 stoplist（消除语义 false positive）

**更新路径**：src/paeg_vocabulary/pipeline/clean_dedup.py + tests/test_lemmatize_fix.py

- `_rule_lemmatize` 新增 `_ING_REAL_WORDS` 实词 stoplist：`-ing` 结尾但语义已独立的词保持原形，
  不再误归并到 base 动词（`evening→even`、`building→build`、`meaning→mean`、
  `interesting→interest`、`surprising→surprise`、`meeting→meet`、`engineering→engineer` 等）
- 覆盖四类：时间/抽象名词、具体名词、形容词、领域/职业名词（简历高频词，避免误切）
- 不回归：真·动名词/动词仍正确还原（`making→make`/`running→run`/`walking→walk`/`worked→work`）
- 测试 +2（test_lemmatize_fix.py：stoplist 保持原形 + 动名词仍还原），全量 203 → 205 passed

## v0.1.4 (2026-08-30) — 交互式网页（翻页 + 点击反馈 + SRS 三态）

**更新路径**：web/web_api.py + web/index.html + src/paeg_vocabulary/registry.py

- 交互式词条浏览：分页（翻页，20/页）+ 搜索 + SRS 三态过滤（生词/学习中/已掌握）
- 点击反馈：点击词条展开详情（词源/例句/搭配）+ SRS 三态标记按钮（对标 LingQ 蓝/黄/白，词条左色条随状态变色）
- 新增端点：`/api/entries`（分页+搜索+过滤）、`/api/srs`（三态推进 new→learning→mastered）
- 词条预览全字段化（完整释义/词源/例句/搭配，不再截断 80 字）——支撑交互式网页
- 网页可公网部署（Flask 单页应用，零外部 CDN 依赖）

## v0.1.3 (2026-08-30) — 独立接入 LLM（环境变量）+ 词汇表排版修复

**更新路径**：src/paeg_vocabulary/llm_client.py（新增）+ registry.py + wordbank.py + pipeline/enrich.py + render/field_renderers.py + pipeline/render_html.py + templates/*.html

**独立 LLM 接入（环境变量）**
- 新增 llm_client.py：DeepSeek 客户端（OpenAI 兼容，零第三方依赖，urllib 直连）
- Key 读取顺序：环境变量 `DEEPSEEK_API_KEY` → `~/.local/share/opencode/auth.json` 的 deepseek.key（与主项目 resume_product.llm_client 一致），可选 `DEEPSEEK_MODEL` / `DEEPSEEK_API_URL`
- `EnvLLM` 实现 LLMCallable 协议，作为 `VocabularyRegistry.llm` 默认值——工具独立运行即可调用 LLM，宿主仍可 `inject(llm=...)` 覆盖
- 无 key 时返回空串（等价 NullLLM），gate/enrich/metadata/review 自动降级到规则层，不阻塞管线
- 实测：书名/作者 LLM 判定 + 批量词条补全均生效（`being_alive_p1-5.pdf` → 自动识别书名 "Being Alive"）

**排版修复（信息不全 / 乱码）**
- ecdict 释义清洗：字面 `\n` → 真实换行、去行首词性前缀（n./vt./a./r. …）、领域标签 `[计]`→`〔计〕`
- 词性标准化：ecdict 非常规码（r./s./a.）→ adv./adj.，CEFR 全词（noun/verb）→ n./v.
- 词条渲染：headword 加 CEFR 难度徽章 + 本书频次徽章（×N）、去重 IPA（仅 ipa-row 展示，口音标签美/英/德/法/西）、gloss 多义项换行 `<br>`、morpheme 去空「」

## v0.1.2 (2026-08-29) — SRS 间隔重复 + 词汇三态（对标 LingQ）

**更新路径**：src/paeg_vocabulary/srs.py（新增）+ executor.py + tests/test_srs.py

- 新增 srs.py：SM-2 遗忘曲线算法（EF 难度因子 + 间隔递增 + 失败重置 + EF 下限 1.3）
- `sm2_review(ef, interval, reps, quality)`：单次复习评分 → 更新 EF/间隔/次数
- `plan_schedule(words, days)`：产出 N 天复习计划（每天到期词 + 总量统计）
- `due_words(state, day)` / `make_srs_state(words)`：到期判断 + 状态初始化
- **词汇三态** `status_from_reps(reps)`：new（生词/蓝）→ learning（学习中/黄）→ mastered（已掌握/白），对标 LingQ 蓝黄白
- executor +2 工具（srs_plan / srs_review）
- 测试 +5（test_srs.py：间隔递增/失败重置/EF 下限/到期判断/复习计划）
- 调研依据：LingQ（分级阅读+蓝黄白+SRS）、Babbel（错题复习对抗遗忘）、Readlang（点击查词）

## v0.1.1 (2026-08-29) — 词条截断修复（词形还原 -es 误切 + 停用词绕过）

**更新路径**：src/paeg_vocabulary/pipeline/clean_dedup.py + tests/test_lemmatize_fix.py

- **修复 1（-es 规则误切）**：`_rule_lemmatize` 的 `-es` 规则无条件匹配所有 -es 结尾词，导致 `sciences→scienc`、`includes→includ`、`decades→decad`、`voices→voic`（词尾丢失畸形词条，约占 10%）。现 -es 规则仅匹配真·es 复数（-ches/-shes/-xes/-zes/-sses），普通 -s 复数走 -s 规则
- **修复 2（停用词绕过）**：`this→(lemmatize)→thi` 绕过停用词过滤，产生畸形词条 thi。现停用词过滤用「原始 token + 词元」双重检查
- **新增 `_recover_truncated`**：词尾丢失恢复（ecdict 词典校验，scienc→science / includ→include / voic→voice，合法词不误伤）
- 测试 +5（test_lemmatize_fix.py：-es 误切/真·es/-ies-ing-ed/-s 安全/恢复）

## v0.1.0 (2026-08) — 发布

**更新路径**：src/paeg_vocabulary/{pipeline/*, enrichers/*, cleaners/*, render/*, mcp_server.py, executor.py, wordbank.py, collocations.py, notable_words.py, quantile_*.py, level_matrix.py} + web/

- 六项能力：PDF 解析/OCR 断裂修复；去重/停用词/自定义筛选；全字段补全（原形/音标/双释义/义项/词源/例句/搭配）；附件产物（词频/句式/风格/学习价值）；Bell Jar CSS 渲染；MCP 插件
- 测试 148 全绿
- 2026-08-28 能力实测：6 项全部 PASS（词源在 wordbank/entry；风格分析在 executor/mcp_server；OCR 修复 ocr_repair.py）

## 2026-08-28 — 接入 PAEG 主 Agent MCP（mcp_servers.json）

- pip install -e 安装 paeg-vocabulary（console script: paeg-vocabulary-mcp）
- 主项目 mcp_servers.json 注册 vocabulary server（5/5 连接 46 工具之一）
