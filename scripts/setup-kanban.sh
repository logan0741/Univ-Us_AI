#!/usr/bin/env bash
# ============================================================
# Univ-Us_AI 칸반 보드 초기 세팅
#
#   1) README 규칙에 맞는 라벨 생성
#   2) 1차 개발(~9/14) 백로그 이슈 생성
#   3) (선택) 생성한 이슈를 GitHub Project 에 카드로 추가
#
# 사전 준비
#   gh auth login              ← GitHub CLI 로그인 (한 번만)
#   gh auth refresh -s project ← 보드에 카드를 넣으려면 필수. 기본 로그인엔 없는 권한입니다
#
# gh 설치가 안 돼 있으면 → docs/서버-작업환경-설정.md 5장
#
# 실행
#   bash scripts/setup-kanban.sh              라벨 + 이슈만
#   bash scripts/setup-kanban.sh 1            + 프로젝트 1번 보드에 카드 추가
#
# 프로젝트 번호는 보드 URL 끝에 있습니다.
#   https://github.com/users/logan0741/projects/1  →  1
#
# 실행 전 목록을 보여주고 확인을 받습니다. 실수로 다 만들어지지 않습니다.
# ============================================================
set -euo pipefail

REPO="logan0741/Univ-Us_AI"
OWNER="logan0741"
PROJECT_NUMBER="${1:-}"

DOC_PLAN="docs/DEV_PLAN.md"
DOC_MOD="docs/AI_MODULES.md"

# ── 사전 확인 ───────────────────────────────────────────────
command -v gh >/dev/null 2>&1 || {
    echo "gh CLI 가 없습니다. https://cli.github.com 에서 설치하세요."
    exit 1
}
gh auth status >/dev/null 2>&1 || {
    echo "GitHub 로그인이 안 되어 있습니다.  gh auth login  을 먼저 실행하세요."
    exit 1
}

# 프로젝트에 카드를 넣으려면 project 권한이 따로 필요합니다.
# 이게 없으면 이슈는 만들어지는데 카드만 조용히 실패해서, 먼저 막아둡니다.
if [ -n "$PROJECT_NUMBER" ] && ! gh auth status 2>&1 | grep -q "project"; then
    echo "GitHub 토큰에 'project' 권한이 없습니다."
    echo "이대로 진행하면 이슈는 생성되지만 보드에 카드가 추가되지 않습니다."
    echo
    echo "  gh auth refresh -s project"
    echo
    echo "를 실행한 뒤 다시 시도하세요. (권한 없이 이슈만 만들려면 인자 없이 실행)"
    exit 1
fi

# ── 라벨 정의 (README 6장) ──────────────────────────────────
# 이름|색상|설명
LABELS=(
    "task|1d76db|작업 단위. 스프린트 백로그가 됩니다"
    "env|c2e0c6|환경·설치 문제"
    "blocked|b60205|이것 때문에 진행이 멈춤 — 우선 처리"
    "core|5319e7|공통 LLM 호출 계층"
    "doc|0e8a16|문서 → 일정 추출"
    "pic|fbca04|사진·이미지 분석"
    "rag|006b75|강의자료 RAG"
    "brief|bfd4f2|아침 브리핑"
    "chat|d4c5f9|대화형 에이전트"
    "notice|f9d0c4|공지 수집·매칭"
    "rule|c5def5|규칙 기반 계산"
    "eval|e99695|평가·모델 비교"
)

# ── 이슈 정의 ───────────────────────────────────────────────
# 담당|라벨|제목|예상|완료 기준(줄바꿈은 ;)
ISSUES=(
"공통|task|[작업] 공통 — 추출 출력 스키마 확정 (pic ↔ doc)|2일|\
pic 과 doc 이 같은 필드·타입·필수 여부를 쓴다;\
신뢰도 값의 범위와 의미가 정해져 있다;\
확정한 형태를 이슈 코멘트로 공유했다;\
src/schemas/ 에 파일로 들어가 있다"

"공통|task|[작업] 공통 — 각자 <영문이름> 브랜치 표기 확정|1일|\
세 명의 표기를 이슈에 적어 공유했다;\
각자 자기 기능 메인 브랜치에서 개인 브랜치를 만들었다"

"공통|task|[작업] 공통 — docs/plans/ 세부 계획서 작성|2일|\
_TEMPLATE.md 를 복사해 자기 파일을 만들었다;\
1~4장(만들 것·입출력·완료 기준·기술 선택)이 채워져 있다;\
PR 로 올렸다"

"김건희|task,core|[작업] core — LLM 호출 계층 골격|3일|\
.env 슬롯 설정을 읽어 LLM 을 호출한다;\
프롬프트와 기대 스키마를 넘기면 검증된 객체가 나온다;\
다른 기능 담당자가 README 만 보고 호출할 수 있다"

"김건희|task,core|[작업] core — 스키마 검증 실패 시 재시도|2일|\
스키마에 안 맞는 JSON 이 오면 자동 재시도한다;\
계속 실패하면 명확한 예외를 던진다;\
재시도 횟수가 설정으로 조절된다"

"김건희|task,core|[작업] core — 토큰 사용량 로깅|1일|\
호출마다 입력·출력 토큰 수가 로그에 남는다;\
어느 기능이 얼마나 썼는지 구분된다"

"김건희|task,core|[작업] core — 응답 캐싱|2일|\
같은 입력을 다시 넣으면 캐시에서 반환한다;\
캐시를 끄는 방법이 있다"

"김건희|task,core|[작업] core — 프롬프트를 prompts/ 파일로 분리|1일|\
코드 안에 프롬프트 문자열이 없다;\
prompts/ 아래 파일로 있고 버전이 구분된다"

"김건희|task,core|[작업] core — 프로바이더 2종으로 같은 호출 성공|2일|\
.env 슬롯 설정만 바꿔서 서로 다른 프로바이더 2개로 같은 호출이 성공한다;\
코드는 한 줄도 안 고쳤다"

"김건희|task,doc|[작업] doc — PDF 텍스트 추출 → 구조화 JSON|3일|\
텍스트 기반 강의계획서 PDF 에서 텍스트를 뽑는다;\
LLM_MAIN 에 스키마를 지정해 JSON 을 받는다;\
결과를 Pydantic 으로 검증한다"

"김건희|task,doc|[작업] doc — 날짜 검증|2일|\
2월 30일 같은 존재하지 않는 날짜를 걸러낸다;\
학기 범위 밖 날짜를 걸러낸다;\
6/12(목) 23:59 · 6월 12일 형식을 읽는다"

"김건희|task,doc|[작업] doc — 중복 검증|1일|\
같은 과제가 두 번 잡히면 하나로 합친다;\
합친 근거가 남는다"

"김건희|task,doc|[작업] doc — 모든 항목에 출처문장 붙이기|2일|\
추출된 항목마다 원문 어디서 나왔는지 문장이 붙는다;\
출처문장이 없으면 결과에 포함하지 않는다"

"김건희|task,doc|[작업] doc — 저신뢰 항목 확인 필요 분리|2일|\
확신이 낮은 항목은 자동 등록하지 않는다;\
확인 필요 목록으로 따로 나온다;\
분리 기준이 문서로 설명돼 있다"

"김건희|task,doc|[작업] doc — 샘플 강의계획서 5건 수동 검수|2일|\
샘플 5건에서 마감일이 수동 검수 결과와 일치한다;\
틀린 건은 원인이 기록돼 있다"

"김건희|task,chat|[작업] chat — 도구 3개 정의·등록|2일|\
일정 등록 · 마감 조회 · 우선순위 조회 를 정의했다;\
함수 이름·파라미터·읽기/쓰기 구분이 정해졌다"

"김건희|task,chat|[작업] chat — 도구 선택과 인자 채우기|3일|\
문장을 넣으면 맞는 도구가 선택되고 인자가 채워진다;\
어느 도구에도 해당 없으면 할 수 없다고 답한다;\
상대 날짜(다음 주 목요일·내일)를 해석한다"

"김건희|task,chat|[작업] chat — 쓰기 작업 사전 확인 게이트|2일|\
등록·수정·삭제는 실행 전 사용자 확인을 거친다;\
읽기 작업은 즉시 실행된다"

"윤지욱|task,pic|[작업] pic — 개발 환경·GPU 확인 및 OCR 후보 조사|3일|\
nvitop 으로 할당된 VRAM 을 확인했다;\
OCR 후보를 2개 이상 비교해 표로 정리했다;\
9.5GiB 안에서 돌아가는지 판단하고 근거를 적었다"

"윤지욱|task,pic|[작업] pic — 이미지에서 텍스트·표 구조 추출 (베이스라인)|4일|\
사진 1장에서 텍스트가 나온다;\
표가 줄글이 아니라 구조로 나온다;\
결과를 JSON 으로 반환한다"

"윤지욱|task,pic|[작업] pic — 시간표 사진 5장에서 과목·요일·시간 추출|3일|\
시간표 사진 5장에서 과목명·요일·시작·종료·강의실이 나온다;\
5장 각각의 성공/실패가 기록돼 있다"

"윤지욱|task,pic|[작업] pic — 저품질 사진 실패 감지 → 확인 필요 분리|3일|\
기울어짐·그림자·저해상도 사진에서 실패를 감지한다;\
잘못 읽은 결과를 조용히 반환하지 않는다;\
실패한 이미지와 원인을 기록으로 남긴다"

"윤지욱|task,pic|[작업] pic — 출력 스키마를 doc 과 통일|2일|\
doc 과 같은 스키마로 결과를 넘긴다;\
스키마 변경 시 doc 담당과 합의했다"

"윤지욱|task,pic|[작업] pic — OCR 후처리 텍스트 요약|3일|\
OCR 로 뽑은 텍스트를 요약한다;\
core 의 LLM 호출 계층을 거쳐 호출한다;\
요약에 원문 근거가 남는다"

"정수빈|task|[작업] 데이터 구글링 (범위 별도 전달 예정)|미정|\
수집 대상·형식·산출물 위치를 전달받았다;\
AI 를 사용하지 않고 수집했다;\
수집 결과를 공유했다"
)

# ── 실행 전 확인 ────────────────────────────────────────────
echo "============================================================"
echo " 저장소   : $REPO"
echo " 라벨     : ${#LABELS[@]}개"
echo " 이슈     : ${#ISSUES[@]}개"
if [ -n "$PROJECT_NUMBER" ]; then
    echo " 프로젝트 : #$PROJECT_NUMBER 에 카드로 추가"
else
    echo " 프로젝트 : 추가 안 함 (번호를 인자로 주면 추가합니다)"
fi
echo "============================================================"
echo
echo "만들 이슈:"
for row in "${ISSUES[@]}"; do
    IFS='|' read -r who labels title est _ <<< "$row"
    printf "  %-7s %-6s %s\n" "$who" "($est)" "$title"
done
echo
read -r -p "진행할까요? [y/N] " ans
[[ "$ans" =~ ^[Yy]$ ]] || { echo "취소했습니다."; exit 0; }

# ── 1) 라벨 ─────────────────────────────────────────────────
echo
echo "### 라벨 생성 ###"
for row in "${LABELS[@]}"; do
    IFS='|' read -r name color desc <<< "$row"
    if gh label create "$name" --repo "$REPO" --color "$color" --description "$desc" 2>/dev/null; then
        echo "  생성  $name"
    else
        gh label edit "$name" --repo "$REPO" --color "$color" --description "$desc" >/dev/null 2>&1 \
            && echo "  갱신  $name" || echo "  건너뜀 $name"
    fi
done

# ── 2) 이슈 ─────────────────────────────────────────────────
echo
echo "### 이슈 생성 ###"
CREATED=()
for row in "${ISSUES[@]}"; do
    IFS='|' read -r who labels title est criteria <<< "$row"

    # 완료 기준을 체크박스로
    checks=""
    IFS=';' read -ra items <<< "$criteria"
    for c in "${items[@]}"; do
        c="$(echo "$c" | sed 's/^ *//;s/ *$//')"
        [ -n "$c" ] && checks+="- [ ] $c"$'\n'
    done

    body="## 담당

$who

## 완료 기준

<!-- \"구현했다\" 가 아니라 \"이렇게 하면 동작을 보여줄 수 있다\" 로 봅니다 -->

$checks
## 예상 소요

$est

## 참고

- [$DOC_PLAN](../blob/main/$DOC_PLAN) — 전체 계획·역할·칸반 규칙
- [$DOC_MOD](../blob/main/$DOC_MOD) — 이 기능의 MVP 완료 기준

## 진행 기록

<!--
데일리 스크럼 대신 여기에 코멘트로 남깁니다. 최소 주 2회.
  - 지난번 이후:
  - 다음:
  - 막힌 것:
하루 이상 막히면 blocked 라벨을 다세요.
-->
"

    url=$(gh issue create --repo "$REPO" \
        --title "$title" \
        --label "$labels" \
        --body "$body")
    echo "  $url"
    CREATED+=("$url")
done

# ── 3) 프로젝트 보드에 추가 ─────────────────────────────────
if [ -n "$PROJECT_NUMBER" ]; then
    echo
    echo "### 프로젝트 #$PROJECT_NUMBER 에 카드 추가 ###"
    for url in "${CREATED[@]}"; do
        gh project item-add "$PROJECT_NUMBER" --owner "$OWNER" --url "$url" >/dev/null \
            && echo "  추가  $url" || echo "  실패  $url"
    done
fi

echo
echo "============================================================"
echo " 완료. 이슈 ${#CREATED[@]}건 생성"
echo
echo " 다음 할 일"
echo "   1. 보드에서 컬럼을 만드세요:"
echo "      Backlog / Ready / In Progress / Review / Done"
echo "   2. 지금 시작할 것만 Ready 로 옮기세요"
echo "   3. In Progress 는 1인 최대 2장입니다"
echo "============================================================"
