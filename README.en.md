# paeg-vocabulary

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-60%2F60-brightgreen.svg)](tests/)
[![MCP](https://img.shields.io/badge/MCP-Server-8A2BE2.svg)](src/paeg_vocabulary/mcp_server.py)

<p align="center">
  <strong>paeg-vocabulary</strong> — Language-learning vocabulary generator: book PDF → structured vocabulary
  <br>
  <em>CEFR-graded · etymology · multi-accent IPA · polysemy · in-book sense · Bell Jar rendering</em>
  <br>
  <em>Detachable, standalone, importable like a Python library into any agent.</em>
</p>

> **English** | [中文](README.md)

---

## What is this

`paeg-vocabulary` is a **vocabulary-generation tool for language learning** — input a book PDF, output a structured vocabulary in the target language (English / German / French / Spanish).

Born from the PAEG educational-agent vocabulary system (§3.116 iterations), rebuilt as a **zero-host-dependency** standalone plugin and an independently extensible sub-agent tool.

| Capability | Description |
|---|---|
| **Full pipeline** | extract → clean/dedup → filter → multi-dimensional enrich → structured render |
| **12-field standard** | word + IPA(multi-accent) + bilingual gloss + etymology + morpheme + senses + in-book examples + collocations + CEFR + freq |
| **Level grading** | CEFR × Zipf dual-track (IELTS/TOEFL/CET/Postgrad/TEM/GAOKAO → threshold) |
| **Form normalization** | inflection lemmatization + derivation preserved (academic terms not merged) |
| **Phenomena detection** | polysemy / collocations / slang — learning-value signals (filter exemption + render tags) |
| **In-book sense** | "in this book, the author means…" sense tagging (context-based) |
| **Beautiful rendering** | full reuse of the Bell Jar CSS template (cover/sections/entry layout) → HTML + PDF |
| **Accessories** | learning-value note / word-frequency report / author-style analysis / high-frequency page |

## Core features

- **Pipeline engine**: 5 stages (ingest → clean → filter → enrich → render), user-customizable filters (freq range / difficulty / level preset)
- **Extensible registry**: `VocabularyRegistry.register_generator(name, fn)` / `register_language(lang)`
- **Zero-host-dependency**: `Protocol` abstractions (LLMCallable / PDFReader) + injectable `chat_fn`
- **Unified executor**: `execute(name, args)` (JSON contract, never raises)
- **MCP server**: `pip install` + MCP config declaration (5 tools)
- **Pluginized enrich sub-agent**: `EnricherRegistry` per-field registration

## Architecture

```
User book PDF
      │
      ▼
┌─────────────┐   ┌──────────────┐   ┌───────────────┐   ┌───────────────┐   ┌─────────────┐
│ ① ingest    │→  │ ② clean      │→  │ ③ filter      │→  │ ④ enrich      │→  │ ⑤ render    │
│ PDF extract │   │ OCR repair   │   │ function-word │   │ IPA/gloss/ety │   │ Bell Jar    │
│ full-text   │   │ example      │   │ level preset  │   │ morpheme/sense│   │ HTML + PDF  │
└─────────────┘   │ sanitize     │   │ phenomena     │   │ book-sense/   │   └──────┬──────┘
                  └──────────────┘   │ exemption     │   │ collocations  │          │
                                     └───────────────┘   └───────────────┘          ▼
                                                                  vocab HTML + PDF + 4 accessories
```

## Install

```bash
pip install -e /path/to/paeg-vocabulary-plugin
pip install -e "paeg-vocabulary-plugin[pdf]"   # PDF extraction
pip install -e "paeg-vocabulary-plugin[nlp]"   # spaCy/wordfreq
pip install -e "paeg-vocabulary-plugin[mcp]"   # MCP server
```

Requires Python 3.9+.

## Quick start

```python
from paeg_vocabulary import VocabularyRegistry, execute

def my_llm(system_prompt, user_prompt):
    return my_model.chat(system_prompt, user_prompt)

VocabularyRegistry.inject(llm=my_llm)

result = VocabularyRegistry.generate_vocabulary(
    "/path/to/book.pdf",
    lang="en",
    user_filter={"preset": "ielts-7.5"},
    chat_fn=my_llm,
)
```

### Level presets (user_filter)

| Mode | Example | Meaning |
|---|---|---|
| Preset | `{"preset": "ielts-7.5"}` | Built-in exam preset (CEFR + Zipf threshold) |
| Custom | `{"exam": "kaoyan", "score": 70}` | Exam system + score |
| Book | `{"book_title": "The Life of the Mind", "book_author": "Arendt"}` | In-book sense tagging |

**Filter direction**: covers all levels *above* the user's level — IELTS 6.5 user gets more words (~3000), 8.0 fewer (~1600).

### Unified executor (MCP contract)

```python
from paeg_vocabulary.executor import execute

print(execute("list_languages"))     # ["de","en","es","fr"]
print(execute("list_generators"))
print(execute("validate_entry", {"headword": "life", "pos": "n."}))
print(execute("clean_examples", {"examples": ["…"]}))
print(execute("generate_vocabulary", {"pdf_path": "book.pdf", "user_filter": {...}}))
```

## MCP

```bash
paeg-vocabulary-mcp    # stdio
```

```json
{ "mcpServers": { "paeg-vocabulary": { "command": "paeg-vocabulary-mcp", "args": [] } } }
```

**5 tools**: `generate_vocabulary` / `list_languages` / `list_generators` / `validate_entry` / `clean_examples`.

## Entry standard (12 fields)

| Tier | Field | Description |
|---|---|---|
| L1 | headword | lemma form, singular |
| L1 | pos | part of speech |
| L1 | ipa | multi-accent (en_us / en_uk / de…) |
| L1 | gloss_bilingual | zh + en gloss |
| L1 | examples | in-book first (real context) |
| L1 | lemma | lemmatization |
| L2 | etymology | language family + root/affix + evolution |
| L2 | morpheme | root/prefix/suffix breakdown |
| L2 | senses | multi-sense (Etymology.Sense numbering) |
| L2 | collocations | phrases |
| L3 | cefr_level | A1-C2 |
| L3 | freq_rank | in-book frequency rank |

**Form normalization**: inflection (POS unchanged -ed/-ing/-s) → lemma; derivation (POS changed / -tion/-ment/-ness) → keep original — `abandonment` is a Heideggerian term, never merged.

## Tests

```bash
python -m pytest tests/ -q    # 60/60 green
```

## Ecosystem (PAEG tool ecosystem)

```
PAEG tool ecosystem
├── paeg-lang-style-plugin      language style (83/83 tests · MCP)
├── paeg-teaching-materials     teaching materials (74/74 tests · MCP)
├── paeg-vocabulary             ⭐ vocabulary generator (60/60 tests · MCP)
└── PAEG main project (plugin-first dual-track · material_bridge · sys.path plugin copies)
```

**Integration**: `pip install` → `import` → register → inject LLM → ready. The main project loads plugin copies via `sys.path`; typing「生成词汇表：xxx.pdf」in chat → magic keyword → `material_router` → `vocab_done` SSE event → frontend popup card.

## License

MIT
