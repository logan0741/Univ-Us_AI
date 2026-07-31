# Univ-Us_AI

인공지능혁신융합사업단 WE-Meet 프로젝트 **Output** 팀의 Univ-Us 프로젝트 「캠퍼스메이트(CampusMate)」에서
**AI 에이전트 부분**을 개발하는 저장소입니다.

> 원본 프로젝트 계획서는 개인정보가 포함되어 있어 저장소에 두지 않습니다. 팀 채널에서 받으세요.

---

## 목차

1. [이 저장소의 범위](#1-이-저장소의-범위)
2. [기능 분해와 담당 브랜치](#2-기능-분해와-담당-브랜치)
3. [개발 환경 설치](#3-개발-환경-설치)
4. [브랜치 생성 규칙](#4-브랜치-생성-규칙)
5. [커밋 메시지 작성법](#5-커밋-메시지-작성법)
6. [이슈 처리 규칙 (카카오톡 + GitHub Issue)](#6-이슈-처리-규칙-카카오톡--github-issue)
7. [PR(Pull Request) 규칙](#7-prpull-request-규칙)
8. [디렉터리 구조](#8-디렉터리-구조)
9. [자주 막히는 지점](#9-자주-막히는-지점)

---

## 1. 이 저장소의 범위

### 여기서 개발하는 것

계획서 4.3의 **AI 계층 전체** — 문서 이해, 구조화 추출, RAG, 도구 호출, 능동 브리핑, 그리고 정확성이 필요한 규칙 기반 계산.

### 여기서 개발하지 않는 것

| 항목 | 담당 |
| --- | --- |
| Next.js 대시보드·대화 UI | 프론트엔드 저장소 |
| FastAPI REST API, 인증, OAuth 연동 | 백엔드 저장소 |
| F15 주변 맛집 추천 (지도 API 중심) | 백엔드 저장소 |
| F17 사업단 프로젝트 관리 플랫폼 (승인 워크플로) | 백엔드 저장소 |

이 저장소는 **"입력을 주면 검증된 결과를 돌려주는 AI 모듈"** 을 만듭니다.
HTTP 엔드포인트로 감싸는 일은 백엔드 저장소에서 합니다. 우리는 **호출 가능한 함수와 스키마**까지 책임집니다.

---

## 2. 기능 분해와 담당 브랜치

계획서의 17개 기능(F1~F17)을 **9개 AI 기능**으로 재편했습니다. 기능마다 메인 브랜치가 1개씩 있습니다.

| 기능 메인 브랜치 | 대응 | 하는 일 |
| --- | --- | --- |
| `core_ai-agent` | 4.3 나·라 | LLM 호출 추상화, 프롬프트 버전 관리, 응답 캐싱, 토큰 사용량 로깅, 재시도 |
| `doc_ai-agent` | F1, F6 | 텍스트 문서(강의계획서 PDF·공지·메일) → 일정 JSON 구조화 추출 |
| `pic_ai-agent` | F1, F6 | 사진·스캔 이미지(시간표 사진, 스캔 강의계획서, 필기) 분석 → 텍스트·표 구조 추출 |
| `rag_ai-agent` | F4 | 강의자료 청킹·색인·검색, 출처 페이지를 붙인 요약·시험 예상 문제 생성 |
| `brief_ai-agent` | F10 | 아침 브리핑 텍스트 생성 + 스케줄 실행 |
| `chat_ai-agent` | F9 | 자연어 입력 → 도구 호출(Function Calling) → 자연어 응답 |
| `notice_ai-agent` | F11~F13 | 공지 수집, 자격 요건 구조화 추출, 사용자 프로필 매칭 |
| `rule_ai-agent` | F2·F3·F5·F7·F8·F14·F16 | **LLM을 쓰지 않는** 결정적 계산 (졸업요건, 출결 한도, 우선순위 점수, 학습 블록, 시간표 제약, 공강 교집합) |
| `eval_ai-agent` | 4.6 | 테스트셋 구축, 정확도·근거표기율·응답시간 측정, **모델 비교 실험으로 사용 모델 확정** |

기능별 MVP 상세(입력 / 출력 / 완료 기준)는 **[docs/AI_MODULES.md](docs/AI_MODULES.md)** 에 있습니다.
작업 시작 전에 자기 기능 항목을 먼저 읽으세요.

### 사용할 AI 모델은 아직 정하지 않았습니다

계획서 4.3 나의 원칙 — *"LLM 호출부는 OpenAI 호환 인터페이스로 추상화하여 특정 모델에 종속되지 않는 구조로 설계한다"* — 을 그대로 따릅니다.

그래서 코드에는 **모델 이름을 직접 쓰지 않고 "슬롯 이름"만 씁니다.**

| 슬롯 | 역할 | 요구 조건 |
| --- | --- | --- |
| `LLM_MAIN` | 판단·생성·구조화 추출 | JSON 구조화 출력, Function Calling 지원 |
| `DOC_PARSER` | 문서 레이아웃·표 인식 | PDF·이미지 → 텍스트 + 표 구조 |
| `VISION` | 이미지 이해 | `pic_ai-agent` 전용. `DOC_PARSER`로 충분하면 안 씀 |
| `EMBEDDING` | 청크 벡터화 | 한국어 문서 검색 품질 |
| `RULE` | 결정적 계산 | 모델이 아님. 순수 Python |

```python
# ✅ 이렇게
model = settings.LLM_MAIN_MODEL

# ❌ 이렇게 하지 마세요 — 모델을 바꿀 때 전 파일을 고쳐야 합니다
model = "solar-pro-3"
```

실제 어떤 모델을 쓸지는 `eval_ai-agent`의 비교 실험 결과로 정합니다.
정해지면 `.env`와 `requirements.txt`만 바뀌고 나머지 코드는 그대로 갑니다.

---

## 3. 개발 환경 설치

> ### GPU는 필수가 아닙니다
> 주 경로는 **외부 API 호출 기반**이라 CPU만으로 거의 모든 기능을 개발할 수 있습니다.
> GPU는 로컬 임베딩·로컬 OCR·모델 비교 실험(`eval_ai-agent`, `pic_ai-agent`)에서만 씁니다.
> **CUDA 설치가 안 되면 그냥 건너뛰고 3-1까지만 하고 개발을 시작하세요.**

### 3-1. 공통 설치 (전원 필수)

```bash
# 1) 저장소 클론
git clone https://github.com/logan0741/Univ-Us_AI.git
cd Univ-Us_AI

# 2) 프로젝트 전용 conda 환경 생성
conda create -n univus-ai python=3.11 -y
conda activate univus-ai

# 3) 패키지 설치
pip install -r requirements.txt -r requirements-dev.txt

# 4) 환경변수 파일 준비 (.env 는 절대 커밋하지 않습니다)
cp .env.example .env

# 5) 커밋 메시지 템플릿 등록 (저장소당 1회)
git config commit.template .gitmessage

# 6) 내 정보 등록 — 이걸 안 하면 git commit 이 실패합니다
#    이메일은 GitHub 계정에 등록된 것과 같아야 커밋이 내 프로필에 연결됩니다
git config user.name "본인 GitHub 사용자명"
git config user.email "본인 GitHub 계정 이메일"
```

**`conda activate univus-ai` 이후 터미널 프롬프트 맨 앞이 `(univus-ai)` 로 바뀌었는지 확인하세요.**
`(base)` 상태로 설치하면 안 됩니다.

> #### base 환경에 설치하지 마세요
> conda의 `base`는 conda 자기 자신이 쓰는 환경입니다. 여기에 프로젝트 패키지를 깔면
> 다른 프로젝트와 버전이 충돌하고, 한 번 꼬이면 conda를 통째로 다시 설치해야 합니다.
> **프로젝트마다 환경을 따로 만드는 것이 원칙입니다.**

설치가 됐는지 확인:

```bash
python -c "import fastapi, pydantic, apscheduler, pypdf; print('설치 완료')"
```

<details>
<summary>conda 대신 venv를 쓰고 싶다면</summary>

```bash
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
```

`environment.yml` 대신 `requirements*.txt`만 쓰면 되고, 나머지 규칙은 동일합니다.
</details>

<details>
<summary>environment.yml 로 한 번에 만들기</summary>

```bash
conda env create -f environment.yml
conda activate univus-ai
```

`requirements.txt` + `requirements-dev.txt`가 함께 설치됩니다.
</details>

### 3-2. GPU / CUDA 설치 (NVIDIA 그래픽카드 있는 사람만)

#### 먼저 알아둘 것

- **CUDA Toolkit을 따로 설치할 필요가 없습니다.** PyTorch 휠(wheel) 안에 CUDA 런타임이 들어 있습니다.
  필요한 건 **NVIDIA 그래픽 드라이버 하나**뿐입니다.
- `nvidia-smi`에 표시되는 CUDA 버전이 설치할 PyTorch의 CUDA 버전보다 **높아도 정상**입니다. 하위 호환됩니다.
- **Windows에서는 `pip install torch` 만 하면 CPU 전용이 깔립니다.**
  기본 PyPI의 Windows용 torch에는 CUDA가 들어 있지 않습니다(Linux용에는 들어 있습니다).
  그래서 `requirements-gpu.txt` 맨 위에 PyTorch 전용 저장소 주소가 들어 있습니다. **그 줄을 지우지 마세요.**
- **WSL2 사용자**: 드라이버는 **Windows 쪽에만** 설치합니다. WSL 안에서 `apt install nvidia-driver-...` 를 하면 오히려 깨집니다.

#### 설치

```bash
# 1) 드라이버 확인 — 표가 뜨고 우측 상단 CUDA Version 이 12.x 이상이면 OK
nvidia-smi

# 2) PyTorch + GPU 패키지 설치 (CUDA 12.9 휠 기준, 약 3GB)
pip install -r requirements-gpu.txt

# 3) 검증 — True 가 나와야 합니다
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

`nvidia-smi`가 명령을 찾지 못하면 → NVIDIA GPU가 없거나 드라이버가 없는 것입니다. **3-2를 건너뛰세요.**

#### CUDA 버전이 안 맞을 때

`requirements-gpu.txt` 첫 줄의 `cu129` 부분만 바꿉니다.

| 상황 | 값 |
| --- | --- |
| 대부분의 경우 | `cu129` (기본값) |
| `nvidia-smi` 의 CUDA Version 이 13.x | `cu130` |
| 드라이버가 오래되어 위 둘 다 안 될 때 | `cu126` |

바꿔서 해결됐다면 **어떤 값을 썼는지 이슈로 남겨주세요.** 같은 그래픽카드를 쓰는 팀원이 바로 씁니다.
최신 설치 명령은 <https://pytorch.org/get-started/locally/> 에서도 확인할 수 있습니다.

---

## 4. 브랜치 생성 규칙

### 브랜치 구조

```text
main                              배포/제출 기준. 직접 커밋 금지
└── develop                       통합·데모 브랜치
    ├── pic_ai-agent              ← 기능 메인 브랜치 (이름 없음)
    │   ├── pic_ai-agent_<영문이름>    ← 개인 작업 브랜치
    │   └── pic_ai-agent_<영문이름>
    ├── doc_ai-agent
    │   └── doc_ai-agent_<영문이름>
    └── ...
```

### 이름 규칙

```text
기능 메인 브랜치    <기능약어>_ai-agent
개인 작업 브랜치    <기능약어>_ai-agent_<영문이름>
```

| 예시 | 뜻 |
| --- | --- |
| `pic_ai-agent` | 사진 분석 기능의 메인 브랜치 |
| `pic_ai-agent_myname` | `myname` 이 사진 분석 기능에서 작업하는 브랜치 |
| `rag_ai-agent_myname` | `myname` 이 RAG 기능에서 작업하는 브랜치 |

**지켜야 할 것**

- 구분자는 두 종류만 씁니다. **`_` 는 덩어리 구분**(기능 / ai-agent / 이름), **`-` 는 단어 구분**(ai-agent).
- **공백은 절대 쓸 수 없습니다.** git이 브랜치 이름으로 받지 않습니다.

  ```text
  $ git check-ref-format --branch "pic_ai agent_myname"
  fatal: 'pic_ai agent_myname' is not a valid branch name
  ```

- 대문자·한글·마침표(`.`)를 쓰지 않습니다. 전부 **영문 소문자**입니다.
- 기능 메인 브랜치는 **팀에서 1개만** 만듭니다. 개인이 새로 만들지 않습니다.
- 개인 브랜치는 **반드시 자기 기능 메인 브랜치에서 분기**합니다. `main`이나 `develop`에서 직접 따지 않습니다.

### `<영문이름>` 부분을 정하는 법

- **GitHub 사용자명을 쓰는 것을 권장합니다.** 중복이 없고, 브랜치 주인이 PR 작성자와 정확히 일치해 추적이 쉽습니다.
- 로마자 이름을 쓴다면 **한 사람이 항상 같은 표기**를 씁니다.
  중간에 표기를 바꾸면 브랜치 목록에서 자기 브랜치를 찾기 어려워집니다.
- 성·이름 순서와 붙여쓰기 방식은 팀에서 하나로 정해 씁니다.
- 새로 합류하면 **자기 표기를 정해 이슈로 한 번 공유한 뒤** 쓰기 시작합니다.

### 작업 시작할 때 (복붙용)

아래는 `pic` 기능에서 작업하는 예시입니다. `pic` 과 `myname` 을 자기 기능약어·이름으로 바꿔 쓰세요.

```bash
# 1) 기능 메인 브랜치를 최신 상태로 받아오기
git fetch origin
git switch pic_ai-agent
git pull origin pic_ai-agent

# 2) 내 작업 브랜치 만들기
git switch -c pic_ai-agent_myname

# 3) 작업 후 커밋 (5장 참고)
git add .
git commit

# 4) 원격에 올리기 (처음 한 번만 -u)
git push -u origin pic_ai-agent_myname
```

작업 도중 기능 메인 브랜치가 업데이트됐다면, PR 올리기 전에 최신 내용을 가져옵니다.

```bash
git fetch origin
git merge origin/pic_ai-agent
# 충돌이 나면 해결 후 git add → git commit
```

### 브랜치를 지우는 시점

PR이 병합되면 **개인 작업 브랜치는 지웁니다.** 기능 메인 브랜치는 프로젝트가 끝날 때까지 유지합니다.

```bash
git switch pic_ai-agent
git branch -d pic_ai-agent_myname          # 로컬 삭제
git push origin --delete pic_ai-agent_myname  # 원격 삭제
```

---

## 5. 커밋 메시지 작성법

커밋 메시지는 **제목 한 줄 + 세 개 항목**으로 씁니다.

```text
[<기능약어>] 한 줄 요약

## 변경사항
- 기존에 있던 것 중 무엇을 고쳤는지

## 추가 개발 내용
- 이번에 새로 만든 것

## 앞으로 진행 방향
- 다음에 무엇을 할 것인지

Issue: #12
```

### 실제 예시

```text
[doc] 강의계획서 마감일 추출 스키마 v1 구현

## 변경사항
- 날짜 파서가 "6/12(목)" 형식을 못 읽던 문제 수정
- 추출 프롬프트에서 출처 문장을 반드시 반환하도록 지시 추가

## 추가 개발 내용
- ScheduleItem Pydantic 스키마 정의 (과목/유형/제목/마감일시/비중/출처문장)
- 추출 결과 검증 로직 추가 (날짜 유효성, 동일 과제 중복 제거)
- 샘플 강의계획서 3건으로 동작 확인

## 앞으로 진행 방향
- 표 형태 강의계획서에서 추출률이 낮음 → DOC_PARSER 표 인식 결과를 붙여 재시도
- 테스트셋 10건 라벨링해서 정확도 측정 (eval 기능과 협의 필요)

Issue: #12
```

### 규칙

- **제목**은 50자 이내, 마침표 없이, `[기능약어]`로 시작합니다. (`[doc]` `[pic]` `[rag]` `[brief]` `[chat]` `[notice]` `[rule]` `[eval]` `[core]` `[docs]` `[chore]`)
- **세 항목은 지우지 않습니다.** 해당 없으면 `- 없음` 이라고 적습니다.
  → "이번엔 변경사항이 없었다"는 것도 정보입니다. 항목을 지우면 다음 사람이 빠뜨린 건지 없었던 건지 알 수 없습니다.
- **"앞으로 진행 방향"이 이 규칙의 핵심입니다.** 며칠 뒤 다시 붙을 때, 그리고 다른 사람이 이어받을 때
  마지막 커밋만 보면 어디서부터 하면 되는지 알 수 있어야 합니다.
- 관련 이슈가 있으면 마지막 줄에 `Issue: #번호` 를 적습니다.

### 템플릿 자동으로 띄우기

아래를 저장소당 한 번만 실행하면, `git commit` 할 때 에디터에 위 양식이 자동으로 채워집니다.

```bash
git config commit.template .gitmessage
```

이후에는 `-m` 옵션 **없이** 커밋합니다.

```bash
git commit        # ✅ 템플릿이 뜹니다
git commit -m "수정"   # ❌ 템플릿이 무시됩니다
```

### 커밋 단위

- **한 커밋에 한 가지 일**만 담습니다. "이것저것 수정" 같은 커밋은 나중에 되돌릴 수 없습니다.
- 하루 작업을 마지막에 한 번에 몰아 커밋하지 않습니다. 기능 하나가 동작하면 그때 커밋합니다.
- **`.env`, 개인 데이터, API 키가 들어갔는지 커밋 전에 확인합니다.** `git status`로 올라가는 파일 목록을 눈으로 봅니다.

---

## 6. 이슈 처리 규칙 (카카오톡 + GitHub Issue)

막히는 게 생기면 **카카오톡으로 묻고, GitHub Issue에도 남깁니다. 둘 다 합니다.**

```text
1. 카카오톡 팀 채널에 질문한다.            ← 빠르게 답을 받기 위해
2. 같은 내용을 GitHub Issue 로 등록한다.    ← 기록을 남기기 위해
3. 카톡에서 답을 받으면 그 답을 Issue 코멘트로 옮겨 적는다.
4. 해결되면 "어떻게 해결했는지"를 코멘트로 남기고 Issue 를 close 한다.
5. 관련 커밋 메시지 마지막 줄에 Issue: #번호 를 적는다.
```

### 왜 두 번 적나요

카카오톡은 **검색이 안 되고 스크롤에 묻힙니다.** 지금 해결한 문제를 두 달 뒤에 다른 사람이 똑같이 겪고,
그때는 아무도 그 대화를 못 찾습니다. 실제로 팀 프로젝트에서 같은 질문이 반복되는 이유가 이것입니다.

계획서 6.2 나에도 *"결정 사항은 문서로 기록"* 이 협업 원칙으로 들어가 있습니다. 이 규칙은 그걸 실행하는 방법입니다.

**Issue 하나를 남기는 데 2분 걸리고, 같은 문제를 두 번째 사람이 다시 푸는 데는 반나절이 걸립니다.**

### Issue 종류

저장소의 [New Issue] 버튼을 누르면 템플릿 3개가 나옵니다.

| 템플릿 | 언제 |
| --- | --- |
| **질문 / 막힌 것** | 카톡에 물어본 내용을 기록할 때. 환경 설치 실패, 에러, 방향 판단이 안 설 때 |
| **작업(Task)** | 기능 개발 단위를 등록할 때. 스프린트 백로그가 됩니다 |
| **버그** | 동작하던 게 깨졌을 때 |

### 질문 Issue에 꼭 넣을 것

- 무엇을 하려던 중이었는지
- **실행한 명령어 원문**
- **에러 메시지 전문** (요약하지 말고 그대로 복사)
- 이미 시도해 본 것
- 카톡에 질문한 시각 (대화를 다시 찾을 수 있게)

에러 메시지를 "그냥 안 돼요"로 줄이면 답을 줄 수 없습니다. **터미널 출력을 통째로 붙여 넣으세요.**

### 라벨

| 라벨 | 뜻 |
| --- | --- |
| `question` | 질문 |
| `bug` | 버그 |
| `task` | 작업 단위 |
| `env` | 환경·설치 문제 |
| `blocked` | 이것 때문에 진행이 멈춤 — **우선 처리** |
| `pic` `doc` `rag` `brief` `chat` `notice` `rule` `eval` `core` | 해당 기능 |

`blocked` 라벨이 붙은 이슈는 팀 회의에서 먼저 다룹니다. **막혔으면 혼자 하루 이상 붙잡지 말고 이 라벨을 붙이세요.**

---

## 7. PR(Pull Request) 규칙

```text
개인 작업 브랜치  →  기능 메인 브랜치  →  develop  →  main
```

- 개인 브랜치를 `develop`이나 `main`으로 **직접 PR하지 않습니다.** 반드시 자기 기능 메인 브랜치로 보냅니다.
- PR 본문은 커밋과 같은 3단 구조(`변경사항` / `추가 개발 내용` / `앞으로 진행 방향`)로 씁니다. 템플릿이 자동으로 뜹니다.
- **리뷰어를 최소 1명 지정**합니다. 자기 PR을 자기가 병합하지 않습니다.
- 리뷰는 "잘못 찾기"가 아니라 **"내가 이 코드를 이어받을 수 있는가"** 를 보는 것입니다.
  이해가 안 되는 부분이 있으면 그대로 질문으로 남기면 됩니다.
- PR 크기는 작게 유지합니다. 파일 20개짜리 PR은 아무도 제대로 리뷰하지 못합니다.

### PR 올리기 전 체크

```bash
ruff check .          # 코드 스타일 검사
pytest                # 테스트 (테스트가 있는 기능만)
git status            # .env / 개인 데이터가 섞이지 않았는지 눈으로 확인
```

---

## 8. 디렉터리 구조

9개 기능이 동시에 진행되므로, **각자 자기 폴더 안에서만 작업**해서 충돌을 구조적으로 줄입니다.

```text
Univ-Us_AI/
├── src/
│   ├── core/          공통 LLM 호출·설정·로깅        (core_ai-agent)
│   ├── doc/           문서 → 일정 추출              (doc_ai-agent)
│   ├── pic/           이미지 분석                   (pic_ai-agent)
│   ├── rag/           강의자료 RAG                  (rag_ai-agent)
│   ├── brief/         아침 브리핑                   (brief_ai-agent)
│   ├── chat/          대화형 에이전트               (chat_ai-agent)
│   ├── notice/        공지 수집·매칭                (notice_ai-agent)
│   ├── rule/          규칙 기반 계산                (rule_ai-agent)
│   ├── eval/          평가·모델 비교                (eval_ai-agent)
│   └── schemas/       기능 간 공유 Pydantic 스키마   ⚠️ 공용
├── prompts/           프롬프트 (버전 관리 대상)
├── tests/             테스트
├── data/              샘플·테스트셋              🚫 git에 올라가지 않음
├── docs/
│   └── AI_MODULES.md  기능별 MVP 상세
├── requirements.txt
├── requirements-dev.txt
├── requirements-gpu.txt
├── environment.yml
├── .env.example
└── .gitmessage
```

### ⚠️ `src/core/` 와 `src/schemas/` 는 공용입니다

여러 기능이 같이 씁니다. 여기를 고치면 **다른 사람 코드가 조용히 깨집니다.**
수정이 필요하면 **먼저 Issue를 열어 공유하고 합의한 뒤에** 고칩니다.

### 프롬프트는 코드처럼 관리합니다

계획서 4.3 라 원칙 — 프롬프트를 코드 안에 문자열로 박아두지 말고 `prompts/` 아래 파일로 두고 버전 관리합니다.
프롬프트를 바꿨으면 **테스트셋 정확도가 좋아졌을 때만** 반영하고, 커밋 메시지에 수치 변화를 적습니다.

### `data/` 폴더

팀원 개인의 강의계획서·이수내역·메일이 들어가는 곳이라 **git에 올라가지 않도록 막아두었습니다**(`.gitignore`).
개인정보가 포함된 데이터는 본인 동의 하에서만 사용하고 외부에 공개하지 않습니다 (계획서 4.2).

---

## 9. 자주 막히는 지점

| 증상 | 원인과 해결 |
| --- | --- |
| `fatal: 'xxx' is not a valid branch name` | 브랜치 이름에 **공백**이 들어갔습니다. `_`와 `-`만 씁니다 → [4장](#4-브랜치-생성-규칙) |
| `git commit` 해도 템플릿이 안 뜸 | `git config commit.template .gitmessage` 를 실행하지 않았거나, `-m` 옵션을 썼습니다 |
| `ModuleNotFoundError` | conda 환경을 켜지 않았습니다. 프롬프트에 `(univus-ai)` 가 보이는지 확인하세요 |
| `pip install` 이 `(base)` 에서 실행됨 | `conda activate univus-ai` 를 먼저 합니다. base에 설치된 건 `pip uninstall` 로 정리하세요 |
| `torch.cuda.is_available()` 이 `False` | ① `nvidia-smi` 가 되는지 확인 ② CPU용 torch가 먼저 깔렸을 수 있음 → `pip uninstall torch torchvision -y` 후 `pip install -r requirements-gpu.txt` 재실행 |
| `nvidia-smi: command not found` | NVIDIA GPU가 없거나 드라이버 미설치입니다. **GPU 없이 개발 가능합니다.** [3-1](#3-1-공통-설치-전원-필수)까지만 하세요 |
| 실수로 `.env` 를 커밋함 | **즉시 팀에 알리고 API 키를 재발급받으세요.** 커밋을 지워도 기록은 남습니다 |
| `main`에 직접 커밋함 | 병합하지 말고 이슈로 공유하세요. 되돌리는 걸 같이 처리합니다 |

여기에 없는 문제는 **[6장](#6-이슈-처리-규칙-카카오톡--github-issue) 규칙대로** 카톡 + Issue로 남겨주세요.
반복되는 문제는 이 표에 추가됩니다.
