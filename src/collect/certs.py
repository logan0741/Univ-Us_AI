"""불완전한 인증서 체인(중간 인증서 누락) 대응 — 공용 CA 번들.

일부 한국 사이트(jnu.ac.kr, all-con.co.kr 등)는 서버가 중간 인증서를 안 보내
검증이 실패한다. AIA 로 중간 인증서를 받아 certifi 번들에 합쳐 캐시한다.
verify=False 로 우회하지 않는다.
"""
from __future__ import annotations

import ssl
from contextlib import suppress
from pathlib import Path

import certifi
import httpx

# 여러 사이트가 공통으로 쓰는 Sectigo DV 중간 인증서
_INTERMEDIATES = [
    "http://crt.sectigo.com/SectigoPublicServerAuthenticationCADVR36.crt",
]
_BUNDLE = Path.home() / ".cache" / "univus" / "ca_bundle.pem"


def bundle() -> str:
    """certifi + 중간 인증서 결합 번들 경로를 반환(없으면 생성·캐시)."""
    if _BUNDLE.exists():
        return str(_BUNDLE)
    _BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    pems = [certifi.contents()]
    for url in _INTERMEDIATES:
        with suppress(Exception):  # 중간 인증서 못 받아도 기본 번들은 동작
            der = httpx.get(url, timeout=15).content
            pems.append(ssl.DER_cert_to_PEM_cert(der))
    _BUNDLE.write_text("\n".join(pems), encoding="utf-8")
    return str(_BUNDLE)
