"""소스별 수집기.

각 파일은 Collector 를 상속해 fetch_items() 만 구현한다.
현재는 '원문 저장'까지 구현되어 있고, 정확한 필드 추출(파서)은
실제 로그인 페이지의 HTML 표본을 본 뒤 붙인다(수집 계획서 §5.1 순서).
"""
from .eclass import EclassCollector
from .sugang_courses import SugangCoursesCollector
from .syllabus import SyllabusCollector
from .timetable import TimetableCollector

REGISTRY = {
    "sugang_courses": SugangCoursesCollector,
    "timetable": TimetableCollector,
    "syllabus": SyllabusCollector,
    "eclass": EclassCollector,
}
