# -*- coding: utf-8 -*-
"""paeg_vocabulary.mcp_server — 词汇表插件 MCP server（§3.116 ⭐ 生态接入）。

像 MCP 一样直接安装即可用（§3.114 可及性）：
- pip install + MCP 配置声明即接入
- console_scripts: paeg-vocabulary-mcp
"""

from __future__ import annotations

import json
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None

from .executor import execute

SERVER_NAME = "paeg-vocabulary"


def build_server() -> "FastMCP":
    """构建 MCP server（幂等）。"""
    if FastMCP is None:
        raise RuntimeError("fastmcp 未安装：pip install 'paeg-vocabulary[mcp]'")

    mcp = FastMCP(name=SERVER_NAME, strict_input_validation=True)

    @mcp.tool()
    def generate_vocabulary(pdf_path: str, lang: str = "en",
                            min_freq: int = 2) -> str:
        """生成词汇表：书籍 PDF → 结构化词汇表（音标/释义/词源/例句/短语）。
        输入书籍 PDF 路径 + 目标语言，输出词汇表 HTML/PDF + 附件。"""
        return execute("generate_vocabulary", {
            "pdf_path": pdf_path, "lang": lang,
            "user_filter": {"min_freq": min_freq}})

    @mcp.tool()
    def list_languages() -> str:
        """支持的目标语言列表（可扩展）。"""
        return execute("list_languages", {})

    @mcp.tool()
    def list_generators() -> str:
        """可用生成器清单（可扩展）。"""
        return execute("list_generators", {})

    @mcp.tool()
    def validate_entry(headword: str, pos: str = "", ipa_json: str = "{}",
                       gloss_json: str = "{}") -> str:
        """校验词汇条目 L1 必填字段。返回缺失字段。"""
        from .core.entry import VocabularyEntry, validate_entry
        try:
            ipa = json.loads(ipa_json) if ipa_json else {}
            gloss = json.loads(gloss_json) if gloss_json else {}
        except Exception:
            ipa, gloss = {}, {}
        entry = VocabularyEntry(headword=headword, pos=pos, ipa=ipa, gloss_bilingual=gloss)
        missing = validate_entry(entry)
        return json.dumps({"ok": len(missing) == 0, "missing": missing},
                          ensure_ascii=False)

    @mcp.tool()
    def clean_examples(examples_json: str) -> str:
        """例句污染清洗（参考文献/脚注/页码/页眉页脚剔除）。"""
        from .cleaners.example_sanitize import sanitize_examples
        try:
            examples = json.loads(examples_json) if examples_json else []
        except Exception:
            examples = []
        cleaned = sanitize_examples(examples)
        return json.dumps({"ok": True, "cleaned": cleaned}, ensure_ascii=False)

    # §3.116 ⭐ 标准化接口新工具（MCP 风格 schema 驱动）
    @mcp.tool()
    def lookup_word(word: str, domains_json: str = "[]") -> str:
        """离线词库查询：音标（CMU）/释义/CEFR/学科术语——多源整合消歧。
        domains_json: 学科范围 JSON 数组（如 ["philosophy","biology"]）。"""
        try:
            domains = json.loads(domains_json) if domains_json else None
        except Exception:
            domains = None
        return execute("lookup_word", {"word": word, "domains": domains})

    @mcp.tool()
    def extract_collocations(corpus_json: str, n: int = 2,
                             min_count: int = 2, top_n: int = 30) -> str:
        """从文本提取固定搭配/短语（N-gram + PMI 显著性）。"""
        try:
            corpus = json.loads(corpus_json) if corpus_json else []
        except Exception:
            corpus = []
        return execute("extract_collocations", {
            "corpus": corpus, "n": n, "min_count": min_count, "top_n": top_n})

    @mcp.tool()
    def quantile_of(word: str, cefr_hint: str = "") -> str:
        """查询词的难度分位 Q（0-1 统一分位空间）。"""
        return execute("quantile_of", {"word": word, "cefr_hint": cefr_hint})

    @mcp.tool()
    def bank_coverage() -> str:
        """本地词库覆盖统计（CMU 音标/CEFR/学科辞典）。"""
        return execute("bank_coverage", {})

    @mcp.tool()
    def list_tools() -> str:
        """工具 schema 清单（MCP tools/list 等价——开发者自动发现）。"""
        from .tools.schema import list_tool_schemas
        return json.dumps({"ok": True, "tools": list_tool_schemas()},
                          ensure_ascii=False)

    return mcp


def main():
    """CLI 入口：启动 MCP server（stdio）。"""
    if FastMCP is None:
        print("错误：fastmcp 未安装，请先 pip install 'paeg-vocabulary[mcp]'", file=sys.stderr)
        sys.exit(1)
    server = build_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
