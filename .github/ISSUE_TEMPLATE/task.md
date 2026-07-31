---
name: 작업 (Task)
about: 기능 개발 단위를 등록합니다. 스프린트 백로그가 됩니다
title: "[작업] "
labels: task
assignees: ''
---

## 기능

<!-- core / doc / pic / rag / brief / chat / notice / rule / eval 중 하나 -->

**기능 메인 브랜치:** `___ai-agent`
**작업 브랜치:** `___ai-agent_<영문이름>`
**대응 기능번호:** <!-- 계획서 F1~F17 중. 예: F6 -->

## 목표

<!-- 이 작업이 끝나면 무엇이 동작하는지 한두 줄로 -->

## 완료 기준

<!--
"구현했다" 가 아니라 "이렇게 하면 동작하는 걸 보여줄 수 있다" 로 적습니다.
docs/AI_MODULES.md 의 해당 기능 완료 기준을 참고하세요.
-->

- [ ]
- [ ]
- [ ]

## 입력 / 출력

| | 내용 |
| --- | --- |
| 입력 | <!-- 예: 강의계획서 PDF 1건 --> |
| 출력 | <!-- 예: {과목, 유형, 제목, 마감일시, 비중, 출처문장} JSON --> |

## 필요한 모델 슬롯

<!-- LLM_MAIN / DOC_PARSER / VISION / EMBEDDING / RULE 중 해당하는 것 -->

- [ ] `LLM_MAIN`
- [ ] `DOC_PARSER`
- [ ] `VISION`
- [ ] `EMBEDDING`
- [ ] `RULE` (LLM 사용 안 함)

## 다른 기능과의 연관

<!-- 공용 코드(src/core, src/schemas)를 건드려야 하면 반드시 여기에 적고 먼저 공유하세요 -->

- [ ] `src/core/` 수정 필요
- [ ] `src/schemas/` 수정 필요
- [ ] 없음

## 예상 소요

<!-- 며칠 / 몇 스프린트 -->
