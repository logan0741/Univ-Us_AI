"""수집 CLI.

  python -m src.collect.cli login              # 브라우저에서 직접 로그인 → 세션 저장
  python -m src.collect.cli collect syllabus   # 한 소스 수집
  python -m src.collect.cli collect-all        # 전체 수집
  python -m src.collect.cli status             # 세션·소스별 마지막 실행
  python -m src.collect.cli sources            # 소스 목록

비밀번호는 저장하지 않습니다. 수집물·세션은 전부 data/ (gitignored) 에 저장됩니다.
"""
from __future__ import annotations

import typer

from . import runlog, session
from .config import SOURCES, settings

app = typer.Typer(add_completion=False, help="JNU 학사 데이터 수집 (본인 세션 기반)")


@app.command("login")
def cmd_login():
    """브라우저를 띄워 직접 로그인하고 세션만 저장합니다 (화면 있는 곳에서 실행)."""
    session.login()


@app.command("sources")
def cmd_sources():
    """수집 가능한 소스 목록."""
    for s in SOURCES:
        typer.echo(f"  {s:16} {settings.url_for(s)}")


@app.command("collect")
def cmd_collect(
    source: str = typer.Argument(..., help=f"{', '.join(SOURCES)} 중 하나"),
    tag: str = typer.Option("service", help="eval / train / service (§5.3)"),
):
    """한 소스를 수집합니다."""
    from .sources import REGISTRY

    if source not in REGISTRY:
        typer.echo(f"알 수 없는 소스: {source}\n가능: {', '.join(SOURCES)}")
        raise typer.Exit(1)
    REGISTRY[source]().run(tag=tag)


@app.command("collect-all")
def cmd_collect_all(tag: str = typer.Option("service")):
    """모든 소스를 순서대로 수집합니다."""
    from .sources import REGISTRY

    if not session.has_session():
        typer.echo("세션이 없습니다. 먼저 `login` 을 실행하세요.")
        raise typer.Exit(1)
    for cls in REGISTRY.values():
        cls().run(tag=tag)


@app.command("status")
def cmd_status():
    """세션 유효성과 소스별 마지막 실행을 보여줍니다."""
    typer.echo(f"세션 파일 : {settings.session_path}")
    typer.echo(f"세션 상태 : {'있음' if session.has_session() else '없음 — login 필요'}")
    typer.echo("소스별 마지막 실행:")
    for s in SOURCES:
        last = runlog.last_run(s)
        if last is None:
            typer.echo(f"  {s:16} (실행 이력 없음)")
        else:
            typer.echo(
                f"  {s:16} {last['ts']}  {last['status']}"
                f"  (신규 {last['items_new']} · 수정 {last['items_changed']})"
            )


if __name__ == "__main__":
    app()
