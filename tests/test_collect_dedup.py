"""중복 판별·방지 단위 테스트 (src/collect/dedup)."""
import importlib

import pytest


@pytest.fixture()
def dd(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from src.collect import config as cfg
    importlib.reload(cfg)
    cfg.settings.data_dir = tmp_path
    from src.collect import dedup
    importlib.reload(dedup)
    dedup.reset_cache()
    return dedup


def test_content_key_stable_and_distinct(dd):
    a = dd.content_key("제목", "본문 내용입니다")
    b = dd.content_key(" 제목 ", "본문   내용입니다!")   # 공백·기호만 다름
    c = dd.content_key("제목", "다른 본문")
    assert a == b       # 정규화로 같은 글로 판정
    assert a != c


def test_file_registry_dedup(dd):
    h = dd.file_hash(b"same-bytes")
    assert dd.seen_file(h) is None
    dd.remember_file(h, "data/raw/x/a.jpg")
    dd.reset_cache()                     # 디스크에서 다시 로드
    assert dd.seen_file(h) is None       # 파일이 실제로 없으면 None (경로 검증)


def test_content_registry(dd):
    k = dd.content_key("공지", "본문")
    assert dd.seen_content(k) is None
    dd.remember_content(k, source="notice_aisw", item_id="u1", url="u1")
    dd.reset_cache()
    rec = dd.seen_content(k)
    assert rec and rec["source"] == "notice_aisw"


def test_audit_finds_duplicate_files(dd, tmp_path):
    raw = tmp_path / "raw" / "s" / "poster"
    raw.mkdir(parents=True)
    (raw / "a.jpg").write_bytes(b"POSTER")
    (raw / "b.jpg").write_bytes(b"POSTER")     # 같은 바이트
    (raw / "c.jpg").write_bytes(b"OTHER")
    s = dd.audit(out=str(tmp_path / "r.md"))
    assert s["file_dup_groups"] == 1
    assert s["extra_files"] == 1
