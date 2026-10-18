"""Email verification transport for Somang Pharmacy.

Requires a separately verified Somang sender domain and private Render
environment variables SOMANG_MAIL_API_KEY and SOMANG_MAIL_FROM.
No email is sent when either is absent.
"""
import json
import os
from urllib.request import Request, urlopen
from urllib.parse import urlparse


def mail_ready():
    sender = os.environ.get("SOMANG_MAIL_FROM", "").strip()
    key = os.environ.get("SOMANG_MAIL_API_KEY", "")
    return bool(key and sender and "@" in sender)


def send_verification_email(recipient, token):
    if not mail_ready():
        raise RuntimeError("Somang email delivery is not configured")
    origin = os.environ.get("SOMANG_PUBLIC_ORIGIN", "https://somang-pharmacy-preview.onrender.com").rstrip("/")
    parsed = urlparse(origin)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise RuntimeError("Invalid public origin")
    # Never log or persist this URL: it contains a one-time verification secret.
    from urllib.parse import quote
    link = origin + "/members/verify?token=" + quote(token, safe="")
    payload = {
        "from": os.environ["SOMANG_MAIL_FROM"],
        "to": [recipient],
        "subject": "소망약국 이메일 인증",
        "text": "소망약국 이메일 인증을 요청하셨습니다. 30분 이내 아래 주소를 열어 주세요.\n"
                + link + "\n본인이 요청하지 않았다면 이 메일을 무시하세요.",
    }
    req = Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + os.environ["SOMANG_MAIL_API_KEY"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(req, timeout=10) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError("Verification mail delivery failed")
    return True
