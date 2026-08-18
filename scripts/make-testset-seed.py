#!/usr/bin/env python3
"""라벨링용 빈칸 seed 생성 (계획서 4.2 테스트셋).

수집된 공지 상세 + 강의계획서 PDF 원문을 읽어, events 가 빈 JSONL 템플릿을 만든다.
정수빈이 events/quote 만 채우면 된다. **이미 채운 라벨은 병합 보존**(덮어쓰지 않음).

  python scripts/make-testset-seed.py

출력(전부 data/testset/, gitignore 됨 = 로컬 보관):
  notices.jsonl   공지 상세 → 빈 템플릿
  syllabus.jsonl  강의계획서 PDF → 빈 템플릿
  qa.jsonl        질의-정답 쌍 예시(질문만 채움, 정답 빈칸)
  _examples.jsonl 채운 정답 예시 2건(참고용, 라벨링 대상 아님)
"""
from __future__ import annotations

import glob
import json
import re
from pathlib import Path

OUT = Path("data/testset")


def _blank_labels() -> dict:
    return {"events": [], "category": ""}


def _load_existing(path: Path) -> dict[str, dict]:
    """이미 있는 파일을 doc_id 로 읽어 둔다(사람이 채운 라벨 보존)."""
    reg: dict[str, dict] = {}
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                reg[r["doc_id"]] = r
    return reg


def _merge_write(path: Path, new_records: list[dict]) -> tuple[int, int]:
    """new_records 를 기존과 병합. 기존에 events 가 채워져 있으면 그대로 둔다."""
    existing = _load_existing(path)
    added = 0
    for rec in new_records:
        old = existing.get(rec["doc_id"])
        if old is None:
            existing[rec["doc_id"]] = rec
            added += 1
        # 이미 있으면: 사람이 채운 labels 를 보존(원문 text 는 최신으로 갱신)
        else:
            old["text"] = rec["text"]
            old["title"] = rec["title"]
    OUT.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in existing.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return added, len(existing)


def _num_id(url: str) -> str:
    m = re.findall(r"(\d{3,})", url)
    return m[-1] if m else re.sub(r"\W+", "", url)[-8:]


def build_notices() -> list[dict]:
    out = []
    for f in sorted(glob.glob("data/processed/notices/*/*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        site = Path(f).parent.name
        out.append({
            "doc_id": f"notice_{site}_{_num_id(d.get('url', f))}",
            "source": site, "doc_type": "공지",
            "title": d.get("title", ""), "url": d.get("url", ""),
            "text": d.get("body", ""),
            "labels": _blank_labels(),
            "labeler": "", "checked_by": "", "tag": "eval",
        })
    return out


def build_syllabus() -> list[dict]:
    try:
        from pypdf import PdfReader
    except ImportError:
        print("  (pypdf 없음 → 계획서 seed 건너뜀)")
        return []
    out = []
    for f in sorted(glob.glob("data/raw/syllabus/*.pdf")):
        code = Path(f).stem.split("__")[-1]              # 파일명 → 과목코드(타임스탬프 제거)
        try:
            text = "\n".join((p.extract_text() or "") for p in PdfReader(f).pages)
        except Exception as e:  # noqa: BLE001
            print(f"  PDF 실패 {Path(f).name}: {e!r}")
            continue
        out.append({
            "doc_id": f"syllabus_{code}", "source": "syllabus",
            "doc_type": "강의계획서", "title": code, "url": "",
            "text": text.strip(),
            "labels": _blank_labels(),
            "labeler": "", "checked_by": "", "tag": "eval",
        })
    return out


QA_SEED = [
    {"qid": "q001", "query": "이번주 과제 뭐 있어?", "today": "2026-09-14",
     "expected": {"answer": "", "evidence": []},
     "expected_tool": {"name": "get_schedule", "args": {"range": "this_week"}}, "labeler": ""},
    {"qid": "q002", "query": "이번주 시험이나 발표 있나?", "today": "2026-09-14",
     "expected": {"answer": "", "evidence": []},
     "expected_tool": {"name": "get_schedule", "args": {"range": "this_week", "type": "시험"}}, "labeler": ""},
    {"qid": "q003", "query": "장학금 관련 공지 있어?", "today": "2026-09-14",
     "expected": {"answer": "", "evidence": []},
     "expected_tool": {"name": "search_notice", "args": {"category": "장학"}}, "labeler": ""},
    {"qid": "q004", "query": "이번주 마감 임박한 공모전 알려줘", "today": "2026-09-14",
     "expected": {"answer": "", "evidence": []},
     "expected_tool": {"name": "search_contest", "args": {"deadline": "this_week"}}, "labeler": ""},
    {"qid": "q005", "query": "오늘 무슨 수업 있지?", "today": "2026-09-14",
     "expected": {"answer": "", "evidence": []},
     "expected_tool": {"name": "get_timetable", "args": {"day": "today"}}, "labeler": ""},
]

EXAMPLES = [
    {"doc_id": "EXAMPLE_notice", "source": "aicoss", "doc_type": "공지",
     "title": "2026-2학기 전공특강 및 중간고사 안내", "url": "https://example",
     "text": "중간고사는 10/21(화) 3-4교시에 시행합니다. 특강 신청 마감은 9월 30일 23:59입니다.",
     "labels": {"events": [
         {"date": "2026-10-21", "type": "시험", "title": "중간고사",
          "quote": "중간고사는 10/21(화) 3-4교시에 시행합니다"},
         {"date": "2026-09-30", "type": "신청마감", "title": "특강 신청 마감",
          "quote": "특강 신청 마감은 9월 30일 23:59입니다"}],
         "category": "학사"},
     "labeler": "예시", "checked_by": "예시", "tag": "example"},
    {"doc_id": "EXAMPLE_syllabus", "source": "syllabus", "doc_type": "강의계획서",
     "title": "SAI0017-1", "url": "",
     "text": "12주차 팀 프로젝트 1차 보고서 제출. 기말고사 15주차.",
     "labels": {"events": [
         {"date": "2026-11-24", "type": "과제", "title": "팀 프로젝트 1차 보고서",
          "quote": "12주차 팀 프로젝트 1차 보고서 제출"},
         {"date": "2026-12-15", "type": "시험", "title": "기말고사",
          "quote": "기말고사 15주차"}],
         "category": ""},
     "labeler": "예시", "checked_by": "예시", "tag": "example"},
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    a1, t1 = _merge_write(OUT / "notices.jsonl", build_notices())
    print(f"notices.jsonl : 신규 {a1} / 총 {t1}")
    a2, t2 = _merge_write(OUT / "syllabus.jsonl", build_syllabus())
    print(f"syllabus.jsonl: 신규 {a2} / 총 {t2}")
    # qa/examples 는 사람 작업물이라 있으면 건드리지 않음
    if not (OUT / "qa.jsonl").exists():
        (OUT / "qa.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in QA_SEED) + "\n", encoding="utf-8")
        print(f"qa.jsonl      : 예시 질의 {len(QA_SEED)}건 생성")
    else:
        print("qa.jsonl      : 이미 있음(보존)")
    (OUT / "_examples.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in EXAMPLES) + "\n", encoding="utf-8")
    print(f"_examples.jsonl: 참고 예시 {len(EXAMPLES)}건")


if __name__ == "__main__":
    main()
