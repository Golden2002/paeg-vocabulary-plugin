# CHANGELOG — paeg-vocabulary-plugin（PAEG 工具生态 14.3 词汇表）

## v0.1.0 (2026-08) — 发布

**更新路径**：src/paeg_vocabulary/{pipeline/*, enrichers/*, cleaners/*, render/*, mcp_server.py, executor.py, wordbank.py, collocations.py, notable_words.py, quantile_*.py, level_matrix.py} + web/

- 六项能力：PDF 解析/OCR 断裂修复；去重/停用词/自定义筛选；全字段补全（原形/音标/双释义/义项/词源/例句/搭配）；附件产物（词频/句式/风格/学习价值）；Bell Jar CSS 渲染；MCP 插件
- 测试 148 全绿
- 2026-08-28 能力实测：6 项全部 PASS（词源在 wordbank/entry；风格分析在 executor/mcp_server；OCR 修复 ocr_repair.py）

## 2026-08-28 — 接入 PAEG 主 Agent MCP（mcp_servers.json）

- pip install -e 安装 paeg-vocabulary（console script: paeg-vocabulary-mcp）
- 主项目 mcp_servers.json 注册 vocabulary server（5/5 连接 46 工具之一）
