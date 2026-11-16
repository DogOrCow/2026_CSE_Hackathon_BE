"""Gmail API 갱신 토큰(refresh token)을 한 번 발급받는 스크립트 (A).

배포 서버는 이 토큰으로 인증 메일을 보낸다 (app/services/mail.py).
Google Cloud에서 "데스크톱 앱" OAuth 클라이언트를 만든 뒤 로컬에서 실행한다.

    python -m scripts.gmail_token

1. 클라이언트 ID와 비밀번호를 입력하면 브라우저가 열린다.
2. 메일을 보낼 Gmail 계정으로 로그인하고 "메일 보내기" 권한을 허용한다.
3. 화면에 나온 GMAIL_REFRESH_TOKEN을 Railway api 서비스 변수에 넣는다.

토큰은 화면에만 출력하고 파일로 저장하지 않는다. 저장소에 올리지 않는다.
"""

import base64
import getpass
import hashlib
import json
import secrets
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/gmail.send"


class _Handler(BaseHTTPRequestHandler):
    result: dict = {}

    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _Handler.result = {k: v[0] for k, v in query.items()}
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("완료. 이 창을 닫고 터미널로 돌아가세요.".encode())

    def log_message(self, *args):
        pass


def main() -> None:
    client_id = input("GMAIL_CLIENT_ID: ").strip()
    client_secret = getpass.getpass("GMAIL_CLIENT_SECRET (입력이 안 보여도 정상): ").strip()

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}"
    state = secrets.token_urlsafe(16)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()

    url = AUTH_URL + "?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    print("\n브라우저에서 메일을 보낼 Gmail 계정으로 로그인하고 권한을 허용하세요.")
    print("브라우저가 안 열리면 아래 주소를 직접 여세요:\n" + url + "\n")
    webbrowser.open(url)

    while not _Handler.result:
        server.handle_request()
    result = _Handler.result
    if result.get("state") != state or "code" not in result:
        raise SystemExit(f"인증 실패: {result.get('error', 'state 불일치')}")

    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": result["code"],
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
    ).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=body, method="POST"), timeout=10) as res:
        tokens = json.loads(res.read())

    refresh = tokens.get("refresh_token")
    if not refresh:
        raise SystemExit("갱신 토큰이 오지 않았습니다. Google 계정의 앱 권한에서 이 앱을 삭제한 뒤 다시 실행하세요.")
    print("Railway api 서비스 변수에 넣을 값:\n")
    print(f"GMAIL_REFRESH_TOKEN={refresh}\n")


if __name__ == "__main__":
    main()
