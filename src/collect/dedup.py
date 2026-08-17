"""중복 저장 점검·방지 (수집 계획서 §4.3).

두 가지를 제공한다.
  1) 전체 점검(batch)  : audit() — data/ 전체를 훑어 겹쳐 저장된 것을 찾아 보고.
  2) 크롤링 중 방지(guard): seen_file()/remember_file(), seen_content()/remember_content()
     — 저장 직전에 호출해 '이미 있는 내용이면 저장 안 함'.

판별은 전부 **결정적(deterministic)** 이다.
  · 파일  : 바이트 sha256 이 같으면 같은 파일 (이미지·PDF·첨부)
  · 레코드: 제목+본문을 정규화한 sha256 이 같으면 같은 공지/공모전 (게시판·카테고리 넘나듦)

의미가 비슷하지만 표현이 다른 '유사 중복'(같은 행사, 다른 문장)은 여기서 걸러지지 않는다.
그건 나중에 notice_ai-agent(LLM 임베딩 유사도)로 처리한다 — 지금은 정확 일치만.
"""
from __future__ import annotations

import glob
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import settings

_FILE_REG = "index/_file_hashes.jsonl"      # 파일 sha256 -> 경로
_CONTENT_REG = "index/_content_keys.jsonl"  # 내용키 -> {source,item_id,url}

_file_cache: dict[str, str] | None = None
_content_cache: dict[str, dict] | None = None


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def reset_cache() -> None:
    """테스트/재빌드용 — 메모리 캐시를 비운다."""
    global _file_cache, _content_cache
    _file_cache = None
    _content_cache = None


# ── 정규화·키 ────────────────────────────────────────────────
def norm(s: str) -> str:
    """비교용 정규화 — 공백·기호를 지워 표기 흔들림을 흡수."""
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^0-9a-z가-힣 ]", "", s)
    return s.strip()


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_key(title: str, body: str) -> str:
    """제목+본문 정규화 sha256 — 게시판이 달라도 같은 글이면 같은 키."""
    base = norm(title) + "\n" + norm(body)[:2000]
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


# ── 파일 레지스트리 (크롤링 중 방지) ─────────────────────────
def _reg_path(name: str) -> Path:
    return settings.data_dir / name


def _load_file_reg() -> dict[str, str]:
    global _file_cache
    if _file_cache is not None:
        return _file_cache
    p = _reg_path(_FILE_REG)
    reg: dict[str, str] = {}
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                reg[r["hash"]] = r["path"]
    else:
        # 최초 1회: 기존 raw 파일을 훑어 시드 (이후엔 append 로 유지)
        reg = _seed_file_reg(p)
    _file_cache = reg
    return reg


def _seed_file_reg(p: Path) -> dict[str, str]:
    reg: dict[str, str] = {}
    raw = settings.data_dir / "raw"
    if not raw.exists():
        return reg
    rows = []
    for f in sorted(raw.rglob("*")):
        if f.is_file():
            h = file_hash(f.read_bytes())
            if h not in reg:
                reg[h] = str(f)
                rows.append({"hash": h, "path": str(f), "first_seen": ""})
    if rows:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return reg


def seen_file(h: str) -> str | None:
    """이 해시의 파일이 이미 저장돼 있으면 그 경로를, 없으면 None."""
    path = _load_file_reg().get(h)
    return path if path and Path(path).exists() else None


def remember_file(h: str, path: str) -> None:
    reg = _load_file_reg()
    if h in reg:
        return
    reg[h] = path
    p = _reg_path(_FILE_REG)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"hash": h, "path": path, "first_seen": _now()},
                            ensure_ascii=False) + "\n")


# ── 내용 레지스트리 (게시판 간 중복 방지) ────────────────────
def _load_content_reg() -> dict[str, dict]:
    global _content_cache
    if _content_cache is not None:
        return _content_cache
    p = _reg_path(_CONTENT_REG)
    reg: dict[str, dict] = {}
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                reg[r["key"]] = r
    _content_cache = reg
    return reg


def seen_content(key: str) -> dict | None:
    """같은 내용이 이미 저장돼 있으면 그 레코드({source,item_id,url})를, 없으면 None."""
    return _load_content_reg().get(key)


def remember_content(key: str, *, source: str, item_id: str, url: str) -> None:
    reg = _load_content_reg()
    if key in reg:
        return
    rec = {"key": key, "source": source, "item_id": item_id, "url": url, "first_seen": _now()}
    reg[key] = rec
    p = _reg_path(_CONTENT_REG)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ── 전체 점검(batch) ─────────────────────────────────────────
def _scan_files() -> dict[str, list[str]]:
    """raw 전체 → 해시별 파일 목록 (2개 이상이면 중복)."""
    by_hash: dict[str, list[str]] = {}
    raw = settings.data_dir / "raw"
    if raw.exists():
        for f in sorted(raw.rglob("*")):
            if f.is_file():
                by_hash.setdefault(file_hash(f.read_bytes()), []).append(str(f))
    return by_hash


def _scan_records() -> dict[str, list[dict]]:
    """processed 공지 상세 + allcon/external 항목 → 내용키별 목록."""
    by_key: dict[str, list[dict]] = {}

    def add(title, body, source, ref):
        by_key.setdefault(content_key(title or "", body or ""), []).append(
            {"source": source, "ref": ref, "title": (title or "")[:60]})

    for f in glob.glob(str(settings.data_dir / "processed/notices/*/*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        add(d.get("title"), d.get("body"), f"notice_{Path(f).parent.name}", Path(f).name)
    for f in glob.glob(str(settings.data_dir / "processed/allcon/*/*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for it in d.get("items", []):
            add(it.get("title"), it.get("body", ""), f"allcon_{Path(f).parent.name}", it.get("id"))
    for f in glob.glob(str(settings.data_dir / "processed/external/*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for it in d.get("items", []):
            add(it.get("title"), "", Path(f).stem, it.get("id"))
    return by_key


def audit(*, fix: bool = False, out: str = "docs/중복-점검.md",
          rebuild_registry: bool = True) -> dict:
    """data/ 전체를 훑어 중복을 보고한다. rebuild_registry=True 면 방지용 레지스트리도 갱신."""
    by_hash = _scan_files()
    file_dups = {h: fs for h, fs in by_hash.items() if len(fs) > 1}
    extra_files = sum(len(fs) - 1 for fs in file_dups.values())
    waste = sum(Path(fs[0]).stat().st_size * (len(fs) - 1) for fs in file_dups.values())

    by_key = _scan_records()
    rec_dups = {k: rs for k, rs in by_key.items()
                if len({r["source"] + str(r["ref"]) for r in rs}) > 1}

    quarantined = 0
    if fix and file_dups:
        qdir = settings.data_dir / "_dupes"
        for fs in file_dups.values():
            for extra in sorted(fs)[1:]:                 # 첫 파일만 남기고 격리
                src = Path(extra)
                dst = qdir / src.relative_to(settings.data_dir)
                dst.parent.mkdir(parents=True, exist_ok=True)
                src.rename(dst)
                quarantined += 1

    if rebuild_registry:
        reset_cache()
        _reg_path(_FILE_REG).unlink(missing_ok=True)
        _load_file_reg()                                 # raw 재시드
        # 내용 레지스트리도 현재 processed 기준으로 재작성
        cp = _reg_path(_CONTENT_REG)
        cp.parent.mkdir(parents=True, exist_ok=True)
        with cp.open("w", encoding="utf-8") as fh:
            for k, rs in by_key.items():
                r0 = rs[0]
                fh.write(json.dumps({"key": k, "source": r0["source"],
                                     "item_id": str(r0["ref"]), "url": "",
                                     "first_seen": ""}, ensure_ascii=False) + "\n")
        reset_cache()

    summary = {"file_dup_groups": len(file_dups), "extra_files": extra_files,
               "waste_mb": round(waste / 1024 / 1024, 2),
               "record_dup_groups": len(rec_dups), "quarantined": quarantined}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(_report_md(summary, file_dups, rec_dups, fix), encoding="utf-8")
    return summary


def _rel(p: str) -> str:
    try:
        return str(Path(p).relative_to(settings.data_dir))
    except ValueError:
        return p


def _report_md(s: dict, file_dups: dict, rec_dups: dict, fixed: bool) -> str:
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    L = ["# 중복 저장 점검", "", f"> `data/` 스캔 자동 생성. 최종 갱신: {now}", "",
         "재실행: `python -m src.collect.cli dedup` (격리까지: `--fix`)", "", "---", "",
         "## 요약", "",
         "| 항목 | 값 |", "| --- | ---: |",
         f"| 파일 중복 그룹 | {s['file_dup_groups']} |",
         f"| 여분 파일 | {s['extra_files']} |",
         f"| 낭비 용량 | {s['waste_mb']}MB |",
         f"| 내용 중복 그룹(게시판·카테고리 간) | {s['record_dup_groups']} |",
         f"| 이번에 격리한 파일 | {s['quarantined']} |", "",
         "판별 기준: 파일=바이트 sha256, 내용=제목+본문 정규화 sha256(정확 일치).",
         "표현만 다른 유사 중복은 추후 LLM 임베딩으로 별도 처리.", "", "---", ""]

    L += ["## 파일 중복 (같은 바이트가 여러 곳에)", ""]
    if not file_dups:
        L.append("없음.")
    else:
        for h, fs in list(file_dups.items())[:50]:
            L.append(f"- `{h[:12]}` × {len(fs)} — " + " · ".join(_rel(x) for x in fs[:4]))
        if len(file_dups) > 50:
            L.append(f"- … 외 {len(file_dups) - 50}그룹")
    L += ["", "## 내용 중복 (게시판·카테고리 넘나든 같은 글)", ""]
    if not rec_dups:
        L.append("없음.")
    else:
        for _k, rs in list(rec_dups.items())[:50]:
            srcs = " · ".join(sorted({r["source"] for r in rs}))
            L.append(f"- \"{rs[0]['title']}\" — {srcs}")
        if len(rec_dups) > 50:
            L.append(f"- … 외 {len(rec_dups) - 50}그룹")
    L += ["", "---", "",
          "## 앞으로 중복이 안 쌓이게",
          "- 다운로드(이미지·PDF·첨부)는 `download` 가 바이트 해시로 같은 파일을 재저장하지 않습니다.",
          "- 공지 상세는 게시판이 달라도 같은 글이면 저장하지 않습니다(내용키).",
          "- 위 두 방지는 이 점검이 만든 레지스트리(`data/index/_*_.jsonl`)를 참조합니다.", ""]
    if fixed:
        L += ["", f"> `--fix` 로 여분 파일 {s['quarantined']}개를 `data/_dupes/` 로 옮겼습니다(삭제 아님)."]
    return "\n".join(L)
