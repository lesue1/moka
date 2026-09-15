"""Flask 主入口 — 给 HR 同事用的 Web 应用"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, Response, render_template, request

load_dotenv()

from exporter import build_workbook
from funnel import funnel_for_all_jobs
from moka_client import (
    MokaError,
    is_logged_in,
    load_jobs_cache,
    refresh_jobs_cache,
    verify_session_valid,
)

app = Flask(__name__)

# 简单内存缓存(防同事多次点"刷新"反复打 moka)
_cache_lock = threading.Lock()
_cache: dict | None = None
_cache_ts: float = 0.0
CACHE_TTL = 60  # 秒


def _get_funnel_rows(force: bool = False) -> tuple[list[dict], list[dict]]:
    """返回 (rows, jobs)。60 秒内复用缓存。"""
    global _cache, _cache_ts

    if not force and _cache and (datetime.now().timestamp() - _cache_ts) < CACHE_TTL:
        return _cache["rows"], _cache["jobs"]

    # 1. 取职位列表(优先缓存,无则现抓)
    jobs = load_jobs_cache()
    if jobs is None:
        jobs = refresh_jobs_cache()

    # 2. 对每个职位抓漏斗
    rows = funnel_for_all_jobs(jobs)

    with _cache_lock:
        _cache = {"rows": rows, "jobs": jobs}
        _cache_ts = datetime.now().timestamp()
    return rows, jobs


@app.route("/")
def index():
    valid, reason = verify_session_valid()
    if not valid:
        return render_template(
            "error.html",
            error=f"Moka 登录态失效:{reason}。请联系管理员运行:python moka_client.py login",
        ), 503

    try:
        rows, jobs = _get_funnel_rows(force=request.args.get("force") == "1")
    except MokaError as e:
        return render_template("error.html", error=f"Moka 接口错误:{e}"), 500
    except Exception as e:
        return render_template("error.html", error=str(e)), 500

    return render_template(
        "index.html",
        rows=rows,
        job_count=len(rows),
        total_applications=sum(r["total"] for r in rows),
        fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    )


@app.route("/export.xlsx")
def export_excel():
    valid, reason = verify_session_valid()
    if not valid:
        return Response(f"Moka 登录态失效:{reason}", status=503)
    try:
        rows, _ = _get_funnel_rows()
    except MokaError as e:
        return Response(f"Moka 接口错误:{e}", status=500)
    except Exception as e:
        return Response(f"导出失败:{e}", status=500)

    data = build_workbook(rows)
    filename = f"moka-funnel-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/health")
def health():
    valid, reason = verify_session_valid()
    return {
        "status": "ok" if valid else "session_invalid",
        "logged_in": valid,
        "reason": reason,
    }


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    # 生产请改 waitress / gunicorn
    app.run(host=host, port=port, debug=False)