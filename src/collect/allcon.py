"""all-con(올콘) 공모전·대외활동 수집 — 카테고리별 저장 + 상세(포스터·PDF·글).

목록: POST /page/ajax.contest_list.php (JSON). 타입 t=1 공모전, t=2 대외활동.
  rows[] = {cl_srl, cl_title(HTML), cl_cate(활동분야+응모대상 badge), cl_status(접수중/마감+D-day), cl_host, cl_view}
스크롤 N번 = page 1..N+1.
상세: /view/contest/{id} — 포스터 이미지(/data/poster/..)와 첨부 PDF, 본문 텍스트를 함께 저장.
카테고리(활동분야)별로 묶어 저장한다. 의미 재분류는 하지 않는다(사이트 값 사용).
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from . import certs, download, runlog
from .config import settings

BASE = "https://www.all-con.co.kr"
_AJAX = BASE + "/page/ajax.contest_list.php"
UA = "Mozilla/5.0 (Univ-Us activity collector)"

TYPES = {"contest": ("1", "공모전"), "activity": ("2", "대외활동")}


def _txt(html: str) -> str:
    return BeautifulSoup(html or "", "lxml").get_text(" ", strip=True)


def _parse_row(row: dict) -> dict:
    cate = BeautifulSoup(row.get("cl_cate", ""), "lxml").select(".cl_cate")
    field = cate[0].get_text(strip=True) if cate else ""       # 활동분야
    target = cate[1].get_text(strip=True) if len(cate) > 1 else ""  # 응모대상
    status_txt = _txt(row.get("cl_status", ""))
    dday = re.search(r"D-?\d+|D-DAY|마감", status_txt)
    return {
        "id": row.get("cl_srl"),
        "title": _txt(row.get("cl_title", "")),
        "field": field, "target": target,
        "host": (row.get("cl_host") or "").strip(),
        "status": "마감" if "마감" in status_txt else "접수중",
        "period_ended": "마감" in status_txt,
        "dday": dday.group(0) if dday else "",
        "view_count": row.get("cl_view"),
        "url": f"{BASE}/view/contest/{row.get('cl_srl')}",
    }


def _fetch_detail(item: dict, cli: httpx.Client, type_key: str) -> dict:
    """상세: 본문 텍스트 + 포스터 이미지 + PDF 첨부 다운로드."""
    try:
        r = cli.get(item["url"]); r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)}
    soup = BeautifulSoup(r.text, "lxml")
    files = []
    # 포스터 이미지 (본문 대표 이미지)
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if "/data/poster/" in src or f"/{item['id']}" in src:
            meta = download.download(urljoin(BASE, src), f"allcon_{type_key}", cli, subdir="poster")
            if meta:
                files.append({"kind": "image", **meta})
            break
    # PDF·첨부
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if any(k in h.lower() for k in (".pdf", ".hwp", ".zip", "download", "file_down")):
            meta = download.download(urljoin(BASE, h), f"allcon_{type_key}", cli, subdir="files")
            if meta:
                files.append({"kind": "file", "name": a.get_text(strip=True), **meta})
    # 본문 텍스트
    body_el = soup.select_one(".view_cont, .board_view, #contents, .con_box") or soup
    body = body_el.get_text("\n", strip=True)[:5000]
    return {"body": body, "files": files}


def collect(type_key: str, *, scrolls: int = 2, max_detail: int = 30) -> dict:
    if type_key not in TYPES:
        raise ValueError(f"type: {type_key} (contest/activity)")
    t, name = TYPES[type_key]
    store = f"allcon_{type_key}"
    ca = certs.bundle()
    hdr = {"User-Agent": UA, "Referer": f"{BASE}/list/contest/{t}/1",
           "X-Requested-With": "XMLHttpRequest"}

    items: dict = {}
    try:
        with httpx.Client(timeout=25, verify=ca, follow_redirects=True, headers=hdr) as cli:
            for page in range(1, scrolls + 2):
                data = {"sortorder": "asc", "page": str(page), "sortname": "cl_order",
                        "stx": "", "sfl": "", "t": t, "ct": "", "sc": "", "tg": ""}
                d = cli.post(_AJAX, data=data).json()
                rows = d.get("rows") or []
                if not rows:
                    break
                for row in rows:
                    it = _parse_row(row)
                    if it["id"] and it["id"] not in items:
                        items[it["id"]] = it
                time.sleep(settings.jnu_collect_min_interval_sec)

            # 상세 + 첨부 다운로드 (max_detail 건까지)
            for i, it in enumerate(items.values()):
                if i >= max_detail:
                    break
                time.sleep(settings.jnu_collect_min_interval_sec)
                it.update(_fetch_detail(it, cli, type_key))
    except Exception as e:  # noqa: BLE001
        runlog.record_run(store, status="failed", detail=repr(e))
        print(f"[{store}] 실패: {e!r}")
        return {"status": "failed", "error": repr(e)}

    rows = list(items.values())
    # 카테고리(활동분야)별로 묶기
    by_cat: dict = {}
    for it in rows:
        by_cat.setdefault(it["field"] or "미분류", []).append(it)

    out_dir = settings.data_dir / "processed" / "allcon" / type_key
    out_dir.mkdir(parents=True, exist_ok=True)
    for cat, arr in by_cat.items():
        safe = re.sub(r"[^\w가-힣]", "_", cat)[:40]
        (out_dir / f"{safe}.json").write_text(json.dumps({
            "type": name, "category": cat, "count": len(arr),
            "collected_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "items": arr,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    ended = sum(1 for x in rows if x["period_ended"])
    files = sum(len(x.get("files", [])) for x in rows)
    runlog.record_run(store, status="ok", items_total=len(rows))
    print(f"[{store}] {name} — {len(rows)}건 / 카테고리 {len(by_cat)}종 / 첨부·이미지 {files}개 (마감 {ended})")
    return {"status": "ok", "total": len(rows), "categories": len(by_cat), "files": files}
