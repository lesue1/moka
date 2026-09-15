"""漏斗统计 — 数 application 列表里每个 stageName 出现多少次。

输出结构(每个职位一行):
  {
    "job_id": "...",
    "job_title": "...",
    "stages": {
      "初筛": 277,
      "用人部门筛选": 337,
      "初试": 204,
      ...
    },
    "archived": 5,         # 已归档数量(单独统计)
    "total": 600,          # 总申请数
    "fetched_at": 1789...  # 抓取时间(毫秒)
  }
"""
from __future__ import annotations

import time
from typing import Iterable

from moka_client import FUNNEL_STAGES, fetch_applications_for_job


def count_funnel(applications: list[dict]) -> dict[str, int]:
    """遍历 applications,数每个 stageName 出现次数。

    注意:moka 的 application 一条记录 = 一个候选人 × 一个职位(可能同候选人多职位)。
    对单职位调用接口时,这里每条 application 都是这个职位的,无需去重。
    """
    counts: dict[str, int] = {s: 0 for s in FUNNEL_STAGES}
    archived = 0
    for app in applications:
        if app.get("archived"):
            archived += 1
        stage = app.get("stageName")
        if stage in counts:
            counts[stage] += 1
        # 未识别的阶段名也记一下(防止 moka 升级改了名字我们漏掉)
        elif stage:
            counts.setdefault(f"_unknown:{stage}", 0)
            counts[f"_unknown:{stage}"] += 1
    counts["__archived__"] = archived
    return counts


def funnel_for_job(job_id: str, job_title: str) -> dict:
    """单个职位完整漏斗。"""
    apps = fetch_applications_for_job(job_id, job_title=job_title)
    counts = count_funnel(apps)
    return {
        "job_id": job_id,
        "job_title": job_title,
        "stages": {k: counts.get(k, 0) for k in FUNNEL_STAGES},
        "archived": counts.get("__archived__", 0),
        "total": len(apps),
        "fetched_at_ms": int(time.time() * 1000),
        "unknown_stages": {k: v for k, v in counts.items() if k.startswith("_unknown:")},
    }


def funnel_for_all_jobs(jobs: Iterable[dict]) -> list[dict]:
    """所有职位依次抓漏斗(串行,慢但稳;后续可加并发)。

    遇到 MokaError 立即抛出,避免静默吞错让 UI 显示空表。其他异常(网络超时等)继续重试下一职位。
    """
    from moka_client import MokaError

    import sys
    import time as _time

    results = []
    job_list = list(jobs)
    total = len(job_list)
    for i, j in enumerate(job_list, 1):
        t0 = _time.time()
        try:
            row = funnel_for_job(j["id"], j["title"])
        except MokaError:
            # session 失效/接口错误 — 立即抛,不吞
            raise
        except Exception as e:
            # 单职位网络超时等临时错误,继续
            print(f"[funnel] [{i}/{total}] {j['title'][:30]} 失败: {e}", file=sys.stderr)
            continue
        elapsed = _time.time() - t0
        print(
            f"[funnel] [{i}/{total}] {j['title'][:30]:30s} total={row['total']:5d} 耗时 {elapsed:.1f}s",
            file=sys.stderr,
        )
        results.append(row)
    return results


if __name__ == "__main__":
    # 测试入口:python funnel.py <job_id> <job_title>
    import json
    import sys
    from moka_client import load_jobs_cache, refresh_jobs_cache

    if len(sys.argv) >= 3:
        job_id = sys.argv[1]
        job_title = sys.argv[2]
        result = funnel_for_job(job_id, job_title)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 用第一个缓存职位测试
        jobs = load_jobs_cache() or refresh_jobs_cache()
        if not jobs:
            print("没有职位,请先跑:python moka_client.py login && python moka_client.py jobs")
            sys.exit(1)
        first = jobs[0]
        print(f"测试职位:{first['title']} ({first['id'][:8]}...)")
        result = funnel_for_job(first["id"], first["title"])
        print(json.dumps(result, ensure_ascii=False, indent=2))