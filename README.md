# paeg-vocabulary

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-179%2F179-brightgreen.svg)](tests/)
[![MCP](https://img.shields.io/badge/MCP-Server-8A2BE2.svg)](src/paeg_vocabulary/mcp_server.py)

<p align="center">
  <strong>paeg-vocabulary</strong> — 语言学习词汇表生成插件：书籍 PDF → 结构化词汇表
  <br>
  <em>CEFR 难度分级 · 词源词根 · 多口音音标 · 熟词生义 · 本书含义 · SRS 间隔重复 · 词汇三态 · Bell Jar 精美渲染</em>
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
| **SRS 间隔重复** | SM-2 遗忘曲线：评分 0-5 → 间隔 1→6→递增、失败重置，产出 N 天复习计划 |
| **词汇三态** | new（生词/蓝）→ learning（学习中/黄）→ mastered（已掌握/白），对标 LingQ |

## 核心特性

- **全流程工作流引擎**：5 阶段管线（ingest → clean → filter → enrich → render），支持用户自定义筛选维度（词频范围 / 难度等级 / 水平档位）
- **可扩充注册表**：`VocabularyRegistry.register_generator(name, fn)` / `register_language(lang)` 即扩展语种与生成器
- **零宿主依赖**：`Protocol` 抽象（LLMCallable / PDFReader）+ 注入式 `chat_fn`——外部智能体可注入自己的 LLM
- **统一执行入口**：`execute(name, args)`（JSON 契约，绝不抛异常）
- **MCP server 直接安装**：`pip install` + MCP 配置声明即接入（5 工具）
- **信息补全 sub-agent 插件化**：`EnricherRegistry` 按字段注册（新增字段/数据源即扩展）
- **SRS 复习调度**：`srs_plan`（N 天复习计划）/ `srs_review`（SM-2 评分复习），对抗遗忘规律

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

## 可扩展性

| 扩展点 | 方式 | 机制 |
|---|---|---|
| **语种** | `VocabularyRegistry.register_language(lang)` | 内置 en/de/fr/es，可扩任意语种 |
| **生成器** | `VocabularyRegistry.register_generator(name, fn)` | 词汇表/附件生成器动态注册 |
| **补全字段** | `EnricherRegistry.register(field, enricher)` | 音标/释义/词源/义项/搭配按字段注册 |
| **清洗器** | `cleaners/` 目录新增 | OCR 修复 / 例句去污染可插拔 |
| **词库** | `wordbank.py` + `ecdict.csv` | 离线词库可替换 / 扩充 |
| **LLM 后端** | `VocabularyRegistry.inject(llm=...)` | 注入式，零宿主耦合 |
| **渲染模板** | `render/` 目录 | Bell Jar 精美模板，可换样式 |

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
python -m pytest tests/ -q    # 169/169 全绿
```

覆盖：词汇条目校验 / 难度矩阵 / 词形归一化 / 语言现象识别 / 附件生成 / 端到端管线 / 词库接线 / 页眉页脚剥离。

## Token 成本估算（LLM 用量模型）

在词库（ECDICT 77 万词 / CMU 音标 / kaikki 词源）与工具库完善的前提下，LLM 只承担三个职责节点，其余全部离线（0 token）。成本由「本书关键术语数 C」驱动。

### 模型常数（DeepSeek deepseek-chat 实测校准）

| 节点 | 批大小 | 输入 token/批 | 输出 token/批 | 说明 |
|---|---|---|---|---|
| book_term_gate（本书术语判断） | 15 词 | 1900 | 1000 | 只判词频 Top 150，固定 10 批 |
| enrich（条目补全） | 6 词 | 2200 | 3600 | 完整字段 JSON |
| review（渲染前审查） | 8 词 | 7000 | 1500 | 词条 JSON + 用户需求上下文 |
| metadata（书名/作者） | 单次 | 1000 | 150 | 1 次调用 |

### 公式

- 候选术语数：`C = min(150, N / 1000)`（N = 书的总词数；每 1000 词约 1 个关键术语，上限 150）
- 批次数：`B₁ = ⌈150/15⌉ = 10`；`B₂ = ⌈C/6⌉`（enrich）；`B₃ = ⌈C/8⌉`（review）
- 输入 token：`T_in = 10×1900 + B₂×2200 + B₃×7000 + 1000`
- 输出 token：`T_out = 10×1000 + B₂×3600 + B₃×1500 + 150`
- 费用：`(T_in/1e6)×P_in + (T_out/1e6)×P_out`（P_in ≈ ¥1–2/M，P_out ≈ ¥3–8/M）

### 算例

| 书的规模 | C | 总 token | 保守费用（¥2/M in, ¥8/M out） | 典型费用（缓存命中 ¥1/M in, ¥5/M out） |
|---|---|---|---|---|
| 8 万词书（如《The Bell Jar》） | 80 | ≈ 0.20M | ≈ ¥0.85 | ≈ ¥0.50 |
| 15 万词书（如学术专著） | 150 | ≈ 0.34M | ≈ ¥1.45 | ≈ ¥0.85 |

### 说明

1. **离线优先**：普通词条的音标/释义/等级/词源全部走本地词库（ECDICT/CMU/kaikki），不计 token；LLM 只处理「本书关键术语」的子集（C ≤ 150）。
2. **gate 固定成本**：本书术语判断固定 10 批（Top 150 词），占总 token 不足 10%，不是成本驱动项；enrich 与 review 随 C 线性增长，是主要成本。
3. **保守口径**：上述按「每批输入取设计上限、输出取保守上界」估算；实际因 must_keep 子集比例与 fixes 稀疏性，通常可再低 30–50%。
4. **缓存**：三节点系统提示词共享前缀命中 DeepSeek 上下文缓存时，输入价格显著下降（表中典型档已考虑）。
5. **重试缓冲**：断点续跑 + 偶发重试建议再预留 1.3× 缓冲。

## 生态定位（PAEG 工具生态）

```
PAEG 工具生态
├── paeg-lang-style-plugin      语言规范（83/83 测试 · MCP）
├── paeg-teaching-materials     教学物料（74/74 测试 · MCP）
├── paeg-vocabulary             ⭐ 词汇表生成（169/169 测试 · MCP）
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

## 语言学学习论文（方法论依据）

| 论文 | 作者/年份 | 核心观点 | 对工具的启示 |
|---|---|---|---|
| **The Input Hypothesis: Issues and Implications** | Krashen (1985) | 可理解输入 i+1：略高于当前水平的输入最有效 | 词汇难度分级（CEFR/词频），只给学习者"够一够"的词 |
| **How Vocabulary is Learned** | Nation (2013) | 词汇学习四要素：meaning-focused input/output + language-focused learning + fluency | 12 字段补全 + 本书义 + 例句 |
| **Distributed Practice in Verbal Recall Tasks** | Cepeda et al. (2006) | 间隔练习优于集中练习，最佳间隔随保留期增长 | SRS 间隔重复（SM-2 遗忘曲线） |
| **A Framework for Developing EFL Reading Vocabulary** | Hunt & Beglar (2005) | 词汇学习框架：分级 + 语境 + 重复 | 分级内容 + 本书语境 + SRS |
| **A New Academic Word List** | Coxhead (2000) | 570 学术词族覆盖学术文本 10% | 学科术语辞典（kaikki topics） |
| **How Large a Vocabulary Is Needed?** | Nation (2006) | 阅读需 8000-9000 词族 | 词频驱动筛选（高频优先） |

## 参考项目仓库

| 项目 | 网址 | 借鉴能力 |
|---|---|---|
| **LingQ** | https://www.lingq.com | 分级阅读 + 蓝/黄/白词汇三态 + 点击查词 + SRS 复习（核心对标） |
| **Readlang** | https://readlang.com | 网页阅读器 + 即点查词 + 闪卡复习 |
| **Lute** | https://github.com/LuteOrg/lute-v3 | 开源 LingQ 替代（阅读 + 词汇库管理） |
| **Anki** | https://apps.ankiweb.net | SRS 间隔重复（SM-2 算法源头） |
| **english-read** | https://github.com/bitbw/english-read | EPUB 阅读器 + 艾宾浩斯间隔（1→30 天）+ 查词 + 学习统计 |
| **HMPrgm/lingo** | https://github.com/HMPrgm/lingo | Language Learning Companion（词汇学习助手） |
| **lang-reactor (开源版)** | https://github.com/sguzman/lang-reactor | 视频字幕查词 + 标注学习 |
| **欧路词典 Eudic** | https://www.eudic.net | 离线 mdx 词典 + 哈希索引快速查词 + 多词典合并 + 生词本（架构对标） |
| **mdict-analysis** | https://github.com/liuyug/mdict-analysis | mdx/mdd 词典格式解析（Python，索引表 + LZO 记录块） |
| **js-mdict** | https://github.com/terasum/js-mdict | mdx/mdd 解析（JS 实现，浏览器查词参考） |
