# -*- coding: utf-8 -*-
"""vocab_web — 词汇表独立网页后端（Flask API）。

提供：上传 PDF → 选水平档位 → 制作词汇表 → 交互式浏览（翻页 + 点击查词 + SRS 三态反馈）
→ 下载 HTML/PDF/附件。复用 paeg-vocabulary-plugin 的 generate_vocabulary。
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
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

# ── 进程内状态（交互式浏览）──
_LAST_ENTRIES = []          # 最近一次生成的词条（全字段，最多 300）
_LAST_BOOK = ""             # 最近书名
_SRS_STATE = {}             # word -> {status: new/learning/mastered, reps: n}

# ── 长任务作业注册表（§2.6-4 ⭐ job_id + 轮询/进度）──
# /api/generate 不再同步阻塞：立即返回 job_id，后台线程跑生成，
# 前端轮询 /api/jobs/<job_id> 拿进度——浏览器断连也不丢任务（服务端继续跑）。
_JOBS = {}                  # job_id -> {job_id, status, progress, stage, result, error, ...}
_JOBS_LOCK = threading.Lock()

# 作业状态机：pending → running → done / error
_JOB_STATUSES = ("pending", "running", "done", "error")

# ── 本地词库预热（点击查词性能）──
# WordBank 首次查询要懒加载 ~285MB（ecdict 63MB + kaikki 学科术语 ~218MB），
# 实测首查 15.7s、缓存后 <10ms。若把这次开销留在用户第一次「点击查词」上，
# 阅读器会卡 15s 无响应。这里在服务启动时后台线程预热词库，把开销移到启动期，
# 用户首查即命中缓存。 /api/health 暴露 wordbank_warm 供前端/测试感知预热完成。
_WORD_BANK_WARM = threading.Event()
_WORD_BANK_ERROR = ""


def _prewarm_wordbank() -> None:
    """后台预热本地词库（触发 WordBank 全部缓存加载）。"""
    global _WORD_BANK_ERROR
    try:
        from paeg_vocabulary.wordbank import WordBank
        WordBank().coverage_stats()  # 触发 cmu/cefr/oxford/kaikki/ecdict 全部缓存
        _WORD_BANK_WARM.set()
    except Exception as e:  # noqa: BLE001 —— 预热失败不阻塞服务，仅记录
        _WORD_BANK_ERROR = str(e)[:200]


def _new_job() -> dict:
    """创建长任务作业并注册（线程安全）。"""
    job_id = uuid.uuid4().hex
    now = time.time()
    job = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "stage": "排队中",
        "result": None,
        "error": "",
        "created_at": now,
        "updated_at": now,
    }
    with _JOBS_LOCK:
        _JOBS[job_id] = job
    return job


def _update_job(job_id: str, **fields) -> None:
    """更新作业状态（线程安全，忽略未知作业）。"""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return
        job.update(fields)
        job["updated_at"] = time.time()


def _book_from_result(result: dict, pdf: str) -> str:
    """从生成结果推导书名（优先 HTML 文件名，回退 PDF 文件名）。"""
    h = str(result.get("html_path") or "")
    if h:
        stem = os.path.basename(h)
        stem = stem.replace("_词汇表.html", "").replace("_词汇表.pdf", "")
        return stem
    return os.path.basename(pdf)


def _run_generate_job(job_id: str, pdf: str, preset: str, lang: str) -> None:
    """后台线程：跑 generate_vocabulary 并把进度/结果写回作业。"""
    try:
        from paeg_vocabulary.registry import VocabularyRegistry

        def _progress_cb(stage: str, pct: int) -> None:
            _update_job(job_id, status="running", stage=stage, progress=int(pct))

        _update_job(job_id, status="running", stage="开始生成", progress=1)
        user_filter = {"preset": preset} if preset else {}
        result = VocabularyRegistry.generate_vocabulary(
            pdf, lang=lang, user_filter=user_filter or None,
            progress_cb=_progress_cb)

        # 存进程内状态（供交互式浏览：/api/entries、/api/srs）
        global _LAST_ENTRIES, _LAST_BOOK
        _LAST_ENTRIES = result.get("entries_preview", []) or []
        _LAST_BOOK = _book_from_result(result, pdf)
        # 注意：不要覆盖 result["entries_count"]（真实词条总数）——
        # entries_preview 是截断到 300 条的预览，两者语义不同。
        _update_job(job_id, status="done", progress=100, stage="完成", result=result)
    except Exception as e:  # noqa: BLE001 —— 后台线程异常也要回写作业（绝不静默丢任务）
        _update_job(job_id, status="error", stage="失败", error=str(e)[:300])


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    _testing = bool(config and config.get("TESTING"))

    # 后台预热词库（daemon 线程，不阻塞服务启动；进程内只预热一次）。
    # 单元测试（TESTING=True）不预热，避免把 ~285MB 词库加载拖进 194 条核心用例。
    if not _testing and not _WORD_BANK_WARM.is_set() and not _WORD_BANK_ERROR:
        threading.Thread(target=_prewarm_wordbank, daemon=True).start()

    @app.route("/api/health")
    def health():
        from paeg_vocabulary.llm_client import available
        return jsonify({"ok": True, "service": "vocab-web",
                        "llm_available": available(),
                        "wordbank_warm": _WORD_BANK_WARM.is_set(),
                        "wordbank_error": _WORD_BANK_ERROR})

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
        safe = f"{int(time.time())}_{os.path.basename(f.filename)}"
        path = _UPLOAD_DIR / safe
        f.save(str(path))
        return jsonify({"ok": True, "pdf_path": str(path), "filename": safe})

    @app.route("/api/generate", methods=["POST"])
    def generate():
        """§2.6-4 ⭐ 长任务改造：不再同步阻塞，立即返回 job_id（202）。

        后台线程跑 generate_vocabulary（1-3 分钟），前端轮询 /api/jobs/<job_id>。
        浏览器断连不丢任务——服务端后台线程继续跑完并保存结果。
        """
        data = request.get_json(force=True) or {}
        pdf = data.get("pdf_path", "")
        preset = data.get("preset", "")
        lang = data.get("lang", "en")
        if not pdf or not os.path.exists(pdf):
            return jsonify({"ok": False, "error": "PDF 不存在——请先上传"}), 400
        job = _new_job()
        threading.Thread(
            target=_run_generate_job,
            args=(job["job_id"], pdf, preset, lang),
            daemon=True,
        ).start()
        return jsonify({"ok": True, "job_id": job["job_id"],
                        "status": job["status"]}), 202

    @app.route("/api/jobs/<job_id>")
    def job_status(job_id):
        """轮询长任务进度（§2.6-4 ⭐）。

        返回：{ok, job_id, status: pending/running/done/error,
                progress: 0-100, stage: str, result?: dict, error?: str}
        result 仅在 status == done 时返回（含 entries_preview/html_path 等）。
        """
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
            if job is None:
                return jsonify({"ok": False, "error": "未知 job_id"}), 404
            snapshot = dict(job)
        return jsonify({"ok": True, **snapshot})

    @app.route("/api/entries")
    def entries():
        """交互式词条分页（翻页）+ 搜索 + SRS 三态过滤。"""
        page = max(1, int(request.args.get("page", 1)))
        page_size = max(5, min(100, int(request.args.get("page_size", 20))))
        q = (request.args.get("q", "") or "").strip().lower()
        status = (request.args.get("status", "") or "").strip()
        items = list(_LAST_ENTRIES)
        if q:
            items = [e for e in items
                     if q in (e.get("headword", "") or "").lower()
                     or q in (e.get("gloss_zh", "") or "").lower()
                     or q in (e.get("gloss_en", "") or "").lower()]
        if status in ("new", "learning", "mastered"):
            items = [e for e in items
                     if _srs_of(e.get("headword")) == status]
        total = len(items)
        start = (page - 1) * page_size
        chunk = items[start:start + page_size]
        # 附 SRS 状态
        for e in chunk:
            e["srs"] = _srs_of(e.get("headword"))
        return jsonify({"ok": True, "book": _LAST_BOOK, "total": total,
                        "page": page, "page_size": page_size,
                        "pages": max(1, (total + page_size - 1) // page_size),
                        "entries": chunk})

    @app.route("/api/srs", methods=["POST"])
    def srs():
        """SRS 三态反馈（对标 LingQ 蓝/黄/白）：new→learning→mastered 循环。"""
        data = request.get_json(force=True) or {}
        word = (data.get("word", "") or "").strip()
        status = (data.get("status", "") or "").strip()
        if not word:
            return jsonify({"ok": False, "error": "缺少 word"}), 400
        order = ("new", "learning", "mastered")
        if status in order:
            _SRS_STATE[word] = {"status": status,
                                "reps": 0 if status == "new" else (1 if status == "learning" else 3)}
        else:  # 循环推进
            cur = _srs_of(word)
            nxt = order[(order.index(cur) + 1) % 3] if cur in order else "learning"
            _SRS_STATE[word] = {"status": nxt,
                                "reps": 0 if nxt == "new" else (1 if nxt == "learning" else 3)}
        return jsonify({"ok": True, "word": word, "srs": _srs_of(word),
                        "state": _SRS_STATE.get(word, {})})

    def _srs_of(word):
        return (_SRS_STATE.get(word) or {}).get("status", "new")

    @app.route("/api/download/<path:name>")
    def download(name):
        out = Path(_PLUGIN_ROOT) / "output"
        safe = os.path.basename(name)
        p = out / safe
        if p.exists():
            return send_file(str(p), as_attachment=True)
        return jsonify({"error": "文件不存在"}), 404

    @app.route("/api/lookup", methods=["POST"])
    def lookup():
        """点击查词（阅读器）——查词义/音标/CEFR/本书义。"""
        data = request.get_json(force=True) or {}
        word = (data.get("word", "") or "").strip()
        if not word:
            return jsonify({"ok": False, "error": "缺少 word"}), 400
        try:
            from paeg_vocabulary.executor import execute
            return jsonify(json.loads(execute("lookup_word", {"word": word})))
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:200]})

    @app.route("/")
    def index():
        idx = _WEB_DIR / "index.html"
        if idx.exists():
            return idx.read_text(encoding="utf-8")
        return "词汇表制作网页运行中"

    @app.route("/reader")
    def reader():
        r = _WEB_DIR / "reader.html"
        if r.exists():
            return r.read_text(encoding="utf-8")
        return "阅读器待构建"

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5002, debug=False)
