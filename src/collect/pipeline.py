"""수집 파이프라인 — 개별 수집기를 정해진 순서로 묶어 한 번에 실행한다.

  python -m src.collect.pipeline                  # 전체 (public → auth → parse → finalize)
  python -m src.collect.pipeline public           # 로그인 불필요한 공개 수집만
  python -m src.collect.pipeline public finalize  # 공개 수집 + 중복점검·집계
  python -m src.collect.pipeline auth parse       # 본인 학사 데이터 수집 + 구조화

단계(stage) 구성:

  public    로그인 불필요 — 공지(notice)·대외활동(external)·올콘(allcon)
  auth      본인 로그인 세션 필요 — 수강내역·시간표·강의계획서·eClass
            (세션이 없으면 이 단계는 건너뛰고 login 안내만 출력)
  parse     수집 원문 구조화 — 현재 timetable (LLM 미사용, 결정적 파서)
  finalize  중복 점검(dedup) + 수집 집계 리포트(report)

각 스텝은 실패해도 파이프라인을 멈추지 않는다(§4.4 — 조용히 실패하지 않되,
한 소스의 실패가 다른 소스 수집을 막지 않는다). 결과는 끝에 표로 요약한다.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

ALLCON_MAX_DETAIL = 30   # 올콘 상세·첨부 다운로드 상한 (details 옵션이 이보다 커도 여기서 자름)


@dataclass
class StepResult:
    step: str
    status: str          # ok | failed | skipped | login_required
    detail: str = ""


# ── 각 스텝 — 기존 모듈을 그대로 호출한다 ────────────────────
# 모든 스텝은 공통 설정(knobs)을 키워드로 받고, 안 쓰는 것은 **_ 로 흘린다.

def _run_notices(*, pages: int, details: int, **_) -> StepResult:
    from . import notice
    fails = []
    for key in notice.SOURCES:
        r = notice.collect(key, max_pages=pages, max_detail=details) or {}
        if r.get("status") not in (None, "ok"):
            fails.append(key)
    return StepResult("notices", "failed" if fails else "ok",
                      f"실패: {', '.join(fails)}" if fails else f"{len(notice.SOURCES)}개 사이트")


def _run_external(*, scrolls: int, **_) -> StepResult:
    from . import external
    fails = []
    for key in external.SOURCES:
        r = external.collect(key, scrolls=scrolls) or {}
        if r.get("status") != "ok":
            fails.append(key)
    return StepResult("external", "failed" if fails else "ok",
                      f"실패: {', '.join(fails)}" if fails else f"{len(external.SOURCES)}개 카테고리")


def _run_allcon(*, scrolls: int, details: int, **_) -> StepResult:
    from . import allcon
    fails = []
    for key in ("contest", "activity"):
        r = allcon.collect(key, scrolls=scrolls, max_detail=min(details, ALLCON_MAX_DETAIL)) or {}
        if r.get("status") != "ok":
            fails.append(key)
    return StepResult("allcon", "failed" if fails else "ok",
                      f"실패: {', '.join(fails)}" if fails else "contest·activity")


def _run_auth_sources(*, tag: str, **_) -> StepResult:
    from . import session
    from .sources import REGISTRY
    if not session.has_session():
        return StepResult("auth_sources", "login_required",
                          "세션 없음 — `python -m src.collect.cli login` 먼저")
    bad = []
    for name, cls in REGISTRY.items():
        r = cls().run(tag=tag) or {}
        if r.get("status") != "ok":
            bad.append(f"{name}({r.get('status')})")
    return StepResult("auth_sources", "failed" if bad else "ok",
                      ", ".join(bad) if bad else f"{len(REGISTRY)}개 소스")


def _run_parse(**_) -> StepResult:
    from .parse.timetable import parse_latest
    try:
        out = parse_latest()
    except FileNotFoundError:
        return StepResult("parse", "skipped", "파싱할 timetable 원문 없음 (auth 단계 먼저)")
    return StepResult("parse", "ok", str(out))


def _run_dedup(**_) -> StepResult:
    from . import dedup
    s = dedup.audit(fix=False, out="docs/중복-점검.md")
    return StepResult("dedup", "ok",
                      f"파일중복 {s['file_dup_groups']}그룹 · 내용중복 {s['record_dup_groups']}그룹")


def _run_report(**_) -> StepResult:
    from . import report
    path = report.run("docs/수집-집계.md")
    return StepResult("report", "ok", str(path))


# ── 파이프라인 정의: 단계 → 스텝 순서 ────────────────────────

PIPELINE: dict[str, list[Callable[..., StepResult]]] = {
    "public":   [_run_notices, _run_external, _run_allcon],
    "auth":     [_run_auth_sources],
    "parse":    [_run_parse],
    "finalize": [_run_dedup, _run_report],
}
STAGE_ORDER = tuple(PIPELINE)


def run_pipeline(
    stages: list[str] | None = None,
    *,
    tag: str = "service",
    pages: int = 100,      # notices: 순회 최대 페이지
    details: int = 200,    # notices: 상세 본문 수집 건수
    scrolls: int = 2,      # external·allcon: 스크롤 횟수
) -> list[StepResult]:
    """지정한 단계들을 STAGE_ORDER 순서로 실행하고 스텝별 결과를 반환한다."""
    want = set(stages or STAGE_ORDER)
    unknown = want - set(STAGE_ORDER)
    if unknown:
        raise SystemExit(f"알 수 없는 단계: {', '.join(sorted(unknown))} (가능: {', '.join(STAGE_ORDER)})")

    knobs = {"tag": tag, "pages": pages, "details": details, "scrolls": scrolls}
    results: list[StepResult] = []
    for stage in STAGE_ORDER:
        if stage not in want:
            continue
        print(f"\n━━ [{stage}] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        for fn in PIPELINE[stage]:
            try:
                res = fn(**knobs)
            except Exception as e:  # noqa: BLE001 — 한 스텝 실패가 파이프라인을 멈추지 않는다
                res = StepResult(fn.__name__.removeprefix("_run_"), "failed", repr(e))
                print(f"[{res.step}] 실패: {e!r}")
            results.append(res)

    icon = {"ok": "✅", "failed": "❌", "skipped": "⏭️ ", "login_required": "🔑"}
    print("\n━━ 파이프라인 결과 ━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for r in results:
        print(f"  {icon.get(r.status, '?')} {r.step:14} {r.status:15} {r.detail}")
    return results


def main() -> None:
    import sys
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return
    results = run_pipeline(args or None)
    if any(r.status == "failed" for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
