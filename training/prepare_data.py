#!/usr/bin/env python3
"""우리 데이터 → 학습용 SFT JSONL 변환 (캐글 데이터가 없어도 바로 학습 시작).

우리가 만든 라벨/구조화 데이터를 messages 형식으로 바꿔 training/data/ 에 넣는다.
  python training/prepare_data.py

입력(있는 것만 사용):
  data/testset/qa.jsonl              질문→정답  (라벨 채워진 것만)
  data/testset/notices.jsonl,        문서→일정(events) 추출  (라벨 채워진 것만)
  data/testset/syllabus.jsonl
출력:
  training/data/sft_from_ours.jsonl  {"messages":[user, assistant]}
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path("training/data/sft_from_ours.jsonl")
EXTRACT_INSTRUCTION = (
    "다음 학사 문서에서 날짜가 있는 일정을 JSON 배열로 뽑아라. "
    'each: {"date":"YYYY-MM-DD","type":"과제|시험|발표|수업변경|신청마감|행사|공지|기타","title":"...","quote":"근거"}')


def _read_jsonl(p: str) -> list[dict]:
    path = Path(p)
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pairs = []

    # 1) QA: 질문 → 정답 (사람이 answer 채운 것만)
    for r in _read_jsonl("data/testset/qa.jsonl"):
        ans = (r.get("expected") or {}).get("answer", "").strip()
        if r.get("query") and ans:
            pairs.append([{"role": "user", "content": r["query"]},
                          {"role": "assistant", "content": ans}])

    # 2) 추출: 문서 원문 → events JSON (events 채운 것만)
    for src in ("data/testset/notices.jsonl", "data/testset/syllabus.jsonl"):
        for r in _read_jsonl(src):
            events = (r.get("labels") or {}).get("events") or []
            if events and r.get("text"):
                user = f"{EXTRACT_INSTRUCTION}\n\n문서:\n{r['text'][:4000]}"
                pairs.append([{"role": "user", "content": user},
                              {"role": "assistant",
                               "content": json.dumps(events, ensure_ascii=False)}])

    if not pairs:
        print("변환할 라벨 데이터가 아직 없습니다.\n"
              "  → data/testset/*.jsonl 에 정답을 채운 뒤 다시 실행하세요 (라벨링-가이드 참고).\n"
              "  → 지금 당장은 캐글 데이터를 training/data/ 에 넣어 학습해도 됩니다.")
        return
    with OUT.open("w", encoding="utf-8") as f:
        for m in pairs:
            f.write(json.dumps({"messages": m}, ensure_ascii=False) + "\n")
    print(f"변환 완료: {OUT}  ({len(pairs)} 샘플)")


if __name__ == "__main__":
    main()
