from pydantic import BaseModel, Field


class WeeklyPlanItem(BaseModel):
    """주차별 학습 내용의 개별 항목을 정의하는 스키마입니다."""

    week: int = Field(
        ...,
        description="학습 주차 (예: 1, 2, 3...)"
    )
    topic: str = Field(
        ...,
        description="해당 주차에 학습할 강의 주제 및 세부 내용"
    )


class SyllabusAnalysisResult(BaseModel):
    """강의계획서 이미지에서 OCR 및 구조화 분석을 거쳐 도출된 최종 결과를 담는 스키마입니다."""

    course_title: str = Field(
        ...,
        description="강의명"
    )
    professor: str = Field(
        ...,
        description="담당 교수명"
    )
    schedule: str = Field(
        ...,
        description="강의 시간 및 강의실 정보 (예: 월요일 3-4교시 / 정보공학관 401호)"
    )
    weekly_plan: list[WeeklyPlanItem] = Field(
        ...,
        description="주차별 학습 내용 목록. 각 주차(week)와 학습 주제(topic)를 매칭하는 객체의 리스트입니다."
    )
    grading_criteria: dict[str, int] = Field(
        ...,
        description="평가 비율 기준 (단위: %). 예: {'midterm': 30, 'final': 40, 'assignment': 30}와 같이 평가 항목과 반영 비율을 포함하는 딕셔너리입니다."
    )
