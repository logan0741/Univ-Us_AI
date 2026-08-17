"""크롤링 실시간 모니터 — 옆 터미널에서 상태를 1초마다 갱신해 본다.

수집기가 data/ 에 쓰는 파일을 읽어 사이트·카테고리별 현황을 표시한다.
  · runlog: 소스별 마지막 실행(상태·시각·건수)
  · raw/<source>/, .../files/, .../poster/: 내려받은 원문·첨부·이미지 수(진행 중 실시간 증가)
  · processed/: 카테고리별 건수(각 수집 완료 시 갱신)

실행:  python -m src.collect.cli monitor
종료:  Ctrl+C
"""
from __future__ import annotations

import json
from contextlib import suppress
import time
from datetime import datetime

from rich.console import Group
from rich.live import Live
from rich.table import Table

from .config import settings


def _last_run(source: str) -> dict | None:
    path = settings.runlog_path(source)
    if not path.exists():
        return None
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return json.loads(lines[-1]) if lines else None


def _count_files(source: str) -> tuple[int, int, int]:
    """(원문, files첨부, poster이미지) 파일 수."""
    base = settings.raw_dir(source)
    raw = sum(1 for p in base.glob("*.*")) if base.exists() else 0
    files = sum(1 for _ in (base / "files").glob("*")) if (base / "files").exists() else 0
    poster = sum(1 for _ in (base / "poster").glob("*")) if (base / "poster").exists() else 0
    return raw, files, poster


def _all_sources() -> list[str]:
    src = set()
    for sub in ("runlog", "raw"):
        d = settings.data_dir / sub
        if d.exists():
            for p in d.iterdir():
                src.add(p.stem if sub == "runlog" else p.name)
    # 로그인 필요 소스도 항상 표시
    src.update({"timetable", "syllabus", "sugang_courses", "eclass"})
    return sorted(src)


def _status_style(st: str | None) -> str:
    return {"ok": "green", "failed": "red", "login_required": "yellow"}.get(st or "", "dim")


def _render() -> Group:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005

    t = Table(title=f"Univ-Us 크롤링 실시간 모니터   {now}", expand=True)
    t.add_column("소스", style="cyan", no_wrap=True)
    t.add_column("마지막 실행", justify="center")
    t.add_column("상태", justify="center")
    t.add_column("건수", justify="right")
    t.add_column("원문", justify="right")
    t.add_column("첨부", justify="right")
    t.add_column("이미지", justify="right")

    for src in _all_sources():
        run = _last_run(src)
        raw, files, poster = _count_files(src)
        st = run["status"] if run else None
        ts = run["ts"][11:19] if run else "-"
        total = str(run.get("items_total", "")) if run else ""
        t.add_row(src, ts, f"[{_status_style(st)}]{st or '-'}[/]",
                  total, str(raw or ""), str(files or ""), str(poster or ""))

    # 카테고리 세부 (allcon / notices)
    c = Table(title="카테고리 세부", expand=True)
    c.add_column("소스/카테고리", style="magenta")
    c.add_column("건수", justify="right")
    cat_dir = settings.data_dir / "processed" / "allcon"
    if cat_dir.exists():
        for tdir in sorted(cat_dir.iterdir()):
            for f in sorted(tdir.glob("*.json")):
                with suppress(Exception):
                    d = json.loads(f.read_text(encoding="utf-8"))
                    ended = sum(1 for x in d.get("items", []) if x.get("period_ended"))
                    c.add_row(f"allcon/{tdir.name}/{d.get('category', f.stem)}",
                              f"{d.get('count', 0)}  (마감 {ended})")
    ext_dir = settings.data_dir / "processed" / "external"
    if ext_dir.exists():
        for f in sorted(ext_dir.glob("*.json")):
            with suppress(Exception):
                d = json.loads(f.read_text(encoding="utf-8"))
                c.add_row(f"external/{d.get('category', f.stem)}",
                          f"{d.get('count', 0)}  (마감 {d.get('period_ended_count', 0)})")
    not_dir = settings.data_dir / "processed" / "notices"
    if not_dir.exists():
        for f in sorted(not_dir.glob("*.json")):
            with suppress(Exception):
                d = json.loads(f.read_text(encoding="utf-8"))
                c.add_row(f"notice/{f.stem}", str(len(d.get("notices", []))))

    return Group(t, c)


def run_monitor() -> None:
    try:
        with Live(_render(), refresh_per_second=1, screen=True) as live:
            while True:
                time.sleep(1)
                live.update(_render())
    except KeyboardInterrupt:
        print("모니터 종료")
