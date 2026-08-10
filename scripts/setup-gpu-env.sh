#!/usr/bin/env bash
# ============================================================
# Univ-Us_AI 개발 환경 설치
#
#   저장소 패키지를 전용 venv 에 설치하고, Jupyter 커널로 등록하고,
#   GPU 가 있으면 동작까지 확인합니다.
#
# 쓰는 때
#   · 서버에서 처음 세팅할 때
#   · pod 가 재시작되어 venv 가 사라졌을 때  ← 이게 주 용도입니다
#
# 실행
#   bash scripts/setup-gpu-env.sh
#
#   VENV=~/.venv/다른이름 bash scripts/setup-gpu-env.sh    경로 바꾸기
#   SKIP_GPU=1          bash scripts/setup-gpu-env.sh    GPU 패키지 건너뛰기
#
# 오래 걸립니다(GPU 포함 시 ~6GB). 세션이 끊겨도 계속 돌게 하려면:
#   setsid nohup bash scripts/setup-gpu-env.sh > ~/setup.log 2>&1 < /dev/null &
#   tail -f ~/setup.log
# ============================================================
set -u

VENV="${VENV:-$HOME/.venv/univus-ai}"
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KERNEL_NAME="univus-ai"

echo "=============================================="
echo " 시작    : $(date '+%F %T')"
echo " 저장소  : $PROJ"
echo " venv    : $VENV"
echo "=============================================="

cd "$PROJ" || { echo "저장소 경로를 찾지 못했습니다"; exit 1; }

# ── GPU 유무 판단 ───────────────────────────────────────────
USE_GPU=0
if [ "${SKIP_GPU:-0}" = "1" ]; then
    echo "SKIP_GPU=1 → GPU 패키지를 건너뜁니다"
elif command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    USE_GPU=1
    echo "GPU 감지됨 → requirements-gpu.txt 포함"
else
    echo "GPU 없음 → CPU 패키지만 설치 (개발에는 지장 없습니다)"
fi

# ── 1. venv ─────────────────────────────────────────────────
echo
echo "### [1/4] venv 준비 ###"
if [ -d "$VENV" ]; then
    echo "  이미 있음: $VENV"
else
    python3 -m venv "$VENV" || { echo "venv 생성 실패"; exit 1; }
    echo "  생성함: $VENV"
fi
"$VENV/bin/python" -m pip install -q --upgrade pip setuptools wheel
echo "  python $("$VENV/bin/python" --version 2>&1 | cut -d' ' -f2) · pip $("$VENV/bin/pip" --version | cut -d' ' -f2)"

# ── 2. 패키지 ───────────────────────────────────────────────
echo
echo "### [2/4] 패키지 설치 ###"
REQS=(-r requirements.txt -r requirements-dev.txt)
[ "$USE_GPU" = "1" ] && REQS+=(-r requirements-gpu.txt)

"$VENV/bin/pip" install "${REQS[@]}"
PIP_EXIT=$?
if [ "$PIP_EXIT" -ne 0 ]; then
    echo
    echo "!!! 설치 실패 (종료 코드 $PIP_EXIT) — 위 로그를 확인하세요 !!!"
    echo "STATUS=FAILED"
    exit "$PIP_EXIT"
fi

# ── 3. Jupyter 커널 ─────────────────────────────────────────
echo
echo "### [3/4] Jupyter 커널 등록 ###"
"$VENV/bin/python" -m ipykernel install --user \
    --name "$KERNEL_NAME" \
    --display-name "Univ-Us AI" 2>&1 | sed 's/^/  /'

# ── 4. 검증 ─────────────────────────────────────────────────
echo
echo "### [4/4] 검증 ###"
"$VENV/bin/python" - <<'PY'
import importlib.metadata as md

for name in ["pydantic", "openai", "langchain", "fastapi", "pypdf", "pytest", "ruff"]:
    try:
        print(f"  OK    {name:16} {md.version(name)}")
    except md.PackageNotFoundError:
        print(f"  없음  {name}")

try:
    import torch
except ImportError:
    print("  torch 미설치 (CPU 환경이면 정상)")
else:
    print(f"\n  torch          {torch.__version__}")
    print(f"  CUDA 런타임    {torch.version.cuda}")
    print(f"  cuda.is_available()  {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  GPU            {torch.cuda.get_device_name(0)}")
        free, total = torch.cuda.mem_get_info()
        print(f"  VRAM           {free/1024**3:.1f} GiB free / {total/1024**3:.1f} GiB total")
        x = torch.randn(1024, 1024, device="cuda")
        (x @ x).sum().item()
        print("  matmul 테스트  OK")
    else:
        print("  !!! GPU 를 인식하지 못했습니다 — nvidia-smi 를 확인하세요 !!!")
PY

if [ "$USE_GPU" = "1" ] && [ -x "$VENV/bin/nvitop" ]; then
    echo
    echo "--- nvitop ---"
    "$VENV/bin/nvitop" -1 2>&1 | head -12
fi

echo
echo "=============================================="
echo " venv 크기: $(du -sh "$VENV" 2>/dev/null | cut -f1)"
echo " STATUS=DONE"
echo " 종료: $(date '+%F %T')"
echo
echo " 쓰려면:  source $VENV/bin/activate"
echo " 노트북:  커널 목록에서 'Univ-Us AI' 선택"
echo "=============================================="
