# training/ — LLM 파인튜닝 작업 폴더

우리 AI agent 에 들어갈 LLM 을 **LoRA/QLoRA** 로 파인튜닝하는 곳입니다.
**캐글에서 데이터·코드를 받아 여기에 넣으면 바로 학습**할 수 있게 구성돼 있습니다.
로컬(이 서버, MIG 9.5GiB)과 캐글(16GB) **둘 다** 되게 맞춰뒀습니다.

> 이 폴더의 `data/ code/ outputs/` 는 git 에 안 올라갑니다(용량·라이선스). 스크립트·설정만 커밋됩니다.

---

## 폴더 구조 — 어디에 뭘 넣나

```text
training/
├── data/         ← 학습 데이터(JSONL) 를 여기에.  캐글 데이터 or 우리 데이터 변환본
├── code/         ← 캐글에서 받은 학습 코드(노트북/스크립트) 를 여기에
├── outputs/      ← 학습 결과(LoRA 어댑터·로그) 가 여기에 저장됨
├── requirements.txt
├── setup.sh              의존성 설치 + GPU 확인
├── train.py             기본 QLoRA 학습 스크립트(캐글 코드 없어도 바로 돌아감)
├── train.sh             ← 모델·경로·하이퍼파라미터를 여기서 바꿈
├── prepare_data.py      우리 라벨 데이터 → 학습용 JSONL 변환
└── kaggle_download.sh   캐글 데이터/커널 받기 헬퍼
```

---

## 바로 학습하는 3단계

```bash
# 1) 준비 (의존성 설치 + GPU 확인)
bash training/setup.sh

# 2) 데이터 넣기 — 아래 셋 중 하나
bash training/kaggle_download.sh dataset <owner>/<slug>   # 캐글 데이터 → training/data
#   또는 캐글 코드도:  bash training/kaggle_download.sh kernel <owner>/<slug> → training/code
python training/prepare_data.py                           # 우리 라벨 데이터 → training/data

# 3) 학습 (모델·경로는 train.sh 상단에서 수정)
bash training/train.sh
```

- **캐글 코드로 학습**할 거면 `training/code/` 의 스크립트를 그대로 실행하면 됩니다(데이터 경로만 `training/data` 로).
- **우리 기본 스크립트로 학습**할 거면 `train.sh` (내부적으로 `train.py`) 를 쓰면 됩니다.

### 데이터 형식 (JSONL, 한 줄=한 샘플) — 아래 아무거나 인식

```json
{"messages":[{"role":"user","content":"이번주 과제?"},{"role":"assistant","content":"..."}]}
{"instruction":"...","input":"...","output":"..."}
{"query":"...","expected":{"answer":"..."}}
```

---

## 모델은 무엇으로? (정하면서 진행)

코드에 모델명을 박지 않습니다 — `train.sh` 의 `MODEL=` **한 줄만** 바꾸면 됩니다.
후보는 [GPU-환경과-모델-선정.md](../docs/GPU-환경과-모델-선정.md) 기준이며, **파인튜닝 관점**으로 추리면:

| 모델 | 크기 | 로컬 9.5GiB(QLoRA) | 캐글 16GB | 메모 |
| --- | --- | :---: | :---: | --- |
| **Qwen/Qwen3-4B** | 4B | ✅ 안전(기본값) | ✅ | 다국어·tool calling, 한국어 준수. **먼저 이걸로 파이프라인 검증 추천** |
| Qwen/Qwen3-8B | 8B | ⚠️ 빡빡(seq 짧게) | ✅ 권장 | 정확도↑. 로컬은 OOM 위험 |
| naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B | 1.5B | ✅ 여유 | ✅ | 한국어 특화·초경량. tool calling 신뢰도는 낮을 수 있음 |
| naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-8B | 8B | ⚠️ | ✅ 권장 | 한국어 특화. 로컬은 캐글로 |

**권장 진행**: 먼저 **Qwen3-4B** 로 로컬에서 파이프라인을 검증(소량 데이터로 1 epoch) → 데이터가 쌓이면 **8B 를 캐글**에서 본학습 → 최종 모델은 `eval_ai-agent` 비교로 확정.
다른 후보를 HF/GitHub 에서 더 찾으면 `MODEL=` 만 바꿔 그대로 실험하면 됩니다.

> ⚠️ 로컬(9.5GiB)에서 OOM 이면: `train.sh` 의 `MAXSEQ=512`, `BATCH=1`, 그리고 4B 이하로. 8B 본학습은 캐글에서.

---

## 참고

- 학습 데이터가 곧 **평가/라벨 데이터**와 같은 형식입니다 → [라벨링-가이드](../docs/라벨링-가이드.md), `prepare_data.py`.
- 파인튜닝은 **선택**입니다. 먼저 RAG+프롬프트로 충분한지 보고, 부족한 부분만 파인튜닝하는 게 비용 효율적입니다.
- 캐글 API 토큰(`~/.kaggle/kaggle.json`)은 비밀입니다 — 커밋 금지.
