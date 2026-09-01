# src/collect — 학사·공지·대외활동 수집 파이프라인

크롤링 관련 코드는 전부 이 패키지 안에 있고, **기능 1개 = 파일 1개** 로 나뉘어 있습니다.
전체 흐름은 `pipeline.py` 가 4단계로 묶어 실행합니다.

## 파이프라인 한눈에

```text
 [public]  로그인 불필요 (누구나 바로 실행 가능)
    notice.py      JNU 공지 게시판 4곳 (aisw/aicoss/nccoss/sojoong)
    external.py    캠퍼스픽 공모전·대외활동·교육·채용 (공개 API)
    allcon.py      올콘 공모전·대외활동 (+포스터·첨부 다운로드)
       │
 [auth]    본인 로그인 세션 필요 (cli login 먼저)
    sources/       수강내역·시간표·강의계획서·eClass 원문 수집
       │
 [parse]   구조화 (LLM 미사용, 결정적 파서)
    parse/         timetable 원문 → 구조화 JSON
       │
 [finalize]
    dedup.py       중복 저장 점검 → docs/중복-점검.md
    report.py      수집 집계 → docs/수집-집계.md
```

## 실행 방법

```bash
# 전체 파이프라인 (세션 없으면 auth 는 건너뛰고 안내만)
python -m src.collect.pipeline

# 단계 골라 실행
python -m src.collect.pipeline public             # 공개 수집만
python -m src.collect.pipeline public finalize    # 공개 수집 + 점검·집계
python -m src.collect.pipeline auth parse         # 본인 학사 데이터 + 구조화

# 같은 것을 cli 로도 실행 가능 (옵션 조절 가능)
python -m src.collect.cli pipeline public --pages 5 --details 20
```

개별 실행·로그인 등 세부 명령은 `python -m src.collect.cli --help` 와
[docs/크롤링-사용법.md](../../docs/크롤링-사용법.md) 를 보세요.

## 기능별 파일 지도

### 진입점

| 파일 | 기능 |
| --- | --- |
| `pipeline.py` | **4단계 파이프라인 실행** (public → auth → parse → finalize) |
| `cli.py` | 개별 명령 CLI (login/collect/notices/external/allcon/parse/pipeline/…) |

### 수집기 (무엇을 긁는가)

| 파일 | 기능 | 로그인 |
| --- | --- | --- |
| `notice.py` | JNU 공지 게시판 수집 (robots 준수, 전 페이지 순회) | 불필요 |
| `external.py` | 캠퍼스픽 공개 API — 공모전·대외활동·교육·채용 | 불필요 |
| `allcon.py` | 올콘 — 공모전·대외활동 + 상세 포스터/PDF | 불필요 |
| `sources/sugang_courses.py` | 수강내역 (sugang.jnu.ac.kr) | 필요 |
| `sources/timetable.py` | 시간표 (hakstd.jnu.ac.kr) | 필요 |
| `sources/syllabus.py` | 강의계획서 (hakstd.jnu.ac.kr) | 필요 |
| `sources/eclass.py` | eClass(Moodle) 대시보드·캘린더 .ics | 필요 |

### 인증·세션 (어떻게 로그인하는가)

| 파일 | 기능 |
| --- | --- |
| `session.py` | 브라우저 로그인 → 세션(쿠키) 저장·재사용. 비밀번호는 저장하지 않음 |
| `weblogin.py` | 헤드리스 서버용 웹 로그인 포털 (noVNC — 휴대폰 인증 대응) |
| `stdauth.py` | JNU StdAuth 재학인증 API (선택) |
| `certs.py` | 학교 사이트 TLS 인증서 체인 보정 |

### 공통 기반 (수집기가 딛고 서는 것)

| 파일 | 기능 |
| --- | --- |
| `base.py` | 수집기 템플릿 — 페이지 열기→항목 추출→저장→실행로그 공통 흐름 |
| `config.py` | 설정 — URL·간격·경로를 `.env` 에서 읽음 |
| `storage.py` | 원문 저장 + 중복 판별 (data/raw·meta·index) |
| `download.py` | 첨부·이미지 다운로드 |
| `dedup.py` | 저장 후 중복 전체 점검·격리 |
| `pii.py` | 개인정보 마스킹 |
| `runlog.py` | 소스별 실행 이력 기록 (data/runlog) |

### 후처리·관찰 (수집 후에 보는 것)

| 파일 | 기능 |
| --- | --- |
| `parse/timetable.py` | 시간표 원문 → 구조화 JSON (결정적 파서) |
| `monitor.py` | 실시간 수집 모니터 (옆 터미널에서 실행) |
| `report.py` | 수집 데이터 집계 리포트 생성 |

## 저장 위치 (전부 gitignored)

```text
data/
├── raw/<source>/       수집 원문
├── meta/<source>/      건별 메타데이터
├── index/<source>.jsonl  수집 인덱스 (중복 판별 키)
├── runlog/<source>.jsonl 실행 이력
├── processed/          구조화 결과 (parse·external)
└── sessions/           로그인 세션 쿠키 — 절대 공유 금지
```

저장 규칙·스키마 상세는 [docs/크롤링-매뉴얼.md](../../docs/크롤링-매뉴얼.md),
수집 현황은 [docs/수집-데이터-현황.md](../../docs/수집-데이터-현황.md) 참고.
