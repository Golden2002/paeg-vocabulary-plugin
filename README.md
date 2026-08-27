# paeg-vocabulary

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-60%2F60-brightgreen.svg)](tests/)
[![MCP](https://img.shields.io/badge/MCP-Server-8A2BE2.svg)](src/paeg_vocabulary/mcp_server.py)

<p align="center">
  <strong>paeg-vocabulary</strong> — 语言学习词汇表生成插件：书籍 PDF → 结构化词汇表
  <br>
  <em>CEFR 难度分级 · 词源词根 · 多口音音标 · 熟词生义 · 本书含义 · Bell Jar 精美渲染</em>
  <br>
  <em>可拆卸、可独立、可像 Python 库一样直接接入任何智能体。</em>
</p>

> **中文** | [English](README.en.md)

---

## 这是什么

`paeg-vocabulary` 是**语言学习词汇表生成工具**——输入用户上传的书籍 PDF，输出对应语言（英语/德语/法语/西班牙语）的结构化语言学习词汇表。

源自 PAEG 教育智能体词汇表系统（§3.116 迭代），改造为**零宿主依赖**独立插件，内置为可独立扩展的 sub-agent 工具。

| 能力 | 说明 |
|---|---|
| **全流程工作流** | 提取 → 清洗去重 → 筛选 → 多维度补全 → 结构化渲染 |
| **12 字段强制标准** | 词形+音标(多口音)+中英释义+词源+词根词缀+多义项+原书例句+短语搭配+CEFR+词频 |
| **难度分级** | CEFR × Zipf 双轨（雅思/托福/四六级/考研/专四专八/高考 → 档位阈值） |
| **词形归一化** | 屈折归一化（lemma）+ 派生保留（学术术语不合并） |
| **语言现象识别** | 熟词生义 / 固定搭配 / 俚语——学习价值信号（筛选豁免 + 渲染标注） |
| **本书含义** | 多义词标注"在本书中，作者的意思是…"（基于原书语境） |
| **精美渲染** | 完整复用 Bell Jar 精美 CSS 模板（封面/章节/词条布局）→ HTML + PDF |
| **附件产物** | 语言学习价值说明 / 全书词频统计 / 作者语言风格分析 / 高明词统计页 |

## 核心特性

- **全流程工作流引擎**：5 阶段管线（ingest → clean → filter → enrich → render），支持用户自定义筛选维度（词频范围 / 难度等级 / 水平档位）
- **可扩充注册表**：`VocabularyRegistry.register_generator(name, fn)` / `register_language(lang)` 即扩展语种与生成器
- **零宿主依赖**：`Protocol` 抽象（LLMCallable / PDFReader）+ 注入式 `chat_fn`——外部智能体可注入自己的 LLM
- **统一执行入口**：`execute(name, args)`（JSON 契约，绝不抛异常）
- **MCP server 直接安装**：`pip install` + MCP 配置声明即接入（5 工具）
- **信息补全 sub-agent 插件化**：`EnricherRegistry` 按字段注册（新增字段/数据源即扩展）

## 架构

```
用户上传书籍 PDF
      │
      ▼
┌─────────────┐   ┌──────────────┐   ┌───────────────┐   ┌───────────────┐   ┌─────────────┐
│ ① ingest    │→  │ ② clean      │→  │ ③ filter      │→  │ ④ enrich      │→  │ ⑤ render    │
│ PDF 提取    │   │ OCR 修复      │   │ 虚词过滤      │   │ 音标/释义/词源 │   │ Bell Jar 模板│
│ 全书单词    │   │ 例句去污染    │   │ 难度档位筛选  │   │ 词根词缀/义项  │   │ HTML + PDF  │
└─────────────┘   └──────────────┘   │ 语言现象豁免  │   │ 本书含义/搭配  │   └──────┬──────┘
                                     └───────────────┘   └───────────────┘          │
                                                                                    ▼
                                                                   词汇表 HTML + PDF + 4 附件
```

**信息补全 sub-agent**（模块 2 ⭐ 内部插件化）：

```
CandidateWord ──→ EnricherRegistry（字段 → 补全器，可扩展）
                    ├─ ipa：CMU dict + espeak-ng 兜底（多口音）
                    ├─ LLM sub-agent：双语释义/词源/词根词缀/义项/本书含义/例句/搭配
                    ├─ 语言现象：熟词生义/固定搭配/俚语识别
                    └─ cefr/freq：wordfreq 计算
```

## 安装

```bash
pip install -e /path/to/paeg-vocabulary-plugin
# 可选依赖：
pip install -e "paeg-vocabulary-plugin[pdf]"    # PDF 提取（pymupdf/pdfplumber/ftfy）
pip install -e "paeg-vocabulary-plugin[nlp]"    # spaCy/wordfreq（词频与词形）
pip install -e "paeg-vocabulary-plugin[mcp]"    # MCP server
pip install -e "paeg-vocabulary-plugin[dev]"    # pytest
```

要求 Python 3.9+。

## 快速开始

```python
from paeg_vocabulary import VocabularyRegistry, execute

# 1. 注入你的 LLM（任何智能体接入点）
def my_llm(system_prompt, user_prompt):
    return my_model.chat(system_prompt, user_prompt)

VocabularyRegistry.inject(llm=my_llm)

# 2. 生成词汇表（PDF → HTML + PDF + 附件）
result = VocabularyRegistry.generate_vocabulary(
    "/path/to/book.pdf",
    lang="en",
    user_filter={"preset": "ielts-7.5"},   # 水平档位（雅思 7.5 ≈ 2200 词）
    chat_fn=my_llm,
)
# result = {
#   "ok": True, "html_path": "...", "pdf_path": "...",
#   "entries_count": 2211, "candidates_count": 3012,
#   "accessories": {"语言学习价值说明.md": "...", "词频统计报告.md": "...", ...},
#   "completed_stages": [...], "cefr_max": "C1",
# }
```

### 水平档位（user_filter）

| 模式 | 示例 | 含义 |
|---|---|---|
| 预设 | `{"preset": "ielts-7.5"}` | 内置考试档位（CEFR + Zipf 阈值） |
| 自定义 | `{"exam": "kaoyan", "score": 70}` | 考试体系 + 分数 |
| 书名 | `{"book_title": "生命现象学", "book_author": "约纳斯"}` | "本书含义"义项标注 |

**筛选方向**：覆盖用户水平"之上"所有等级——雅思 6.5 用户词多（约 3000），8.0 词少（约 1600）。

### 统一执行入口（MCP 契约）

```python
from paeg_vocabulary.executor import execute

print(execute("list_languages"))            # ["de","en","es","fr"]
print(execute("list_generators"))           # ["generate_accessories","generate_vocabulary"]
print(execute("validate_entry", {"headword": "life", "pos": "n."}))
print(execute("clean_examples", {"examples": ["…混入页码的例句…"]}))
print(execute("generate_vocabulary", {"pdf_path": "book.pdf", "user_filter": {...}}))
```

## MCP 接入

```bash
# 方式 1：直接运行（stdio）
paeg-vocabulary-mcp

# 方式 2：声明式配置（Claude Code / 任意 MCP 客户端）
```

```json
{
  "mcpServers": {
    "paeg-vocabulary": {
      "command": "paeg-vocabulary-mcp",
      "args": []
    }
  }
}
```

**5 个 MCP 工具**：`generate_vocabulary` / `list_languages` / `list_generators` / `validate_entry` / `clean_examples`。

## 词汇条目标准（12 字段）

| 层级 | 字段 | 说明 |
|---|---|---|
| L1 必填 | headword | 词目（lemma 形，单数原形） |
| L1 必填 | pos | 词性（n./v./adj./adv.） |
| L1 必填 | ipa | 多口音音标（en_us / en_uk / de…） |
| L1 必填 | gloss_bilingual | 中文释义 + 英文释义 |
| L1 必填 | examples | 原书例句优先（真实语境） |
| L1 必填 | lemma | 词元（lemmatization） |
| L2 | etymology | 词源（语系归属 + 词根词缀 + 演变路径） |
| L2 | morpheme | 词根词缀拆解（roots/prefix/suffix + 语言 + 含义） |
| L2 | senses | 多义项（Wiktionary 风格 词源.义项 双层编号） |
| L2 | collocations | 短语/固定搭配 |
| L3 | cefr_level | A1-C2 |
| L3 | freq_rank | 全书词频排名 |

**词形归一化策略**（§3.116）：屈折（POS 不变 -ed/-ing/-s）归一化 lemma；派生（POS 改变 / -tion/-ment/-ness）保留原形——`abandonment` 是海德格尔学术术语，不合并。

## 测试

```bash
python -m pytest tests/ -q    # 60/60 全绿
```

覆盖：词汇条目校验 / 难度矩阵 / 词形归一化 / 语言现象识别 / 附件生成 / 端到端管线。

## 生态定位（PAEG 工具生态）

```
PAEG 工具生态
├── paeg-lang-style-plugin      语言规范（83/83 测试 · MCP）
├── paeg-teaching-materials     教学物料（74/74 测试 · MCP）
├── paeg-vocabulary             ⭐ 词汇表生成（60/60 测试 · MCP）
└── 主项目 PAEG（插件优先双轨 · material_bridge · sys.path 引用插件副本）
```

**接入方式**：`pip install` → `import` → 注册 → 注入 LLM → 可用。主项目通过 `sys.path` 引用插件副本（`server.py` 插件加载循环），对话中输入「生成词汇表：xxx.pdf」→ magic 关键词 → `material_router` 路由 → `vocab_done` SSE 事件 → 前端弹出展示卡片。

## License

MIT

## 参考文献

本项目的能力设计参考了以下资源：

| 参考 | 网址 | 参考内容 |
|---|---|---|
| **Nation BNC/COCA 词族表** | https://www.wgtn.ac.nz/lals/resources/paul-nations-resources/vocabulary-lists | 10000 词族 10 档（难度分位 family_q 信号） |
| **CMU Pronouncing Dictionary** | https://github.com/cmusphinx/cmudict | 126,052 词 ARPAbet 音标（IPA 转换） |
| **ECDICT 英汉词典** | https://github.com/skywind3000/ECDICT | 77 万词中文释义+词频（MIT） |
| **kaikki Wiktionary** | https://kaikki.org/dictionary/ | 学科术语辞典（philosophy/biology/physics/chemistry 等 722 topics） |
| **CEFR-J Vocabulary Profile** | https://github.com/openlanguageprofiles/olp-en-cefrj | CEFR 分级词表（A1-C2） |
| **Oxford 3000** | https://www.oxfordlearnersdictionaries.com/wordlists/ | CEFR 分级权威词表 |
| **《生命现象学》/《The Bell Jar》渲染模板** | 用户英语学习资产 | Bell Jar 精美 CSS 模板（渲染引擎完整复用） |

> 注：词库数据为第三方开源数据（各自主许可）；下载脚本 scripts/download_wordbank.py 按需获取。
