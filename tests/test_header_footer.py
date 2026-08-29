# -*- coding: utf-8 -*-
"""页眉页脚剥离测试：跨页重复行 + 页码正则 + 坐标带。"""
import pytest

from paeg_vocabulary.pipeline.pdf_ingest import (
    _strip_headers_footers, _strip_repeated_lines, _is_page_number,
)


def test_is_page_number():
    assert _is_page_number("42")
    assert _is_page_number(" 42 ")
    assert _is_page_number("42 / 120")
    assert _is_page_number("Page 7")
    assert _is_page_number("vii")  # 罗马数字
    assert not _is_page_number("Population Genetics")
    assert not _is_page_number("Chapter 3")


def test_strip_repeated_lines():
    # 每页都有书名行 + 页码行 + 不同正文
    pages = [
        "Population Genetics\n12\nAllele frequency\nis measured",
        "Population Genetics\n13\nGenotype distribution\nvaries",
        "Population Genetics\n14\nPhenotype expression\ndepends",
    ]
    text = "\n\n".join(pages)
    stripped = _strip_repeated_lines(text)
    assert "Population Genetics" not in stripped  # 重复行被剥
    assert "12" not in stripped and "13" not in stripped  # 页码被剥
    assert "Allele frequency" in stripped  # 正文保留
    assert "Genotype" in stripped


def test_strip_headers_footers_cross_page():
    from paeg_vocabulary.core.context import PageMeta
    metas = [
        PageMeta(page_no=1, header="Population Genetics", footer="12",
                 body="Allele frequency is measured by genotyping"),
        PageMeta(page_no=2, header="Population Genetics", footer="13",
                 body="Genotype distribution varies across loci"),
        PageMeta(page_no=3, header="Population Genetics", footer="14",
                 body="Phenotype expression depends on environment"),
    ]
    kept, dropped = _strip_headers_footers(metas)
    # 书名在页眉重复 → 剥离
    assert "Population Genetics" not in " ".join(m[1].body for m in kept)
    assert "Population Genetics" in dropped
    # 正文保留
    assert "Allele frequency" in kept[0][1].body


def test_strip_headers_footers_keeps_unique_body():
    from paeg_vocabulary.core.context import PageMeta
    metas = [
        PageMeta(page_no=1, header="Chapter 1", footer="1",
                 body="The quick brown fox jumps over the lazy dog"),
        PageMeta(page_no=2, header="Chapter 2", footer="2",
                 body="A different unique sentence appears here"),
    ]
    kept, dropped = _strip_headers_footers(metas)
    bodies = " ".join(m[1].body for m in kept)
    assert "quick brown fox" in bodies  # 唯一正文保留
