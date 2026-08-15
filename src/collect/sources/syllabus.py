"""수업 계획서 (Suup051).

계획서는 과목별로 열리며 PDF 다운로드일 수 있다.
1차 구현은 계획서 조회 페이지 원문(HTML)을 저장한다.
과목별 PDF 링크 추출은 실제 페이지 구조 확인 후 붙인다(§5.1).
"""
from __future__ import annotations

from ..base import Collector, Item
from ..config import settings


class SyllabusCollector(Collector):
    source = "syllabus"

    def fetch_items(self, page) -> list[Item]:
        self.goto(page, settings.jnu_syllabus_url)
        page.wait_for_load_state("networkidle")
        html = page.content().encode("utf-8")
        return [Item(item_id="syllabus_index", url=page.url, data=html)]
