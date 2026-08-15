"""실행 이력·실패 기록 (수집 계획서 §4.4).

모든 수집 작업은 실행 이력을 남긴다.
"언제부터 수집이 멈췄는지"를 사후에 알 수 있어야 한다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import settings


def record_run(
    source: str,
    *,
    status: str,               # ok / failed / skipped / login_required
    detail: str = "",
    items_new: int = 0,
    items_changed: int = 0,
    items_total: int = 0,
) -> None:
    path = settings.runlog_path(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source": source,
        "status": status,
        "detail": detail,
        "items_new": items_new,
        "items_changed": items_changed,
        "items_total": items_total,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def last_run(source: str) -> dict | None:
    path = settings.runlog_path(source)
    if not path.exists():
        return None
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return json.loads(lines[-1]) if lines else None
