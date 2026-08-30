# -*- coding: utf-8 -*-
"""download_wordnet.py — 下载 WordNet 离线数据（NLTK 语料）作为附加词典源。

WordNet（普林斯顿大学，开放许可）提供英文同义词集（synset）义项定义，
作为 multi_dict 的第五个离线词典源（可选——未下载时 multi_dict 自动降级为空）。

用法：
    python scripts/download_wordnet.py

依赖：pip install nltk（项目 [nlp] 附加依赖可选包含）。
下载内容：wordnet（义项定义 + 词性）+ omw-1.4（Open Multilingual WordNet）。
下载位置：NLTK 默认 data 目录（~\\nltk_data 或 ~/nltk_data）。
来源：https://www.nltk.org/nltk_data/ · https://wordnet.princeton.edu/
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    try:
        import nltk
    except Exception:
        print("缺少 nltk，请先: pip install nltk")
        return 1
    ok = True
    for pkg in ("wordnet", "omw-1.4"):
        try:
            print(f"下载 {pkg} ...")
            nltk.download(pkg)
        except Exception as e:
            print(f"✗ {pkg}: {str(e)[:120]}")
            ok = False
    if ok:
        print("完成：WordNet 离线数据已就绪，multi_dict 查询将自动纳入 wordnet 来源。")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
