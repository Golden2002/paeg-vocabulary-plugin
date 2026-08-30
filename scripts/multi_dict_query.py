# -*- coding: utf-8 -*-
"""multi_dict_query.py — 多词典一次性查询 CLI（义项合并去重 + 来源标注）。

一次性查多个离线词库（ECDICT / CEFR / kaikki / WordNet）并合并相同/近似义项，
打印 JSON（含每条义项的来源标注）。

用法：
    python scripts/multi_dict_query.py life phenomenon abandonment
    python scripts/multi_dict_query.py --no-wordnet genotype

离线可用：全部走本地 data/（ECDICT/CMU/kaikki/CEFR/Oxford）+ 可选 NLTK WordNet。
"""
import io
import json
import sys

# 把 src 加入 sys.path（脚本独立运行，无需 pip install -e）
import os
_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    args = [a for a in sys.argv[1:]]
    use_wordnet = "--no-wordnet" not in args
    args = [a for a in args if not a.startswith("--")]
    if not args:
        print("用法: python scripts/multi_dict_query.py [--no-wordnet] <word> [<word> ...]")
        return 1

    from paeg_vocabulary.multi_dict import MultiDict
    md = MultiDict(use_wordnet=use_wordnet)
    out = []
    for w in args:
        try:
            out.append(md.query(w))
        except Exception as e:  # 单词失败不阻塞其余
            out.append({"word": w, "error": str(e)[:120]})
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
