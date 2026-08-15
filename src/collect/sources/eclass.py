"""eClass = Moodle 과제·마감.

sel.jnu.ac.kr 은 Moodle 이다(로그인이 /login/index.php 로 감).
Moodle 은 캘린더를 .ics 로 내보낼 수 있어, 게시판을 긁는 것보다 안정적이다.

우선순위:
  1) JNU_ECLASS_ICS_URL 이 있으면 그 .ics 를 세션으로 받아 저장 (권장)
  2) 없으면 eClass 대시보드 HTML 을 원문으로 저장 (폴백)

.ics URL 발급법은 docs/크롤링-사용법.md 참고 (Moodle: 캘린더 → 내보내기 → URL 가져오기).
"""
from __future__ import annotations

from ..base import Collector, Item
from ..config import settings


class EclassCollector(Collector):
    source = "eclass"

    def fetch_items(self, page) -> list[Item]:
        ics_url = settings.jnu_eclass_ics_url.strip()
        if ics_url:
            # 세션 쿠키를 그대로 쓰는 브라우저 컨텍스트로 .ics 를 받는다.
            resp = page.request.get(ics_url)
            if not resp.ok:
                raise RuntimeError(f"ICS 요청 실패: {resp.status}")
            body = resp.body()
            return [Item(item_id="eclass_calendar", url=ics_url, data=body, ext="ics")]

        # 폴백: 대시보드 원문
        self.goto(page, settings.jnu_eclass_url)
        page.wait_for_load_state("networkidle")
        html = page.content().encode("utf-8")
        return [Item(
            item_id="eclass_dashboard", url=page.url, data=html,
            extra_meta={"note": "ICS URL 미설정 — 대시보드 HTML 폴백"},
        )]
