"""대외활동·공모전·채용·교육 수집 (campuspick 등 외부 사이트).

JNU 공지(notice.py)와 달리 대학 무관 전국 대상 사이트다.
campuspick 은 JS(React) 사이트라 프런트가 쓰는 공개 API 를 그대로 호출한다
(사이트가 브라우저에서 부르는 것과 동일한 요청). robots.txt 는 대상 페이지를 허용한다.

스크롤 N번 = API offset 0,20,...,20*N (한 번에 20개).
각 항목의 endDate 로 '기간 종료 여부(period_ended)'를 계산한다.
카테고리 의미 분류는 하지 않는다(사이트가 카테고리를 이미 나눔).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx

from . import download, runlog
from .config import settings

UA = "Mozilla/5.0 (Univ-Us activity collector)"
_API = "https://api2.campuspick.com"
_HDR = {"Referer": "https://www.campuspick.com/", "Origin": "https://www.campuspick.com",
        "User-Agent": UA}


@dataclass
class ExtSource:
    key: str
    name: str
    endpoint: str
    base_data: dict
    item_key: str          # result 안의 배열 이름
    web_path: str          # 상세 URL 경로 (campuspick.com/<web_path>/<id>)
    kind: str = "activity"  # activity | job


SOURCES = {
    "campuspick_contest":   ExtSource("campuspick_contest", "캠퍼스픽 공모전",
        "/find/activity/list", {"target": "1", "sort": "recommend"}, "activities", "contest"),
    "campuspick_activity":  ExtSource("campuspick_activity", "캠퍼스픽 대외활동",
        "/find/activity/list", {"target": "2", "sort": "recommend"}, "activities", "activity"),
    "campuspick_education": ExtSource("campuspick_education", "캠퍼스픽 교육",
        "/find/activity/list", {"target": "3", "sort": "recommend"}, "activities", "education"),
    "campuspick_job":       ExtSource("campuspick_job", "캠퍼스픽 채용",
        "/find/job/companies", {}, "recruits", "job", kind="job"),
}


def _period_ended(end: str | None) -> bool | None:
    if not end:
        return None
    try:
        return datetime.strptime(end, "%Y-%m-%d").date() < date.today()  # noqa: DTZ007,DTZ011 — 달력 날짜 비교(시간대 무관)
    except ValueError:
        return None


def _norm(src: ExtSource, it: dict) -> dict:
    end = it.get("endDate")
    return {
        "id": it.get("id"),
        "title": (it.get("title") or "").replace("&lt;", "<").replace("&gt;", ">"),
        "company": it.get("company") or it.get("companyName"),
        "end_date": end,
        "period_ended": _period_ended(end),   # 기간 종료 여부
        "view_count": it.get("viewCount"),
        "region": it.get("region"),
        "image": it.get("image"),
        "url": f"https://www.campuspick.com/{src.web_path}/{it.get('id')}",
    }


def collect(source_key: str, *, scrolls: int = 2, limit: int = 20) -> dict:
    """한 카테고리를 스크롤 N번(offset 0..20*N)만큼 수집해 저장한다."""
    src = SOURCES[source_key]
    items: dict[int, dict] = {}       # id 로 중복 제거
    try:
        with httpx.Client(timeout=20, headers=_HDR) as cli:
            for i in range(scrolls + 1):        # 최초 + 스크롤 N번
                data = {**src.base_data, "limit": str(limit), "offset": str(i * limit)}
                r = cli.post(_API + src.endpoint, data=data)
                r.raise_for_status()
                res = r.json().get("result", {})
                arr = res.get(src.item_key) or []
                if not arr:
                    break
                for it in arr:
                    n = _norm(src, it)
                    if n["id"] is not None:
                        items[n["id"]] = n
    except Exception as e:  # noqa: BLE001 — 조용히 실패하지 않는다
        runlog.record_run(source_key, status="failed", detail=repr(e))
        print(f"[{src.key}] 실패: {e!r}")
        return {"status": "failed", "error": repr(e)}

    rows = list(items.values())
    # 각 항목 대표 이미지(썸네일/포스터) 다운로드
    imgs = 0
    with httpx.Client(timeout=20, headers=_HDR) as icli:
        for it in rows:
            if it.get("image"):
                meta = download.download(it["image"], source_key, icli, subdir="poster")
                if meta and meta.get("path"):
                    it["image_path"] = meta["path"]; imgs += 1
    ended = sum(1 for x in rows if x["period_ended"])
    out_dir = settings.data_dir / "processed" / "external"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{src.key}.json").write_text(json.dumps({
        "source": src.name, "category": src.web_path,
        "collected_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "count": len(rows), "period_ended_count": ended,
        "items": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    runlog.record_run(source_key, status="ok", items_total=len(rows))
    print(f"[{src.key}] {src.name} — {len(rows)}건 (마감 {ended} · 이미지 {imgs})")
    return {"status": "ok", "total": len(rows), "ended": ended, "images": imgs}
