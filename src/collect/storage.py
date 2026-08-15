"""원문 보존 + 메타 + 중복 판별 (수집 계획서 §5).

핵심 원칙(§5.1): 변환 전 원문을 반드시 보존한다.
파싱 결과만 저장하면 파싱 로직 개선 시 재처리가 불가능하다.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from .config import settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _now_stamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class SaveResult:
    source: str
    item_id: str
    raw_path: str
    hash: str
    is_new: bool          # 처음 보는 내용인가
    is_changed: bool      # 같은 id 인데 내용이 바뀌었나 (§4.3 수정 감지)
    fetched_at: str


def _load_index(source: str) -> dict[str, dict]:
    """중복 인덱스: item_id -> {hash, url, first_seen, last_seen}."""
    path = settings.index_path(source)
    if not path.exists():
        return {}
    idx: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rec = json.loads(line)
            idx[rec["item_id"]] = rec
    return idx


def _write_index(source: str, idx: dict[str, dict]) -> None:
    path = settings.index_path(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in idx.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def save_original(
    *,
    source: str,
    item_id: str,
    url: str,
    data: bytes,
    ext: str = "html",
    tag: str = "service",
    extra_meta: dict | None = None,
) -> SaveResult:
    """원문을 저장하고 중복·수정 여부를 판별한다.

    §4.3 중복 판별: 우선순위대로 item_id 를 만들어 넘긴다(호출부 책임).
    같은 item_id + 같은 hash → 스킵 대상(is_new=False, is_changed=False).
    같은 item_id + 다른 hash → 수정됨(is_changed=True).
    """
    h = content_hash(data)
    idx = _load_index(source)
    prev = idx.get(item_id)

    is_new = prev is None
    is_changed = (prev is not None) and (prev.get("hash") != h)
    fetched_at = _now_iso()

    # 내용이 그대로면 원문을 다시 저장하지 않는다 (디스크 절약).
    if not is_new and not is_changed:
        return SaveResult(source, item_id, prev["raw_path"], h, False, False, fetched_at)

    raw_dir = settings.raw_dir(source)
    raw_dir.mkdir(parents=True, exist_ok=True)
    safe_id = item_id.replace("/", "_").replace("\\", "_")[:80]
    raw_path = raw_dir / f"{_now_stamp()}__{safe_id}.{ext}"
    raw_path.write_bytes(data)

    meta_dir = settings.meta_dir(source)
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "source": source,
        "item_id": item_id,
        "url": url,
        "raw_path": str(raw_path),
        "hash": h,
        "bytes": len(data),
        "tag": tag,                 # eval / train / service (§5.3)
        "fetched_at": fetched_at,
        **(extra_meta or {}),
    }
    (meta_dir / f"{safe_id}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    idx[item_id] = {
        "item_id": item_id,
        "url": url,
        "hash": h,
        "raw_path": str(raw_path),
        "first_seen": prev["first_seen"] if prev else fetched_at,
        "last_seen": fetched_at,
    }
    _write_index(source, idx)

    return SaveResult(source, item_id, str(raw_path), h, is_new, is_changed, fetched_at)
