"""개인 시간표 (Suup090)."""
from __future__ import annotations

from ..base import Collector, Item
from ..config import settings


class TimetableCollector(Collector):
    source = "timetable"

    def fetch_items(self, page) -> list[Item]:
        self.goto(page, settings.jnu_timetable_url)
        page.wait_for_load_state("networkidle")
        html = page.content().encode("utf-8")
        return [Item(item_id="timetable_current", url=page.url, data=html)]
