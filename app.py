import os
import sqlite3
import uuid
from functools import wraps

from flask import (
    Flask,
    request,
    redirect,
    url_for,
    session,
    flash,
    render_template_string,
)
from werkzeug.security import generate_password_hash, check_password_hash


# =========================================================
# 기본 설정
# =========================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "golf_again.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "golf-again-change-this-secret-key"
)

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


# =========================================================
# DB
# =========================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = db()

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            email TEXT UNIQUE NOT NULL,

            nickname TEXT NOT NULL,

            password_hash TEXT NOT NULL,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );


        CREATE TABLE IF NOT EXISTS listings(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            title TEXT NOT NULL,

            category TEXT NOT NULL,

            brand TEXT,

            price INTEGER NOT NULL,

            condition TEXT,

            shaft TEXT,

            flex TEXT,

            region TEXT,

            trade_method TEXT,

            description TEXT,

            image TEXT,

            status TEXT DEFAULT '판매중',

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(user_id)
            REFERENCES users(id)
        );


        CREATE TABLE IF NOT EXISTS favorites(

            user_id INTEGER NOT NULL,

            listing_id INTEGER NOT NULL,

            PRIMARY KEY(user_id, listing_id),

            FOREIGN KEY(user_id)
            REFERENCES users(id),

            FOREIGN KEY(listing_id)
            REFERENCES listings(id)
        );
        """
    )

    conn.commit()
    conn.close()


init_db()


# =========================================================
# 로그인 체크
# =========================================================

def login_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:

            flash("로그인이 필요합니다.")

            return redirect(
                url_for("login")
            )

        return func(
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# 이미지
# =========================================================

def save_image(file):

    if not file:

        return None


    if not file.filename:

        return None


    if "." not in file.filename:

        return None


    ext = (
        file.filename
        .rsplit(".", 1)[-1]
        .lower()
    )


    if ext not in ALLOWED_EXT:

        return None


    filename = (
        f"{uuid.uuid4().hex}.{ext}"
    )


    file.save(
        os.path.join(
            UPLOAD_FOLDER,
            filename
        )
    )


    return filename


def delete_image(filename):

    if not filename:

        return


    path = os.path.join(
        UPLOAD_FOLDER,
        filename
    )


    if os.path.exists(path):

        try:

            os.remove(path)

        except OSError:

            pass


# =========================================================
# 공통 화면
# =========================================================

BASE_HTML = """
<!doctype html>

<html lang="ko">

<head>

<meta charset="utf-8">

<meta
name="viewport"
content="width=device-width,initial-scale=1"
>

<title>
{{ title }} | GOLF AGAIN
</title>

<style>

*{
box-sizing:border-box;
}

body{

margin:0;

background:#f5f7f5;

color:#1e241f;

font-family:
-apple-system,
BlinkMacSystemFont,
"Segoe UI",
"Apple SD Gothic Neo",
"Noto Sans KR",
Arial,
sans-serif;

}

a{

text-decoration:none;

color:inherit;

}


header{

background:#125f37;

color:white;

}


.nav{

max-width:1100px;

margin:auto;

padding:18px 16px;

display:flex;

align-items:center;

gap:12px;

}


.logo{

font-weight:900;

font-size:23px;

letter-spacing:2px;

white-space:nowrap;

}


.navlinks{

margin-left:auto;

display:flex;

align-items:center;

gap:8px;

flex-wrap:wrap;

justify-content:flex-end;

}


.navlinks a,
.navlinks span{

padding:9px 11px;

border-radius:9px;

background:
rgba(255,255,255,.12);

font-size:14px;

}


.navlinks .primary{

background:white;

color:#125f37;

font-weight:800;

}


main{

max-width:1100px;

margin:auto;

padding:
24px 16px 60px;

}


.flash{

background:#fff3c5;

border:
1px solid #ecd879;

padding:11px 13px;

border-radius:10px;

margin-bottom:14px;

}


.hero{

background:white;

border-radius:18px;

padding:38px 24px;

box-shadow:
0 3px 18px
rgba(0,0,0,.06);

text-align:center;

}


.hero h1{

color:#125f37;

margin:0 0 12px;

font-size:31px;

}


.hero p{

color:#667066;

line-height:1.7;

}


.actions{

display:flex;

justify-content:center;

gap:10px;

flex-wrap:wrap;

margin-top:20px;

}


.btn{

display:inline-block;

border:
1px solid #d7dfd8;

background:white;

border-radius:10px;

padding:11px 15px;

font-weight:800;

cursor:pointer;

}


.btn.green{

background:#125f37;

border-color:#125f37;

color:white;

}


.btn.danger{

background:#fff0f0;

border-color:#efc6c6;

color:#a33;

}


.section-title{

margin:
30px 0 15px;

}


.cards{

display:grid;

grid-template-columns:
repeat(3,1fr);

gap:15px;

}


.card{

background:white;

border:
1px solid #e3e8e3;

border-radius:15px;

overflow:hidden;

}


.pic{

height:220px;

background:#e8eee9;

display:flex;

align-items:center;

justify-content:center;

color:#849087;

font-weight:700;

overflow:hidden;

}


.pic img{

width:100%;

height:100%;

object-fit:cover;

}


.card-body{

padding:14px;

}


.tag{

display:inline-block;

background:#edf5ef;

color:#23613c;

border-radius:7px;

padding:5px 7px;

font-size:11px;

}


.price{

font-size:19px;

font-weight:900;

color:#125f37;

margin:8px 0;

}


.meta{

font-size:12px;

color:#7a837b;

line-height:1.5;

}


.status{

font-size:12px;

font-weight:800;

margin-top:8px;

}


.form-card{

max-width:650px;

margin:0 auto;

background:white;

border:
1px solid #e3e8e3;

border-radius:18px;

padding:24px;

}


.field{

margin:15px 0;

}


.field label{

display:block;

font-size:13px;

font-weight:800;

margin-bottom:7px;

}


.field input,
.field select,
.field textarea{

width:100%;

padding:13px;

border:
1px solid #d4dbd5;

border-radius:10px;

font:inherit;

background:white;

}


.field textarea{

min-height:120px;

resize:vertical;

}


.row{

display:grid;

grid-template-columns:
1fr 1fr;

gap:12px;

}


.toolbar{

display:flex;

gap:8px;

flex-wrap:wrap;

align-items:center;

justify-content:
space-between;

margin-bottom:16px;

}


.search{

display:flex;

gap:8px;

flex:1;

flex-wrap:wrap;

}


.search input,
.search select{

padding:11px;

border:
1px solid #d6ddd6;

border-radius:9px;

font:inherit;

min-width:150px;

}


.search input{

flex:1;

}


.empty{

background:white;

border-radius:15px;

padding:44px 18px;

text-align:center;

color:#7e8780;

}


.detail{

display:grid;

grid-template-columns:
1.05fr .95fr;

gap:24px;

}


.detail-photo{

background:#e8eee9;

border-radius:18px;

min-height:430px;

display:flex;

align-items:center;

justify-content:center;

overflow:hidden;

color:#7d877f;

}


.detail-photo img{

width:100%;

height:100%;

object-fit:cover;

}


.panel{

background:white;

border:
1px solid #e3e8e3;

border-radius:18px;

padding:22px;

}


hr{

border:0;

border-top:
1px solid #ecefec;

margin:18px 0;

}


footer{

text-align:center;

color:#8b938c;

padding:25px;

font-size:12px;

}


@media(max-width:760px){

.logo{

font-size:18px;

}

.nav{

align-items:flex-start;

}

.navlinks a,
.navlinks span{

padding:7px 8px;

font-size:12px;

}

.hero{

padding:28px 16px;

}

.hero h1{

font-size:25px;

}

.cards{

grid-template-columns:
repeat(2,1fr);

gap:10px;

}

.pic{

height:150px;

}

.row{

grid-template-columns:1fr;

}

.detail{

grid-template-columns:1fr;

}

.detail-photo{

min-height:300px;

}

}

</style>

</head>


<body>


<header>

<div class="nav">

<a
class="logo"
href="{{ url_for('index') }}"
>
GOLF AGAIN
</a>


<div class="navlinks">

<a href="{{ url_for('listings') }}">
상품 둘러보기
</a>


{% if session.get('user_id') %}


<a
href="{{ url_for('sell') }}"
class="primary"
>
판매하기
</a>


<a href="{{ url_for('my') }}">
{{ session.get('nickname') }}님
</a>


<a href="{{ url_for('logout') }}">
로그아웃
</a>


{% else %}


<a href="{{ url_for('register') }}">
회원가입
</a>


<a href="{{ url_for('login') }}">
로그인
</a>


{% endif %}

</div>

</div>

</header>


<main>


{% with messages =
get_flashed_messages() %}


{% for message in messages %}

<div class="flash">

{{ message }}

</div>

{% endfor %}


{% endwith %}


{{ content|safe }}


</main>


<footer>

© 2026 GOLF AGAIN

<br>

골프용품 중고거래 플랫폼

</footer>


</body>

</html>
"""


def page(
    title,
    content_template,
    **context
):

    content = render_template_string(
        content_template,
        **context
    )

    return render_template_string(
        BASE_HTML,
        title=title,
        content=content
    )


# =========================================================
# 홈
# =========================================================

@app.route("/")
def index():

    conn = db()

    recent = conn.execute(
        """
        SELECT

        listings.*,

        users.nickname,

        (
            SELECT COUNT(*)
            FROM favorites f
            WHERE f.listing_id =
            listings.id
        ) AS fav_count

        FROM listings

        JOIN users
        ON users.id =
        listings.user_id

        WHERE
        listings.status =
        '판매중'

        ORDER BY
        listings.id DESC

        LIMIT 6
        """
    ).fetchall()

    conn.close()


    return page(
        "홈",
        """

        <section class="hero">

        <h1>
        좋은 골프용품,
        다시 필드로 ⛳
        </h1>

        <p>

        사용하지 않는 골프용품을 판매하고

        <br>

        필요한 골프용품을
        합리적인 가격에 만나보세요.

        </p>


        <div class="actions">

        <a
        class="btn green"
        href="{{ url_for('listings') }}"
        >
        상품 둘러보기
        </a>


        {% if session.get('user_id') %}


        <a
        class="btn"
        href="{{ url_for('sell') }}"
        >
        상품 판매하기
        </a>


        <a
        class="btn"
        href="{{ url_for('my') }}"
        >
        마이페이지
        </a>


        {% else %}


        <a
        class="btn"
        href="{{ url_for('register') }}"
        >
        회원가입
        </a>


        <a
        class="btn"
        href="{{ url_for('login') }}"
        >
        로그인
        </a>


        {% endif %}


        </div>

        </section>


        <h2 class="section-title">

        최근 등록 상품

        </h2>


        {% if recent %}


        <div class="cards">


        {% for item in recent %}


        <a
        class="card"
        href="{{ url_for('item', item_id=item['id']) }}"
        >


        <div class="pic">


        {% if item['image'] %}


        <img
        src="{{ url_for('static', filename='uploads/' + item['image']) }}"
        alt=""
        >


        {% else %}


        사진 없음


        {% endif %}


        </div>


        <div class="card-body">


        <span class="tag">

        {{ item['category'] }}

        </span>


        <div style="
        font-weight:800;
        margin-top:8px
        ">

        {{ item['title'] }}

        </div>


        <div class="price">

        {{ "{:,}".format(item['price']) }}원

        </div>


        <div class="meta">

        {{ item['region'] or '지역 미입력' }}

        ·

        {{ item['nickname'] }}

        ·

        ♥ {{ item['fav_count'] }}

        </div>


        </div>


        </a>


        {% endfor %}


        </div>


        {% else %}


        <div class="empty">

        아직 등록된 상품이 없습니다.

        </div>


        {% endif %}

        """,

        recent=recent
    )


# =========================================================
# 상품 목록
# =========================================================

@app.route("/listings")
def listings():

    q = (
        request.args
        .get("q", "")
        .strip()
    )


    category = (
        request.args
        .get("category", "")
        .strip()
    )


    conn = db()


    sql = """
        SELECT

        listings.*,

        users.nickname,

        (
            SELECT COUNT(*)
            FROM favorites f
            WHERE
            f.listing_id =
            listings.id
        ) AS fav_count

        FROM listings

        JOIN users
        ON users.id =
        listings.user_id

        WHERE
        listings.status =
        '판매중'
    """


    params = []


    if q:

        sql += """
        AND
        (
            listings.title
            LIKE ?

            OR

            listings.brand
            LIKE ?

            OR

            listings.description
            LIKE ?
        )
        """

        like = f"%{q}%"

        params.extend(
            [
                like,
                like,
                like
            ]
        )


    if category:

        sql += """
        AND
        listings.category = ?
        """

        params.append(
            category
        )


    sql += """
    ORDER BY
    listings.id DESC
    """


    items = conn.execute(
        sql,
        params
    ).fetchall()


    favs = set()


    if "user_id" in session:

        favs = {

            row["listing_id"]

            for row in conn.execute(
                """
                SELECT listing_id
                FROM favorites
                WHERE user_id=?
                """,

                (
                    session["user_id"],
                )

            ).fetchall()

        }


    conn.close()


    categories = [

        "드라이버",

        "아이언",

        "웨지",

        "퍼터",

        "골프채",

        "골프백",

        "골프웨어",

        "골프화",

        "거리측정기",

        "골프공",

        "기타"

    ]


    return page(
        "상품 둘러보기",
        """

        <div class="toolbar">

        <h2 style="margin:0">

        ⛳ 상품 둘러보기

        </h2>


        {% if session.get('user_id') %}

        <a
        class="btn green"
        href="{{ url_for('sell') }}"
        >
        + 상품 판매하기
        </a>

        {% endif %}


        </div>


        <form
        class="search"
        method="get"
        >


        <input
        name="q"
        value="{{ q }}"
        placeholder="상품명, 브랜드 검색"
        >


        <select name="category">


        <option value="">

        전체 카테고리

        </option>


        {% for c in categories %}


        <option
        value="{{ c }}"
        {% if c == category %}
        selected
        {% endif %}
        >

        {{ c }}

        </option>


        {% endfor %}


        </select>


        <button
        class="btn green"
        type="submit"
        >

        검색

        </button>


        </form>


        <div style="height:16px"></div>


        {% if items %}


        <div class="cards">


        {% for item in items %}


        <div class="card">


        <a
        href="{{ url_for('item', item_id=item['id']) }}"
        >


        <div class="pic">


        {% if item['image'] %}


        <img
        src="{{ url_for('static', filename='uploads/' + item['image']) }}"
        alt=""
        >


        {% else %}


        사진 없음


        {% endif %}


        </div>


        <div class="card-body">


        <span class="tag">

        {{ item['category'] }}

        </span>


        <div style="
        font-weight:800;
        margin-top:8px
        ">

        {{ item['title'] }}

        </div>


        <div class="price">

        {{ "{:,}".format(item['price']) }}원

        </div>


        <div class="meta">

        {{ item['region'] or '지역 미입력' }}

        ·

        {{ item['nickname'] }}

        ·

        ♥ {{ item['fav_count'] }}

        </div>


        </div>


        </a>


        {% if session.get('user_id') %}


        <form
        method="post"
        action="{{ url_for('favorite', item_id=item['id']) }}"
        style="padding:0 14px 14px"
        >


        <button
        class="btn"
        style="width:100%"
        >


        {% if item['id'] in favs %}


        ♥ 찜 취소


        {% else %}


        ♡ 찜하기


        {% endif %}


        </button>


        </form>


        {% endif %}


        </div>


        {% endfor %}


        </div>


        {% else %}


        <div class="empty">

        조건에 맞는 상품이 없습니다.

        </div>


        {% endif %}

        """,

        items=items,

        favs=favs,

        q=q,

        category=category,

        categories=categories
    )


# =========================================================
# 회원가입
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        email = (
            request.form
            .get("email", "")
            .strip()
            .lower()
        )


        nickname = (
            request.form
            .get("nickname", "")
            .strip()
        )


        password = (
            request.form
            .get("password", "")
        )


        if (
            not email
            or not nickname
            or not password
        ):

            flash(
                "모든 항목을 입력해주세요."
            )

            return redirect(
                url_for("register")
            )


        if len(password) < 6:

            flash(
                "비밀번호는 6자 이상으로 입력해주세요."
            )

            return redirect(
                url_for("register")
            )


        conn = db()


        try:

            cur = conn.execute(
                """
                INSERT INTO users
                (
                    email,
                    nickname,
                    password_hash
                )

                VALUES
                (?,?,?)
                """,

                (
                    email,

                    nickname,

                    generate_password_hash(
                        password
                    )
                )
            )


            conn.commit()


            session["user_id"] = (
                cur.lastrowid
            )


            session["nickname"] = (
                nickname
            )


            flash(
                "회원가입이 완료되었습니다."
            )


            return redirect(
                url_for("index")
            )


        except sqlite3.IntegrityError:

            flash(
                "이미 가입된 이메일입니다."
            )


        finally:

            conn.close()


    return page(
        "회원가입",
        """

        <div class="form-card">

        <h2>

        회원가입

        </h2>


        <form method="post">


        <div class="field">

        <label>

        이메일

        </label>

        <input
        type="email"
        name="email"
        required
        >

        </div>


        <div class="field">

        <label>

        닉네임

        </label>

        <input
        type="text"
        name="nickname"
        required
        >

        </div>


        <div class="field">

        <label>

        비밀번호

        </label>

        <input
        type="password"
        name="password"
        minlength="6"
        required
        >

        </div>


        <button
        class="btn green"
        style="width:100%"
        type="submit"
        >

        회원가입

        </button>


        </form>


        <div style="
        text-align:center;
        margin-top:16px
        ">

        이미 회원이신가요?

        <a
        href="{{ url_for('login') }}"
        style="
        color:#125f37;
        font-weight:800
        "
        >

        로그인

        </a>


        </div>


        </div>

        """
    )


# =========================================================
# 로그인
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = (
            request.form
            .get("email", "")
            .strip()
            .lower()
        )


        password = (
            request.form
            .get("password", "")
        )


        conn = db()


        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email=?
            """,

            (
                email,
            )

        ).fetchone()


        conn.close()


        if (
            user
            and
            check_password_hash(
                user["password_hash"],
                password
            )
        ):

            session["user_id"] = (
                user["id"]
            )


            session["nickname"] = (
                user["nickname"]
            )


            flash(
                "로그인되었습니다."
            )


            return redirect(
                url_for("index")
            )


        flash(
            "이메일 또는 비밀번호가 올바르지 않습니다."
        )


    return page(
        "로그인",
        """

        <div class="form-card">

        <h2>

        로그인

        </h2>


        <form method="post">


        <div class="field">

        <label>

        이메일

        </label>

        <input
        type="email"
        name="email"
        required
        >

        </div>


        <div class="field">

        <label>

        비밀번호

        </label>

        <input
        type="password"
        name="password"
        required
        >

        </div>


        <button
        class="btn green"
        style="width:100%"
        type="submit"
        >

        로그인

        </button>


        </form>


        </div>

        """
    )


# =========================================================
# 로그아웃
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "로그아웃되었습니다."
    )

    return redirect(
        url_for("index")
    )


# =========================================================
# 상품 판매
# =========================================================

@app.route(
    "/sell",
    methods=["GET", "POST"]
)
@login_required
def sell():

    categories = [

        "드라이버",

        "아이언",

        "웨지",

        "퍼터",

        "골프채",

        "골프백",

        "골프웨어",

        "골프화",

        "거리측정기",

        "골프공",

        "기타"

    ]


    if request.method == "POST":

        title = (
            request.form
            .get("title", "")
            .strip()
        )


        category = (
            request.form
            .get("category", "")
            .strip()
        )


        price_raw = (
            request.form
            .get("price", "")
            .strip()
        )


        if (
            not title
            or not category
            or not price_raw
        ):

            flash(
                "상품명, 카테고리, 가격은 필수입니다."
            )

            return redirect(
                url_for("sell")
            )


        try:

            price = int(
                price_raw
            )

        except ValueError:

            flash(
                "가격은 숫자로 입력해주세요."
            )

            return redirect(
                url_for("sell")
            )


        image = save_image(
            request.files.get(
                "image"
            )
        )


        conn = db()


        cur = conn.execute(
            """
            INSERT INTO listings
            (
                user_id,

                title,

                category,

                brand,

                price,

                condition,

                shaft,

                flex,

                region,

                trade_method,

                description,

                image
            )

            VALUES
            (
                ?,?,?,?,?,?,?,?,?,?,?,?
            )
            """,

            (
                session["user_id"],

                title,

                category,

                request.form
                .get("brand", "")
                .strip(),

                price,

                request.form
                .get("condition", "")
                .strip(),

                request.form
                .get("shaft", "")
                .strip(),

                request.form
                .get("flex", "")
                .strip(),

                request.form
                .get("region", "")
                .strip(),

                request.form
                .get("trade_method", "")
                .strip(),

                request.form
                .get("description", "")
                .strip(),

                image
            )
        )


        conn.commit()


        item_id = (
            cur.lastrowid
        )


        conn.close()


        flash(
            "상품이 등록되었습니다."
        )


        return redirect(
            url_for(
                "item",
                item_id=item_id
            )
        )


    return page(
        "상품 판매하기",
        """

        <div class="form-card">

        <h2>

        ⛳ 상품 등록

        </h2>


        <form
        method="post"
        enctype="multipart/form-data"
        >


        <div class="field">

        <label>

        상품 사진

        </label>

        <input
        type="file"
        name="image"
        accept="image/*"
        >

        </div>


        <div class="field">

        <label>

        상품명 *

        </label>

        <input
        name="title"
        required
        placeholder="예: 테일러메이드 Qi10 드라이버"
        >

        </div>


        <div class="row">


        <div class="field">

        <label>

        카테고리 *

        </label>

        <select
        name="category"
        required
        >


        <option value="">

        선택하세요

        </option>


        {% for c in categories %}


        <option>

        {{ c }}

        </option>


        {% endfor %}


        </select>


        </div>


        <div class="field">

        <label>

        가격 *

        </label>

        <input
        type="number"
        name="price"
        min="0"
        required
        placeholder="원"
        >

        </div>


        </div>


        <div class="row">


        <div class="field">

        <label>

        브랜드

        </label>

        <input
        name="brand"
        >

        </div>


        <div class="field">

        <label>

        상품 상태

        </label>

        <select
        name="condition"
        >

        <option>
        새상품
        </option>

        <option>
        거의 새상품
        </option>

        <option>
        상
        </option>

        <option>
        중
        </option>

        <option>
        사용감 있음
        </option>

        </select>


        </div>


        </div>


        <div class="row">


        <div class="field">

        <label>

        샤프트

        </label>

        <input
        name="shaft"
        >

        </div>


        <div class="field">

        <label>

        Flex

        </label>

        <select
        name="flex"
        >

        <option value="">
        </option>

        <option>
        R
        </option>

        <option>
        SR
        </option>

        <option>
        S
        </option>

        <option>
        X
        </option>

        </select>


        </div>


        </div>


        <div class="row">


        <div class="field">

        <label>

        거래 지역

        </label>

        <input
        name="region"
        placeholder="예: 서울 성동구"
        >

        </div>


        <div class="field">

        <label>

        거래 방법

        </label>

        <select
        name="trade_method"
        >

        <option>
        직거래 · 택배
        </option>

        <option>
        직거래
        </option>

        <option>
        택배
        </option>

        </select>


        </div>


        </div>


        <div class="field">

        <label>

        상품 설명

        </label>

        <textarea
        name="description"
        placeholder="사용기간, 흠집, 구성품 등을 적어주세요."
        ></textarea>

        </div>


        <button
        class="btn green"
        style="width:100%"
        type="submit"
        >

        상품 등록하기

        </button>


        </form>


        </div>

        """,

        categories=categories
    )


# =========================================================
# 상품 상세
# =========================================================

@app.route(
    "/item/<int:item_id>"
)
def item(item_id):

    conn = db()


    listing = conn.execute(
        """
        SELECT

        listings.*,

        users.nickname,

        (
            SELECT COUNT(*)
            FROM favorites f
            WHERE
            f.listing_id =
            listings.id
        ) AS fav_count

        FROM listings

        JOIN users
        ON users.id =
        listings.user_id

        WHERE
        listings.id=?
        """,

        (
            item_id,
        )

    ).fetchone()


    is_favorite = False


    if (
        listing
        and
        "user_id" in session
    ):

        is_favorite = (

            conn.execute(
                """
                SELECT 1
                FROM favorites
                WHERE
                user_id=?
                AND
                listing_id=?
                """,

                (
                    session["user_id"],
                    item_id
                )

            ).fetchone()

            is not None

        )


    conn.close()


    if not listing:

        return (
            "상품을 찾을 수 없습니다.",
            404
        )


    return page(
        listing["title"],
        """

        <div class="detail">


        <div class="detail-photo">


        {% if listing['image'] %}


        <img
        src="{{ url_for('static', filename='uploads/' + listing['image']) }}"
        alt=""
        >


        {% else %}


        사진 없음


        {% endif %}


        </div>


        <div class="panel">


        <span class="tag">

        {{ listing['category'] }}

        </span>


        <h1 style="font-size:26px">

        {{ listing['title'] }}

        </h1>


        <div class="price">

        {{ "{:,}".format(listing['price']) }}원

        </div>


        <div class="status">

        {{ listing['status'] }}

        </div>


        <hr>


        <p>

        <b>판매자</b>

        {{ listing['nickname'] }}

        </p>


        <p>

        <b>브랜드</b>

        {{ listing['brand'] or '-' }}

        </p>


        <p>

        <b>상태</b>

        {{ listing['condition'] or '-' }}

        </p>


        <p>

        <b>샤프트 / Flex</b>

        {{ listing['shaft'] or '-' }}

        /

        {{ listing['flex'] or '-' }}

        </p>


        <p>

        <b>지역</b>

        {{ listing['region'] or '-' }}

        </p>


        <p>

        <b>거래방법</b>

        {{ listing['trade_method'] or '-' }}

        </p>


        <p>

        <b>찜</b>

        {{ listing['fav_count'] }}

        </p>


        <hr>


        <div style="
        white-space:pre-wrap;
        line-height:1.7
        ">

        {{
        listing['description']
        or
        '상품 설명이 없습니다.'
        }}

        </div>


        {% if session.get('user_id') %}


        <div
        class="actions"
        style="
        justify-content:flex-start
        "
        >


        <form
        method="post"
        action="{{ url_for('favorite', item_id=listing['id']) }}"
        >


        <button
        class="btn"
        type="submit"
        >


        {% if is_favorite %}


        ♥ 찜 취소


        {% else %}


        ♡ 찜하기


        {% endif %}


        </button>


        </form>


        {% if session.get('user_id') ==
        listing['user_id'] %}


        <a
        class="btn green"
        href="{{ url_for('my') }}"
        >

        내 상품 관리

        </a>


        {% endif %}


        </div>


        {% endif %}


        </div>


        </div>

        """,

        listing=listing,

        is_favorite=is_favorite
    )


# =========================================================
# 찜
# =========================================================

@app.post(
    "/favorite/<int:item_id>"
)
@login_required
def favorite(item_id):

    conn = db()


    exists = conn.execute(
        """
        SELECT 1
        FROM favorites
        WHERE
        user_id=?
        AND
        listing_id=?
        """,

        (
            session["user_id"],
            item_id
        )

    ).fetchone()


    if exists:

        conn.execute(
            """
            DELETE FROM favorites
            WHERE
            user_id=?
            AND
            listing_id=?
            """,

            (
                session["user_id"],
                item_id
            )
        )


    else:

        conn.execute(
            """
            INSERT OR IGNORE
            INTO favorites
            (
                user_id,
                listing_id
            )

            VALUES
            (?,?)
            """,

            (
                session["user_id"],
                item_id
            )
        )


    conn.commit()

    conn.close()


    return redirect(
        request.referrer
        or
        url_for("listings")
    )


# =========================================================
# 마이페이지
# =========================================================

@app.route("/my")
@login_required
def my():

    conn = db()


    mine = conn.execute(
        """
        SELECT *
        FROM listings
        WHERE user_id=?
        ORDER BY id DESC
        """,

        (
            session["user_id"],
        )

    ).fetchall()


    favorites = conn.execute(
        """
        SELECT listings.*

        FROM listings

        JOIN favorites
        ON favorites.listing_id =
        listings.id

        WHERE
        favorites.user_id=?

        ORDER BY
        listings.id DESC
        """,

        (
            session["user_id"],
        )

    ).fetchall()


    conn.close()


    return page(
        "마이페이지",
        """

        <div class="toolbar">


        <h2 style="margin:0">

        {{ session.get('nickname') }}님의 마이페이지

        </h2>


        <a
        class="btn green"
        href="{{ url_for('sell') }}"
        >

        + 상품 판매하기

        </a>


        </div>


        <h3>

        내가 올린 상품

        </h3>


        {% if mine %}


        <div class="cards">


        {% for item in mine %}


        <div class="card">


        <a
        href="{{ url_for('item', item_id=item['id']) }}"
        >


        <div class="pic">


        {% if item['image'] %}


        <img
        src="{{ url_for('static', filename='uploads/' + item['image']) }}"
        alt=""
        >


        {% else %}


        사진 없음


        {% endif %}


        </div>


        <div class="card-body">


        <div style="font-weight:800">

        {{ item['title'] }}

        </div>


        <div class="price">

        {{ "{:,}".format(item['price']) }}원

        </div>


        <div class="status">

        {{ item['status'] }}

        </div>


        </div>


        </a>


        <div style="
        display:flex;
        gap:6px;
        padding:0 14px 14px
        ">


        <form
        method="post"
        action="{{ url_for('status', item_id=item['id']) }}"
        style="flex:1"
        >


        <button
        class="btn"
        style="width:100%"
        type="submit"
        >

        상태 변경

        </button>


        </form>


        <form
        method="post"
        action="{{ url_for('delete', item_id=item['id']) }}"
        style="flex:1"
        onsubmit="
        return confirm('정말 삭제할까요?')
        "
        >


        <button
        class="btn danger"
        style="width:100%"
        type="submit"
        >

        삭제

        </button>


        </form>


        </div>


        </div>


        {% endfor %}


        </div>


        {% else %}


        <div class="empty">

        아직 등록한 상품이 없습니다.

        </div>


        {% endif %}


        <h3 style="margin-top:32px">

        찜한 상품

        </h3>


        {% if favorites %}


        <div class="cards">


        {% for item in favorites %}


        <a
        class="card"
        href="{{ url_for('item', item_id=item['id']) }}"
        >


        <div class="pic">


        {% if item['image'] %}


        <img
        src="{{ url_for('static', filename='uploads/' + item['image']) }}"
        alt=""
        >


        {% else %}


        사진 없음


        {% endif %}


        </div>


        <div class="card-body">


        <div style="font-weight:800">

        {{ item['title'] }}

        </div>


        <div class="price">

        {{ "{:,}".format(item['price']) }}원

        </div>


        </div>


        </a>


        {% endfor %}


        </div>


        {% else %}


        <div class="empty">

        찜한 상품이 없습니다.

        </div>


        {% endif %}

        """,

        mine=mine,

        favorites=favorites
    )


# =========================================================
# 판매 상태 변경
# =========================================================

@app.post(
    "/status/<int:item_id>"
)
@login_required
def status(item_id):

    conn = db()


    listing = conn.execute(
        """
        SELECT *
        FROM listings
        WHERE id=?
        """,

        (
            item_id,
        )

    ).fetchone()


    if (
        not listing
        or
        listing["user_id"]
        !=
        session["user_id"]
    ):

        conn.close()

        return (
            "권한 없음",
            403
        )


    if listing["status"] == "판매중":

        new_status = "판매완료"

    else:

        new_status = "판매중"


    conn.execute(
        """
        UPDATE listings
        SET status=?
        WHERE id=?
        """,

        (
            new_status,
            item_id
        )
    )


    conn.commit()

    conn.close()


    flash(
        f"상품 상태가 '{new_status}'(으)로 변경되었습니다."
    )


    return redirect(
        url_for("my")
    )


# =========================================================
# 상품 삭제
# =========================================================

@app.post(
    "/delete/<int:item_id>"
)
@login_required
def delete(item_id):

    conn = db()


    listing = conn.execute(
        """
        SELECT *
        FROM listings
        WHERE id=?
        """,

        (
            item_id,
        )

    ).fetchone()


    if (
        not listing
        or
        listing["user_id"]
        !=
        session["user_id"]
    ):

        conn.close()

        return (
            "권한 없음",
            403
        )


    conn.execute(
        """
        DELETE FROM favorites
        WHERE listing_id=?
        """,

        (
            item_id,
        )
    )


    conn.execute(
        """
        DELETE FROM listings
        WHERE id=?
        """,

        (
            item_id,
        )
    )


    conn.commit()

    conn.close()


    delete_image(
        listing["image"]
    )


    flash(
        "상품이 삭제되었습니다."
    )


    return redirect(
        url_for("my")
    )


# =========================================================
# 실행
# =========================================================

if __name__ == "__main__":

    init_db()

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                "5000"
            )
        ),
        debug=False
    )
