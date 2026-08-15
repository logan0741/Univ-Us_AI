"""수집 설정 — .env 에서 URL·간격·경로를 읽는다.

core_ai-agent 가 쓰는 것과 같은 pydantic-settings 패턴이다.
모델 슬롯을 코드에 박지 않듯, 수집 대상 URL 도 .env 로 뺀다.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class CollectSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── 수집 대상 (본인 로그인 필요) ──────────────────────────
    jnu_sugang_courses_url: str = "https://sugang.jnu.ac.kr/Pages/Suup080"
    jnu_timetable_url: str = "https://hakstd.jnu.ac.kr/web/Suup/Suup090"
    jnu_syllabus_url: str = "https://hakstd.jnu.ac.kr/web/Suup/Suup051"
    jnu_eclass_url: str = "https://sel.jnu.ac.kr/"

    # eClass(Moodle) 캘린더 .ics 내보내기 URL — 본인 계정에서 발급.
    # 사용법 문서 참고. 비어 있으면 eclass 는 대시보드 HTML 만 저장한다.
    jnu_eclass_ics_url: str = ""

    # 로그인 시작 페이지 — 세션이 없을 때 이 URL 을 먼저 연다.
    jnu_login_start_url: str = "https://hakstd.jnu.ac.kr/"

    # ── 예의(§4.2·§6): 요청 간격 ──────────────────────────────
    jnu_collect_min_interval_sec: float = 3.0
    jnu_page_timeout_ms: int = 30000

    # ── StdAuth 재학인증 (선택) ───────────────────────────────
    jnu_stdauth_base_url: str = "https://jnuapi.jnu.ac.kr"
    jnu_stdauth_apikey: str = ""

    # ── 저장 경로 (전부 data/ 아래 = gitignored) ──────────────
    data_dir: Path = Path("data")

    @property
    def session_path(self) -> Path:
        return self.data_dir / "sessions" / "jnu_storage_state.json"

    def raw_dir(self, source: str) -> Path:
        return self.data_dir / "raw" / source

    def meta_dir(self, source: str) -> Path:
        return self.data_dir / "meta" / source

    def index_path(self, source: str) -> Path:
        return self.data_dir / "index" / f"{source}.jsonl"

    def runlog_path(self, source: str) -> Path:
        return self.data_dir / "runlog" / f"{source}.jsonl"

    def url_for(self, source: str) -> str:
        return {
            "sugang_courses": self.jnu_sugang_courses_url,
            "timetable": self.jnu_timetable_url,
            "syllabus": self.jnu_syllabus_url,
            "eclass": self.jnu_eclass_url,
        }[source]


settings = CollectSettings()

SOURCES = ("sugang_courses", "timetable", "syllabus", "eclass")
