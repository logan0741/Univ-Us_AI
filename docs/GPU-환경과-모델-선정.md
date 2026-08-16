# GPU 환경과 모델 선정

> 이 서버에서 **어떤 모델이 실제로 돌아가는지**와 그에 따른 후보를 정리한 문서입니다.
> 누가 무슨 작업을 맡았는지는 **[칸반 보드](https://github.com/users/logan0741/projects/4)** 를 보세요.
>
> 조사 시점: 2026-08-10 · 모델 시장은 빨리 바뀌므로 **착수 시점에 다시 확인하세요.**

---

## 1. 우리 GPU 환경 (실측)

```bash
nvitop -1
python -c "import torch; print(torch.cuda.get_device_name(0))"
```

| 항목 | 값 |
| --- | --- |
| GPU | **NVIDIA A100 80GB PCIe — MIG `1g.10gb`** |
| **실제 가용 VRAM** | **9.5 GiB** (9728 MiB) |
| 드라이버 | 570.133.20 (CUDA Driver 12.8) |
| PyTorch | 2.13.0+cu129 (CUDA 런타임 12.9) |
| venv | `~/.venv/univus-ai` |

> ### 80GB가 아닙니다
> A100 카드 하나를 **MIG로 8조각 내서** 나눠 쓰는 구조입니다. 우리 몫은 `1g.10gb` 슬라이스 하나입니다.
> `nvidia-smi` 상단에 `A100 80GB`라고 떠도 **쓸 수 있는 건 9.5GiB뿐**입니다.
>
> venv 는 컨테이너 overlay 에 있어 **pod 재시작 시 사라집니다.** 복구는
> [서버 작업환경 설정](서버-작업환경-설정.md) 참고.

### 9.5GiB 예산표

가중치 외에 **KV 캐시 + 런타임 오버헤드로 2~4GB**가 더 듭니다. 컨텍스트를 길게 잡을수록 KV 캐시가 커집니다.

| 모델 크기 | bf16/fp16 | 4-bit (Q4_K_M) | 9.5GiB 에서 |
| --- | --- | --- | --- |
| 1~2B | 2~4 GB | ~1 GB | ✅ 여유 |
| **4B** | ~8 GB | ~2.5 GB | ✅ 4-bit 여유 · bf16 은 빠듯 |
| **8B** | ~16 GB ❌ | ~5 GB | ⚠️ **4-bit 만 가능.** 실사용 7~9GB — 컨텍스트 길면 OOM |
| 14B | ~28 GB ❌ | ~9 GB | ❌ 사실상 불가 |
| 32B | ~64 GB ❌ | ~18 GB ❌ | ❌ |

**결론: 로컬로 돌릴 수 있는 상한은 8B 4-bit 입니다.**

---

## 2. `LLM_MAIN` 에 필요한 능력

모델 슬롯의 정의는 [AI_MODULES.md](AI_MODULES.md)에 있습니다. 그중 `LLM_MAIN` 에 요구되는 건 3가지입니다.

| # | 능력 | 왜 필요한가 |
| --- | --- | --- |
| 1 | **한국어 문서 이해** | 강의계획서·공지가 전부 한국어. 날짜 표기도 `6/12(목) 23:59`, `12주차` 등 제각각 |
| 2 | **JSON 구조화 출력** | 추출 결과를 Pydantic 으로 검증해야 함. 스키마를 못 지키면 재시도 비용이 계속 발생 |
| 3 | **Function Calling** | 대화형 에이전트가 도구를 골라 실행하고 인자를 채워야 함 |

추가로 **긴 컨텍스트**(강의계획서 통째로 넣음)와 **원문 근거 문장 인용**이 필요합니다.
근거 인용은 모델 성능보다 프롬프트·검증 설계에 더 좌우되므로 모델 선정 기준에서는 뺐습니다.

---

## 3. 후보

### 3-1. API 경로 — **주 경로입니다**

[README 3장](../README.md)이 정한 기본 방향이 *"외부 API 호출 기반"* 입니다. GPU 없이도 개발할 수 있게 하려는 설계입니다.

| 후보 | 한국어 점수 | 메모 |
| --- | ---: | --- |
| **Upstage Solar** | **80.1** (1위) | `requirements.txt` 에 `# langchain-upstage` 가 **이미 주석으로 준비돼 있음** — 원래 후보였던 것으로 보임 |
| A.X (SK텔레콤) | 78.0 | API 전용 |
| K-EXAONE (LG) | 76.0 | API 전용 |
| OpenAI 호환 아무거나 | — | `core` 가 **프로바이더 2종**을 요구하므로 최소 2개 필요 |

> 점수는 [BenchLM Korea AI Leaderboard](https://benchlm.ai/leaderboards/korean-llm) (2026-07) 기준입니다.

### 3-2. 로컬 경로 — eval 비교 실험용

9.5GiB 제약을 통과하는 것만 남겼습니다.

| 모델 | 크기 | 메모 |
| --- | --- | --- |
| [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) | 4-bit ~5GB | **상한선.** Qwen-Agent 로 tool calling 지원. 컨텍스트 길이 주의 |
| [Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B) | 4-bit ~2.5GB | 안전한 선택. 정확도는 8B 보다 낮음 |
| [HyperCLOVAX-SEED-Omni-8B](https://huggingface.co/naver-hyperclovax/HyperCLOVAX-SEED-Omni-8B) | 양자화 필요 | 한국어 특화(Naver). 멀티모달이라 `pic` 쪽과 겹칠 수 있음 |

### 3-3. `EMBEDDING` 슬롯 (1차 범위 밖)

| 모델 | 크기 | 메모 |
| --- | --- | --- |
| [dragonkue/BGE-m3-ko](https://huggingface.co/dragonkue/BGE-m3-ko) | 568M | 한국어 최적화 BGE-M3 파생. **아주 작아 GPU 여유 충분** |
| [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) | — | 원본. 8192 토큰, 100개국어, dense+sparse+multi-vector |

---

## 4. 9.5GiB 가 만드는 제약 — 한국어 특화 모델을 대부분 못 씁니다

한국어 리더보드 상위권을 **공개 여부 + 크기**로 거르면 남는 게 거의 없습니다.

| 모델 | 한국어 | 공개 | 제공 크기 | 9.5GiB |
| --- | ---: | --- | --- | :---: |
| Solar (Upstage) | 80.1 | API 전용 | — | 해당 없음 |
| HyperCLOVA X (Naver) | 78.4 | 공개 | SEED 0.5B / 8B / 14B / 32B | 8B 만 |
| A.X (SKT) | 78.0 | API 전용 | — | 해당 없음 |
| K-EXAONE (LG) | 76.0 | API 전용 | — | 해당 없음 |
| EXAONE 4.0 (LG) | 75.2 | 공개 | **1.2B 또는 32B** | ❌ |

**EXAONE 4.0 은 1.2B 와 32B 두 종류뿐이라 중간 크기가 아예 없습니다.**
32B 는 AWQ 양자화해도 18GB 이상이라 불가능하고, 1.2B 는 Function Calling 신뢰도가 떨어집니다.

즉 **한국어 특화 오픈 모델을 로컬로 돌린다는 선택지는 사실상 HyperCLOVA X SEED 8B 하나뿐**이고,
나머지는 범용 다국어 모델(Qwen3)로 가야 합니다.

---

## 5. 그래서 지금 어떻게 하나

**지금 모델을 고르지 않습니다.** 프로젝트가 이미 그렇게 설계돼 있습니다.

- `core` 의 존재 이유가 *"설정만 바꿔 모델을 갈아끼우는 것"* 입니다
- 코드에는 모델 이름 대신 **슬롯 이름**(`LLM_MAIN` 등)만 씁니다 → [README 2장](../README.md)
- 실제 모델은 **`eval_ai-agent` 비교 실험 결과로 확정**합니다 → [AI_MODULES.md](AI_MODULES.md)

```python
# ✅ 이렇게
model = settings.LLM_MAIN_MODEL

# ❌ 이렇게 하지 마세요
model = "solar-pro-3"
```

### 당장 필요한 것

**OpenAI 호환 API 2종 확보.** `core` 완료 기준에 *"서로 다른 프로바이더 2개로 같은 호출이 성공한다"* 가 있습니다.
로컬 모델은 어차피 [개발 순서](DEV_PLAN.md) 4단계(모델 비교 실험) 일입니다.

### 확정되면 바꿀 것

모델이 정해지면 **아래 두 곳만** 바뀝니다. 나머지 코드는 그대로입니다.

| 파일 | 무엇을 |
| --- | --- |
| `.env` | 슬롯별 모델명·엔드포인트·키 |
| `requirements.txt` | 프로바이더 SDK 주석 해제 (`langchain-upstage` 등) |

---

## 참고

| 문서 | 내용 |
| --- | --- |
| [칸반 보드](https://github.com/users/logan0741/projects/4) | **누가 무엇을 하고 있는지** |
| [AI_MODULES.md](AI_MODULES.md) | 모델 슬롯 정의, 기능별 MVP 완료 기준 |
| [DEV_PLAN.md](DEV_PLAN.md) | 1차 개발 계획, 개발 순서 |
| [서버-작업환경-설정.md](서버-작업환경-설정.md) | venv 재설치, GPU 확인 |
