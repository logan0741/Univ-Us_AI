"""수강신청 내역 (Suup080) — 내가 신청한 강의 목록.

주의: 수강신청 사이트는 신청 기간에만 열릴 수 있다(수집 계획서 §1.1).
기간 종료 후 접근 경로가 바뀌면 login_required 또는 빈 페이지가 될 수 있다.
"""
from __future__ import annotations

from ..base import Collector, Item
from ..config import settings


class SugangCoursesCollector(Collector):
    source = "sugang_courses"

    def fetch_items(self, page) -> list[Item]:
        self.goto(page, settings.jnu_sugang_courses_url)
        page.wait_for_load_state("networkidle")
        html = page.content().encode("utf-8")
        # 원문 저장 우선. 학기 단위 1건으로 관리(같은 학기면 수정 감지).
        return [Item(item_id="sugang_courses_current", url=page.url, data=html)]
