#!/usr/bin/env bash
# ============================================================
# 서버 웹 로그인 포털(noVNC) 의존성 설치
#
#   서버에서 실제 브라우저를 띄워 학교 통합인증(비번+휴대폰 인증)을
#   웹으로 처리하기 위한 스택을 깝니다.
#
#   ⚠️ 이 패키지들은 시스템(/usr)에 깔려 pod 재시작 시 사라집니다.
#      재시작 후 다시 이 스크립트를 실행하세요. (playwright 크롬은 유지됨)
#
# 실행:  bash scripts/setup-weblogin.sh
# ============================================================
set -u

echo "### 웹 로그인 포털 스택 설치 ###"
echo "  Xvfb(가상 디스플레이) · x11vnc · noVNC · websockify · 한글 폰트"
echo ""

sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    xvfb x11vnc novnc websockify fonts-nanum
APT_EXIT=$?

echo ""
echo "### 확인 ###"
ok=1
for c in Xvfb x11vnc websockify; do
    if command -v "$c" >/dev/null 2>&1; then echo "  $c ✅"; else echo "  $c ❌"; ok=0; fi
done
[ -f /usr/share/novnc/vnc.html ] && echo "  noVNC ✅" || { echo "  noVNC ❌"; ok=0; }

# playwright 크롬은 영구 볼륨(~/.cache)이라 보통 남아 있지만, 없으면 설치
if [ ! -d "$HOME/.cache/ms-playwright" ]; then
    echo ""
    echo "  playwright 크롬이 없어 설치합니다..."
    python -m playwright install chromium
fi

echo ""
if [ "$ok" = "1" ] && [ "$APT_EXIT" = "0" ]; then
    echo "STATUS=DONE — 이제 실행하세요:  python -m src.collect.cli weblogin"
else
    echo "STATUS=FAILED — 위 로그를 확인하세요"
    exit 1
fi
