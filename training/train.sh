#!/usr/bin/env bash
# 학습 실행 래퍼 — 이 위쪽 값만 바꾸면 됨.
set -euo pipefail
cd "$(dirname "$0")/.."

# ── 여기만 수정 ─────────────────────────────────────────────
MODEL="Qwen/Qwen3-4B"        # 후보는 training/README.md 참고 (로컬 안전=4B, 정확도=8B는 캐글)
DATA="training/data"          # 학습 JSONL 폴더 (캐글 데이터 or prepare_data.py 결과)
OUTPUT="training/outputs"
EPOCHS=3
MAXSEQ=1024                   # 9.5GiB 에서 OOM 나면 512 로
BATCH=1
# ────────────────────────────────────────────────────────────

python training/train.py \
  --model "$MODEL" --data "$DATA" --output "$OUTPUT" \
  --epochs "$EPOCHS" --max-seq "$MAXSEQ" --batch "$BATCH" "$@"
