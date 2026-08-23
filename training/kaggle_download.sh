#!/usr/bin/env bash
# 캐글에서 데이터셋/커널(코드) 받기.
#   먼저 ~/.kaggle/kaggle.json (API 토큰) 필요: 캐글 Account → Create New API Token
#   chmod 600 ~/.kaggle/kaggle.json
#
#   bash training/kaggle_download.sh dataset <owner>/<dataset-slug>   # 데이터 → training/data
#   bash training/kaggle_download.sh kernel  <owner>/<kernel-slug>    # 코드   → training/code
set -euo pipefail
cd "$(dirname "$0")/.."
KIND="${1:?dataset|kernel}"; SLUG="${2:?<owner>/<slug>}"
case "$KIND" in
  dataset) kaggle datasets download -d "$SLUG" -p training/data --unzip ;;
  kernel)  kaggle kernels pull "$SLUG" -p training/code ;;
  *) echo "kind 는 dataset 또는 kernel"; exit 1 ;;
esac
echo "완료 → training/${KIND/dataset/data}"
