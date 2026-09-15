"""Moka 招聘系统客户端 — 抓取职位列表与候选人漏斗数据

数据获取流程:
  1. 启动时检查 moka_session.json 是否存在有效登录态
  2. 没有则启动 Playwright headless 浏览器打开登录页,人工输入账号密码后保存 cookie
  3. 抓取左侧职位列表 DOM 缓存到 jobs_cache.json
  4. 对每个职位调 search-candidate/v2 接口拿候选人列表
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
SESSION_FILE = BASE_DIR / "moka_session.json"
JOBS_CACHE_FILE = BASE_DIR / "jobs_cache.json"
MOKA_BASE = os.getenv("MOKA_BASE_URL", "https://app.mokahr.com").rstrip("/")
SEARCH_URL = f"{MOKA_BASE}/api/outer/ats-candidate-search-left/candidate/search-candidate/v2"
PAGING_URL = f"{MOKA_BASE}/api/outer/ats-jc/job/jobs/paging"

# 漏斗 9 个固定阶段 + 1 个归档状态
FUNNEL_STAGES = [
    "初筛",
    "用人部门筛选",
    "初试",
    "测评",
    "复试",
    "终试",
    "沟通Offer",
    "待入职",
    "已入职",
]


class MokaError(Exception):
    pass


def _load_session() -> dict | None:
    """读取持久化的 Playwright storage_state。"""
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        # 简化:不严格校验 cookie 过期时间,由 Playwright 重新登录处理
        return data
    except Exception:
        return None


def _save_session(storage_state: dict) -> None:
    SESSION_FILE.write_text(
        json.dumps(storage_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_logged_in() -> bool:
    valid, _ = verify_session_valid()
    return valid


def verify_session_valid() -> tuple[bool, str]:
    """真实验证 session 是否有效 — 发一次轻量请求看 moka 响应。

    返回 (is_valid, reason)。比单纯检查文件存在更靠谱,避免 session 过期却误报已登录。
    """
    if not SESSION_FILE.exists():
        return False, "session file not found"
    try:
        sess = _requests_session()
        resp = sess.post(
            SEARCH_URL,
            json={"pipelineId": "40490", "limit": 1},
            timeout=10,
        )
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        payload = resp.json()
        if not payload.get("success"):
            return False, payload.get("msg", "unknown error")
        return True, ""
    except Exception as e:
        return False, str(e)


def login_interactive() -> None:
    """首次登录:启动 Playwright 打开 moka 登录页,等用户手动输入账号密码。

    用户登录成功后(URL 不再是登录页),把 cookies 存盘。
    """
    from playwright.sync_api import sync_playwright

    print("[moka] 正在打开登录页...请在浏览器窗口里输入账号密码")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 必须有窗口才能让用户输入
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.goto(f"{MOKA_BASE}/login", wait_until="domcontentloaded")

        # 等用户登录成功 — 多种判断方式(SPA 可能 URL 不变)
        for _ in range(180):  # 最多 3 分钟
            time.sleep(1)
            url = page.url
            cookies = context.cookies()
            cookie_names = {c["name"] for c in cookies}

            # 判定 1:URL 不在登录页
            url_ok = "/login" not in url and "mokahr.com" in url
            # 判定 2:moka 特有的已登录 cookie(USER_TOKEN / moka_session / recruiter_uid 等)
            cookie_ok = bool({"USER_TOKEN", "moka_session", "_token"} & cookie_names)
            # 判定 3:页面 DOM 出现已登录特征(用户头像、候选人管理入口等)
            dom_ok = page.evaluate(
                """
                () => {
                    const t = document.body.innerText || '';
                    return t.includes('候选人管理') || t.includes('招聘职位')
                        || document.querySelector('[class*="avatar"]') !== null;
                }
                """
            )

            if url_ok or cookie_ok or dom_ok:
                time.sleep(2)
                storage = context.storage_state()
                _save_session(storage)
                print(f"[moka] 登录成功(URL={url_ok}, cookie={cookie_ok}, DOM={dom_ok})")
                print(f"[moka] cookie 已存到 {SESSION_FILE}")
                browser.close()
                return

            if _ % 15 == 0 and _ > 0:
                print(f"[moka] 等待登录...({_}s) url={url[:60]} cookies={len(cookies)}")

        browser.close()
        raise MokaError("登录超时(3 分钟),请检查是否真的登录成功")


def _session_cookies() -> list[dict]:
    """从 storage_state 提取 cookies 列表(requests 用)。"""
    state = _load_session()
    if not state:
        raise MokaError("未登录,请先运行 moka_client.login_interactive()")
    return state.get("cookies", [])


def _requests_session() -> requests.Session:
    sess = requests.Session()
    for c in _session_cookies():
        sess.cookies.set(
            name=c["name"],
            value=c["value"],
            domain=c.get("domain", ".mokahr.com"),
            path=c.get("path", "/"),
        )
    sess.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": MOKA_BASE,
            "Referer": f"{MOKA_BASE}/candidates",
            "Content-Type": "application/json;charset=UTF-8",
        }
    )
    return sess


def fetch_jobs_via_browser() -> list[dict]:
    """通过 paging 接口一次拿全所有 open 职位(id + title)。

    历史背景:早期用 Playwright 打开 /candidates 页面 + 解析 DOM,只能拿到 50 个。
    2026-09-15 调试发现:
      - /jobs 页面对应 paging 接口: POST /api/outer/ats-jc/job/jobs/paging
      - 默认 pageSize=30,默认只返前 30 条(且响应无 cursor 字段)
      - body 加 pageSize=200 一次拿全 94 个职位 + 完整 job 对象(含 id + title)
      - 不需要 Playwright 浏览器,纯 requests 就够

    返回 [{"id": uuid, "title": "..."} ...]
    """
    sess = _requests_session()
    try:
        resp = sess.post(
            PAGING_URL,
            json={"jobStatusList": ["open"], "pageSize": 200},
            timeout=30,
        )
    except Exception as e:
        raise MokaError(f"调用 paging 接口失败: {e}") from e

    if resp.status_code != 200:
        raise MokaError(f"paging 接口 HTTP {resp.status_code}: {resp.text[:200]}")

    payload = resp.json()
    if not payload.get("success"):
        raise MokaError(f"paging 接口返回失败: {payload.get('msg')}")

    data = payload.get("data", {})
    inner = data.get("data", []) if isinstance(data, dict) else []

    jobs: list[dict] = []
    for job in inner:
        if not isinstance(job, dict):
            continue
        jid = job.get("id")
        jtitle = job.get("title")
        if jid and jtitle:
            jobs.append({"id": str(jid), "title": str(jtitle)})

    if not jobs:
        raise MokaError(
            "fetch_jobs_via_browser: paging 接口没拿到任何职位 "
            "(可能 moka 接口字段名变了)"
        )

    print(f"[moka] fetch_jobs_via_browser 拿到 {len(jobs)} 个职位 (接口报告 total={data.get('count')})")
    return jobs

def load_jobs_cache() -> list[dict] | None:
    """读取缓存的职位列表(若 1 小时内抓过)。"""
    if not JOBS_CACHE_FILE.exists():
        return None
    try:
        data = json.loads(JOBS_CACHE_FILE.read_text(encoding="utf-8"))
        if time.time() - data.get("fetched_at", 0) < 3600:
            return data.get("jobs", [])
    except Exception:
        return None
    return None


def refresh_jobs_cache() -> list[dict]:
    jobs = fetch_jobs_via_browser()
    JOBS_CACHE_FILE.write_text(
        json.dumps(
            {"fetched_at": time.time(), "jobs": jobs},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return jobs


def fetch_applications_for_job(
    job_id: str,
    job_title: str | None = None,
    pipeline_id: str = "40490",
    limit: int = 200,
    max_pages: int = 50,
) -> list[dict]:
    """对单个职位调一次搜索接口,返回该职位的候选人 application 列表。

关键发现:不能传 stageId,传了 moka 返回 0 条;不传就返回该职位所有候选人。
    """
    sess = _requests_session()
    all_apps: list[dict] = []
    cursor: str | None = None
    page_idx = 0
    last_cursor: str | None = None  # 防无限循环

    while page_idx < max_pages:
        body = {
            "pipelineId": pipeline_id,
            "outerStage": "0",
            # 不传 stageId — 让 moka 返回所有候选人
            "jobPreference": "all",
            "enableAiFilter": False,
            "folderId": "0",
            "jobIds": [job_id],
            "jobStatus": ["open"],
            "limit": limit,
            "onlyHmAssignment": False,
        }
        if job_title:
            body["title"] = job_title
        if cursor:
            body["cursor"] = cursor

        if cursor:
            body["cursor"] = cursor

        resp = sess.post(SEARCH_URL, json=body, timeout=30)
        if resp.status_code != 200:
            raise MokaError(f"接口 HTTP {resp.status_code}: {resp.text[:200]}")

        payload = resp.json()
        if not payload.get("success"):
            raise MokaError(f"接口返回失败: {payload.get('msg')}")

        data = payload.get("data", {})
        apps = data.get("applications", [])
        all_apps.extend(apps)
        page_idx += 1

        # 防无限循环:游标没变就停
        new_cursor = data.get("lastCursor") or data.get("firstCursor")
        if new_cursor == last_cursor:
            break
        last_cursor = new_cursor

        if not data.get("hasMore") or not apps:
            break
        if not new_cursor:
            break
        cursor = new_cursor

    return all_apps


if __name__ == "__main__":
    # 测试入口:python moka_client.py
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "login":
        login_interactive()
    elif cmd == "jobs":
        jobs = refresh_jobs_cache()
        print(f"刷新到 {len(jobs)} 个职位:")
        for j in jobs[:5]:
            print(f"  {j['id'][:8]}...  {j['title']}")
    elif cmd == "status":
        print(f"已登录: {is_logged_in()}")
    else:
        print(f"未知命令: {cmd} (login/jobs/status)")