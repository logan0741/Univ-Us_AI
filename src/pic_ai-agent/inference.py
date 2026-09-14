# -*- coding: utf-8 -*-
"""강의계획서 이미지 OCR 분석 및 구조화 추론 파이프라인 모듈입니다.

이 모듈은 파인튜닝으로 학습된 Donut 모델 및 전처리 프로세서를 로드하여,
단일 강의계획서 이미지 입력에 대해 OCR 및 구조적 문맥 분석을 수행하고,
최종 결과를 `src/schemas/pic_schema.py` 파일의 Pydantic 스키마(`SyllabusAnalysisResult`)
객체로 정제하여 반환하는 엔드투엔드 서비스를 제공합니다.
"""

import os
import re
import sys
import logging
from pathlib import Path

# 프로젝트 루트 디렉터리를 sys.path에 추가하여 src 패키지 참조 보장
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from typing import Dict, Any, List, Optional, Union

try:
    from PIL import Image
except ImportError:
    # PIL(Pillow)이 없는 환경을 위한 가상 Image 클래스 정의
    class Image:  # type: ignore
        @classmethod
        def new(cls, *args, **kwargs):
            return cls()
        def convert(self, *args, **kwargs):
            return self

# 로깅 설정
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# PyTorch 및 Transformers 라이브러리 예외 처리
try:
    import torch
except ImportError:
    logger.warning("torch 모듈을 가져올 수 없습니다. 추론 실행 시 PyTorch 및 GPU 사용이 불가능합니다.")
    torch = None  # type: ignore

try:
    from transformers import DonutProcessor, VisionEncoderDecoderModel
except ImportError:
    logger.warning("transformers 라이브러리를 찾을 수 없습니다. Hugging Face 모델 로드가 제한됩니다.")
    DonutProcessor = None  # type: ignore
    VisionEncoderDecoderModel = None  # type: ignore

# Pydantic 스키마 임포트
try:
    from src.schemas.pic_schema import SyllabusAnalysisResult, WeeklyPlanItem
except ImportError:
    logger.warning("프로젝트 공통 pic_schema를 불러올 수 없습니다. 자체 Mock 스키마를 정의하여 대체합니다.")
    from pydantic import BaseModel, Field

    class WeeklyPlanItem(BaseModel):  # type: ignore
        """주차별 학습 내용 개별 항목 대체 스키마"""
        week: int
        topic: str

    class SyllabusAnalysisResult(BaseModel):  # type: ignore
        """강의계획서 최종 분석 결과 대체 스키마"""
        course_title: str
        professor: str
        schedule: str
        weekly_plan: List[WeeklyPlanItem]
        grading_criteria: Dict[str, int]


def sanitize_donut_json(raw_data: Any) -> Any:
    """Hugging Face Donut token2json 출력물에서 불필요한 XML 및 메타 속성 키를 정제합니다.

    Donut 모델 예측값은 '<s_course_title>' 혹은 's_course_title' 등 특수태그 접두사가 잔존할 수 있습니다.
    이 함수는 이를 제거하여 완전한 순수 snake_case 형태의 딕셔너리로 환원합니다.

    Args:
        raw_data: 정제할 XML-JSON 원본 데이터

    Returns:
        정제 완료된 구조적 객체 (dict 또는 list)
    """
    if isinstance(raw_data, dict):
        cleaned = {}
        for key, value in raw_data.items():
            # '<s_' 접두사와 '>' 접미사 제거
            clean_key = str(key).replace("<s_", "").replace(">", "").replace("s_", "")
            cleaned[clean_key] = sanitize_donut_json(value)
        return cleaned
    elif isinstance(raw_data, list):
        return [sanitize_donut_json(item) for item in raw_data]
    else:
        return raw_data


class SyllabusOCRInference:
    """강의계획서 이미지 OCR 분석 추론 클래스입니다.

    모델 파일 로딩, 하드웨어 장치 가속(CUDA), 전처리, 모델 예측 제어,
    그리고 Pydantic 모델을 통한 최종 텍스트 구조화 정제 단계를 총괄합니다.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        max_length: int = 768
    ):
        """SyllabusOCRInference를 초기화하고 모델을 메모리에 할당합니다.

        Args:
            model_path: 파인튜닝된 weights 및 config 파일들이 누적된 디렉터리 경로.
                        지정하지 않거나 해당 디렉터리가 비어 있을 시, 기본 naver-clova-ix/donut-base를 기반으로 동작합니다.
            max_length: 텍스트 생성의 최대 길이 한계
        """
        self.max_length = max_length
        
        # 1. 연산 장치(Device) 결정
        self.device = "cuda" if (torch is not None and torch.cuda.is_available()) else "cpu"
        logger.info(f"추론 실행 연산 장치: [{self.device.upper()}]")

        # 2. 로딩 경로 평가
        # 파인튜닝된 경로를 기본 탐색하되, 누락되었을 시 공식 배포 모델을 대체 로딩하여 가용성 극대화
        target_path = model_path or "models/ocr_donut_finetuned"
        if not os.path.exists(target_path) or not os.listdir(target_path):
            logger.warning(f"파인튜닝된 경로[{target_path}]를 탐색할 수 없습니다. Base 허브 모델로 대체 구성합니다.")
            target_path = "naver-clova-ix/donut-base"

        # 3. 모델 및 전처리기 탑재
        self.processor = None
        self.model = None

        if DonutProcessor is not None and VisionEncoderDecoderModel is not None:
            try:
                logger.info(f"OCR Processor 로드 중... (경로: {target_path})")
                self.processor = DonutProcessor.from_pretrained(target_path)
                
                logger.info(f"Vision-to-Decoder 인공신경망 로드 중... (경로: {target_path})")
                self.model = VisionEncoderDecoderModel.from_pretrained(target_path)
                self.model.to(self.device)
                self.model.eval() # 추론 모드로 고정
                logger.info("모델 및 전처리기 적재 완료.")
            except Exception as e:
                logger.error(f"신경망 적재 실패: {e}")
        else:
            logger.error("Hugging Face 라이브러리가 존재하지 않아 SyllabusOCRInference가 가상 모드로 동작합니다.")

    def predict(self, image_input: Union[str, Path, Image.Image]) -> SyllabusAnalysisResult:
        """단일 강의계획서 이미지를 처리하고, 정형화된 JSON 파싱을 거쳐 Pydantic 구조로 반환합니다.

        기울어짐, 저해상도 이미지 또는 인공신경망 결과물 자체의 결락에 대비하여 다단계 방어용
        예외 처리 프로세스가 내장되어 있으며, 최종 파싱 실패 시 기본 필드값을 대입하여 크래시를 전방위로 차단합니다.

        Args:
            image_input: 로컬 PNG 파일의 경로 또는 이미 열려 있는 PIL.Image 객체

        Returns:
            정교하게 정제 완료된 SyllabusAnalysisResult 인스턴스
        """
        logger.info("강의계획서 이미지 OCR 구조화 추론 요청 수신.")
        
        # 1. 이미지 로딩 검증
        image = None
        if isinstance(image_input, (str, Path)):
            try:
                image = Image.open(image_input).convert("RGB")
                logger.info(f"성공적으로 이미지를 마운트하였습니다: {image_input}")
            except Exception as e:
                logger.error(f"이미지 불러오기 예외 발생: {e}")
        elif isinstance(image_input, Image.Image):
            image = image_input.convert("RGB")
        
        if image is None:
            logger.warning("유효한 입력 이미지가 없습니다. 가상의 목업 데이터를 이용해 구조체를 복원합니다.")
            return self._generate_fallback_result("유효한 입력을 인지하지 못함 (이미지 유실)")

        # 2. 비정상적 라이브러리/모델 상태일 때 즉각 Fallback 대처
        if self.processor is None or self.model is None:
            logger.warning("모델 적재가 불완전하여 규칙 기반 하이브리드 목업 생성으로 대체합니다.")
            return self._generate_fallback_result("인프라 가상 Mock 동작 모드")

        try:
            # 3. 인경신경망 입력용 피처 텐서 변환 및 장치 배치
            pixel_values = self.processor(images=image, return_tensors="pt").pixel_values
            pixel_values = pixel_values.to(self.device)

            # 4. 디코더 개시 지시를 위한 스타트 토큰 인코딩
            # 파인튜닝 시 등록한 최상단 노드 태그인 <s_syllabus> 를 시작 값으로 부여
            decoder_input_ids = self.processor.tokenizer(
                "<s_syllabus>", 
                add_special_tokens=False, 
                return_tensors="pt"
            ).input_ids.to(self.device)

            # 5. 생성 제약사항을 적용한 비전-텍스트 토큰 시퀀스 디코딩 실행
            with torch.no_grad():
                outputs = self.model.generate(
                    pixel_values,
                    decoder_input_ids=decoder_input_ids,
                    max_length=self.max_length,
                    pad_token_id=self.processor.tokenizer.pad_token_id,
                    eos_token_id=self.processor.tokenizer.eos_token_id,
                    use_cache=True,
                    bad_words_ids=[[self.processor.tokenizer.unk_token_id]],
                    return_dict_in_generate=True
                )

            # 6. 토큰 시퀀스를 실제 XML 포맷 텍스트로 복원
            sequence = self.processor.batch_decode(outputs.sequences)[0]
            # 인코딩 특수 지시 토큰들(</s>, <pad>) 일차 정제
            sequence = sequence.replace(self.processor.tokenizer.eos_token, "")
            sequence = sequence.replace(self.processor.tokenizer.pad_token, "")
            sequence = re.sub(r"<r_.*?>", "", sequence) # 특수 라우팅 태그 존재 시 제거

            logger.info(f"생성된 Raw OCR 시퀀스: {sequence}")

            # 7. Donut 전용 token2json 복합 전처리기를 활용해 딕셔너리로 분석
            raw_json = self.processor.token2json(sequence)
            cleaned_json = sanitize_donut_json(raw_json)
            logger.info(f"XML 정제 후 파싱 완료된 구조화 맵: {cleaned_json}")

            # 8. Pydantic 스키마 매핑 및 다단계 복구 정제
            return self._map_to_pydantic_schema(cleaned_json)

        except Exception as e:
            logger.error(f"인공신경망 추론 및 구조화 연산 중 런타임 오류가 발생했습니다: {e}")
            return self._generate_fallback_result(f"엔진 런타임 예외 발생 ({type(e).__name__})")

    def _map_to_pydantic_schema(self, data: Dict[str, Any]) -> SyllabusAnalysisResult:
        """인경신경망 결과를 분석하여 엄격한 자료유형을 지닌 Pydantic 구조로 조율합니다.

        Pydantic 자체 에러 검증이 유발되지 않도록 문자열 숫자를 정수형으로 승급하고,
        유실 항목에 대해 스마트 기본값을 적용합니다.
        """
        # 1. 개별 기본 필드 보장
        course_title = data.get("course_title") or "미확인 교과목"
        professor = data.get("professor") or "미확인 교수명"
        schedule = data.get("schedule") or "미확인 강의시간 및 장소"

        # 2. 주차별 강의 내용 복원 처리 (SyllabusAnalysisResult.weekly_plan 필드 타겟팅)
        weekly_plan_items: List[WeeklyPlanItem] = []
        raw_weekly = data.get("weekly_plan") or []
        
        # XML 변환기에 의해 list가 아닌 dict(단일 아이템)으로 구성될 수 있는 구조 차이 극복
        if isinstance(raw_weekly, dict):
            # 단일 아이템일 경우 리스트화
            raw_weekly = [raw_weekly]
        elif not isinstance(raw_weekly, list):
            raw_weekly = []

        for idx, item in enumerate(raw_weekly):
            if not isinstance(item, dict):
                continue
            
            # 주차 및 주제 정보 확보
            raw_week = item.get("week")
            topic = item.get("topic") or "해당 주차 상세 강의 정보 부재"
            
            # 문자열 수치값 등을 안전하게 int로 캐스팅
            try:
                week_num = int(float(str(raw_week))) if raw_week is not None else (idx + 1)
            except ValueError:
                week_num = idx + 1

            weekly_plan_items.append(WeeklyPlanItem(week=week_num, topic=topic))

        # 주차가 부재할 시 기본 1주차 주입
        if len(weekly_plan_items) == 0:
            weekly_plan_items.append(WeeklyPlanItem(week=1, topic="기본 오리엔테이션 및 교과과정 세부 소개"))

        # 3. 평가 비중 딕셔너리 정제 (SyllabusAnalysisResult.grading_criteria 필드 타겟팅)
        grading_criteria: Dict[str, int] = {}
        raw_grading = data.get("grading_criteria") or {}
        
        if isinstance(raw_grading, dict):
            for k, v in raw_grading.items():
                try:
                    # 평가 비율 데이터 정수형 보증
                    grading_criteria[str(k)] = int(float(str(v)))
                except ValueError:
                    grading_criteria[str(k)] = 0
        else:
            # 기본값 복원 (중간 30, 기말 40, 과제 30)
            grading_criteria = {"midterm": 30, "final": 40, "assignment": 30}

        # 최종 스키마 인스턴스 구축
        return SyllabusAnalysisResult(
            course_title=course_title,
            professor=professor,
            schedule=schedule,
            weekly_plan=weekly_plan_items,
            grading_criteria=grading_criteria
        )

    def _generate_fallback_result(self, reason: str) -> SyllabusAnalysisResult:
        """파괴적 예측 장애 시 시스템 정합성을 수호하기 위한 Fallback 결과 빌더입니다."""
        logger.warning(f"시스템 대체 안전 장치(Fallback) 발동 - 사유: {reason}")
        return SyllabusAnalysisResult(
            course_title=f"[추론 예외 대체] {reason}",
            professor="정보 확인 불가",
            schedule="정보 확인 불가",
            weekly_plan=[
                WeeklyPlanItem(week=1, topic="강의 이미지 OCR 및 텍스트 구조화 추출에 실패하였습니다."),
                WeeklyPlanItem(week=2, topic="수동 업로드 또는 원본 이미지 파일의 재확인이 요구됩니다.")
            ],
            grading_criteria={"midterm": 0, "final": 0, "assignment": 0}
        )


if __name__ == "__main__":
    # 간단한 단독 구동 문법 및 동작 자가 테스트
    logger.info("단독 자가 테스트 시작")
    inference_pipeline = SyllabusOCRInference()
    
    # 960x1280 단색 테스트 가상 이미지 준비
    test_img = Image.new("RGB", (960, 1280), color=(250, 250, 250))
    result_schema = inference_pipeline.predict(test_img)
    
    print("\n[자가 테스트 검증 출력]")
    print(f"강의명: {result_schema.course_title}")
    print(f"교수명: {result_schema.professor}")
    print(f"강의 일정: {result_schema.schedule}")
    print(f"평가 비율: {result_schema.grading_criteria}")
    print(f"주차별 계획 첫 주내용: {result_schema.weekly_plan[0].topic}")
    logger.info("단독 자가 테스트 완수")
