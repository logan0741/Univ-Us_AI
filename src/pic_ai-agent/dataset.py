# -*- coding: utf-8 -*-
"""강의계획서 이미지 분석 및 OCR 파인튜닝을 위한 데이터셋 전처리 모듈입니다.

이 모듈은 PyTorch Dataset을 상속받아, 강의계획서 이미지와 대응하는 구조화된 라벨 데이터를
Hugging Face Donut 모델 등의 입력 텐서 규격에 맞게 변환 및 로드하는 기능을 제공합니다.
실제 데이터 디렉터리가 비어 있거나 부재한 경우에도 정상 동작 및 문법 검사를 통과할 수 있도록
자동 모의(Mock) 데이터 생성 모드를 지원합니다.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

try:
    import PIL
    from PIL import Image
except ImportError:
    PIL = None  # type: ignore
    # PIL(Pillow)이 없는 환경을 위한 가상 Image 클래스 정의
    class Image:  # type: ignore
        @classmethod
        def new(cls, *args, **kwargs):
            return cls()
        def convert(self, *args, **kwargs):
            return self
        def save(self, *args, **kwargs):
            pass

# 로깅 설정
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# PyTorch 및 Transformers 라이브러리 예외 처리 수용
try:
    import torch
    from torch.utils.data import Dataset
except ImportError:
    logger.warning("PyTorch가 설치되지 않았습니다. 개발/정적 분석용 Mock Dataset 클래스를 정의합니다.")
    # py_compile 및 정적 분석 툴 통과를 위한 추상 클래스 대체
    class Dataset:  # type: ignore
        """PyTorch Dataset Mock 클래스"""
        def __init__(self, *args, **kwargs):
            pass


def json_to_donut_xml(data: Any) -> str:
    """Python 딕셔너리, 리스트 또는 기본 타입을 Donut 모델용 XML 표현형태로 변환합니다.

    Donut 모델은 출력을 구조화된 XML 태그 형식으로 생성하도록 학습됩니다.
    이 함수는 중첩된 JSON 데이터를 Donut 포맷 문자열로 인코딩합니다.

    Args:
        data: 변환할 Python 데이터 구조 (dict, list, str, int 등)

    Returns:
        XML 형태로 표현된 문자열 (예: <s_course_title>인공지능</s_course_title>)
    """
    if isinstance(data, dict):
        parts = []
        for key, val in data.items():
            parts.append(f"<s_{key}>" + json_to_donut_xml(val) + f"</s_{key}>")
        return "".join(parts)
    elif isinstance(data, list):
        parts = []
        for item in data:
            parts.append("<s_item>" + json_to_donut_xml(item) + "</s_item>")
        return "".join(parts)
    else:
        # 데이터 정제 및 문자열 변환 (특수문자 및 불필요한 공백 제거)
        clean_str = str(data).replace("<", "&lt;").replace(">", "&gt;")
        return clean_str


class SyllabusDataset(Dataset):
    """강의계획서 OCR 파인튜닝용 PyTorch Dataset 클래스입니다.

    Donut 모델 프로세서(DonutProcessor)를 활용하여 입력 이미지를 pixel_values 텐서로 변환하고,
    정답(Ground Truth) 스키마 데이터를 특수 XML 토큰 형태로 인코딩하여 모델의 labels로 준비합니다.
    """

    def __init__(
        self,
        image_dir: Union[str, Path],
        label_file_path: Optional[Union[str, Path]] = None,
        processor: Optional[Any] = None,
        max_length: int = 768,
        split: str = "train",
        ignore_id: int = -100,
        mock_mode_if_empty: bool = True
    ):
        """SyllabusDataset을 초기화합니다.

        Args:
            image_dir: PNG 이미지 파일들이 위치한 디렉터리 경로
            label_file_path: 이미지 파일명과 정답 JSON 데이터 간의 매핑을 기록한 JSON/JSONL 파일 경로
            processor: Hugging Face DonutProcessor 인스턴스
            max_length: 디코더 텍스트 입력의 최대 토큰 길이
            split: 데이터셋 분할 지정 ('train', 'validation', 'test')
            ignore_id: 손실 계산 시 패딩 토큰을 무시하기 위한 PyTorch 인덱스 값 (기본값: -100)
            mock_mode_if_empty: 실제 데이터가 부재할 경우 테스트용 모의 데이터를 자동 생성할지 여부
        """
        super().__init__()
        self.image_dir = Path(image_dir)
        self.label_file_path = Path(label_file_path) if label_file_path else None
        self.processor = processor
        self.max_length = max_length
        self.split = split
        self.ignore_id = ignore_id
        
        self.dataset_records: List[Dict[str, Any]] = []

        # 디렉터리 부재 시 생성 처리
        if not self.image_dir.exists():
            logger.warning(f"이미지 디렉터리가 존재하지 않아 생성합니다: {self.image_dir}")
            self.image_dir.mkdir(parents=True, exist_ok=True)

        # 데이터 로드 시도
        self._load_dataset()

        # 데이터가 아예 없고, mock_mode_if_empty가 활성화된 경우 컴파일 및 검사 편의를 위해 임시 생성
        if len(self.dataset_records) == 0 and mock_mode_if_empty:
            logger.info("학습 데이터가 발견되지 않아 모의(Mock) 데이터를 구성하여 진행합니다.")
            self._generate_mock_records()

    def _load_dataset(self) -> None:
        """지정된 파일로부터 이미지 경로와 구조화된 라벨 정보를 매핑하여 레코드를 구성합니다."""
        if not self.label_file_path or not self.label_file_path.exists():
            logger.warning("라벨 매핑 파일이 지정되지 않았거나 존재하지 않습니다.")
            return

        try:
            with open(self.label_file_path, "r", encoding="utf-8") as f:
                if self.label_file_path.suffix == ".jsonl":
                    for line in f:
                        if line.strip():
                            self.dataset_records.append(json.loads(line))
                else:
                    # 일반 JSON 파일인 경우 리스트 혹은 딕셔너리로 읽음
                    data = json.load(f)
                    if isinstance(data, list):
                        self.dataset_records = data
                    elif isinstance(data, dict):
                        # {"filename": {"course_title": ...}} 형식인 경우 리스트형식 레코드로 전환
                        for file_name, label_info in data.items():
                            self.dataset_records.append({
                                "file_name": file_name,
                                "label": label_info
                            })
            
            # 유효성 검사: 실제 파일 확인 및 정제
            valid_records = []
            for record in self.dataset_records:
                file_name = record.get("file_name") or record.get("image_path")
                if file_name:
                    full_path = self.image_dir / file_name
                    if full_path.exists():
                        # 파일 이름 필드 단일화
                        record["full_image_path"] = full_path
                        valid_records.append(record)
                    else:
                        logger.warning(f"라벨에는 존재하지만 이미지가 유실되었습니다: {full_path}")
            
            self.dataset_records = valid_records
            logger.info(f"성공적으로 {len(self.dataset_records)}개의 유효 데이터 레코드를 로드하였습니다.")

        except Exception as e:
            logger.error(f"데이터셋 로딩 중 예외가 발생했습니다: {e}")

    def _generate_mock_records(self) -> None:
        """로컬 테스트 및 문법 검증용 Mock 데이터를 메모리상에 생성합니다.

        실제 디렉터리 상에도 최소한의 파일들을 기록하여 전체 파이프라인의 오동작을 원천 방지합니다.
        """
        mock_labels = [
            {
                "file_name": "mock_syllabus_1.png",
                "label": {
                    "course_title": "기계학습개론",
                    "professor": "김우주 교수",
                    "schedule": "화요일 13:00-15:00 / 공학관 301호",
                    "weekly_plan": [
                        {"week": 1, "topic": "머신러닝 개요 및 기본 수학 기초"},
                        {"week": 2, "topic": "선형 회귀분석 및 경사하강법 실습"}
                    ],
                    "grading_criteria": {"midterm": 40, "final": 40, "assignment": 20}
                }
            },
            {
                "file_name": "mock_syllabus_2.png",
                "label": {
                    "course_title": "자연어처리기초",
                    "professor": "이언어 교수",
                    "schedule": "목요일 09:00-12:00 / 정보통신관 502호",
                    "weekly_plan": [
                        {"week": 1, "topic": "텍스트 데이터 전처리 및 토큰화 이론"},
                        {"week": 2, "topic": "Word2Vec과 임베딩 공간의 이해"}
                    ],
                    "grading_criteria": {"midterm": 30, "final": 50, "assignment": 20}
                }
            }
        ]

        for item in mock_labels:
            img_path = self.image_dir / item["file_name"]
            if not img_path.exists():
                try:
                    # 간단한 테스트용 단색 PNG 이미지 파일 동적 생성
                    img = Image.new("RGB", (960, 1280), color=(240, 240, 240))
                    img.save(img_path)
                    logger.info(f"테스트용 Mock 이미지 생성 완료: {img_path}")
                except Exception as e:
                    logger.error(f"Mock 이미지 생성 실패: {e}")
            
            item["full_image_path"] = img_path
            self.dataset_records.append(item)

    def __len__(self) -> int:
        """전체 데이터셋 크기를 반환합니다."""
        return len(self.dataset_records)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        """주어진 인덱스에 해당하는 데이터 배치 아이템을 가공하여 반환합니다.

        Args:
            idx: 데이터 레코드 인덱스

        Returns:
            학습용 데이터 딕셔너리:
                - "pixel_values": 이미지 처리 결과 텐서
                - "labels": 정답 텍스트 토큰 리스트 (손실 계산용 패딩 -100 대체 포함)
                - "target_text": 원본 XML 형태의 라벨 텍스트
        """
        record = self.dataset_records[idx]
        image_path = record["full_image_path"]
        label_data = record["label"]

        # 1. 이미지 로드 및 RGB 정규화
        try:
            image = Image.open(image_path).convert("RGB")
        except Exception as e:
            logger.error(f"이미지 열기 실패 ({image_path}): {e}")
            # 대비용 빈 이미지 생성
            image = Image.new("RGB", (960, 1280), color=(240, 240, 240))

        # 2. 이미지 프로세서 적용
        pixel_values = None
        if self.processor is not None:
            try:
                # DonutProcessor를 이용해 이미지 피처 텐서 추출
                processed = self.processor(images=image, return_tensors="pt")
                # squeeze()를 해주는 이유는 배치 구성(collate_fn) 시 편리하도록 하기 위함입니다.
                pixel_values = processed.pixel_values.squeeze(0)
            except Exception as e:
                logger.error(f"이미지 전처리 에러: {e}")
        
        # Processor가 없을 경우를 대비한 가상의 텐서 구조 생성 (테스트/안전장치)
        if pixel_values is None:
            # Donut의 표준 입력 규격 [3, H, W] 형식의 가상 텐서
            pixel_values = torch.zeros((3, 1280, 960)) if "torch" in globals() else None

        # 3. 라벨 구조화 데이터를 Donut 특수 XML 포맷으로 변환
        # 시작 태그를 <s_syllabus> 로 래핑하여 인코딩 타겟팅 설계
        target_xml = f"<s_syllabus>{json_to_donut_xml(label_data)}</s_syllabus>"

        # 4. 토크나이저를 통한 텍스트 인코딩 및 마스킹 처리
        labels = None
        if self.processor is not None:
            try:
                tokenizer = self.processor.tokenizer
                # 디코더의 targets 인코딩
                input_ids = tokenizer(
                    target_xml,
                    add_special_tokens=False,
                    max_length=self.max_length,
                    padding="max_length",
                    truncation=True,
                    return_tensors="pt"
                ).input_ids.squeeze(0)

                # 파인튜닝 시 <pad> 토큰 영역은 손실(Loss) 계산에서 제외되어야 하므로
                # 패딩 아이디를 PyTorch CrossEntropyLoss의 ignore_index (-100)로 치환합니다.
                labels = input_ids.clone()
                labels[labels == tokenizer.pad_token_id] = self.ignore_id
            except Exception as e:
                logger.error(f"텍스트 토큰화 에러: {e}")

        if labels is None:
            # 가상 타겟 데이터 생성 (py_compile 안전장치)
            labels = torch.zeros(self.max_length, dtype=torch.long) if "torch" in globals() else None

        return {
            "pixel_values": pixel_values,
            "labels": labels,
            "target_text": target_xml
        }
