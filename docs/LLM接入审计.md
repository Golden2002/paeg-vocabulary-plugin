# LLM 接入审计 — paeg-vocabulary-plugin

> 审计目标：逐环节列出「LLM 已接入 / 未接入 / 接入质量」，给出补强清单与每个 LLM 环节的系统提示词要点。
> 统一设计原则（§3.120）：**python 脚本算确定性数据 + 系统提示词 harness LLM 做判别/生成**——LLM 只负责分析/判别/生成，不负责算数；确定性数据（词频/CEFR/词源/音标）一律由离线脚本算好再喂给 LLM。
> 降级铁律：**LLM 失败一律优雅降级不阻塞**（无 key → 空串 → 规则层兜底；任何异常 → 静默跳过）。

---

## 一、总体结论

| 维度 | 结论 |
|---|---|
| LLM 已接入环节 | **7 个**（OCR 清理 / 术语识别 / 元数据 / 批量补全 / 渲染审查 / 智能解读 / 趣味解读） |
| 有意不接 LLM（离线确定性） | 音标（CMU）、分级（Oxford/CEFR-J）、词源（kaikki 离线）、搭配（N-gram+PMI）、SRS（SM-2）、分位筛选（Q 分位）——这些「不接 LLM」是正确设计，保速度、省 token |
| 接入质量总体 | 良好：全部带失败降级、全部带确定性输入打底、JSON schema 校验防串味 |
| 主要缺口 | OCR 清理为新增（需实测校准）；批量补全已补 CEFR 字段；review 覆盖字段有限（仅 gloss/pos/etymology 三层回写） |

---

## 二、逐环节审计表

### 0. 离线确定性层（有意不接 LLM ⭐）

| 环节 | 文件 | LLM 状态 | 说明 |
|---|---|---|---|
| 音标 | wordbank.py（CMU）+ enrichers/ipa_enricher.py | **未接入**（正确） | CMU 13 万词 ARPAbet→IPA 离线；espeak-ng 兜底。LLM 音标成本高、易错、无必要 |
| CEFR 分级 | wordbank.py（Oxford/CEFR-J）+ filter.py（wordfreq→zipf→CEFR） | **未接入**（正确） | 离线词表权威；wordfreq Zipf 桥接 |
| 词源/多义项 | wordbank.py（kaikki Wiktionary 分片） | **未接入**（正确） | 学科术语离线辞典；LLM 仅在批量补全阶段精修 |
| 搭配 | collocations.py（N-gram + PMI） | **未接入**（正确） | 原著统计，LLM 无法比 PMI 更准 |
| SRS | srs.py（SM-2） | **未接入**（正确） | 确定性算法 |
| 分位筛选 | quantile_engine.py / quantile_filter.py | **未接入**（正确） | Q 分位纯离线 |

---

### 1. OCR 词库清理 / 判别 / 修复 / 错误提取（新增 ⭐ 本次改造）

| 项 | 内容 |
|---|---|
| 文件 | `src/paeg_vocabulary/enrichers/ocr_llm_cleaner.py` |
| 接入点 | `registry.generate_vocabulary` 阶段 2（clean_corpus 之后、filter 之前） |
| 状态 | **已接入**（v0.1.12 新增） |
| 质量 | 确定性打标 + LLM 判别；`repair/spelling` 改写词形、`proper/noise` 剔除、`keep` 保留；失败降级到规则层（`_is_clean_word`/`_is_proper_noun` 继续兜底） |
| 降级 | 无 chat_fn / LLM 空响应 / 任何异常 → 返回原 ctx（规则层兜底，不阻塞） |
| **系统提示词要点** | ① 五类判别 `repair/spelling/proper/noise/keep` 明确定义与例句（scienc→science / Plath / gggg）② 只输出 JSON `{"decisions":[{word,action,replacement,reason}]}` ③ 每个输入词必给一条 decision ④ 不确定一律判 `keep`（宁可不改、不误删合法词）⑤ 大写比例高的词优先考虑专名 |
| 确定性输入 | 词频（Counter）+ 大写比例（capitalized_stats）→ 只挑「离线词典外词」（ecdict/CMU/CEFR/Oxford/wordfreq≥4.0 均不认识）送 LLM，上限 200 词 |

---

### 2. 本书关键术语识别（must_keep 豁免）

| 项 | 内容 |
|---|---|
| 文件 | `src/paeg_vocabulary/enrichers/book_term_gate.py` |
| 接入点 | filter 之前（`judge_book_terms` → `must_keep` → 筛选豁免） |
| 状态 | **已接入** |
| 质量 | 良好：只判词频 Top 150、15 词/批；无 LLM 兜底（domain 命中 + freq≥3 且 zipf≥3） |
| 降级 | 无 LLM → `fallback_must_keep` 启发式 |
| **系统提示词要点** | ① 判定标准三选一（学科核心术语 / 反复出现的框架词 / 普通高频词不算）② 输出 `{"must_keep":[{word,reason}]}` ③ 给出「the/and/one 不算」的反例约束 |
| 缺口 | 未带本书上下文（contexts 多数为空）；reason 只用于展示未参与排序 |

---

### 3. 书名 / 作者元数据判定

| 项 | 内容 |
|---|---|
| 文件 | `src/paeg_vocabulary/metadata.py` |
| 接入点 | filter 之后、enrich 之前（`extract_book_meta_llm`） |
| 状态 | **已接入** |
| 质量 | 良好：读前 15 页、重试 2 次、文件名特征拦截（`_looks_like_filename`）、用户提供优先 |
| 降级 | 用户提供 > LLM 判定 > 文件名兜底 |
| **系统提示词要点** | ① 书名取标题页/扉页/版权页正式书名 ② 严禁输出文件名/ISBN/出版社/年份/系列名 ③ 只输出 `{"book_title","book_author"}` |
| 缺口 | 仅英文书名路径充分；多语种书名未单独调优 |

---

### 4. 词条批量补全（在线制作词条）

| 项 | 内容 |
|---|---|
| 文件 | `src/paeg_vocabulary/enrichers/batch_llm.py`（批量）+ `llm_enricher.py`（单条兜底） |
| 接入点 | enrich 阶段（wordbank 离线优先之后） |
| 状态 | **已接入**（v0.1.12 补强：新增 `cefr_level` 字段） |
| 质量 | 良好：6 词/批（防截断）、JSON schema + headword 校验防串味、断点续跑；**本次审计补齐 CEFR 等级字段** |
| 降级 | 无 LLM → wordbank 离线字段已先填；批失败跳过不阻塞 |
| **系统提示词要点** | ① 输出 JSON 数组、长度/顺序与输入一致 ② `headword` 必须与输入完全一致（防串味校验）③ 全字段：`pos/gloss_zh/gloss_en/ipa/etymology/morpheme/senses/book_sense/examples/collocations/cefr_level` ④ 多义词按义项拆分 senses ⑤ 无法确定留空但字段名保留 |
| 缺口 | `book_sense` 依赖书名/作者已判定（弱模式时为通用义）；`morpheme` 深层词根链未强制 |

---

### 5. 渲染前审查（review）

| 项 | 内容 |
|---|---|
| 文件 | `src/paeg_vocabulary/pipeline/review.py` |
| 接入点 | enrich 之后、render 之前 |
| 状态 | **已接入** |
| 质量 | 中：8 词/批、`{"fixes":[{word,field,before,after,action}]}`、支持 remove/replace/add；但 registry 回写仅覆盖 `gloss_bilingual/pos/etymology` 三层 |
| 降级 | 无 LLM → 原样返回 |
| **系统提示词要点** | ① 按「用户需求」逐条审查六类问题（释义错/词性错/音标错/例句不匹配/噪声 remove/缺字段补全）② 只列需修正的词条 ③ 输出 `{"fixes":[...]}` |
| 缺口 | 审查回写字段不全（senses/examples/collocations/ipa 未回写）；与 L0 校对（lang_style）重复劳动可合并 |

---

### 6. 附件：智能学习解读

| 项 | 内容 |
|---|---|
| 文件 | `src/paeg_vocabulary/accessories/__init__.py::llm_analysis` |
| 接入点 | generate_all_accessories（渲染后） |
| 状态 | **已接入** |
| 质量 | 良好：三段式（高频词主题聚类 / 作者风格画像 / 学习价值路径）+ 确定性统计打底（高频词/CEFR/POS/句长/TTR） |
| 降级 | 失败 → 空串，不产出该附件 |
| **系统提示词要点** | ① 三部分结构固定 ② 每节 3-6 条要点 ③ 直接引用统计数字作依据 ④ 拒绝空话套话 |

---

### 7. 附件：趣味语言解读（新增 ⭐ 本次改造）

| 项 | 内容 |
|---|---|
| 文件 | `src/paeg_vocabulary/accessories/__init__.py::llm_fun_insights` |
| 接入点 | generate_all_accessories + 交互式交付页「趣味解读」标签页 |
| 状态 | **已接入**（v0.1.12 新增） |
| 质量 | 良好：四段式（关键术语「为什么重要」/ 语言冷知识 / 同源词族 / 学习小贴士）+ 确定性数据（高频词+词源+CEFR）打底 |
| 降级 | 失败 → 空串，不产出该附件、交互页该标签显示「暂无」 |
| **系统提示词要点** | ① 四部分结构固定（为什么重要 / 冷知识 / 同源词族 / 学习小贴士）② 直接引用给定词/词源数据作依据 ③ 有趣可读、拒绝空话 ④ 中文输出、markdown、## 分节 |

---

## 三、补强清单（按优先级）

| # | 项 | 优先级 | 说明 |
|---|---|---|---|
| 1 | review 回写字段补全 | P1 | 审查结果仅回写 gloss/pos/etymology，应扩展到 senses/examples/collocations/ipa |
| 2 | OCR 清理实测校准 | P1 | 新增环节，需在真实 OCR 样本上校准 `_known_word` 阈值（wordfreq≥4.0）与 `repair/spelling` 判别的误改率 |
| 3 | book_term_gate 带上下文 | P2 | 把候选词的本书上下文传给 LLM，提升术语判定精度 |
| 4 | 多语种元数据判定 | P2 | de/fr/es 书名/作者判定路径单独调优 |
| 5 | batch_llm 词根链深度 | P3 | morpheme 增加「派生链」（如 phenomenon → phenomena → phenomenal） |
| 6 | LLM 失败重试/缓存 | P3 | 三节点共享系统提示词前缀命中 DeepSeek 上下文缓存，进一步降本 |

---

## 四、系统提示词要点速查（一页纸）

| 环节 | 一句话系统提示词核心 |
|---|---|
| OCR 清理 | 「五类判别 repair/spelling/proper/noise/keep；不确定一律 keep；只输出 JSON decisions」 |
| 术语识别 | 「学科核心术语 / 反复出现框架词保留；普通高频词不算；输出 must_keep」 |
| 元数据 | 「从标题页文本识别真书名/作者；严禁输出文件名/ISBN/年份；只输出 JSON」 |
| 批量补全 | 「JSON 数组长度顺序与输入一致；headword 完全一致；12 字段全给；多义词拆义项」 |
| 渲染审查 | 「按用户需求逐条审查六类问题；只列需修正项；输出 fixes」 |
| 智能解读 | 「三部分结构；直接引用统计数字；拒绝空话」 |
| 趣味解读 | 「四部分结构；引用词源数据；有趣可读」 |
