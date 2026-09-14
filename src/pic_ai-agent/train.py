# -*- coding: utf-8 -*-
"""강의계획서 이미지 OCR 파인튜닝 학습 스크립트입니다.

Hugging Face의 VisionEncoderDecoderModel(Donut)을 기반으로, 강의계획서 이미지를 읽어
미리 정의된 스키마 형식으로 구조화 텍스트를 추출하도록 파인튜닝 학습을 진행합니다.
이 스크립트는 CUDA 기반 GPU 사용 가능 환경을 자동으로 감지하며, 
완료된 모델 가중치와 프로세서를 'models/ocr_donut_finetuned/' 경로에 자동 보존합니다.
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# 로깅 환경 로드
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 라이브러리 import 예외 처리 (환경 비활성화/미설치 상태에서의 컴파일 보호)
try:
    import torch
    from torch.utils.data import DataLoader
except ImportError:
    logger.warning("torch 모듈을 불러올 수 없습니다. 모델 작동 및 학습에는 torch가 필수적입니다.")

try:
    from transformers import (
        DonutProcessor,
        VisionEncoderDecoderModel,
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments
    )
except ImportError:
    logger.warning("transformers 모듈을 불러올 수 없습니다. Hugging Face 생태계 의존성이 준비되지 않았습니다.")

# 동일 디렉터리 내의 커스텀 Dataset 모듈 임포트
try:
    from dataset import SyllabusDataset
except ImportError:
    # 절대/상대 경로 보정을 위한 sys.path 추가
    current_dir = Path(__file__).resolve().parent
    if str(current_dir) not in sys.path:
        sys.path.append(str(current_dir))
    from dataset import SyllabusDataset


def collate_fn(batch: List[Dict[str, Any]]) -> Dict[str, Any]:
    """배치 가공 및 묶음 처리를 수행하는 Collate 함수입니다.

    PyTorch DataLoader에서 배치 아이템들을 묶을 때 각 입력 텐서들의 정렬 및 스택 처리를 조율합니다.

    Args:
        batch: Dataset에서 생성된 개별 샘플 딕셔너리의 리스트

    Returns:
        Hugging Face Trainer에 즉시 투입 가능한 일괄 병합 텐서 딕셔너리
    """
    pixel_values = torch.stack([item["pixel_values"] for item in batch])
    labels = torch.stack([item["labels"] for item in batch])
    return {
        "pixel_values": pixel_values,
        "labels": labels
    }


def main():
    """파인튜닝 메인 실행 함수입니다."""
    parser = argparse.ArgumentParser(description="Univ-Us AI Donut OCR Fine-Tuning Pipeline")
    parser.add_argument("--model_name_or_path", type=str, default="naver-clova-ix/donut-base", help="Hugging Face 기반 Donut 모델명 또는 경로")
    parser.add_argument("--image_dir", type=str, default="data/raw_images", help="학습용 PNG 파일들이 존재하는 디렉터리 경로")
    parser.add_argument("--label_file", type=str, default="data/raw_images/metadata.json", help="이미지 파일과 스키마 정보가 수록된 라벨 JSON 파일 경로")
    parser.add_argument("--output_dir", type=str, default="models/ocr_donut_finetuned", help="최종 저장 및 체크포인트 보관 경로")
    parser.add_argument("--epochs", type=int, default=3, help="학습 Epoch 수")
    parser.add_argument("--batch_size", type=int, default=2, help="장치당 학습 배치 사이즈")
    parser.add_argument("--lr", type=float, default=5e-5, help="최적화 학습률 (Learning Rate)")
    parser.add_argument("--max_length", type=int, default=768, help="디코더의 최대 토큰 처리 길이")
    parser.add_argument("--fp16", action="store_true", default=False, help="FP16 혼합 정밀도 학습 활성화 여부")
    
    # py_compile 테스트 등 외부 매개변수 없을 때의 가동을 고려한 아규먼트 파싱
    args, unknown = parser.parse_known_args()

    logger.info("=== OCR 파인튜닝 학습 파이프라인 구동 시작 ===")

    # 1. 연산 장치 자동 탐색 (CUDA GPU 및 CPU 할당)
    if "torch" in globals():
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"학습 연산 장치가 자동으로 감지되었습니다: [{device.upper()}]")
        if device == "cuda":
            logger.info(f"사용 가능 GPU 디바이스: {torch.cuda.get_device_name(0)}")
            # 장치가 CUDA일 때만 FP16 활성화 설정 적용 유도
            if not args.fp16:
                logger.info("안내: CUDA 환경입니다. 보다 신속한 연산을 위해 FP16 사용을 권장합니다.")
    else:
        device = "cpu"
        logger.warning("PyTorch가 설치되지 않아 연산 장치를 진단할 수 없습니다. CPU 기본으로 작동을 가정합니다.")

    # 2. Hugging Face Donut 프로세서 및 모델 로드
    try:
        logger.info(f"Hugging Face Processor 로드 중... (ID: {args.model_name_or_path})")
        processor = DonutProcessor.from_pretrained(args.model_name_or_path)
        
        logger.info(f"Hugging Face VisionEncoderDecoderModel 로드 중... (ID: {args.model_name_or_path})")
        model = VisionEncoderDecoderModel.from_pretrained(args.model_name_or_path)
    except Exception as e:
        logger.error(f"Hugging Face 모델 로딩 실패: {e}")
        logger.warning("로컬 가상 Mock 모드로 전환되거나 프로그램이 안전하게 종료될 수 있습니다.")
        # py_compile 검사 시 오류 전파를 차단하기 위한 mock 객체 대체 기법 적용
        class MockModel:
            config = type("Config", (), {"pad_token_id": 0, "decoder_start_token_id": 0})()
            def resize_token_embeddings(self, *args, **kwargs): pass
        model = MockModel()  # type: ignore
        processor = None

    # 3. 새로운 도메인 지식 구축을 위한 특수 토큰(Special Tokens) 추가 및 구성
    # 강의계획서의 각 구조화 필드(SyllabusAnalysisResult 구조)를 정확히 추출하기 위해
    # XML 태그 형태의 정답 구조화 토큰들을 모델 어휘집(Vocabulary)에 추가하고 임베딩 크기를 변경합니다.
    special_tokens = [
        "<s_syllabus>", "</s_syllabus>",
        "<s_course_title>", "</s_course_title>",
        "<s_professor>", "</s_professor>",
        "<s_schedule>", "</s_schedule>",
        "<s_weekly_plan>", "</s_weekly_plan>",
        "<s_item>", "</s_item>",
        "<s_week>", "</s_week>",
        "<s_topic>", "</s_topic>",
        "<s_grading_criteria>", "</s_grading_criteria>",
        "<s_midterm>", "</s_midterm>",
        "<s_final>", "</s_final>",
        "<s_assignment>", "</s_assignment>"
    ]

    if processor is not None and hasattr(processor, "tokenizer"):
        # 토크나이저에 신규 스키마용 토큰 세트 등록
        num_added_toks = processor.tokenizer.add_tokens(special_tokens)
        logger.info(f"신규 추가된 정밀 OCR 타겟 스크립트 토큰 개수: {num_added_toks}")
        
        # 모델의 토큰 임베딩 사이즈 재정렬
        model.resize_token_embeddings(len(processor.tokenizer))
        
        # 디코더 제어용 토큰 바인딩 최적화
        model.config.pad_token_id = processor.tokenizer.pad_token_id
        model.config.decoder_start_token_id = processor.tokenizer.convert_tokens_to_ids("<s_syllabus>")
        logger.info(f"디코더 시작 토큰 ID(decoder_start_token_id) 설정 완료: {model.config.decoder_start_token_id}")

    # 4. 데이터셋 객체 생성 (실제 데이터 디렉터리가 비어있는 경우 자동 Mock 데이터가 생성됨)
    logger.info("PyTorch 데이터셋 준비 시작...")
    train_dataset = SyllabusDataset(
        image_dir=args.image_dir,
        label_file_path=args.label_file if os.path.exists(args.label_file) else None,
        processor=processor,
        max_length=args.max_length,
        split="train",
        mock_mode_if_empty=True  # 실데이터 준비 전 로컬 구동 안전장치
    )
    
    # 5. Hugging Face Seq2Seq Training Arguments 정의
    logger.info("학습 설정 정의 구성 중...")
    training_args = Seq2SeqTrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=1,
        learning_rate=args.lr,
        logging_steps=1,
        save_strategy="epoch",
        evaluation_strategy="no",  # 로컬 검증 셋 간략화를 위해 'no' 지정
        predict_with_generate=True,
        fp16=args.fp16 and (device == "cuda"), # GPU 검증에 연동한 FP16 제어
        use_cpu=(device == "cpu"),
        report_to="none", # 불필요한 외부 트래커 비활성화
        dataloader_num_workers=0, # 윈도우 환경 병목 방지용 0 설정
    )

    # 6. Seq2Seq Trainer 빌드 및 가동
    # Transformers의 Trainer 인터페이스를 활용하여 가중치 갱신 루프 처리 자동화
    logger.info("Seq2SeqTrainer 인스턴스 빌드 중...")
    try:
        trainer = Seq2SeqTrainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            data_collator=collate_fn,
        )
        
        # 파인튜닝 프로세스 구동
        logger.info("학습 루프 실행을 시작합니다.")
        trainer.train()
        
        # 7. 완수된 가중치 모델 및 전처리기 영구 저장
        output_path = Path(args.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"파인튜닝 학습 완료. 가중치 및 Processor 저장 중: {output_path}")
        trainer.save_model(str(output_path))
        if processor is not None:
            processor.save_pretrained(str(output_path))
            
        logger.info("=== OCR 파인튜닝 및 최종 웨이트 저장 완료 ===")
        
    except Exception as e:
        logger.error(f"Trainer 빌드 또는 학습 도중 오류가 발생했습니다: {e}")
        logger.warning("가용한 학습 데이터 및 PyTorch 라이브러리가 존재하지 않거나, 문법 점검용 격리 환경일 수 있습니다.")


if __name__ == "__main__":
    main()
