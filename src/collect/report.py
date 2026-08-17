"""수집 데이터 집계 리포트 — data/ 를 스캔해 마크다운으로 요약.

python -m src.collect.cli report [출력경로]
기본 출력: docs/수집-집계.md (항상 최신 숫자로 재생성)
"""
from __future__ import annotations

import glob
import json
from datetime import datetime
from pathlib import Path


def _files(p: str) -> int:
    d = Path(p)
    return sum(1 for f in d.rglob("*") if f.is_file()) if d.exists() else 0


def _size_mb(p: str) -> float:
    d = Path(p)
    return sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / 1024 / 1024 if d.exists() else 0.0


def build() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")  # noqa: DTZ005
    L = ["# 수집 데이터 집계", "",
         f"> `data/` 스캔 자동 생성. 최종 갱신: {now}", "",
         "재생성: `python -m src.collect.cli report`", "", "---", ""]

    # 공지
    notice_rows, tot_notice = [], 0
    for f in sorted(glob.glob("data/processed/notices/*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        site = Path(f).stem
        n = len(d["notices"]); tot_notice += n
        det = len(glob.glob(f"data/processed/notices/{site}/*.json"))
        att = _files(f"data/raw/notice_{site}/files")
        notice_rows.append(f"| {d['board']} | {n} | {det} | {att} |")

    # campuspick
    ext_rows, tot_ext = [], 0
    for f in sorted(glob.glob("data/processed/external/*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        n = d["count"]; tot_ext += n
        img = _files(f"data/raw/{Path(f).stem}/poster")
        ext_rows.append(f"| {d['source']} | {n} | {img} | {d.get('period_ended_count', 0)} |")

    # allcon
    allcon_rows, tot_allcon = [], 0
    for t in ("contest", "activity"):
        files = glob.glob(f"data/processed/allcon/{t}/*.json")
        n = sum(json.loads(Path(x).read_text(encoding="utf-8"))["count"] for x in files)
        tot_allcon += n
        img = _files(f"data/raw/allcon_{t}/poster")
        att = _files(f"data/raw/allcon_{t}/files")
        ended = sum(sum(1 for it in json.loads(Path(x).read_text(encoding="utf-8"))["items"]
                        if it.get("period_ended")) for x in files)
        allcon_rows.append(f"| allcon {t} | {n} | {len(files)}종 | {img} | {att} | {ended} |")

    # 로그인 필요
    tt = json.loads(Path("data/processed/timetable/timetable.json").read_text(encoding="utf-8"))["courses"] \
        if Path("data/processed/timetable/timetable.json").exists() else []
    syl = len(glob.glob("data/raw/syllabus/*.pdf"))

    imgs = len(glob.glob("data/raw/**/poster/*", recursive=True))
    atts = len(glob.glob("data/raw/**/files/*", recursive=True)) + syl
    raws = _files("data/raw")
    total = tot_notice + tot_ext + tot_allcon

    L += ["## 총량 요약", "",
          "| 구분 | 건수 |", "| --- | ---: |",
          f"| 공지 (4개 게시판) | **{tot_notice}** |",
          f"| campuspick (대외활동·공모전·교육·채용) | **{tot_ext}** |",
          f"| allcon (공모전·대외활동) | **{tot_allcon}** |",
          f"| **총 레코드** | **{total}** |",
          f"| 내 시간표 | {len(tt)}과목 |",
          f"| 내 강의계획서 PDF | {syl}개 |", "",
          "## 파일·용량", "",
          "| 항목 | 수 |", "| --- | ---: |",
          f"| 이미지(포스터·썸네일) | {imgs} |",
          f"| 첨부·PDF | {atts} |",
          f"| 원문·바이너리 파일 총 | {raws} |",
          f"| `data/` 전체 용량 | {_size_mb('data'):.1f}MB |", "",
          "---", "", "## 공지 (로그인 불필요)", "",
          "| 게시판 | 목록 | 상세 | 첨부 |", "| --- | ---: | ---: | ---: |",
          *notice_rows, "",
          "## 대외활동·공모전 (로그인 불필요)", "",
          "| campuspick | 건수 | 이미지 | 마감 |", "| --- | ---: | ---: | ---: |",
          *ext_rows, "",
          "| allcon | 건수 | 카테고리 | 포스터 | 첨부 | 마감 |",
          "| --- | ---: | ---: | ---: | ---: | ---: |",
          *allcon_rows, "",
          "## 로그인 필요 (내 학사)", "",
          f"- 시간표: {len(tt)}과목 (구조화)",
          f"- 강의계획서 PDF: {syl}개", "",
          "---", "", "## 세부사항 전부 받는 명령", "",
          "목록 전 페이지 + 상세(본문·첨부·이미지·PDF)를 **전량** 내려받습니다.", "",
          "```bash", "bash scripts/collect-full.sh            # 공개 사이트 전부",
          "bash scripts/collect-full.sh notices    # 공지만",
          "bash scripts/collect-full.sh allcon     # allcon만",
          "bash scripts/collect-full.sh external   # campuspick만", "```", "",
          "개별 명령으로도 됩니다:", "",
          "```bash",
          "# 공지 4곳 — 전 페이지 + 신규 전량 상세",
          "python -m src.collect.cli notices all --pages 100 --details 100000",
          "# 공모전·대외활동 — 스크롤 최대 + 상세 전량",
          "python -m src.collect.cli allcon contest  --scrolls 50 --details 100000",
          "python -m src.collect.cli allcon activity --scrolls 50 --details 100000",
          "# campuspick — 목록 + 대표 이미지",
          "python -m src.collect.cli external all --scrolls 30", "```", "",
          "> 상세는 항목마다 요청 간격(기본 1초)을 둬서 **공지 전량은 수십 분** 걸립니다.",
          "> 진행 상황은 옆 터미널에서 `python -m src.collect.cli monitor` 로 확인하세요.", "",
          "### 로그인 필요한 학사 데이터(시간표·강의계획서)", "",
          "세션이 만료되면 먼저 로그인부터 다시 합니다(브라우저 필요 → 로컬 실행).", "",
          "```bash",
          "python -m src.collect.cli weblogin   # 서버(noVNC) · 또는 로컬은 login",
          "python -m src.collect.cli collect-all", "```", ""]
    return "\n".join(L)


def run(out: str = "docs/수집-집계.md") -> Path:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build(), encoding="utf-8")
    return path
