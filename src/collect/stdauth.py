"""StdAuth 재학인증 (jnuapi.jnu.ac.kr) — 선택 유틸.

용도: 대량 수집이 아니라 **가입 시 1인 재학 확인**이다.
      사용자가 자기 학번·이름을 넣어 "실제 재학생인가"를 확인한다.
      명부 전체를 내려받는 GetAllUsers 계열은 쓰지 않는다(개인정보 최소수집).

주의:
  · apikey 가 필요하다(학교 발급). .env 의 JNU_STDAUTH_APIKEY.
  · jnuapi 는 중간 인증서를 안 보내 체인이 불완전하다(학교 서버 설정).
    → 정식 사용 시 학교가 준 중간 인증서를 verify 로 지정한다.
      임시로 verify 를 끄지 말 것(중간자 위험). 미설정이면 이 함수는 막혀 있다.
"""
from __future__ import annotations

import httpx

from .config import settings


def verify_student(*, userid: str, kname: str, snumber: str, ca_bundle: str | None = None) -> str:
    """재학 여부를 확인한다. ca_bundle(학교가 준 인증서 경로)이 있어야 동작한다."""
    if not settings.jnu_stdauth_apikey:
        raise RuntimeError("JNU_STDAUTH_APIKEY 가 비어 있습니다. 학교에서 발급받아 .env 에 넣으세요.")
    if not ca_bundle:
        raise RuntimeError(
            "jnuapi 는 인증서 체인이 불완전합니다. 학교가 준 중간 인증서 경로를 ca_bundle 로 넘기세요. "
            "(verify=False 로 우회하지 마세요 — 중간자 공격 위험)"
        )
    params = {
        "apikey": settings.jnu_stdauth_apikey,
        "userid": userid,
        "kname": kname,
        "snumber": snumber,
    }
    with httpx.Client(verify=ca_bundle, timeout=15) as client:
        r = client.get(f"{settings.jnu_stdauth_base_url}/api/StdAuth", params=params)
        r.raise_for_status()
        return r.text
