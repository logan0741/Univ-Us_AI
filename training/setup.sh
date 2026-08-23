#!/usr/bin/env bash
# 학습 환경 준비: 의존성 설치 + GPU 확인.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== 의존성 설치 =="
pip install -r training/requirements.txt
echo "== GPU 확인 =="
python - <<'PY'
import torch
print("CUDA:", torch.cuda.is_available())
if torch.cuda.is_available():
    free, total = torch.cuda.mem_get_info()
    print(f"GPU: {torch.cuda.get_device_name(0)}  가용 {free/1024**3:.1f}/{total/1024**3:.1f} GiB")
    if free/1024**3 < 11:
        print("⚠️ 11GiB 미만 → 4-bit + 4B 급 + max-seq 512 권장. 8B 는 캐글(16GB)에서.")
PY
echo "준비 끝. 데이터를 training/data/*.jsonl 로 넣고  bash training/train.sh"
