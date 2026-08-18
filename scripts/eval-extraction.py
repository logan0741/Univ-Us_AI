#!/usr/bin/env python3
"""일정 추출 평가 (계획서 4.2 · eval_ai-agent 골격).

라벨(정답)과 모델 추출을 비교해 정밀도/재현율/F1 을 낸다.
모델 없이도 지금 바로 되는 것:
  --validate   : 라벨 형식 검사(필드·enum·날짜) — 정수빈이 채운 뒤 자가점검용
  --self-test  : 정답을 예측으로 넣어 채점기가 F1=1.0 나오는지 확인(채점 로직 검증)
모델 붙이면:
  --model      : LLM_MAIN(.env) 로 text 에서 events 추출해 정답과 비교

사용:
  python scripts/eval-extraction.py --validate
  python scripts/eval-extraction.py --self-test
  python scripts/eval-extraction.py --model            # .env 에 LLM_MAIN_* 필요
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from pathlib import Path

TYPES = {"과제", "시험", "발표", "수업변경", "신청마감", "행사", "공지", "기타"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GOLD_GLOB = "data/testset/*.jsonl"


def load_gold() -> list[dict]:
    recs = []
    for f in sorted(glob.glob(GOLD_GLOB)):
        if Path(f).name.startswith("_") or Path(f).name == "qa.jsonl":
            continue
        for ln in Path(f).read_text(encoding="utf-8").splitlines():
            if ln.strip():
                recs.append(json.loads(ln))
    return recs


# ── 형식 검사 ────────────────────────────────────────────────
def validate(recs: list[dict]) -> int:
    errs, labeled = 0, 0
    for r in recs:
        did = r.get("doc_id", "?")
        evs = r.get("labels", {}).get("events", [])
        if evs:
            labeled += 1
        for i, e in enumerate(evs):
            where = f"{did}[{i}]"
            d = e.get("date")
            if d is not None and not DATE_RE.match(str(d)):
                print(f"  ✗ {where} date 형식(YYYY-MM-DD/null): {d!r}"); errs += 1
            if e.get("type") not in TYPES:
                print(f"  ✗ {where} type 목록 밖: {e.get('type')!r}"); errs += 1
            if not (e.get("quote") or "").strip():
                print(f"  ✗ {where} quote(근거) 비어 있음"); errs += 1
            if not (e.get("title") or "").strip():
                print(f"  ✗ {where} title 비어 있음"); errs += 1
    print(f"\n총 {len(recs)}건 · 라벨 채워진 문서 {labeled}건 · 형식 오류 {errs}개")
    return errs


# ── 채점 ─────────────────────────────────────────────────────
def _key(e: dict) -> tuple:
    return (str(e.get("date")), e.get("type"))


def score(gold: list[dict], pred: list[dict]) -> dict:
    g = {_key(e) for e in gold}
    p = {_key(e) for e in pred}
    tp = len(g & p); fp = len(p - g); fn = len(g - p)
    prec = tp / (tp + fp) if tp + fp else 1.0
    rec = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec, "f1": f1}


def aggregate(pairs: list[tuple[list, list]]) -> dict:
    tot = {"tp": 0, "fp": 0, "fn": 0}
    for gold, pred in pairs:
        s = score(gold, pred)
        for k in tot:
            tot[k] += s[k]
    prec = tot["tp"] / (tot["tp"] + tot["fp"]) if tot["tp"] + tot["fp"] else 1.0
    rec = tot["tp"] / (tot["tp"] + tot["fn"]) if tot["tp"] + tot["fn"] else 1.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {**tot, "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)}


# ── 모델 추출(선택) — OpenAI 호환 엔드포인트 ──────────────────
_PROMPT = (
    "다음 학사 문서에서 날짜가 있는 일정을 뽑아 JSON 배열로만 답하라. "
    'each item: {"date":"YYYY-MM-DD","type":"과제|시험|발표|수업변경|신청마감|행사|공지|기타",'
    '"title":"...","quote":"원문 근거 문장"}. 날짜 없으면 제외.\n\n문서:\n')


def predict_events(text: str) -> list[dict]:
    """LLM_MAIN 으로 events 추출. 미설정이면 RuntimeError."""
    base = os.environ.get("LLM_MAIN_BASE_URL"); key = os.environ.get("LLM_MAIN_API_KEY")
    model = os.environ.get("LLM_MAIN_MODEL")
    if not (base and key and model):
        raise RuntimeError("`.env` 의 LLM_MAIN_BASE_URL/API_KEY/MODEL 미설정 — 모델 평가 불가")
    import httpx
    r = httpx.post(f"{base.rstrip('/')}/chat/completions",
                   headers={"Authorization": f"Bearer {key}"},
                   json={"model": model, "temperature": 0,
                         "messages": [{"role": "user", "content": _PROMPT + text[:6000]}]},
                   timeout=60)
    r.raise_for_status()
    out = r.json()["choices"][0]["message"]["content"]
    m = re.search(r"\[.*\]", out, re.DOTALL)
    return json.loads(m.group(0)) if m else []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--model", action="store_true")
    args = ap.parse_args()
    recs = load_gold()
    if not recs:
        print("data/testset/*.jsonl 이 비었습니다. 먼저 make-testset-seed.py 실행."); return

    if args.self_test:
        pairs = [(r["labels"]["events"], r["labels"]["events"]) for r in recs]
        print("자가검증(정답=예측):", aggregate(pairs), "→ f1 1.0 이어야 정상")
        return
    if args.model:
        labeled = [r for r in recs if r["labels"]["events"]]
        if not labeled:
            print("채워진 정답이 없습니다. 라벨링 먼저."); return
        pairs = []
        for r in labeled:
            try:
                pred = predict_events(r["text"])
            except Exception as e:  # noqa: BLE001
                print(f"  추출 실패 {r['doc_id']}: {e!r}"); pred = []
            pairs.append((r["labels"]["events"], pred))
            print(f"  {r['doc_id']}: {score(r['labels']['events'], pred)}")
        print("\n전체:", aggregate(pairs))
        return
    # 기본: 형식 검사
    raise SystemExit(1 if validate(recs) else 0)


if __name__ == "__main__":
    main()
