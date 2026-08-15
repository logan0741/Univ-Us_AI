"""수집 저장·중복판별·마스킹 단위 테스트.

로그인이 필요 없는 순수 로직만 테스트한다.
(브라우저·세션이 필요한 부분은 실제 로그인 후 수동 확인)
"""
import importlib

import pytest


@pytest.fixture()
def collect_env(tmp_path, monkeypatch):
    """data/ 를 임시 폴더로 바꿔 실제 디스크에 안 남게."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # settings 는 import 시점에 고정되므로 config 를 리로드
    from src.collect import config as cfg
    importlib.reload(cfg)
    cfg.settings.data_dir = tmp_path
    import src.collect.storage as storage
    importlib.reload(storage)
    return storage


def test_save_new_then_duplicate(collect_env):
    storage = collect_env
    data = b"<html>syllabus v1</html>"

    r1 = storage.save_original(source="syllabus", item_id="x", url="u", data=data)
    assert r1.is_new and not r1.is_changed

    # 같은 내용 재수집 → 신규도 수정도 아님 (중복 스킵)
    r2 = storage.save_original(source="syllabus", item_id="x", url="u", data=data)
    assert not r2.is_new and not r2.is_changed
    assert r2.raw_path == r1.raw_path  # 원문 다시 저장 안 함


def test_change_detection(collect_env):
    storage = collect_env
    storage.save_original(source="syllabus", item_id="x", url="u", data=b"v1")
    r = storage.save_original(source="syllabus", item_id="x", url="u", data=b"v2")
    assert r.is_changed and not r.is_new  # §4.3 수정 감지


def test_hash_stable(collect_env):
    storage = collect_env
    assert storage.content_hash(b"abc") == storage.content_hash(b"abc")
    assert storage.content_hash(b"abc") != storage.content_hash(b"abd")


def test_pii_masking():
    from src.collect import pii
    masked = pii.mask("홍길동 010-1234-5678 학번 201812345 test@jnu.ac.kr")
    assert "010-1234-5678" not in masked
    assert "201812345" not in masked
    assert "test@jnu.ac.kr" not in masked
    assert pii.mask_name("홍길동") == "홍*동"
    assert pii.mask_name("김이") == "김*"
