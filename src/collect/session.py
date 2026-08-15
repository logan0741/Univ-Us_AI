"""Playwright 로그인 세션 관리.

핵심 원칙: **비밀번호를 저장하지 않는다.**
  · login()  : 브라우저를 띄운다 → 사용자가 직접 SSO 로그인 → 세션(쿠키)만 저장
  · browser(): 저장된 세션으로 헤드리스 브라우저를 연다
  · 세션이 만료되면 로그인 페이지로 튕기므로, 각 소스가 그것을 감지해 멈춘다.

세션 파일(data/sessions/…json)은 '살아있는 인증'이라 비밀번호만큼 민감하다.
data/ 는 gitignore 되어 있고, 절대 커밋·공유하지 않는다.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager

from .config import settings


def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        sys.exit(
            "playwright 가 설치되지 않았습니다.\n"
            "  pip install -r requirements-collect.txt\n"
            "  playwright install chromium"
        )


def login() -> None:
    """브라우저를 띄워 사용자가 직접 로그인하게 하고, 세션만 저장한다.

    화면(display)이 있는 곳에서 실행해야 한다(로컬 PC 권장).
    헤드리스 서버라면 사용법 문서의 'xvfb / 세션 핸드오프' 절 참고.
    """
    sync_playwright = _require_playwright()
    settings.session_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(settings.jnu_login_start_url, timeout=settings.jnu_page_timeout_ms)

        print("=" * 60)
        print(" 브라우저에서 학교 계정으로 로그인하세요.")
        print(" (이 프로그램은 비밀번호를 저장하지 않습니다 — 세션 쿠키만 저장)")
        print(" 로그인을 마쳤으면 이 터미널에서 Enter 를 누르세요.")
        print("=" * 60)
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            print("\n취소했습니다. 세션을 저장하지 않습니다.")
            browser.close()
            return

        context.storage_state(path=str(settings.session_path))
        browser.close()

    print(f"세션을 저장했습니다: {settings.session_path}")
    print("이제 collect 명령을 쓸 수 있습니다.")


def has_session() -> bool:
    return settings.session_path.exists()


@contextmanager
def browser_page(headless: bool = True):
    """저장된 세션으로 페이지를 연다. 세션이 없으면 안내 후 종료."""
    if not has_session():
        sys.exit("세션이 없습니다. 먼저 `login` 을 실행하세요.")

    sync_playwright = _require_playwright()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=str(settings.session_path))
        page = context.new_page()
        page.set_default_timeout(settings.jnu_page_timeout_ms)
        try:
            yield page
        finally:
            browser.close()


# 로그인 페이지로 튕겼는지(세션 만료) 판별하는 힌트.
# 소스별로 다를 수 있어 넉넉히 잡는다.
LOGIN_URL_HINTS = ("login", "Login", "sso", "SSO", "auth", "Auth")


def looks_like_login(url: str) -> bool:
    return any(h in url for h in LOGIN_URL_HINTS)
