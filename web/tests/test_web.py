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
    app = create_app({"TESTING": True})
    app.config["TESTING"] = True
    return app.test_client()


# ── R1: 健康检查 ──
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_health_reports_wordbank_status(client):
    """/api/health 暴露词库预热状态（wordbank_warm / wordbank_error）。"""
    d = client.get("/api/health").get_json()
    assert "wordbank_warm" in d
    assert isinstance(d["wordbank_warm"], bool)
    assert "wordbank_error" in d


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


# ── R4: 生成校验（无 PDF）→ 400（§2.6-4 job_id 改造后，缺失 PDF 直接拒绝）──
def test_generate_no_pdf(client):
    r = client.post("/api/generate", json={"pdf_path": "", "preset": "ielts-7.5"})
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


# ── R5: 前端页面 ──
def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "外语词汇表工作台" in html
    assert "上传" in html
    assert "水平" in html
    assert "制作词汇表" in html


# ── R6: 下载路径安全 ──
def test_download_missing(client):
    r = client.get("/api/download/nonexistent_file.pdf")
    assert r.status_code == 404


# ── R7: 长任务 job_id + 轮询（§2.6-4 ⭐）──
def test_job_status_unknown(client):
    """轮询不存在的 job_id → 404。"""
    r = client.get("/api/jobs/doesnotexist")
    assert r.status_code == 404


def test_job_registry_lifecycle(client):
    """作业注册表：pending → running → done，轮询端点逐步可见。"""
    import web_api
    job = web_api._new_job()
    job_id = job["job_id"]

    # 初始 pending
    d = client.get(f"/api/jobs/{job_id}").get_json()
    assert d["ok"] is True
    assert d["status"] == "pending"
    assert d["progress"] == 0

    # 运行中 + 进度
    web_api._update_job(job_id, status="running", stage="解析 PDF", progress=8)
    d2 = client.get(f"/api/jobs/{job_id}").get_json()
    assert d2["status"] == "running"
    assert d2["stage"] == "解析 PDF"
    assert d2["progress"] == 8

    # 完成 + 结果
    web_api._update_job(job_id, status="done", progress=100, stage="完成",
                        result={"ok": True, "entries_count": 3, "entries_preview": []})
    d3 = client.get(f"/api/jobs/{job_id}").get_json()
    assert d3["status"] == "done"
    assert d3["progress"] == 100
    assert d3["result"]["entries_count"] == 3
