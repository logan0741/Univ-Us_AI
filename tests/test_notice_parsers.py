"""공지 게시판 파서 단위 테스트 (합성 HTML, 네트워크 없음)."""
from src.collect.notice import (
    _norm_date,
    _parse_jnu_cms,
    _parse_kboard,
    _parse_wp_kboard,
)


def test_norm_date():
    assert _norm_date("2026.08.10") == "2026-08-10"
    assert _norm_date("2026-8-1") == "2026-08-01"
    assert _norm_date("등록 26.08 13 조회") == "2026-08-13"
    assert _norm_date("날짜없음") == ""


def test_jnu_cms():
    html = """<table><tbody>
      <tr><td>일반공지</td>
          <td><a href="/bbs/aisw/64/1051409/artclView.do">도전장학 안내</a></td>
          <td>인공지능학부</td><td>2026.08.10</td><td>271</td><td></td></tr>
    </tbody></table>"""
    ns = _parse_jnu_cms(html, "https://aisw.jnu.ac.kr/aisw/518/subview.do")
    assert len(ns) == 1
    assert ns[0].title == "도전장학 안내"
    assert ns[0].url == "https://aisw.jnu.ac.kr/bbs/aisw/64/1051409/artclView.do"
    assert ns[0].date == "2026-08-10"
    assert ns[0].category == "일반공지"


def test_kboard_movepageview():
    html = """<table><tbody>
      <tr><td>Notice</td>
          <td><a href="javascript:movePageView(4091);">교육과정 안내 New</a></td>
          <td>2026.08.10</td><td>275</td></tr>
    </tbody></table>"""
    ns = _parse_kboard(html, "https://www.aicoss.kr/www/notice/?cate=x")
    assert len(ns) == 1
    assert ns[0].url == "https://www.aicoss.kr/www/notice/view/4091?bd=notice"
    assert ns[0].date == "2026-08-10"
    assert "New" not in ns[0].title


def test_wp_kboard():
    html = """<table><tbody>
      <tr><td>26.08 13 <a href="/notice/notice-board/?uid=1001&mod=document">마일리지 공지</a></td></tr>
    </tbody></table>"""
    ns = _parse_wp_kboard(html, "https://sojoong.kr/notice/notice-board/")
    assert len(ns) == 1
    assert ns[0].url == "https://sojoong.kr/notice/notice-board/?uid=1001&mod=document"
    assert ns[0].date == "2026-08-13"
