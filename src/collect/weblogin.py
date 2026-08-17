"""서버 웹 로그인 포털 (noVNC).

헤드리스 서버에서 실제 브라우저를 Xvfb 가상 디스플레이에 띄우고,
그 화면을 noVNC 로 웹에 넘긴다. 사용자는 SSH 포트포워딩으로 접속해
학교 통합인증(비번 + 휴대폰 앱/OTP)을 **직접** 완료한 뒤,
터미널에서 Enter 를 눌러 세션을 저장한다.

  · 비밀번호를 프로그램이 저장/기록하지 않는다 (사용자가 실제 페이지에 직접 입력)
  · MFA(휴대폰 앱/OTP)도 사용자가 실제 페이지에서 처리하므로 그대로 통과된다
  · 어느 탭/사이트에 있든 상관없이, Enter 시점의 세션(쿠키 전체)을 저장한다

실행:  python -m src.collect.cli weblogin
접속:  로컬에서 SSH 포트포워딩 후 브라우저로 http://localhost:6080/vnc.html
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

from .config import settings

DISPLAY = ":99"
SCREEN = "1280x800x16"  # 16bit 색심도 = 대역폭↓ (noVNC 속도↑)
VNC_PORT = 5900
WEB_PORT = int(os.environ.get("WEBLOGIN_PORT", "6080"))
NOVNC_DIR = "/usr/share/novnc"


def _need(cmd: str) -> None:
    if shutil.which(cmd) is None:
        sys.exit(f"'{cmd}' 가 없습니다. 먼저 실행하세요:  bash scripts/setup-weblogin.sh")


def _wait_display(timeout: float = 10) -> bool:
    sock = Path(f"/tmp/.X11-unix/X{DISPLAY.lstrip(':')}")
    for _ in range(int(timeout * 10)):
        if sock.exists():
            return True
        time.sleep(0.1)
    return False


def run_weblogin() -> None:
    for c in ("Xvfb", "x11vnc", "websockify"):
        _need(c)
    if not Path(NOVNC_DIR, "vnc.html").exists():
        sys.exit("noVNC 가 없습니다. bash scripts/setup-weblogin.sh 를 먼저 실행하세요.")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright 미설치. pip install -r requirements-collect.txt && playwright install chromium")

    settings.session_path.parent.mkdir(parents=True, exist_ok=True)
    procs: list[subprocess.Popen] = []

    def cleanup(*_):
        for p in procs:
            with suppress(ProcessLookupError, OSError):
                p.terminate()
        time.sleep(0.5)
        for p in procs:
            with suppress(ProcessLookupError, OSError):
                p.kill()

    signal.signal(signal.SIGTERM, lambda *a: (cleanup(), sys.exit(143)))

    try:
        # 1) 가상 디스플레이
        procs.append(subprocess.Popen(
            ["Xvfb", DISPLAY, "-screen", "0", SCREEN, "-nolisten", "tcp"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ))
        if not _wait_display():
            sys.exit("Xvfb 가 뜨지 않았습니다.")
        env = {**os.environ, "DISPLAY": DISPLAY}

        # 2) VNC (localhost 전용 — SSH 터널로만)
        procs.append(subprocess.Popen(
            ["x11vnc", "-display", DISPLAY, "-rfbport", str(VNC_PORT),
             "-localhost", "-nopw", "-forever", "-shared", "-quiet",
             "-threads", "-ncache", "10", "-ncache_cr", "-wait", "20"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ))
        time.sleep(1)

        # 3) noVNC 웹 (localhost 전용)
        procs.append(subprocess.Popen(
            ["websockify", "--web", NOVNC_DIR, f"127.0.0.1:{WEB_PORT}", f"127.0.0.1:{VNC_PORT}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ))
        time.sleep(1)

        # 4) 실제 브라우저를 디스플레이에 띄우고 로그인 시작 지점으로
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, env=env,
                                        args=["--start-maximized", "--no-sandbox"])
            context = browser.new_context(no_viewport=True)
            page = context.new_page()
            page.goto(settings.jnu_login_start_url, wait_until="domcontentloaded",
                      timeout=settings.jnu_page_timeout_ms)
            with suppress(Exception):
                page.click("#btnLogin", timeout=3000)

            print("=" * 64)
            print(" 서버에 로그인 브라우저를 띄웠습니다.")
            print()
            print(" 1) 로컬 PC 터미널에서 SSH 포트포워딩:")
            print(f"      ssh -N -L {WEB_PORT}:localhost:{WEB_PORT} <서버 SSH 접속정보>")
            print("      (VS Code Remote-SSH 면 포트가 자동 전달되기도 함)")
            print(" 2) 로컬 브라우저에서 접속:")
            print(f"      http://localhost:{WEB_PORT}/vnc.html")
            print(" 3) 학교 통합인증으로 직접 로그인 (비번 + 휴대폰 인증)")
            print()
            print("  ★ 로그인을 모두 마쳤으면(강좌/시간표 화면이 보이면)")
            print("    이 터미널로 돌아와 Enter 를 누르세요. → 세션 저장")
            print("    (취소: Ctrl+C)")
            print("=" * 64)

            try:
                input()
            except (EOFError, KeyboardInterrupt):
                print("\n취소했습니다. 세션을 저장하지 않습니다.")
                browser.close()
                return

            # Enter 시점의 세션(쿠키 전체) 저장 — 어느 탭이든 상관없음
            context.storage_state(path=str(settings.session_path))
            n = len(json.loads(settings.session_path.read_text()).get("cookies", []))
            print(f"세션 저장 완료: {settings.session_path} (쿠키 {n}개)")
            if n == 0:
                print("  ⚠️ 쿠키가 0개입니다 — 로그인이 안 된 상태일 수 있습니다. 다시 시도하세요.")
            else:
                print("  이제:  python -m src.collect.cli collect syllabus")
            browser.close()
    finally:
        cleanup()
