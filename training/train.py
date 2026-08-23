#!/usr/bin/env python3
"""LLM QLoRA(4-bit LoRA) 파인튜닝 — 우리 AI agent 용 기본 학습 스크립트.

캐글에서 받은 학습 코드가 있으면 그걸 써도 되고, 없으면 이 스크립트로
우리 JSONL 데이터(training/data/*.jsonl)를 바로 학습할 수 있다.

  # 1) 준비
  bash training/setup.sh
  # 2) 데이터 넣기 (캐글 데이터 or 우리 데이터 변환본)  → training/data/*.jsonl
  # 3) 학습
  bash training/train.sh                 # 설정(모델·경로)은 train.sh 상단에서
  #   또는
  python training/train.py --model Qwen/Qwen3-4B --data training/data --output training/outputs

지원 데이터 형식(JSONL, 한 줄에 하나):
  {"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
  {"instruction":"...", "input":"...", "output":"..."}
  {"query":"...", "expected":{"answer":"..."}}     # 우리 qa.jsonl 형식

9.5GiB(로컬 MIG)에서는 4-bit + 작은 배치 + 짧은 seq 로 4B 급까지. 8B 는 캐글(16GB) 권장.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path


def _load_records(data_dir: str) -> list[dict]:
    files = sorted(glob.glob(str(Path(data_dir) / "*.jsonl")))
    recs = []
    for f in files:
        for ln in Path(f).read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln:
                recs.append(json.loads(ln))
    return recs


def _to_messages(rec: dict) -> list[dict] | None:
    """여러 형식을 chat messages 로 통일."""
    if isinstance(rec.get("messages"), list) and rec["messages"]:
        return rec["messages"]
    if rec.get("instruction") and rec.get("output"):
        user = rec["instruction"] + (f"\n\n{rec['input']}" if rec.get("input") else "")
        return [{"role": "user", "content": user},
                {"role": "assistant", "content": str(rec["output"])}]
    if rec.get("query") and rec.get("expected", {}).get("answer"):
        return [{"role": "user", "content": rec["query"]},
                {"role": "assistant", "content": rec["expected"]["answer"]}]
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-4B", help="HF 모델 id (config/train.sh 에서 지정)")
    ap.add_argument("--data", default="training/data")
    ap.add_argument("--output", default="training/outputs")
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--max-seq", type=int, default=1024)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--no-4bit", action="store_true", help="4-bit 끄기(메모리 여유 있을 때)")
    args = ap.parse_args()

    # 의존성은 실행 시점에 확인(설치 안 됐으면 친절히 안내)
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from trl import SFTConfig, SFTTrainer
    except ImportError as e:
        sys.exit(f"[의존성 없음] {e}\n먼저:  bash training/setup.sh  (pip install -r training/requirements.txt)")

    records = _load_records(args.data)
    pairs = [m for m in (_to_messages(r) for r in records) if m]
    if not pairs:
        sys.exit(f"[데이터 없음] {args.data}/*.jsonl 에 학습 쌍이 없습니다.\n"
                 f"  캐글 데이터를 넣거나  python training/prepare_data.py  로 우리 데이터를 변환하세요.")
    print(f"학습 샘플 {len(pairs)}개  ·  모델 {args.model}  ·  4bit={not args.no_4bit}")

    use_4bit = (not args.no_4bit) and torch.cuda.is_available()
    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    quant = None
    if use_4bit:
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                   bnb_4bit_compute_dtype=torch.bfloat16,
                                   bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, quantization_config=quant, trust_remote_code=True,
        device_map="auto", torch_dtype=torch.bfloat16)

    def fmt(ex):
        return {"text": tok.apply_chat_template(ex["messages"], tokenize=False,
                                                add_generation_prompt=False)}
    ds = Dataset.from_list([{"messages": m} for m in pairs]).map(fmt)

    lora = LoraConfig(r=args.lora_r, lora_alpha=args.lora_r * 2, lora_dropout=0.05,
                      bias="none", task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                      "gate_proj", "up_proj", "down_proj"])
    cfg = SFTConfig(
        output_dir=args.output, num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch, gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr, max_seq_length=args.max_seq, logging_steps=5,
        save_strategy="epoch", bf16=True, gradient_checkpointing=True,
        report_to="none", dataset_text_field="text")
    trainer = SFTTrainer(model=model, args=cfg, train_dataset=ds, peft_config=lora,
                         processing_class=tok)
    trainer.train()
    trainer.save_model(args.output)
    tok.save_pretrained(args.output)
    print(f"완료 → {args.output} (LoRA 어댑터 저장)")


if __name__ == "__main__":
    main()
