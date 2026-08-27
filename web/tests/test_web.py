# -*- coding: utf-8 -*-
"""词汇表独立网页测试（web_api + 前端页面）。"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_WEB = os.path.dirname(_HERE)  # web 目录
if _WEB not in sys.path:
    sys.path.insert(0, _WEB)

import pytest

from web_api import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


# ── R1: 健康检查 ──
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


# ── R2: 档位清单 ──
def test_presets(client):
    r = client.get("/api/presets")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    # 至少含 ielts-7.5
    ids = [p["id"] for p in d.get("presets", [])]
    assert "ielts-7.5" in ids, "应含雅思 7.5 档位"


# ── R3: 上传校验 ──
def test_upload_rejects_non_pdf(client):
    """非 PDF 上传 → 400。"""
    import io
    r = client.post("/api/upload",
                    data={"file": (io.BytesIO(b"not pdf"), "test.txt")},
                    content_type="multipart/form-data")
    assert r.status_code == 400


# ── R4: 生成校验（无 PDF）──
def test_generate_no_pdf(client):
    r = client.post("/api/generate", json={"pdf_path": "", "preset": "ielts-7.5"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is False


# ── R5: 前端页面 ──
def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "外语词汇表制作" in html
    assert "上传" in html
    assert "水平" in html


# ── R6: 下载路径安全 ──
def test_download_missing(client):
    r = client.get("/api/download/nonexistent_file.pdf")
    assert r.status_code == 404
