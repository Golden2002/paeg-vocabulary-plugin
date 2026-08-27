# -*- coding: utf-8 -*-
"""download_wordbank.py — 下载离线词库数据（CMU 音标/ECDICT/CEFR-J/kaikki 学科辞典）。

用途：pip install 后首次运行前执行——下载大型离线词库到 data/。
（Git 铁律：333MB 词库不入库，由本脚本下载；小词表 level_matrix/cefr_words/oxford3000 已入库。）

用法：
    python scripts/download_wordbank.py          # 全量下载（~330MB）
    python scripts/download_wordbank.py --min    # 仅核心（CMU+ECDICT+CEFR-J，~66MB）
"""
import io
import os
import ssl
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "src", "paeg_vocabulary", "data")
os.makedirs(DATA, exist_ok=True)

# 忽略 SSL 证书过期（部分词库源证书过期）
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

# (文件名, URL, 大小约)
SOURCES = {
    # 核心（~66MB）
    "cmudict.dict": "https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict",
    "ecdict.csv": "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv",
    "lemma.en.txt": "https://raw.githubusercontent.com/skywind3000/ECDICT/master/lemma.en.txt",
    "cefrj.csv": "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/cefrj-vocabulary-profile-1.5.csv",
    "octanove.csv": "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/octanove-vocabulary-profile-c1c2-1.0.csv",
    # Nation 词族（10 档）
    **{f"headwords {n}th 1000.txt": f"https://www.wgtn.ac.nz/lals/resources/paul-nations-resources/paul-nations-publications/publications/documents/10000-headwords.zip"
       for n in range(1, 11)},
    # kaikki 学科辞典（phenomenology 等哲学类 + 生物/物理/化学）
    "kaikki_topic_philosophy.jsonl": "https://kaikki.org/dictionary/English/topics/Iz/philosophy/kaikki.org-dictionary-English-topic-philosophy.jsonl",
    "kaikki_topic_physics.jsonl": "https://kaikki.org/dictionary/English/topics/dC/physics/kaikki.org-dictionary-English-topic-physics.jsonl",
    "kaikki_topic_biology.jsonl": "https://kaikki.org/dictionary/English/topics/r4/biology/kaikki.org-dictionary-English-topic-biology.jsonl",
    "kaikki_topic_chemistry.jsonl": "https://kaikki.org/dictionary/English/topics/3g/chemistry/kaikki.org-dictionary-English-topic-chemistry.jsonl",
    "kaikki_topic_biochemistry.jsonl": "https://kaikki.org/dictionary/English/topics/wp/biochemistry/kaikki.org-dictionary-English-topic-biochemistry.jsonl",
    "kaikki_topic_genetics.jsonl": "https://kaikki.org/dictionary/English/topics/Ow/genetics/kaikki.org-dictionary-English-topic-genetics.jsonl",
    "kaikki_topic_anatomy.jsonl": "https://kaikki.org/dictionary/English/topics/3V/anatomy/kaikki.org-dictionary-English-topic-anatomy.jsonl",
}


def download(url: str, dest: str) -> bool:
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        print(f"  ✓ 已存在: {os.path.basename(dest)}")
        return True
    try:
        print(f"  ⬇ {os.path.basename(dest)} ...")
        if "wgtn.ac.nz" in url:
            # Nation 词族是 zip 包——需解压
            import zipfile
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=300, context=_CTX).read()
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                # 找对应档位的文件
                band = os.path.basename(dest).split()[1]  # "1st"/"2nd"...
                for name in z.namelist():
                    if band in name:
                        with open(dest, "wb") as f:
                            f.write(z.read(name))
                        print(f"  ✓ {os.path.basename(dest)} ({round(len(z.read(name))/1048576,1)} MB)")
                        return True
            return False
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=600, context=_CTX).read()
        with open(dest, "wb") as f:
            f.write(data)
        print(f"  ✓ {os.path.basename(dest)} ({round(len(data)/1048576,1)} MB)")
        return True
    except Exception as e:
        print(f"  ✗ {os.path.basename(dest)}: {str(e)[:80]}")
        return False


def main():
    only_core = "--min" in sys.argv
    ok, fail = 0, 0
    for name, url in SOURCES.items():
        if only_core and "kaikki" in name:
            continue
        if download(url, os.path.join(DATA, name)):
            ok += 1
        else:
            fail += 1
    print(f"\n完成: {ok} 成功, {fail} 失败")
    if fail:
        print("失败项可重跑本脚本（断点续传——已存在文件跳过）")


if __name__ == "__main__":
    main()
