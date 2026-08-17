"""첨부파일·이미지 다운로드 — 상세 크롤링 시 원문 바이너리 보존.

data/raw/<source>/files/ 아래에 저장하고 로컬 경로를 반환한다.
모든 수집기가 상세로 들어가면 이걸로 pdf/이미지를 함께 내려받는다.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from .config import settings


def _safe_name(url: str, fallback_ext: str = "") -> str:
    path = unquote(urlparse(url).path)
    name = Path(path).name or hashlib.sha1(url.encode()).hexdigest()[:12]
    name = re.sub(r"[^\w.\-가-힣]", "_", name)[:80]
    if "." not in name and fallback_ext:
        name += fallback_ext
    return name


def download(url: str, source: str, client: httpx.Client, *,
             subdir: str = "files") -> dict | None:
    """url 을 내려받아 data/raw/<source>/<subdir>/ 에 저장. 메타(dict) 반환."""
    try:
        r = client.get(url)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001 — 개별 첨부 실패는 스킵
        return {"url": url, "error": repr(e)}
    ct = r.headers.get("content-type", "")
    ext = ".pdf" if "pdf" in ct else (".png" if "png" in ct else (".jpg" if "jpeg" in ct else ""))
    d = settings.raw_dir(source) / subdir
    d.mkdir(parents=True, exist_ok=True)
    fname = _safe_name(url, ext)
    (d / fname).write_bytes(r.content)
    return {"url": url, "path": str(d / fname), "bytes": len(r.content), "content_type": ct}
