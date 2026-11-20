"""라우터가 쓰는 앱 컨테이너 (main.create_app에서 채운다)."""

from fastapi import Request


def container(request: Request):
    return request.app.state.container
