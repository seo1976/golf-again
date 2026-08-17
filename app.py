import os
import sqlite3
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "somang_pharmacy.db")

PHARMACY_NAME = "소망약국"
PHARMACY_TAGLINE = "가까이에서 건강을 함께 살피는 약국"
PHONE = "전화번호 입력"
ADDRESS = "주소 입력"
HOURS = "영업시간 입력"
MAP_LINK = "#"

ADMIN_ID = os.environ.get("ADMIN_ID", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me-1234")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "somang-pharmacy-change-this-secret")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS admins(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        views INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    admin = conn.execute("SELECT * FROM admins WHERE username=?", (ADMIN_ID,)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO admins(username, password_hash) VALUES(?,?)",
            (ADMIN_ID, generate_password_hash(ADMIN_PASSWORD))
        )
    count = conn.execute("SELECT COUNT(*) AS c FROM posts").fetchone()["c"]
    if count == 0:
        conn.executemany(
            "INSERT INTO posts(category,title,content) VALUES(?,?,?)",
            [
                ("공지사항", "소망약국 홈페이지에 오신 것을 환영합니다.", "소망약국 홈페이지가 새롭게 문을 열었습니다.\n약국 소식과 건강정보를 이곳에서 전해드리겠습니다."),
                ("건강정보", "복용 중인 약이 여러 개라면 꼭 알려주세요.", "병원이나 약국을 이용할 때 현재 복용 중인 처방약, 일반의약품, 건강기능식품을 함께 알려주시면 복약상담에 도움이 됩니다."),
                ("약국소식", "소망약국 게시판을 운영합니다.", "공지사항, 일반 건강정보, 약국소식을 게시판을 통해 안내드릴 예정입니다.")
            ]
        )
    conn.commit()
    conn.close()


init_db()


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            flash("관리자 로그인이 필요합니다.")
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)
    return wrapper


BASE_HTML = r'''
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} | {{ pharmacy_name }}</title>
<style>
*{box-sizing:border-box}:root{--green:#2f6b57;--green2:#edf6f1;--deep:#173c31;--line:#e4ebe6;--text:#202823;--muted:#6d776f}
body{margin:0;background:#f7f9f7;color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Apple SD Gothic Neo","Noto Sans KR",Arial,sans-serif}a{text-decoration:none;color:inherit}
header{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}.nav{max-width:1100px;margin:auto;padding:15px 18px;display:flex;align-items:center;gap:18px}.logo{font-size:25px;font-weight:900;color:var(--green);white-space:nowrap}.navlinks{margin-left:auto;display:flex;gap:15px;align-items:center;font-size:14px}.wrap{max-width:1100px;margin:auto;padding:27px 18px 70px}
.flash{background:#fff5cc;border:1px solid #eadb8b;padding:11px 13px;border-radius:10px;margin-bottom:14px}.hero{background:linear-gradient(135deg,#2f6b57,#4c8a73);color:#fff;border-radius:24px;padding:48px 35px;display:grid;grid-template-columns:1.3fr .7fr;align-items:center;gap:20px}.hero h1{font-size:40px;margin:0 0 12px;letter-spacing:-2px}.hero p{margin:0;line-height:1.75}.hero-icon{text-align:center;font-size:92px}
.quick{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:18px}.quick a{background:#fff;border:1px solid var(--line);border-radius:15px;padding:18px;text-align:center;font-weight:800}.section{margin-top:35px}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:19px}.card h3{margin:0 0 9px;color:var(--deep)}.muted{color:var(--muted);font-size:13px}
.board{background:#fff;border:1px solid var(--line);border-radius:16px;overflow:hidden}.board-row{display:grid;grid-template-columns:110px 1fr 120px 75px;gap:10px;padding:14px 16px;border-bottom:1px solid var(--line);align-items:center}.board-head{background:#f1f6f3;font-weight:800}.cat{display:inline-block;background:var(--green2);color:var(--green);font-size:12px;font-weight:800;padding:5px 8px;border-radius:7px}
.btn{display:inline-block;border:1px solid var(--line);background:#fff;border-radius:10px;padding:10px 13px;font-weight:800;cursor:pointer}.btn.primary{background:var(--green);color:#fff;border-color:var(--green)}.btn.danger{background:#fff0f0;color:#a43b3b;border-color:#efcccc}.toolbar{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:15px}.filters{display:flex;gap:7px;flex-wrap:wrap}.filters a{border:1px solid var(--line);background:#fff;border-radius:18px;padding:7px 11px;font-size:13px}.filters a.on{background:var(--deep);color:#fff}
.form{max-width:760px;margin:auto;background:#fff;border:1px solid var(--line);border-radius:18px;padding:25px}.field{margin:15px 0}.field label{display:block;margin-bottom:7px;font-size:13px;font-weight:800}.field input,.field select,.field textarea{width:100%;padding:12px;border:1px solid #d6dfd8;border-radius:9px;font:inherit}.field textarea{min-height:300px;resize:vertical}.post{background:#fff;border:1px solid var(--line);border-radius:18px;padding:27px}.post h1{margin:10px 0;font-size:28px}.post-content{white-space:pre-wrap;line-height:1.85;margin-top:25px}.notice{background:#f1f6f3;border-radius:12px;padding:14px;line-height:1.7;color:#526158;font-size:13px}
footer{background:#21352d;color:#dce6e0;padding:30px 18px;margin-top:60px}.footer-in{max-width:1100px;margin:auto;font-size:13px;line-height:1.8}.bottom-actions{display:none}
@media(max-width:760px){.navlinks a:nth-child(2),.navlinks a:nth-child(3){display:none}.hero{grid-template-columns:1fr;padding:32px 22px}.hero h1{font-size:31px}.hero-icon{font-size:63px}.quick{grid-template-columns:repeat(3,1fr)}.quick a{padding:14px 5px;font-size:13px}.cards{grid-template-columns:1fr}.board-row{grid-template-columns:80px 1fr}.board-row>div:nth-child(3),.board-row>div:nth-child(4){display:none}.bottom-actions{display:grid;position:fixed;bottom:0;left:0;right:0;z-index:30;grid-template-columns:repeat(3,1fr);background:#fff;border-top:1px solid var(--line)}.bottom-actions a{padding:13px 3px;text-align:center;font-size:13px;font-weight:800}body{padding-bottom:48px}}
</style>
</head>
<body>
<header><div class="nav"><a class="logo" href="{{ url_for('home') }}">{{ pharmacy_name }}</a><div class="navlinks"><a href="{{ url_for('about') }}">약국소개</a><a href="{{ url_for('services') }}">취급안내</a><a href="{{ url_for('board') }}">게시판</a><a href="{{ url_for('location') }}">오시는길</a>{% if session.get('admin') %}<a href="{{ url_for('admin_dashboard') }}">관리자</a>{% endif %}</div></div></header>
<div class="wrap">{% with messages=get_flashed_messages() %}{% for message in messages %}<div class="flash">{{ message }}</div>{% endfor %}{% endwith %}{{ content|safe }}</div>
<div class="bottom-actions"><a href="tel:{{ phone }}">📞 전화하기</a><a href="{{ map_link }}">📍 길찾기</a><a href="{{ url_for('board') }}">📋 게시판</a></div>
<footer><div class="footer-in"><b>{{ pharmacy_name }}</b><br>{{ address }}<br>{{ hours }} · {{ phone }}<br><br>※ 본 홈페이지의 건강정보는 일반적인 정보 제공을 목적으로 하며 개인의 진단이나 치료를 대신하지 않습니다.</div></footer>
</body></html>
'''


def page(title, body, **context):
    content = render_template_string(body, **context)
    return render_template_string(
        BASE_HTML,
        title=title,
        content=content,
        pharmacy_name=PHARMACY_NAME,
        phone=PHONE,
        address=ADDRESS,
        hours=HOURS,
        map_link=MAP_LINK
    )


@app.route("/")
def home():
    conn = db()
    recent = conn.execute("SELECT * FROM posts ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()
    return page("홈", r'''
    <section class="hero"><div><div style="font-weight:800;margin-bottom:8px">SOMANG PHARMACY</div><h1>{{ pharmacy_name }}</h1><p>{{ tagline }}<br>편안하게 상담받을 수 있는 가까운 건강 파트너가 되겠습니다.</p></div><div class="hero-icon">💊</div></section>
    <div class="quick"><a href="tel:{{ phone }}">📞<br>전화하기</a><a href="{{ map_link }}">📍<br>길찾기</a><a href="{{ url_for('board') }}">📋<br>게시판</a></div>
    <section class="section"><h2>소망약국 안내</h2><div class="cards"><div class="card"><h3>💬 복약상담</h3><p>복용 중인 의약품과 건강기능식품에 대해 편안하게 상담해 주세요.</p></div><div class="card"><h3>🧴 취급안내</h3><p>일반의약품, 의약외품, 건강기능식품 등 다양한 건강 관련 제품을 안내합니다.</p></div><div class="card"><h3>🕒 영업시간</h3><p>{{ hours }}</p><p class="muted">방문 전 전화 확인을 권장합니다.</p></div></div></section>
    <section class="section"><div class="toolbar"><h2>최근 게시글</h2><a class="btn" href="{{ url_for('board') }}">전체보기</a></div><div class="board">{% for p in recent %}<a class="board-row" href="{{ url_for('post_detail', post_id=p['id']) }}"><div><span class="cat">{{ p['category'] }}</span></div><div><b>{{ p['title'] }}</b></div><div class="muted">{{ p['created_at'][:10] }}</div><div class="muted">조회 {{ p['views'] }}</div></a>{% endfor %}</div></section>
    <section class="section"><div class="notice"><b>건강정보 안내</b><br>홈페이지의 건강정보는 일반적인 정보 제공을 위한 내용입니다. 증상이나 의약품 복용에 관한 개인별 판단은 의료전문가와 상담해 주세요.</div></section>
    ''', pharmacy_name=PHARMACY_NAME, tagline=PHARMACY_TAGLINE, phone=PHONE, hours=HOURS, map_link=MAP_LINK, recent=recent)


@app.route("/about")
def about():
    return page("약국소개", r'''<div class="post"><span class="cat">약국소개</span><h1>{{ pharmacy_name }}</h1><div class="post-content">소망약국은 지역 주민 여러분이 건강과 의약품에 대해 편안하게 질문하고 상담할 수 있는 약국을 지향합니다.\n\n처방조제 및 일반적인 복약상담, 건강 관련 제품 안내 등 약국에서 필요한 서비스를 정성껏 안내하겠습니다.</div></div>''', pharmacy_name=PHARMACY_NAME)


@app.route("/services")
def services():
    return page("취급안내", r'''<h1>취급안내</h1><div class="cards"><div class="card"><h3>💊 일반의약품</h3><p>증상과 복용 중인 약을 확인한 뒤 복약상담을 제공합니다.</p></div><div class="card"><h3>🩹 의약외품</h3><p>생활 속 건강관리에 필요한 다양한 의약외품을 안내합니다.</p></div><div class="card"><h3>🍊 건강기능식품</h3><p>복용 중인 의약품이나 건강상태를 고려해 상담해 주세요.</p></div><div class="card"><h3>🧴 건강·위생용품</h3><p>개인위생 및 일상 건강관리에 필요한 제품을 안내합니다.</p></div><div class="card"><h3>👨‍👩‍👧 가족 건강용품</h3><p>어린이부터 어르신까지 가족 건강관리에 필요한 제품을 안내합니다.</p></div><div class="card"><h3>💬 복약상담</h3><p>현재 복용 중인 약이나 건강기능식품이 있다면 상담 시 함께 알려주세요.</p></div></div>''')


@app.route("/location")
def location():
    return page("오시는길", r'''<div class="post"><span class="cat">오시는길</span><h1>{{ pharmacy_name }}</h1><p><b>주소</b><br>{{ address }}</p><p><b>전화</b><br>{{ phone }}</p><p><b>영업시간</b><br>{{ hours }}</p><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:20px"><a class="btn primary" href="tel:{{ phone }}">전화하기</a><a class="btn" href="{{ map_link }}">지도에서 길찾기</a></div></div>''', pharmacy_name=PHARMACY_NAME, address=ADDRESS, phone=PHONE, hours=HOURS, map_link=MAP_LINK)


CATEGORIES = ["공지사항", "건강정보", "약국소식"]


@app.route("/board")
def board():
    category = request.args.get("category", "").strip()
    conn = db()
    if category:
        posts = conn.execute("SELECT * FROM posts WHERE category=? ORDER BY id DESC", (category,)).fetchall()
    else:
        posts = conn.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
    conn.close()
    return page("게시판", r'''
    <div class="toolbar"><h1 style="margin:0">게시판</h1>{% if session.get('admin') %}<a class="btn primary" href="{{ url_for('post_new') }}">글쓰기</a>{% endif %}</div>
    <div class="filters"><a class="{% if not category %}on{% endif %}" href="{{ url_for('board') }}">전체</a>{% for c in categories %}<a class="{% if category == c %}on{% endif %}" href="{{ url_for('board', category=c) }}">{{ c }}</a>{% endfor %}</div><div style="height:15px"></div>
    <div class="board"><div class="board-row board-head"><div>분류</div><div>제목</div><div>작성일</div><div>조회</div></div>{% for p in posts %}<a class="board-row" href="{{ url_for('post_detail', post_id=p['id']) }}"><div><span class="cat">{{ p['category'] }}</span></div><div><b>{{ p['title'] }}</b></div><div class="muted">{{ p['created_at'][:10] }}</div><div class="muted">{{ p['views'] }}</div></a>{% else %}<div style="padding:35px;text-align:center;color:#777">등록된 게시글이 없습니다.</div>{% endfor %}</div>
    ''', category=category, categories=CATEGORIES, posts=posts)


@app.route("/post/<int:post_id>")
def post_detail(post_id):
    conn = db()
    conn.execute("UPDATE posts SET views = views + 1 WHERE id=?", (post_id,))
    conn.commit()
    post = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    conn.close()
    if not post:
        return "게시글을 찾을 수 없습니다.", 404
    return page(post["title"], r'''<div class="post"><span class="cat">{{ post['category'] }}</span><h1>{{ post['title'] }}</h1><div class="muted">{{ post['created_at'][:16] }} · 조회 {{ post['views'] }}</div><div class="post-content">{{ post['content'] }}</div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:25px"><a class="btn" href="{{ url_for('board') }}">목록으로</a>{% if session.get('admin') %}<a class="btn primary" href="{{ url_for('post_edit', post_id=post['id']) }}">수정</a><form method="post" action="{{ url_for('post_delete', post_id=post['id']) }}" onsubmit="return confirm('이 글을 삭제할까요?')"><button class="btn danger" type="submit">삭제</button></form>{% endif %}</div></div>''', post=post)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = db()
        admin = conn.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin"] = True
            session["admin_name"] = username
            flash("관리자로 로그인했습니다.")
            return redirect(url_for("admin_dashboard"))
        flash("아이디 또는 비밀번호가 올바르지 않습니다.")
    return page("관리자 로그인", r'''<div class="form"><h2>관리자 로그인</h2><form method="post"><div class="field"><label>아이디</label><input name="username" required></div><div class="field"><label>비밀번호</label><input type="password" name="password" required></div><button class="btn primary" style="width:100%" type="submit">로그인</button></form></div>''')


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("관리자 로그아웃되었습니다.")
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = db()
    posts = conn.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
    conn.close()
    return page("관리자", r'''<div class="toolbar"><h1 style="margin:0">관리자</h1><div style="display:flex;gap:8px"><a class="btn primary" href="{{ url_for('post_new') }}">+ 새 글</a><a class="btn" href="{{ url_for('admin_logout') }}">로그아웃</a></div></div><div class="board">{% for p in posts %}<div class="board-row"><div><span class="cat">{{ p['category'] }}</span></div><div><a href="{{ url_for('post_detail', post_id=p['id']) }}"><b>{{ p['title'] }}</b></a></div><div class="muted">{{ p['created_at'][:10] }}</div><div><a href="{{ url_for('post_edit', post_id=p['id']) }}">수정</a></div></div>{% endfor %}</div>''', posts=posts)


@app.route("/admin/post/new", methods=["GET", "POST"])
@admin_required
def post_new():
    if request.method == "POST":
        category = request.form.get("category", "").strip()
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        if not category or not title or not content:
            flash("분류, 제목, 내용을 모두 입력해주세요.")
            return redirect(url_for("post_new"))
        conn = db()
        conn.execute("INSERT INTO posts(category,title,content) VALUES(?,?,?)", (category, title, content))
        conn.commit()
        conn.close()
        flash("게시글이 등록되었습니다.")
        return redirect(url_for("board"))
    return page("글쓰기", r'''<div class="form"><h2>새 게시글</h2><form method="post"><div class="field"><label>분류</label><select name="category" required>{% for c in categories %}<option>{{ c }}</option>{% endfor %}</select></div><div class="field"><label>제목</label><input name="title" required></div><div class="field"><label>내용</label><textarea name="content" required></textarea></div><button class="btn primary" style="width:100%" type="submit">등록하기</button></form></div>''', categories=CATEGORIES)


@app.route("/admin/post/<int:post_id>/edit", methods=["GET", "POST"])
@admin_required
def post_edit(post_id):
    conn = db()
    post = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return "게시글을 찾을 수 없습니다.", 404
    if request.method == "POST":
        category = request.form.get("category", "").strip()
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        conn.execute("UPDATE posts SET category=?, title=?, content=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (category, title, content, post_id))
        conn.commit()
        conn.close()
        flash("게시글이 수정되었습니다.")
        return redirect(url_for("post_detail", post_id=post_id))
    conn.close()
    return page("글 수정", r'''<div class="form"><h2>게시글 수정</h2><form method="post"><div class="field"><label>분류</label><select name="category" required>{% for c in categories %}<option value="{{ c }}" {% if c == post['category'] %}selected{% endif %}>{{ c }}</option>{% endfor %}</select></div><div class="field"><label>제목</label><input name="title" value="{{ post['title'] }}" required></div><div class="field"><label>내용</label><textarea name="content" required>{{ post['content'] }}</textarea></div><button class="btn primary" style="width:100%" type="submit">수정 저장</button></form></div>''', categories=CATEGORIES, post=post)


@app.post("/admin/post/<int:post_id>/delete")
@admin_required
def post_delete(post_id):
    conn = db()
    conn.execute("DELETE FROM posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    flash("게시글이 삭제되었습니다.")
    return redirect(url_for("board"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
