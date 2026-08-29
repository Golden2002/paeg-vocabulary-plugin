# spaCy POS 词形还原路径验证（§3.116 ⭐ Round 7）

承接 Round 6 遗留 nextStep ①：词元化仍存动名词兼名词歧义（`reading/feeling/drawing/writing/
painting/cooking` 既是动名词又是独立名词），频率信号 + stoplist 三层已收敛但无法彻底消除。
本轮在本机 py3.12 venv 安装 spaCy + en_core_web_sm，让 `_lemmatize_with_pos` 的 POS 感知路径
真正生效，并用测试锁定行为。

## 一、环境

```powershell
py -3.12 -m venv D:\wbo-workspace\.venv-spacy312
.venv-spacy312\Scripts\python.exe -m pip install "spacy>=3.7" pytest
.venv-spacy312\Scripts\python.exe -m spacy download en_core_web_sm
```

实测：`spacy 3.8.16` + `en_core_web_sm 3.8.0`。

## 二、动词/名词上下文消歧实测

`_lemmatize_with_pos(["I","am","reading","a","book"])`（动词上下文）：

| token | lemma | pos | lemma_pos |
|---|---|---|---|
| reading | `read` | VERB | VERB |
| am | `be` | AUX | VERB |

`_lemmatize_with_pos(["the","reading","of","the","book"])`（名词上下文）：

| token | lemma | pos | lemma_pos |
|---|---|---|---|
| reading | `reading` | NOUN | NOUN |

**结论**：spaCy 按上下文 POS 判定——动词 `reading` 还原为 `read`，名词 `reading` 保持原形。
这正是规则级兜底无法消除的歧义。

## 三、不规则三单（与规则兜底一致）

| token | lemma | pos |
|---|---|---|
| goes | `go` | VERB |
| does | `do` | AUX |
| has | `have` | VERB |

与 Round 6 规则兜底 `_IRREGULAR_LEMMAS`（`goes→go`/`does→do`/`has→have`）结果一致，双路径收敛。

## 四、端到端（clean_corpus）

输入 `raw_corpus = "I am reading a book. The reading was beautiful."`，`clean_corpus` 产出：

```
lemmas:   ['read', 'book', 'reading', 'beautiful']
tokens:   ['reading', 'book', 'reading', 'beautiful']
```

- 动词 `reading` → 折叠为 `read`
- 名词 `reading` → 保留为独立词条 `reading`
- 停用词（`I/am/a/the/was`）正确过滤（`be`/`i`/`a` 不在 lemma 集合）

## 五、测试结果

| 环境 | 命令 | 结果 |
|---|---|---|
| py3.14（无 spaCy） | `python -m pytest tests/ web/tests/ -q` | `206 passed, 1 skipped`（spaCy 测试自动跳过） |
| py3.12 venv（spaCy） | `python -m pytest tests/ -q` | `198 passed`（190 原有 + 8 新 spaCy 测试） |
| py3.12 venv（spaCy） | `python -m pytest tests/test_spacy_pos.py -v` | `8 passed` |

`test_spacy_pos.py` 用 `pytest.importorskip("spacy")` 自动降级：无 spaCy 时跳过（不阻塞管线、
不影响「pytest 全绿」），有 spaCy 时锁定 POS 消歧行为。规则级兜底路径仍由
`test_lemmatize_fix.py` 全量覆盖（无 spaCy 环境的验收口径）。

## 六、代码位置

- 被测路径：`src/paeg_vocabulary/pipeline/clean_dedup.py::_lemmatize_with_pos`
  （spaCy 可用时按上下文 POS 消歧；缺失时降级 `_rule_lemmatize`，见文件内 V-R8 注释）
- 新测试：`tests/test_spacy_pos.py`（8 用例）
- 文档：`CHANGELOG.md` v0.1.7、`README.md`（测试说明）
