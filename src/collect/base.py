"""수집기 공통 흐름 (템플릿 메서드).

모든 소스 수집기는 BaseCollector 를 상속해 fetch_items() 만 구현한다.
공통 흐름 = 세션으로 페이지 열기 → 항목 추출 → 원문 저장(중복판별) → 실행로그.
수집 계획서 §4.4(실패처리)·§5(저장)·§6(간격)을 여기서 강제한다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import runlog, storage
from .config import settings
from .session import browser_page, looks_like_login


@dataclass
class Item:
    """수집할 한 건. item_id 는 중복 판별 키다(§4.3)."""
    item_id: str
    url: str
    data: bytes
    ext: str = "html"
    extra_meta: dict = field(default_factory=dict)


class LoginRequired(Exception):
    """세션이 만료되어 로그인 페이지로 튕겼을 때."""


class Collector:
    source: str = "base"

    def fetch_items(self, page) -> list[Item]:
        """페이지에서 저장할 항목들을 만들어 반환한다. 소스별로 구현."""
        raise NotImplementedError

    # ── 공통 실행 ─────────────────────────────────────────────
    def run(self, *, tag: str = "service") -> dict:
        try:
            with browser_page() as page:
                items = self.fetch_items(page)
        except LoginRequired as e:
            runlog.record_run(self.source, status="login_required", detail=str(e))
            print(f"[{self.source}] 세션이 만료되었습니다. `login` 을 다시 실행하세요.")
            return {"status": "login_required"}
        except Exception as e:  # noqa: BLE001  — 조용히 실패하지 않는다(§4.4)
            runlog.record_run(self.source, status="failed", detail=repr(e))
            print(f"[{self.source}] 실패: {e!r}")
            return {"status": "failed", "error": repr(e)}

        new = changed = 0
        for it in items:
            res = storage.save_original(
                source=self.source,
                item_id=it.item_id,
                url=it.url,
                data=it.data,
                ext=it.ext,
                tag=tag,
                extra_meta=it.extra_meta,
            )
            new += int(res.is_new)
            changed += int(res.is_changed)
            time.sleep(settings.jnu_collect_min_interval_sec)  # §6 예의

        runlog.record_run(
            self.source, status="ok",
            items_new=new, items_changed=changed, items_total=len(items),
        )
        print(f"[{self.source}] 완료 — 총 {len(items)}건 (신규 {new} · 수정 {changed})")
        return {"status": "ok", "total": len(items), "new": new, "changed": changed}

    # ── 유틸: 세션 만료 감지 후 원문 확보 ─────────────────────
    def goto(self, page, url: str) -> str:
        page.goto(url, wait_until="domcontentloaded")
        if looks_like_login(page.url):
            raise LoginRequired(f"{url} → {page.url}")
        return page.url
