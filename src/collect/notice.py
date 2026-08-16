"""공개 게시판 공지 수집 (경로 C, 수집 계획서 §3.3·§6).

로그인 없는 공개 공지만 수집한다. 세션이 필요 없어 httpx 로 가볍게 받는다.
사이트마다 게시판 구조가 달라 파서를 개별 구현한다.

원칙(§6):
  · robots.txt 를 확인해 허용된 경로만 수집
  · 요청 간격을 두고 동시요청 없이 순차 수집
  · User-Agent 에 프로젝트를 명시
카테고리 분류는 하지 않는다 — 나중에 notice_ai-agent 가 LLM 으로 한다.
여기서는 사이트가 주는 구분값(있으면)만 그대로 담는다.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from . import runlog, storage
from .config import settings

USER_AGENT = "Univ-Us-Bot/0.1 (+academic notice collector; contact: team channel)"
_DATE_RE = re.compile(r"(20\d{2})[.\-/]\s?(\d{1,2})[.\-/]\s?(\d{1,2})")
_YYMMDD_RE = re.compile(r"\b(\d{2})[.\-/]\s?(\d{1,2})\s+(\d{1,2})\b")


@dataclass
class Notice:
    title: str
    url: str
    date: str          # YYYY-MM-DD (가능하면)
    category: str = ""
    board: str = ""


@dataclass
class NoticeSource:
    key: str
    name: str
    list_url: str
    parser: str        # 파서 함수 키


def _norm_date(s: str) -> str:
    m = _DATE_RE.search(s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = _YYMMDD_RE.search(s)
    if m:
        return f"20{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


# ── 사이트별 파서 ───────────────────────────────────────────
def _parse_jnu_cms(html: str, list_url: str) -> list[Notice]:
    """전남대 CMS(subview/artclView) — 학과 게시판."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for tr in soup.select("table tbody tr"):
        a = tr.find("a", href=re.compile(r"artclView"))
        if not a:
            continue
        tds = tr.find_all("td")
        cat = tds[0].get_text(strip=True) if tds else ""
        date = ""
        for td in tds:
            d = _norm_date(td.get_text(strip=True))
            if d:
                date = d
                break
        out.append(Notice(title=a.get_text(" ", strip=True),
                           url=urljoin(list_url, a["href"]),
                           date=date, category=cat))
    return out


def _parse_kboard(html: str, list_url: str) -> list[Notice]:
    """movePageView(uid) 방식 게시판 — 사업단(aicoss/nccoss)."""
    soup = BeautifulSoup(html, "lxml")
    base = list_url.split("?")[0]
    out = []
    for tr in soup.select("table tbody tr"):
        a = tr.find("a", href=re.compile(r"movePageView"))
        if not a:
            continue
        m = re.search(r"movePageView\((\d+)\)", a["href"])
        if not m:
            continue
        tds = tr.find_all("td")
        cat = tds[0].get_text(strip=True) if tds else ""
        date = ""
        for td in tds:
            d = _norm_date(td.get_text(strip=True))
            if d:
                date = d
                break
        title = re.sub(r"\s*New\s*", " ", a.get_text(" ", strip=True)).strip()
        out.append(Notice(title=title,
                           url=f"{base}view/{m.group(1)}?bd=notice",
                           date=date, category=cat))
    return out


def _parse_wp_kboard(html: str, list_url: str) -> list[Notice]:
    """워드프레스 KBoard — 소프트웨어중심사업단."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for a in soup.select("a[href*='mod=document']"):
        title = a.get_text(" ", strip=True)
        if not title:
            continue
        row_text = a.find_parent(["tr", "li", "div"])
        date = _norm_date(row_text.get_text(" ", strip=True)) if row_text else ""
        out.append(Notice(title=title, url=urljoin(list_url, a["href"]), date=date))
    # 중복 URL 제거
    seen, uniq = set(), []
    for n in out:
        if n.url not in seen:
            seen.add(n.url)
            uniq.append(n)
    return uniq



# ── 상세 본문·첨부 추출 ─────────────────────────────────────
_BODY_SEL = {
    "jnu_cms": ".view-con",
    "kboard": "section.viewContainer, .viewContainer-wrap",
    "wp_kboard": ".kboard-content, .kboard-document-content",
}
_FILE_EXT = (".pdf", ".hwp", ".hwpx", ".doc", ".docx", ".xls", ".xlsx",
             ".ppt", ".pptx", ".zip", ".jpg", ".png")


def extract_detail(html: str, parser: str, page_url: str) -> dict:
    """상세 페이지 HTML → {body, attachments}. 네비/헤더/푸터는 제거한다."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.select(
        "script,style,header,footer,nav,.gnb,.lnb,.snb,#header,#footer,#gnb,.header,.footer,.quick,.top"
    ):
        tag.decompose()
    el = soup.select_one(_BODY_SEL.get(parser, "body"))
    body = el.get_text("\n", strip=True) if el else ""

    atts = []
    for a in soup.find_all("a", href=True):
        h = a["href"]
        name = a.get_text(strip=True)
        if any(k in h.lower() for k in ("download", "file_down", "attach", "fileDown")) \
                or h.lower().endswith(_FILE_EXT):
            atts.append({"name": name, "url": urljoin(page_url, h)})
    return {"body": body, "attachments": atts}


_PARSERS = {"jnu_cms": _parse_jnu_cms, "kboard": _parse_kboard, "wp_kboard": _parse_wp_kboard}

SOURCES = {
    "aisw": NoticeSource("aisw", "인공지능학부(학과)",
        "https://aisw.jnu.ac.kr/aisw/518/subview.do?enc=Zm5jdDF8QEB8JTJGYmJzJTJGYWlzdyUyRjY0JTJGYXJ0Y2xMaXN0LmRvJTNGYmJzQ2xTZXElM0QlMjZiYnNPcGVuV3JkU2VxJTNENDUlMjZpc1ZpZXdNaW5lJTNEZmFsc2UlMjZzcmNoQ29sdW1uJTNEc2olMjZzcmNoV3JkJTNEJTI2",
        "jnu_cms"),
    "aicoss": NoticeSource("aicoss", "인공지능혁신융합사업단",
        "https://www.aicoss.kr/www/notice/?cate=%EC%A0%84%EB%82%A8%EB%8C%80%ED%95%99%EA%B5%90", "kboard"),
    "nccoss": NoticeSource("nccoss", "차세대통신혁신융합사업단",
        "https://jnu.nccoss.kr/www/notice/", "kboard"),
    "sojoong": NoticeSource("sojoong", "소프트웨어중심사업단",
        "https://sojoong.kr/notice/notice-board/", "wp_kboard"),
}


def _robots_ok(list_url: str) -> bool:
    from urllib.parse import urlparse
    o = urlparse(list_url)
    rp = RobotFileParser()
    rp.set_url(f"{o.scheme}://{o.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:  # noqa: BLE001 — robots 없으면 제한 없음으로 간주
        return True
    return rp.can_fetch(USER_AGENT, list_url)


def collect(source_key: str, *, fetch_detail: bool = True, max_detail: int = 40) -> dict:
    """한 사이트 공지 목록을 수집하고, 신규 공지의 상세 원문을 저장한다."""
    src = SOURCES[source_key]
    store_src = f"notice_{src.key}"
    if not _robots_ok(src.list_url):
        runlog.record_run(store_src, status="failed", detail="robots.txt 가 수집을 금지함")
        print(f"[{src.key}] robots.txt 가 금지 — 수집 중단")
        return {"status": "blocked"}

    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as cli:
            r = cli.get(src.list_url)
            r.raise_for_status()
            notices = _PARSERS[src.parser](r.text, src.list_url)
            if not notices:
                runlog.record_run(store_src, status="failed", detail="목록 파싱 0건 (구조 변경?)")
                print(f"[{src.key}] 공지 0건 — 게시판 구조가 바뀌었을 수 있습니다")
                return {"status": "failed"}

            # 목록(메타)을 processed 로 저장
            out_dir = settings.data_dir / "processed" / "notices"
            out_dir.mkdir(parents=True, exist_ok=True)
            import json
            (out_dir / f"{src.key}.json").write_text(json.dumps({
                "board": src.name, "list_url": src.list_url,
                "parsed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "notices": [n.__dict__ | {"board": src.name} for n in notices],
            }, ensure_ascii=False, indent=2), encoding="utf-8")

            # 신규 공지의 상세 원문 저장 (이미 본 URL 은 건너뜀 = 예의)
            new = 0
            if fetch_detail:
                seen = _seen_urls(store_src)
                for n in notices:
                    if n.url in seen or new >= max_detail:
                        continue
                    time.sleep(settings.jnu_collect_min_interval_sec)
                    try:
                        dr = cli.get(n.url)
                        dr.raise_for_status()
                    except Exception as e:  # noqa: BLE001
                        print(f"    상세 실패 {n.url[:60]}: {e!r}")
                        continue
                    storage.save_original(
                        source=store_src, item_id=n.url, url=n.url,
                        data=dr.text.encode("utf-8"), ext="html", tag="service",
                        extra_meta={"title": n.title, "date": n.date,
                                    "category": n.category, "board": src.name},
                    )
                    # 본문·첨부 추출 → 구조화 저장 (원문은 위에서 보존)
                    detail = extract_detail(dr.text, src.parser, n.url)
                    doc_dir = out_dir / src.key
                    doc_dir.mkdir(parents=True, exist_ok=True)
                    safe = n.url.replace("/", "_").replace("?", "_")[:80]
                    (doc_dir / f"{safe}.json").write_text(json.dumps({
                        "title": n.title, "date": n.date, "category": n.category,
                        "board": src.name, "url": n.url,
                        "body": detail["body"], "attachments": detail["attachments"],
                    }, ensure_ascii=False, indent=2), encoding="utf-8")
                    new += 1
    except Exception as e:  # noqa: BLE001 — 조용히 실패하지 않는다(§4.4)
        runlog.record_run(store_src, status="failed", detail=repr(e))
        print(f"[{src.key}] 실패: {e!r}")
        return {"status": "failed", "error": repr(e)}

    runlog.record_run(store_src, status="ok", items_total=len(notices), items_new=new)
    print(f"[{src.key}] {src.name} — 목록 {len(notices)}건, 신규 상세 {new}건 저장")
    return {"status": "ok", "total": len(notices), "new": new}


def _seen_urls(store_src: str) -> set[str]:
    idx = settings.index_path(store_src)
    if not idx.exists():
        return set()
    import json
    return {json.loads(ln)["item_id"] for ln in idx.read_text(encoding="utf-8").splitlines() if ln.strip()}
