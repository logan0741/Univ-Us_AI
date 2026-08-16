"""수업 계획서 (Suup051) — 과목별 계획서 PDF 수집.

경로:
  시간표에서 내 과목(과목코드·분반)을 뽑고,
  계획서조회에서 과목명으로 검색 → 결과행의 OpenDown(...) →
  ClipReport 리포트 뷰어(rptbi) 팝업 → "PDF 저장" → 계획서 PDF 원문 저장.

원문(PDF)을 그대로 보존한다(수집 계획서 §5.1). 필드 추출(과제·시험 일정)은
doc_ai-agent 의 강의계획서 PDF 파이프라인이 담당한다.
"""
from __future__ import annotations

import re

from ..base import Collector, Item
from ..config import settings

# 시간표 셀의 "…과목명…과목코드-분반[수업형태]" 패턴에서 (코드, 분반, 과목명) 추출
_COURSE_RE = re.compile(r"([가-힣A-Za-z0-9·\(\)]+?)\s*담당교수.*?([A-Z]{2,4}\d{4})-(\d+)")


def _parse_timetable_courses(html: str) -> list[dict]:
    """시간표 원문에서 내 수강과목 목록을 뽑는다."""
    from bs4 import BeautifulSoup

    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    seen: dict[str, dict] = {}
    # "[ N 교시 ] 과목명 담당교수 :교수 강의실 CODE-CLASS [형태]"
    for m in re.finditer(
        r"\]\s*([가-힣A-Za-z0-9·\(\)]+?)\s*담당교수\s*:\s*\S+.*?([A-Z]{2,4}\d{4})-(\d+)", text
    ):
        name, code, cls = m.group(1).strip(), m.group(2), m.group(3)
        key = f"{code}-{cls}"
        if key not in seen:
            seen[key] = {"subj": code, "cls": cls, "name": name}
    return list(seen.values())


class SyllabusCollector(Collector):
    source = "syllabus"

    def fetch_items(self, page) -> list[Item]:
        yy, term = settings.syllabus_yy, settings.syllabus_term

        # 1) 시간표에서 내 과목 목록
        self.goto(page, settings.jnu_timetable_url)
        page.wait_for_load_state("networkidle")
        courses = _parse_timetable_courses(page.content())
        if not courses:
            raise RuntimeError("시간표에서 과목을 찾지 못했습니다 (학기·로그인 확인)")
        print(f"  내 과목 {len(courses)}개: " + ", ".join(f"{c['subj']}-{c['cls']}" for c in courses))

        # 2) 계획서 조회 페이지 준비
        self.goto(page, settings.jnu_syllabus_url)
        page.wait_for_load_state("networkidle")
        page.select_option("select[name*='ddlYY']", yy)
        page.wait_for_load_state("networkidle")
        page.select_option("select[name*='ddlTerm']", term)
        page.wait_for_load_state("networkidle")

        items: list[Item] = []
        for c in courses:
            pdf = self._fetch_one(page, c, yy, term)
            if pdf:
                items.append(Item(
                    item_id=f"{c['subj']}-{c['cls']}_{yy}-{term}",
                    url=settings.jnu_syllabus_url,
                    data=pdf, ext="pdf",
                    extra_meta={"subj": c["subj"], "class_no": c["cls"],
                                "name": c["name"], "yy": yy, "term": term},
                ))
                print(f"    ✅ {c['subj']}-{c['cls']} {c['name']} — {len(pdf)} bytes")
            else:
                print(f"    ⚠️ {c['subj']}-{c['cls']} {c['name']} — 계획서 없음/실패")
        return items

    def _fetch_one(self, page, course: dict, yy: str, term: str) -> bytes | None:
        """한 과목: 검색 → OpenDown → ClipReport PDF 저장."""
        subj, cls, name = course["subj"], course["cls"], course["name"]
        # 검색어(과목명) 입력 후 조회
        page.fill("input[name*='txtSubj']", name)
        page.click("#ContentPlaceHolder_ContentPlaceHolderSub_btnSearch")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1200)

        # 내 (과목코드,분반)에 해당하는 OpenDown 링크 찾기
        links = page.query_selector_all("a[href*='OpenDown']")
        target = None
        args = None
        for a in links:
            href = a.get_attribute("href") or ""
            m = re.search(r"OpenDown\(([^)]*)\)", href)
            if not m:
                continue
            parts = [x.strip().strip("'\"") for x in m.group(1).split(",")]
            if len(parts) >= 4 and parts[0] == subj and parts[1] == cls:
                target, args = a, parts
                break
        if target is None:
            return None

        # 한국어 계획서로 강제 호출(가능하면), 아니면 링크 그대로 클릭
        try:
            with page.expect_popup(timeout=15000) as pi:
                if args and len(args) >= 6:
                    page.evaluate(
                        "a => OpenDown(a[0],a[1],a[2],a[3],a[4],a[5],'KOR')", args
                    )
                else:
                    target.click()
            popup = pi.value
        except Exception:  # noqa: BLE001 — 팝업 안 뜨면 계획서 없음 처리
            return None

        try:
            popup.wait_for_load_state("networkidle")
            popup.wait_for_timeout(2500)
            with popup.expect_download(timeout=20000) as di:
                popup.click("button[title*='PDF'], img[src*='pdf.svg'], "
                            "[class*='pdf_button']")
            download = di.value
            data = download.path().read_bytes()
            return data if data[:4] == b"%PDF" else None
        except Exception:  # noqa: BLE001 — 내보내기 실패는 스킵
            return None
        finally:
            with __import__("contextlib").suppress(Exception):
                popup.close()
