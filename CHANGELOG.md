# CHANGELOG — paeg-vocabulary-plugin（PAEG 工具生态 14.3 词汇表）

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
