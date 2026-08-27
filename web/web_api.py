# -*- coding: utf-8 -*-
"""vocab_web — 词汇表独立网页后端（Flask API）。

三项目总控："词汇表有独立的前端网页"。提供：
上传 PDF → 选水平档位 → 制作词汇表 → 下载 HTML/PDF/附件。
复用 paeg-vocabulary-plugin 的 generate_vocabulary。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_file

# 词汇表插件 src（web/ 的上一级 = 插件根目录）
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VOCAB_SRC = os.path.join(_PLUGIN_ROOT, "src")
if os.path.isdir(_VOCAB_SRC) and _VOCAB_SRC not in sys.path:
    sys.path.insert(0, _VOCAB_SRC)

_WEB_DIR = Path(__file__).resolve().parent  # web 目录
_UPLOAD_DIR = _WEB_DIR / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    @app.route("/api/health")
    def health():
        return jsonify({"ok": True, "service": "vocab-web",
                        "plugin": "paeg-vocabulary" in sys.modules or True})

    @app.route("/api/presets")
    def presets():
        try:
            from paeg_vocabulary.level_matrix import user_presets
            return jsonify({"ok": True, "presets": user_presets()})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:200]})

    @app.route("/api/upload", methods=["POST"])
    def upload():
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify({"ok": False, "error": "缺少 PDF 文件"}), 400
        if not f.filename.lower().endswith(".pdf"):
            return jsonify({"ok": False, "error": "仅支持 PDF"}), 400
        import time
        safe = f"{int(time.time())}_{os.path.basename(f.filename)}"
        path = _UPLOAD_DIR / safe
        f.save(str(path))
        return jsonify({"ok": True, "pdf_path": str(path), "filename": safe})

    @app.route("/api/generate", methods=["POST"])
    def generate():
        data = request.get_json(force=True) or {}
        pdf = data.get("pdf_path", "")
        preset = data.get("preset", "")
        if not pdf or not os.path.exists(pdf):
            return jsonify({"ok": False, "error": "PDF 不存在——请先上传"})
        try:
            from paeg_vocabulary.registry import VocabularyRegistry
            user_filter = {}
            if preset:
                user_filter["preset"] = preset
            result = VocabularyRegistry.generate_vocabulary(
                pdf, lang=data.get("lang", "en"),
                user_filter=user_filter or None)
            return jsonify(result)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:300]})

    @app.route("/api/download/<path:name>")
    def download(name):
        # 词汇表产物在插件 output/ 目录
        out = Path(_PLUGIN_ROOT) / "output"
        safe = os.path.basename(name)
        p = out / safe
        if p.exists():
            return send_file(str(p), as_attachment=True)
        return jsonify({"error": "文件不存在"}), 404

    @app.route("/")
    def index():
        idx = _WEB_DIR / "index.html"
        if idx.exists():
            return idx.read_text(encoding="utf-8")
        return "词汇表制作网页运行中"

    return app
