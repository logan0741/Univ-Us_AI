#!/usr/bin/env python3
"""강의계획서 PDF → 항목별 구조화 JSON (규칙 기반, LLM 미사용 = 비용 0).

JNU 수업계획서 양식은 라벨이 고정이라 정규식으로 항목을 분리한다.
  python scripts/parse-syllabus.py [입력] [출력폴더] [--limit N]
  · 입력 = 폴더면 그 안의 *.pdf 전부, 파일 하나면 그것만
기본 입력: Univ-Us_AI-agent/수업계획서   출력: data/processed/syllabus

예) 나중에 받은 계획서 하나를 JSON 으로:
  python scripts/parse-syllabus.py ~/받은계획서.pdf data/processed/syllabus
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

EVAL_COLS = ["중간고사", "기말고사", "개별과제", "팀과제", "수업참여도", "출석", "기타"]


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()


def _search(pat: str, text: str, flags=0) -> str:
    m = re.search(pat, text, flags)
    return _clean(m.group(1)) if m else ""


def _dedup_words(s: str) -> str:
    """'광주은행홀 광주은행홀 ...' 처럼 반복된 토큰을 하나로."""
    seen, out = set(), []
    for w in s.split():
        if w not in seen:
            seen.add(w); out.append(w)
    return " ".join(out)


_EXAM_RE = re.compile(r"중간|기말|시험|고사|Midterm|Final|Exam", re.IGNORECASE)
_TASK_RE = re.compile(r"과제|보고서|제출|발표|Assignment|Project|Report|Presentation", re.IGNORECASE)


def parse_weekly(text: str) -> list[dict]:
    m = re.search(r"(?:주별 수업계획서|Weekly Course Schedule)(.*?)"
                  r"(?:\* ?수업일정|기타 참고 사항|참고1\.|Notes|References)", text, re.DOTALL)
    if not m:
        return []
    lines = [ln.strip() for ln in m.group(1).splitlines()]
    weeks = {}
    for i, line in enumerate(lines):
        inline = re.match(r"^(\d{1,2})\s+(\S.+)$", line)   # "8 중간고사"
        if inline:
            wk, content = int(inline.group(1)), _clean(inline.group(2))
        elif re.fullmatch(r"\d{1,2}", line):               # 번호만 있는 줄 → 다음 줄이 내용
            wk = int(line)
            nxt = next((lines[j] for j in range(i + 1, len(lines)) if lines[j]), "")
            content = _clean(re.sub(r"\(.+?\)\s*PAGE.*$", "", nxt))
        else:
            continue
        if 1 <= wk <= 20 and wk not in weeks and content:  # 첫 등장만
            weeks[wk] = {
                "week": wk, "content": content,
                "is_exam": bool(_EXAM_RE.search(content)),
                "has_task": bool(_TASK_RE.search(content)),
            }
    return [weeks[k] for k in sorted(weeks)]


def parse_eval(text: str) -> dict:
    # 헤더(한글/영문) 위치를 찾고, 그 뒤 첫 '숫자만 있는 줄'을 배점으로 본다.
    idx = text.find("합계(%)")
    if idx < 0:
        idx = text.find("Total (%)")
    if idx < 0:
        return {"raw": "", "total": None, "by_item": None}
    nums = []
    for line in text[idx:idx + 500].splitlines()[1:]:
        toks = line.split()
        if len(toks) >= 3 and all(re.fullmatch(r"\d{1,3}", t) for t in toks):
            nums = [int(t) for t in toks[:8]]
            break
    if not nums:
        return {"raw": "", "total": None, "by_item": None}
    # 양식마다 '합계(100)' 컬럼이 있기도/없기도 함 → 100 이 있으면 그게 합계
    if 100 in nums:
        total, items = 100, [n for n in nums if n != 100]
    else:
        items, total = nums, sum(nums)
    # 빈칸이 생략되면 컬럼 매핑 불가(항목 7개일 때만 신뢰)
    by_item = dict(zip(EVAL_COLS, items)) if len(items) == 7 else None
    return {"raw": " ".join(map(str, nums)), "total": total, "by_item": by_item}


def parse_textbooks(text: str) -> list[str]:
    m = re.search(r"(?:출판연도|Year of Publication)(.*?)"
                  r"(?:주별 수업계획서|Weekly Course Schedule|기타 참고)", text, re.DOTALL)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        line = _clean(line)
        if line and re.match(r"^(주교재|부교재|참고자료|기타자료|Main Textbook|Sub Textbook|References?)", line) \
                and len(line) > 5:
            out.append(line)
    return out


def parse_pdf(path: Path, curriculum: str) -> dict:
    reader = PdfReader(str(path))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)

    # 첫 줄 '과목명(코드) PAGE' — 한글/영문 양식 공통
    name_code = re.search(r"^\s*(.+?)\(([A-Za-z]{2,6}\d{3,6}-\d+)\)\s*PAGE", text, re.MULTILINE) \
        or re.search(r"(?:교과목명|Course Title)\s+(.+?)\(([A-Za-z]{2,6}\d{3,6}-\d+)\)", text)
    name = _clean(name_code.group(1)) if name_code else ""
    code = name_code.group(2) if name_code else ""
    overview = _search(r"(?:교과요목|Course Description)\s*(.*?)\s*(?:대학\s*인재상|University|Core Compet)",
                       text, re.DOTALL)
    if not overview:
        mm = re.search(r"(?:교과요목|Course Description)\s*(.{20,600})", text, re.DOTALL)
        overview = _clean(mm.group(1)) if mm else ""

    return {
        "course_name": re.sub(r"^\[.*?\]", "", name).strip(),
        "course_name_raw": name,
        "course_code": code,
        "curriculum": curriculum,                                  # 학년-학기 (파일명)
        "term": _search(r"(\d{4}학년도 \d학기)", text),             # 문서상 학기
        "category": _search(r"(?:과목구분|Course Type)\s+(\S+)", text),
        "credits": _search(r"(?:학점\(시수\)|\(Credit Hours\))\s+([\d.]+)", text),
        "department": _search(r"(?:담당학과\(부\)|\(College\))\s+(.+?)\s+(?:담당교수|Instructor)", text),
        "professor": _search(r"(?:담당교수|Instructor)\s+(\S+)", text),
        "grade": _search(r"(?:수강학년|Year in School\))\s+(\d+)", text),
        "contact": _search(r"(?:연락처|Phone)\s+([\d\-]+)", text),
        "email": _search(r"E-mail\s+(\S+@\S+)", text),
        "classroom": _dedup_words(_search(r"(?:강의실|Classroom)\s+(.+?)\s+E-mail", text)),
        "class_time": _search(r"(?:강의시간|Class Hours)\s+(\S+)", text),
        "office_hours": _search(r"(?:면담시간|Office Hours)\s+(.+?)\s*(?:선수과목|Prerequisite)", text, re.DOTALL),
        "prerequisite": _search(r"(?:선수과목|Prerequisite\(s\))\s*(.*?)\s*(?:교과요목|Course Description)",
                                text, re.DOTALL),
        "overview": overview,
        "evaluation": parse_eval(text),
        "textbooks": parse_textbooks(text),
        "weekly_plan": parse_weekly(text),
        "source_file": str(path),
        "_meta": {"pages": len(reader.pages),
                  "parsed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                  "method": "rule-based (no LLM)"},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("indir", nargs="?", default="Univ-Us_AI-agent/수업계획서")
    ap.add_argument("outdir", nargs="?", default="data/processed/syllabus")
    ap.add_argument("--limit", type=int, default=0, help="처음 N개만(0=전부)")
    args = ap.parse_args()

    out = Path(args.outdir); out.mkdir(parents=True, exist_ok=True)
    inp = Path(args.indir)
    # PDF 파일 하나든 폴더든 받는다 (새 계획서 1개만 변환할 때 편하게)
    pdfs = [inp] if inp.is_file() and inp.suffix.lower() == ".pdf" else sorted(inp.glob("*.pdf"))
    if not pdfs:
        print(f"PDF 를 못 찾음: {inp}"); return
    if args.limit:
        pdfs = pdfs[:args.limit]

    index = []
    for p in pdfs:
        curriculum = p.name[:3] if re.match(r"\d-\d", p.name) else ""
        try:
            rec = parse_pdf(p, curriculum)
        except Exception as e:  # noqa: BLE001
            print(f"  실패 {p.name}: {e!r}"); continue
        safe = re.sub(r"[^\w가-힣.\-]", "_", f"{curriculum}_{rec['course_code'] or p.stem}")[:80]
        (out / f"{safe}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        exams = [w["week"] for w in rec["weekly_plan"] if w["is_exam"]]
        index.append({"file": f"{safe}.json", "code": rec["course_code"],
                      "name": rec["course_name"], "curriculum": curriculum,
                      "professor": rec["professor"], "weeks": len(rec["weekly_plan"]),
                      "exam_weeks": exams})
    (out / "_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in index if r["weeks"] > 0)
    print(f"파싱 {len(index)}개 → {out}/  (주차계획 추출 성공 {ok}개)")


if __name__ == "__main__":
    main()
