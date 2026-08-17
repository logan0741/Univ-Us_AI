#!/usr/bin/env bash
# 세부사항 전부 수집 — 목록 전 페이지 + 상세(본문·첨부·이미지·PDF) 전량.
#
#   bash scripts/collect-full.sh            # 공개 사이트 전부
#   bash scripts/collect-full.sh notices    # 공지만
#   bash scripts/collect-full.sh allcon     # allcon만
#   bash scripts/collect-full.sh external   # campuspick만
#
# ⚠️ 상세는 항목마다 요청 간격을 둡니다(서버 부하 방지). 공지 전량은 수십 분 걸릴 수 있음.
#    아래 INTERVAL 로 간격을 조절합니다(기본 1초, 폴라이트 유지).
set -euo pipefail
cd "$(dirname "$0")/.."
export JNU_COLLECT_MIN_INTERVAL_SEC="${INTERVAL:-1}"
WHAT="${1:-all}"

run() { echo -e "\n\033[1;36m▶ $*\033[0m"; python -m src.collect.cli "$@"; }

if [[ "$WHAT" == "all" || "$WHAT" == "notices" ]]; then
  # 4개 게시판: 전 페이지 순회 + 신규 전량 상세·첨부
  for s in aisw aicoss nccoss sojoong; do
    run notices "$s" --pages 100 --details 100000
  done
fi
if [[ "$WHAT" == "all" || "$WHAT" == "allcon" ]]; then
  # 공모전·대외활동: 스크롤 최대 + 상세 전량(포스터·PDF·본문)
  run allcon contest  --scrolls 50 --details 100000
  run allcon activity --scrolls 50 --details 100000
fi
if [[ "$WHAT" == "all" || "$WHAT" == "external" ]]; then
  # campuspick: 목록 + 대표 이미지 (상세 API 없음)
  run external all --scrolls 30
fi

echo -e "\n\033[1;32m✔ 완료 — 집계 생성 중\033[0m"
python -m src.collect.cli report
echo "→ docs/수집-집계.md"
