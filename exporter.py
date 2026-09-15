"""Excel 导出 — 用 openpyxl 把漏斗数据写成 .xlsx"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from moka_client import FUNNEL_STAGES

HEADER_FILL = PatternFill(start_color="305496", end_color="305496", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
CENTER = Alignment(horizontal="center", vertical="center")


def build_workbook(rows: list[dict]) -> bytes:
    """rows: 来自 funnel.funnel_for_all_jobs() 的列表。

    返回 xlsx 二进制内容(给 Flask send_file 用)。
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "招聘漏斗"

    # 表头:职位 + 9 阶段 + 已归档 + 总数 + 抓取时间
    headers = ["职位名称"] + FUNNEL_STAGES + ["已归档", "总数", "抓取时间"]
    for col, name in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=name)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER

    # 数据行
    for row_idx, row in enumerate(rows, 2):
        ws.cell(row=row_idx, column=1, value=row.get("job_title", ""))
        for col_idx, stage in enumerate(FUNNEL_STAGES, 2):
            ws.cell(row=row_idx, column=col_idx, value=row["stages"].get(stage, 0))
        # 已归档、总数、最后列
        ws.cell(row=row_idx, column=len(headers) - 2, value=row.get("archived", 0))
        ws.cell(row=row_idx, column=len(headers) - 1, value=row.get("total", 0))
        ts_ms = row.get("fetched_at_ms", 0)
        ts_str = (
            datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            if ts_ms
            else ""
        )
        ws.cell(row=row_idx, column=len(headers), value=ts_str)

    # 列宽自适应
    for col in range(1, len(headers) + 1):
        letter = get_column_letter(col)
        ws.column_dimensions[letter].width = 14 if col > 1 else 32

    # 冻结首行
    ws.freeze_panes = "A2"

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


if __name__ == "__main__":
    # 测试入口:python exporter.py
    from funnel import funnel_for_all_jobs
    from moka_client import load_jobs_cache, refresh_jobs_cache

    jobs = load_jobs_cache() or refresh_jobs_cache()
    if not jobs:
        print("没有职位,请先跑:python moka_client.py login && python moka_client.py jobs")
        raise SystemExit(1)

    rows = funnel_for_all_jobs(jobs)
    data = build_workbook(rows)
    out = Path(__file__).parent / "exports" / "funnel_test.xlsx"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(data)
    print(f"已导出 {len(rows)} 行到 {out}")