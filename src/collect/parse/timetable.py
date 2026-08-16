"""개인 시간표 HTML → 구조화 JSON (결정적 파서, LLM 미사용).

시간표는 7열 그리드다: [시간, 월, 화, 수, 목, 금, 토].
각 과목 셀 = "[ N 교시 ]<br>과목명<br>담당교수 :교수<br>강의실<br>코드-분반<br>[수업형태]".
한 과목은 30분 슬롯마다 반복 등장하므로 (과목, 요일)로 묶어 시간 범위를 만든다.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from ..config import settings

_CODE_RE = re.compile(r"^([A-Z]{2,4}\d{4})-(\d+)$")
_PERIOD_RE = re.compile(r"\[\s*(\d+)\s*교시\s*\]")
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


def _to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _to_hhmm(mins: int) -> str:
    return f"{mins // 60:02d}:{mins % 60:02d}"


def _parse_cell(td) -> dict | None:
    """과목 셀 하나를 파싱. 과목이 없으면 None."""
    # <br> 로 나뉜 조각들
    parts = [t.strip() for t in td.get_text("\n").split("\n") if t.strip()]
    if not parts:
        return None
    code = class_no = subject = professor = room = ctype = None
    period = None
    for p in parts:
        mp = _PERIOD_RE.search(p)
        mc = _CODE_RE.match(p)
        if mp:
            period = int(mp.group(1))
        elif mc:
            code, class_no = mc.group(1), mc.group(2)
        elif p.startswith("담당교수"):
            professor = p.split(":", 1)[-1].strip()
        elif p.startswith("[") and p.endswith("]"):
            ctype = p.strip("[]")
        elif subject is None:
            subject = p          # 첫 일반 텍스트 = 과목명
        elif room is None:
            room = p             # 그 다음 = 강의실
    if not code:
        return None
    return {"code": code, "class_no": class_no, "subject": subject,
            "professor": professor, "room": room, "type": ctype, "period": period}


def parse_timetable(html: str) -> dict:
    """시간표 HTML → {courses: [...]}."""
    soup = BeautifulSoup(html, "lxml")

    # 요일 헤더가 있는 표 찾기
    table = None
    for t in soup.find_all("table"):
        heads = "".join(th.get_text(strip=True) for th in t.find_all("th"))
        if all(d in heads for d in ("월요일", "화요일", "금요일")):
            table = t
            break
    if table is None:
        raise ValueError("시간표 표를 찾지 못했습니다")

    rows = table.find_all("tr")
    header_cells = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    # 열 index -> 요일 (0번은 '시간')
    day_of_col = {i: h.replace("요일", "") for i, h in enumerate(header_cells) if i > 0}

    # (code-class, day) -> {정보, times:set, periods:set, room}
    acc: dict[tuple, dict] = {}
    for tr in rows[1:]:
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        time_txt = cells[0].get_text(strip=True)
        if not _TIME_RE.match(time_txt):
            continue
        for ci, td in enumerate(cells):
            if ci == 0 or ci not in day_of_col:
                continue
            info = _parse_cell(td)
            if not info:
                continue
            day = day_of_col[ci]
            key = (f"{info['code']}-{info['class_no']}", day)
            slot = acc.setdefault(key, {**info, "day": day, "times": set(), "periods": set()})
            slot["times"].add(time_txt)
            if info["period"]:
                slot["periods"].add(info["period"])
            if info["room"] and not slot.get("room"):
                slot["room"] = info["room"]

    # (code-class) 로 과목을 묶고 meetings 배열 구성
    courses: dict[str, dict] = {}
    for (cc, _day), slot in acc.items():
        c = courses.setdefault(cc, {
            "code": slot["code"], "class_no": slot["class_no"],
            "subject": slot["subject"], "professor": slot["professor"],
            "type": slot["type"], "meetings": [],
        })
        times = sorted(slot["times"], key=_to_min)
        start, end = times[0], _to_hhmm(_to_min(times[-1]) + 30)
        c["meetings"].append({
            "day": slot["day"],
            "periods": sorted(slot["periods"]),
            "start": start, "end": end,
            "room": slot.get("room"),
        })

    day_order = "월화수목금토일"
    for c in courses.values():
        c["meetings"].sort(key=lambda m: (day_order.index(m["day"]) if m["day"] in day_order else 9, m["start"]))

    return {"courses": sorted(courses.values(), key=lambda c: c["code"])}


def parse_latest() -> Path:
    """가장 최근 수집한 시간표 원문을 파싱해 data/processed 에 저장."""
    raw_dir = settings.raw_dir("timetable")
    files = sorted(raw_dir.glob("*.html"))
    if not files:
        raise FileNotFoundError("수집된 시간표 원문이 없습니다. 먼저 collect timetable 하세요.")
    latest = files[-1]
    result = parse_timetable(latest.read_text(encoding="utf-8", errors="replace"))
    result["source_file"] = str(latest)
    result["parsed_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    out_dir = settings.data_dir / "processed" / "timetable"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "timetable.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
