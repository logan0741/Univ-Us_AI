"""시간표 파서 단위 테스트 (LLM 없이 결정적)."""
from src.collect.parse.timetable import parse_timetable

# 최소 합성 시간표: DSC0010-1 이 월요일 1~2교시(09:00~11:00) 2슬롯,
# ECE3043-1 이 화요일 1교시(09:00~10:00) 1슬롯.
FIXTURE = """
<table>
<tr><th>시간</th><th>월요일</th><th>화요일</th><th>수요일</th>
    <th>목요일</th><th>금요일</th><th>토요일</th></tr>
<tr><td>09:00</td>
    <td>[ 1 교시 ]<br>인공지능로봇실습<br>담당교수 :방도연<br>도서관별관316<br>DSC0010-1<br>[대면수업]</td>
    <td>[ 1 교시 ]<br>시스템프로그래밍<br>담당교수 :박혁로<br>공7-217<br>ECE3043-1<br>[대면수업]</td>
    <td></td><td></td><td></td><td></td></tr>
<tr><td>09:30</td>
    <td>[ 1 교시 ]<br>인공지능로봇실습<br>담당교수 :방도연<br>도서관별관316<br>DSC0010-1<br>[대면수업]</td>
    <td>[ 1 교시 ]<br>시스템프로그래밍<br>담당교수 :박혁로<br>공7-217<br>ECE3043-1<br>[대면수업]</td>
    <td></td><td></td><td></td><td></td></tr>
<tr><td>10:00</td>
    <td>[ 2 교시 ]<br>인공지능로봇실습<br>담당교수 :방도연<br>도서관별관316<br>DSC0010-1<br>[대면수업]</td>
    <td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>10:30</td>
    <td>[ 2 교시 ]<br>인공지능로봇실습<br>담당교수 :방도연<br>도서관별관316<br>DSC0010-1<br>[대면수업]</td>
    <td></td><td></td><td></td><td></td><td></td></tr>
</table>
"""


def _course(data, code):
    return next(c for c in data["courses"] if c["code"] == code)


def test_parse_basic():
    data = parse_timetable(FIXTURE)
    assert len(data["courses"]) == 2

    dsc = _course(data, "DSC0010")
    assert dsc["class_no"] == "1"
    assert dsc["subject"] == "인공지능로봇실습"
    assert dsc["professor"] == "방도연"
    assert dsc["type"] == "대면수업"
    # 월요일 1개 모임, 09:00~11:00, 1·2교시
    assert len(dsc["meetings"]) == 1
    m = dsc["meetings"][0]
    assert m["day"] == "월"
    assert m["start"] == "09:00"
    assert m["end"] == "11:00"        # 마지막 슬롯 10:30 + 30분
    assert m["periods"] == [1, 2]
    assert m["room"] == "도서관별관316"


def test_single_slot_end_time():
    data = parse_timetable(FIXTURE)
    ece = _course(data, "ECE3043")
    m = ece["meetings"][0]
    assert m["day"] == "화"
    assert m["start"] == "09:00"
    assert m["end"] == "10:00"        # 09:00,09:30 → 09:30+30
    assert m["periods"] == [1]
