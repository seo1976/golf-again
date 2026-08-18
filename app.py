import os
import sqlite3
import secrets
from functools import wraps
from datetime import datetime
from flask import Flask, request, redirect, url_for, session, flash, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'bojjimi.db')

ADMIN_ID = os.environ.get('ADMIN_ID', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'change-me-1234')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'bojjimi-change-this-secret')


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = db()
    conn.executescript("\n    CREATE TABLE IF NOT EXISTS admins(\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        username TEXT UNIQUE NOT NULL,\n        password_hash TEXT NOT NULL\n    );\n\n    CREATE TABLE IF NOT EXISTS users(\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        email TEXT UNIQUE NOT NULL,\n        nickname TEXT NOT NULL,\n        phone TEXT,\n        password_hash TEXT NOT NULL,\n        created_at DATETIME DEFAULT CURRENT_TIMESTAMP\n    );\n\n    CREATE TABLE IF NOT EXISTS addresses(\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        user_id INTEGER NOT NULL,\n        label TEXT DEFAULT '\uae30\ubcf8 \ubc30\uc1a1\uc9c0',\n        recipient TEXT NOT NULL,\n        phone TEXT NOT NULL,\n        postcode TEXT,\n        address1 TEXT NOT NULL,\n        address2 TEXT,\n        is_default INTEGER DEFAULT 0,\n        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,\n        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE\n    );\n\n    CREATE TABLE IF NOT EXISTS products(\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        product_type TEXT NOT NULL DEFAULT '\uacf5\ub3d9\uad6c\ub9e4',\n        brand TEXT,\n        category TEXT NOT NULL,\n        title TEXT NOT NULL,\n        subtitle TEXT,\n        original_price INTEGER,\n        sale_price INTEGER,\n        image_url TEXT,\n        buy_url TEXT,\n        description TEXT,\n        badge TEXT,\n        status TEXT DEFAULT '\ud310\ub9e4\uc911',\n        featured INTEGER DEFAULT 0,\n        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,\n        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP\n    );\n\n    CREATE TABLE IF NOT EXISTS favorites(\n        user_id INTEGER NOT NULL,\n        product_id INTEGER NOT NULL,\n        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,\n        PRIMARY KEY(user_id, product_id),\n        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,\n        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE\n    );\n\n    CREATE TABLE IF NOT EXISTS cart_items(\n        user_id INTEGER NOT NULL,\n        product_id INTEGER NOT NULL,\n        quantity INTEGER NOT NULL DEFAULT 1,\n        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,\n        PRIMARY KEY(user_id, product_id),\n        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,\n        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE\n    );\n\n    CREATE TABLE IF NOT EXISTS orders(\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        order_no TEXT UNIQUE NOT NULL,\n        user_id INTEGER NOT NULL,\n        recipient TEXT NOT NULL,\n        phone TEXT NOT NULL,\n        postcode TEXT,\n        address1 TEXT NOT NULL,\n        address2 TEXT,\n        subtotal INTEGER NOT NULL DEFAULT 0,\n        shipping_fee INTEGER NOT NULL DEFAULT 0,\n        total INTEGER NOT NULL DEFAULT 0,\n        status TEXT NOT NULL DEFAULT '\uc8fc\ubb38\uc811\uc218',\n        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,\n        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE\n    );\n\n    CREATE TABLE IF NOT EXISTS order_items(\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        order_id INTEGER NOT NULL,\n        product_id INTEGER,\n        title TEXT NOT NULL,\n        price INTEGER NOT NULL,\n        quantity INTEGER NOT NULL,\n        FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE\n    );\n\n    CREATE TABLE IF NOT EXISTS compare_items(\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        title TEXT NOT NULL,\n        brand TEXT,\n        model_no TEXT,\n        category TEXT,\n        image_url TEXT,\n        description TEXT,\n        created_at DATETIME DEFAULT CURRENT_TIMESTAMP\n    );\n\n    CREATE TABLE IF NOT EXISTS compare_offers(\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        item_id INTEGER NOT NULL,\n        seller TEXT NOT NULL,\n        price INTEGER NOT NULL,\n        shipping INTEGER DEFAULT 0,\n        buy_url TEXT NOT NULL,\n        note TEXT,\n        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,\n        FOREIGN KEY(item_id) REFERENCES compare_items(id) ON DELETE CASCADE\n    );\n\n    CREATE TABLE IF NOT EXISTS vendors(\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        name TEXT NOT NULL,\n        subtext TEXT,\n        logo_text TEXT,\n        url TEXT,\n        sort_order INTEGER DEFAULT 0,\n        active INTEGER DEFAULT 1\n    );\n    ")

    admin = conn.execute('SELECT * FROM admins WHERE username=?', (ADMIN_ID,)).fetchone()
    if not admin:
        conn.execute(
            'INSERT INTO admins(username,password_hash) VALUES(?,?)',
            (ADMIN_ID, generate_password_hash(ADMIN_PASSWORD))
        )

    if conn.execute('SELECT COUNT(*) c FROM products').fetchone()['c'] == 0:
        conn.executemany(
            'INSERT INTO products(\n                product_type,brand,category,title,subtitle,\n                original_price,sale_price,image_url,buy_url,\n                description,badge,status,featured\n            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
            [
                ('\uacf5\ub3d9\uad6c\ub9e4','\uc5c4\ub9c8\uc7a5\ub3c5','\uc2dd\ud488','\uc5c4\ub9c8\uc7a5\ub3c5 \uae40\uce58','\uc9d1\ubc25\uc774 \uc0dd\uac01\ub098\ub294 \uc815\uc131 \uac00\ub4dd \uae40\uce58',35000,29900,'','#','\uc5c4\ub9c8\uc7a5\ub3c5 \ub300\ud45c \uc0c1\ud488\uc785\ub2c8\ub2e4.','\ub300\ud45c\uc0c1\ud488','\ud310\ub9e4\uc911',1),
                ('\uacf5\ub3d9\uad6c\ub9e4','\uc5c4\ub9c8\uc7a5\ub3c5','\uc2dd\ud488','\uc5c4\ub9c8\uac00 \ub9cc\ub4e0 \uc870\uc120\uac04\uc7a5','\uae4a\uace0 \uae54\ub054\ud55c \uc804\ud1b5 \uc7a5\ub9db',25000,22000,'','#','\uc9d1\ubc25\uc758 \uae30\ubcf8\uc774 \ub418\ub294 \uc870\uc120\uac04\uc7a5\uc785\ub2c8\ub2e4.','\uc5c4\ub9c8\uc7a5\ub3c5','\ud310\ub9e4\uc911',1),
                ('\uacf5\ub3d9\uad6c\ub9e4','\uc5c4\ub9c8\uc7a5\ub3c5','\uc2dd\ud488','\uc5c4\ub9c8\uac00 \ub9cc\ub4e0 \ub41c\uc7a5','\uad6c\uc218\ud558\uace0 \uae4a\uc740 \uc9d1\ub41c\uc7a5',28000,25000,'','#','\ucc0c\uac1c\uc640 \ubb34\uce68\uc5d0 \uc798 \uc5b4\uc6b8\ub9ac\ub294 \ub41c\uc7a5\uc785\ub2c8\ub2e4.','\uc5c4\ub9c8\uc7a5\ub3c5','\ud310\ub9e4\uc911',1),
                ('\uacf5\ub3d9\uad6c\ub9e4','RUBIE','\ubdf0\ud2f0','RUBIE \ucc9c\uc5f0\uc624\uc77c \ucf00\uc5b4','\ub8e8\ube44\uc5d0 \ube0c\ub79c\ub4dc \uc900\ube44\uc911',59000,39900,'','#','RUBIE \ucc9c\uc5f0\uc624\uc77c \uae30\ubc18 \ub77c\uc774\ud504 \ubdf0\ud2f0 \uc81c\ud488 \uc608\uc2dc\uc785\ub2c8\ub2e4.','COMING SOON','\uc900\ube44\uc911',1),
            ]
        )

    if conn.execute('SELECT COUNT(*) c FROM compare_items').fetchone()['c'] == 0:
        items = [
            ('\ub2e4\uc774\uc2a8 \uc5d0\uc5b4\ub7a9 \ucef4\ud50c\ub9ac\ud2b8 \ub871','Dyson','HS05','\ubdf0\ud2f0\uac00\uc804','','\ud310\ub9e4\ucc98\ubcc4 \uc2e4\uad6c\ub9e4\uac00 \ube44\uad50'),
            ('Apple \uc5d0\uc5b4\ud31f \ud504\ub85c 2\uc138\ub300','Apple','MTJV3KH/A','\uac00\uc804','','\ud310\ub9e4\ucc98\ubcc4 \uc2e4\uad6c\ub9e4\uac00 \ube44\uad50'),
        ]
        ids=[]
        for x in items:
            cur=conn.execute('INSERT INTO compare_items(title,brand,model_no,category,image_url,description) VALUES(?,?,?,?,?,?)',x)
            ids.append(cur.lastrowid)
        conn.executemany(
            'INSERT INTO compare_offers(item_id,seller,price,shipping,buy_url,note) VALUES(?,?,?,?,?,?)',
            [
                (ids[0],'A\ubab0',548000,0,'#','\ubb34\ub8cc\ubc30\uc1a1'),
                (ids[0],'B\ubab0',555000,0,'#','\uce74\ub4dc\ud560\uc778 \ubcc4\ub3c4'),
                (ids[1],'A\ubab0',269000,0,'#','\ubb34\ub8cc\ubc30\uc1a1'),
                (ids[1],'B\ubab0',274000,2500,'#','\uc77c\ubc18\ubc30\uc1a1'),
            ]
        )

    if conn.execute('SELECT COUNT(*) c FROM vendors').fetchone()['c'] == 0:
        conn.executemany(
            'INSERT INTO vendors(name,subtext,logo_text,url,sort_order,active) VALUES(?,?,?,?,?,?)',
            [
                ('\ucfe0\ud321','\ub2e4\uc591\ud55c \uc0c1\ud488\uc744 \ube60\ub974\uace0 \ud3b8\ub9ac\ud558\uac8c','coupang','#',1,1),
                ('\ub124\uc774\ubc84 \uc1fc\ud551','\ub124\uc774\ubc84\uc5d0\uc11c \ucc3e\uc740 \uc2a4\ub9c8\ud2b8\ud55c \uc1fc\ud551','N','#',2,1),
                ('11\ubc88\uac00','\ud2b9\ubcc4\ud55c \ud61c\ud0dd\uc744 \ub9cc\ub098\ubcf4\uc138\uc694','11','#',3,1),
                ('G\ub9c8\ucf13','\ub300\ud55c\ubbfc\uad6d \ub300\ud45c \uc628\ub77c\uc778 \uc1fc\ud551\ubab0','G','#',4,1),
                ('\uc5c4\ub9c8\uc7a5\ub3c5 \uacf5\uc2dd\ubab0','\uc5c4\ub9c8\uc7a5\ub3c5 \uacf5\uc2dd \uc2a4\ud1a0\uc5b4','\uc5c4\ub9c8\uc7a5\ub3c5','#',5,1),
                ('RUBIE \uacf5\uc2dd\ubab0','RUBIE \uacf5\uc2dd \uc2a4\ud1a0\uc5b4','RUBIE','#',6,1),
            ]
        )

    conn.commit()
    conn.close()


init_db()


def _hangul_score(text):
    if not isinstance(text, str):
        return 0
    return sum(1 for ch in text if '\uac00' <= ch <= '\ud7a3')


def _repair_text(value):
    if not isinstance(value, str) or not value:
        return value

    suspicious = ('\xc2', '\xc3', '\xec', '\xeb', '\xed', '\xea', '\ufffd')
    if not any(x in value for x in suspicious):
        return value

    candidates = [value]
    for enc in ('latin1', 'cp1252'):
        try:
            candidates.append(value.encode(enc).decode('utf-8'))
        except Exception:
            pass

    best = max(candidates, key=lambda x: (_hangul_score(x), -x.count('\ufffd')))
    return best


def repair_existing_db_text():
    conn = db()

    table_columns = {
        'products': ['product_type','brand','category','title','subtitle','description','badge','status'],
        'compare_items': ['title','brand','model_no','category','description'],
        'compare_offers': ['seller','note'],
        'vendors': ['name','subtext','logo_text'],
        'users': ['nickname'],
        'addresses': ['label','recipient','address1','address2'],
        'orders': ['recipient','address1','address2','status'],
        'order_items': ['title'],
    }

    for table, columns in table_columns.items():
        try:
            rows = conn.execute(f"SELECT rowid, * FROM {table}").fetchall()
        except Exception:
            continue

        for row in rows:
            updates = {}
            for col in columns:
                if col not in row.keys():
                    continue
                old = row[col]
                new = _repair_text(old)
                if new != old:
                    updates[col] = new

            if updates:
                sets = ', '.join(f"{k}=?" for k in updates)
                values = list(updates.values()) + [row['rowid']]
                conn.execute(f"UPDATE {table} SET {sets} WHERE rowid=?", values)

    conn.commit()
    conn.close()


repair_existing_db_text()




def money(v):
    if v is None or v == '':
        return ''
    return f"{int(v):,}"

app.jinja_env.filters['money'] = money


def user_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash('\ub85c\uadf8\uc778\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.')
            return redirect(url_for('login', next=request.path))
        return func(*args, **kwargs)
    return wrapper


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get('admin'):
            flash('\uad00\ub9ac\uc790 \ub85c\uadf8\uc778\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.')
            return redirect(url_for('admin_login'))
        return func(*args, **kwargs)
    return wrapper


def user_counts():
    if not session.get('user_id'):
        return {'favorites':0, 'cart':0}
    conn=db()
    fav=conn.execute('SELECT COUNT(*) c FROM favorites WHERE user_id=?',(session['user_id'],)).fetchone()['c']
    cart=conn.execute('SELECT COALESCE(SUM(quantity),0) c FROM cart_items WHERE user_id=?',(session['user_id'],)).fetchone()['c']
    conn.close()
    return {'favorites':fav,'cart':cart}


BASE_HTML = '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n<title>{{ title }} | \ubcf4\ucc0c\ubbf8</title>\n<style>\n*{box-sizing:border-box}:root{--pink:#ff2f78;--pink2:#ff6a93;--line:#ececef;--muted:#757b82;--bg:#fafafa;--dark:#20242a;--green:#19865b}\nbody{margin:0;background:var(--bg);color:#1f2328;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Apple SD Gothic Neo","Noto Sans KR",Arial,sans-serif}a{text-decoration:none;color:inherit}button,input,select,textarea{font:inherit}\n.top{background:#fff;border-bottom:1px solid var(--line)}.top-inner{max-width:1500px;margin:auto;padding:14px 22px;display:grid;grid-template-columns:250px minmax(300px,1fr) 330px;gap:20px;align-items:center}.logo-wrap{display:flex;align-items:center;gap:10px}.logo-icon{width:42px;height:42px;border:2px solid var(--pink);border-radius:13px;display:flex;align-items:center;justify-content:center;color:var(--pink);font-size:22px}.logo{color:var(--pink);font-size:30px;font-weight:950}.logo-sub{font-size:12px;font-weight:700}.search-main{display:flex;height:48px;border:1.5px solid #dcdce2;border-radius:8px;overflow:hidden}.search-main input{flex:1;border:0;outline:0;padding:0 16px}.search-main button{width:55px;border:0;background:linear-gradient(135deg,var(--pink),var(--pink2));color:#fff;font-size:20px}.quick-icons{display:flex;justify-content:flex-end;gap:23px}.quick-icons a{text-align:center;font-size:12px;font-weight:750;position:relative}.quick-icons b{display:block;font-size:22px;margin-bottom:3px;font-weight:500}.count{position:absolute;right:3px;top:-5px;background:var(--pink);color:white;border-radius:12px;min-width:18px;padding:2px 5px;font-size:10px}\n.navbar{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:40}.navbar-inner{max-width:1500px;margin:auto;display:flex;align-items:center;padding:0 20px;overflow-x:auto}.navbar-inner a{padding:17px 18px;font-size:14px;font-weight:850;white-space:nowrap}.navbar-inner a:hover,.navbar-inner a:first-child{color:var(--pink)}\n.page{max-width:1500px;margin:auto;padding:22px 20px 60px}.flash{max-width:1500px;margin:14px auto 0;background:#fff7d8;border:1px solid #eedf94;padding:10px 13px;border-radius:8px}.layout{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:22px}.sidebar{position:sticky;top:76px}.hero{min-height:320px;border-radius:13px;background:linear-gradient(135deg,#fff7f9,#ffeef4);border:1px solid #ffe0ea;padding:42px 48px;display:grid;grid-template-columns:1.15fr .85fr;align-items:center}.hero h1{margin:0;font-size:44px;line-height:1.35;letter-spacing:-2px}.hero h1 strong{color:var(--pink)}.hero p{font-size:17px;color:#5a5d63;line-height:1.7}.hero-btn,.btn{display:inline-block;border:1px solid var(--line);background:#fff;border-radius:8px;padding:10px 14px;font-weight:900;cursor:pointer}.hero-btn,.btn.pink{background:var(--pink);border-color:var(--pink);color:#fff}.btn.dark{background:#222;border-color:#222;color:#fff}.btn.green{background:var(--green);border-color:var(--green);color:#fff}.btn.danger{background:#fff0f0;color:#a33;border-color:#efcccc}.hero-art{height:220px;display:flex;align-items:center;justify-content:center}.bag{width:160px;height:180px;background:linear-gradient(135deg,#ef91b0,#da5e89);border-radius:8px;color:white;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:950;box-shadow:0 18px 40px rgba(224,80,125,.22)}\n.shortcuts{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:18px}.shortcut{background:#fff;border:1px solid var(--line);border-radius:10px;min-height:110px;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:7px;text-align:center;font-weight:900}.ico{width:50px;height:50px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:23px;background:#ffe8f0}.section{margin-top:34px}.section-head{display:flex;justify-content:space-between;align-items:end;gap:12px;margin-bottom:14px}.section-head h2{margin:0;font-size:24px}.muted{color:var(--muted);font-size:12px}.product-grid,.compare-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card,.compare-card{background:#fff;border:1px solid var(--line);border-radius:11px;overflow:hidden}.card-img{aspect-ratio:1/1;background:#f4f1ee;display:flex;align-items:center;justify-content:center;font-size:52px;overflow:hidden;position:relative}.card-img img{width:100%;height:100%;object-fit:cover}.badge{position:absolute;top:9px;left:9px;background:var(--pink);color:white;padding:5px 7px;border-radius:6px;font-size:10px;font-weight:900}.card-body{padding:13px}.tag{display:inline-block;background:#ffe4ee;color:var(--pink);padding:4px 6px;border-radius:5px;font-size:10px;font-weight:900}.card-title{font-size:14px;font-weight:900;min-height:38px;line-height:1.4;margin-top:7px}.sale{color:var(--pink);font-size:18px;font-weight:950;margin-top:8px}.original{color:#9ca0a5;font-size:12px;text-decoration:line-through}.card-actions{display:flex;gap:6px;margin-top:10px}.card-actions form{flex:1}.card-actions button{width:100%;padding:8px;border-radius:7px;border:1px solid var(--line);background:white}.compare-search{display:flex;border:1.5px solid #ffd4e2;border-radius:9px;overflow:hidden;background:white;height:48px}.compare-search input{flex:1;border:0;outline:0;padding:0 14px}.compare-search button{width:130px;border:0;background:var(--pink);color:white;font-weight:900}.compare-img{aspect-ratio:1.35/1;background:#f6f6f6;display:flex;align-items:center;justify-content:center;font-size:45px}.compare-body{padding:12px}.lowest{color:var(--pink);font-weight:950;margin-top:7px}.outline-btn{display:block;border:1px solid var(--pink);color:var(--pink);text-align:center;padding:8px;border-radius:6px;margin-top:9px;font-size:12px;font-weight:900}\n.vendor-box,.panel,.form,.side-card,.admin-box,.offer-table{background:#fff;border:1px solid var(--line);border-radius:11px}.vendor-box{border:2px solid var(--pink);overflow:hidden}.vendor-head{padding:15px;border-bottom:1px solid var(--line)}.vendor-item{display:grid;grid-template-columns:55px 1fr;gap:11px;padding:13px;border-bottom:1px solid var(--line)}.vendor-logo{width:55px;height:55px;border-radius:10px;background:#f6f6f8;display:flex;align-items:center;justify-content:center;font-weight:950}.vendor-item h4{margin:0 0 4px}.vendor-item p{margin:0;font-size:11px;color:var(--muted)}.vendor-link{display:inline-block;background:#ff738b;color:white;border-radius:5px;padding:6px 12px;font-size:11px;font-weight:900;margin-top:6px}.side-card{padding:16px;margin-top:13px}.form{max-width:800px;margin:auto;padding:24px}.panel{padding:22px}.field{margin:14px 0}.field label{display:block;font-size:13px;font-weight:900;margin-bottom:7px}.field input,.field select,.field textarea{width:100%;padding:12px;border:1px solid #dadbe0;border-radius:8px}.field textarea{min-height:140px}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.table{background:white;border:1px solid var(--line);border-radius:11px;overflow:hidden}.tr{display:grid;grid-template-columns:1.4fr .8fr .8fr .8fr;gap:10px;padding:13px 15px;border-bottom:1px solid var(--line);align-items:center}.tr.head{background:#f6f6f8;font-weight:900}.empty{background:white;border:1px solid var(--line);border-radius:11px;padding:38px;text-align:center;color:var(--muted)}\n.profile-grid{display:grid;grid-template-columns:230px 1fr;gap:18px}.profile-menu{background:white;border:1px solid var(--line);border-radius:11px;overflow:hidden}.profile-menu a{display:block;padding:13px 15px;border-bottom:1px solid var(--line);font-weight:800}.profile-menu a:hover{color:var(--pink);background:#fff7fa}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.summary .panel{text-align:center}.summary strong{display:block;font-size:25px;color:var(--pink);margin-top:5px}\nfooter{background:#1c1c1d;color:#d7d7da;margin-top:55px}.footer-inner{max-width:1500px;margin:auto;padding:32px 22px;display:grid;grid-template-columns:1.4fr repeat(3,1fr);gap:25px;font-size:12px;line-height:1.8}.footer-brand{font-size:20px;font-weight:950;color:#fff}.copyright{text-align:center;border-top:1px solid #333;padding:13px;font-size:11px;color:#999}\n@media(max-width:1100px){.top-inner{grid-template-columns:220px 1fr}.quick-icons{display:none}.layout{grid-template-columns:1fr}.sidebar{position:static}.product-grid,.compare-grid{grid-template-columns:repeat(2,1fr)}}\n@media(max-width:720px){.top-inner{grid-template-columns:1fr;padding:11px}.logo-wrap{justify-content:center}.logo-sub{display:none}.page{padding:13px 11px 40px}.navbar-inner{padding:0 5px}.navbar-inner a{padding:15px 11px;font-size:12px}.hero{grid-template-columns:1fr;padding:28px 22px;min-height:auto}.hero h1{font-size:31px}.hero-art{height:150px}.bag{width:115px;height:130px;font-size:21px}.shortcuts{grid-template-columns:repeat(5,120px);overflow-x:auto}.row,.profile-grid{grid-template-columns:1fr}.summary{grid-template-columns:repeat(3,1fr)}.tr{grid-template-columns:1fr 1fr}.tr.head{display:none}.footer-inner{grid-template-columns:1fr 1fr}}\n/* MOBILE V2 */\n@media(max-width:760px){\nhtml,body{width:100%;max-width:100%;overflow-x:hidden}\n.top-inner{display:flex;flex-direction:column;gap:10px;min-height:auto;padding:14px 12px 12px}\n.logo-wrap{width:100%;justify-content:center;gap:8px}.logo-icon{width:34px;height:34px}.logo{font-size:26px}.logo-sub,.quick-icons{display:none}\n.search-main{width:100%;height:44px}.search-main input{min-width:0;font-size:13px}.search-main button{width:52px}\n.navbar-inner{width:100%;min-height:46px;overflow-x:auto;flex-wrap:nowrap;gap:0;padding:0 6px;scrollbar-width:none}.navbar-inner::-webkit-scrollbar{display:none}\n.navbar-inner a{flex:0 0 auto;padding:14px 10px;font-size:11px}.navbar-inner a:nth-last-child(-n+3){display:none}\n.page{width:100%;padding:12px 10px 32px}.layout{display:block}.maincol{width:100%}\n.hero{min-height:235px;padding:22px 20px;border-radius:13px;display:block;position:relative}\n.hero h1{max-width:76%;font-size:28px;line-height:1.38;letter-spacing:-1.1px}.hero p{max-width:72%;margin:13px 0 16px;font-size:12px;line-height:1.6}\n.hero-btn{padding:10px 14px;font-size:12px}.hero-art{position:absolute;right:16px;bottom:18px;width:82px;height:82px;margin:0;display:block}\n.hero-art .product-mock{display:none}.bag{width:82px;height:82px;border-radius:11px;font-size:17px;box-shadow:none}\n.shortcuts{width:100%;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px;margin-top:11px;overflow:visible}\n.shortcut{min-width:0;min-height:78px;padding:7px 2px;gap:4px;border-radius:8px;font-size:9px;line-height:1.2}.shortcut .ico{width:36px;height:36px;font-size:17px}.shortcut span{display:none}\n.section{margin-top:23px}.section-head{margin-bottom:10px}.section-head h2{font-size:19px}.section-head a{font-size:10px}\n.product-grid,.compare-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.card,.compare-card{min-width:0}\n.card-body,.compare-body{padding:9px}.card-title,.compare-title{font-size:11px;min-height:32px}.sale,.lowest{font-size:14px}.original{font-size:9px}\n.compare-search{height:42px}.compare-search input{font-size:11px;min-width:0}.compare-search button{width:82px;font-size:11px}\n.sidebar{position:static;width:100%;margin-top:22px}.vendor-box{display:block;width:100%;border-width:1.5px}\n.vendor-item{grid-template-columns:46px minmax(0,1fr);gap:9px;padding:11px}.vendor-logo{width:46px;height:46px;font-size:13px}\n.vendor-item h4{font-size:12px}.vendor-item p{font-size:9px}.vendor-link{padding:5px 10px;font-size:9px}\n.row,.profile-grid{grid-template-columns:1fr}.form{width:100%;padding:15px}.footer-inner{grid-template-columns:1fr 1fr;gap:16px;padding:23px 14px;font-size:9px}\n}\n@media(max-width:390px){.hero h1{font-size:25px}.hero p{font-size:11px}.shortcuts{gap:4px}.shortcut{font-size:8px}}\n</style>\n</head>\n<body>\n<div class="top"><div class="top-inner">\n<div class="logo-wrap"><div class="logo-icon">\u2661</div><a class="logo" href="{{url_for(\'home\')}}">\ubcf4\ucc0c\ubbf8</a><span class="logo-sub">\uc88b\uc740 \uc81c\ud488\uc744 \uc88b\uc740 \uac00\uaca9\uc5d0</span></div>\n<form class="search-main" action="{{url_for(\'compare\')}}"><input name="q" placeholder="\uc0c1\ud488\uba85, \ube0c\ub79c\ub4dc, \ubaa8\ub378\uba85\uc744 \uac80\uc0c9\ud574\ubcf4\uc138\uc694"><button>\u2315</button></form>\n<div class="quick-icons">\n{% if session.get(\'user_id\') %}<a href="{{url_for(\'mypage\')}}"><b>\u2659</b>{{session.get(\'nickname\')}}\ub2d8</a>{% else %}<a href="{{url_for(\'login\')}}"><b>\u2659</b>\ub85c\uadf8\uc778</a>{% endif %}\n<a href="{{url_for(\'favorites_page\')}}"><b>\u2661</b>\ucc1c \ubaa9\ub85d{% if counts.favorites %}<span class="count">{{counts.favorites}}</span>{% endif %}</a>\n<a href="{{url_for(\'cart\')}}"><b>\U0001f6d2</b>\uc7a5\ubc14\uad6c\ub2c8{% if counts.cart %}<span class="count">{{counts.cart}}</span>{% endif %}</a>\n</div></div></div>\n<div class="navbar"><div class="navbar-inner"><a href="{{url_for(\'home\')}}">\ubcf4\ucc0c\ubbf8 \ud648</a><a href="{{url_for(\'shop\')}}">\uc624\ub298\uc758 \ucc1c / \uacf5\ub3d9\uad6c\ub9e4</a><a href="{{url_for(\'brand_page\',brand=\'\uc5c4\ub9c8\uc7a5\ub3c5\')}}">\uc5c4\ub9c8\uc7a5\ub3c5</a><a href="{{url_for(\'brand_page\',brand=\'RUBIE\')}}">RUBIE</a><a href="{{url_for(\'compare\')}}">\ucd5c\uc800\uac00 \ucc3e\uae30</a>{% if session.get(\'user_id\') %}<a href="{{url_for(\'orders\')}}">\uc8fc\ubb38\ub0b4\uc5ed</a><a href="{{url_for(\'mypage\')}}">\ub9c8\uc774\ud398\uc774\uc9c0</a>{% endif %}{% if session.get(\'admin\') %}<a href="{{url_for(\'admin_dashboard\')}}">\uad00\ub9ac\uc790</a>{% endif %}</div></div>\n{% with msgs=get_flashed_messages() %}{% for m in msgs %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}\n<div class="page">{{content|safe}}</div>\n<footer><div class="footer-inner"><div><div class="footer-brand">\ubcf4\ucc0c\ubbf8</div>\uc88b\uc740 \uac83\ub9cc \uace8\ub77c \ucc1c.</div><div><b>\ud68c\uc0ac \uc815\ubcf4</b><br>\ud68c\uc0ac\uc18c\uac1c<br>\uc774\uc6a9\uc57d\uad00<br>\uac1c\uc778\uc815\ubcf4\ucc98\ub9ac\ubc29\uce68</div><div><b>\uace0\uac1d\uc13c\ud130</b><br>\uacf5\uc9c0\uc0ac\ud56d<br>1:1 \ubb38\uc758<br>\uc790\uc8fc \ubb3b\ub294 \uc9c8\ubb38</div><div><b>\ud30c\ud2b8\ub108</b><br>\ud310\ub9e4\uc790 \uc81c\ud734<br>\uc785\uc810 \uc548\ub0b4<br>\uad11\uace0 \ubb38\uc758</div></div><div class="copyright">\xa9 2026 BOJJIMI</div></footer>\n</body></html>'


def page(title, body, **ctx):
    content=render_template_string(body, **ctx)
    return render_template_string(BASE_HTML, title=title, content=content, counts=user_counts())


def product_card(p):
    img=f'<img src="{p['image_url']}" alt="">' if p['image_url'] else '\U0001f381'
    sale=f'{money(p['sale_price'])}\uc6d0' if p['sale_price'] else '\uac00\uaca9\ubb38\uc758'
    original=f'<div class="original">\uc815\uc0c1\uac00 {money(p['original_price'])}\uc6d0</div>' if p['original_price'] else ''
    badge=f'<div class="badge">{p['badge']}</div>' if p['badge'] else ''
    actions=''
    if session.get('user_id'):
        actions=f'''<div class="card-actions"><form method="post" action="{url_for('favorite_toggle',product_id=p['id'])}"><button>\u2661 \ucc1c</button></form><form method="post" action="{url_for('cart_add',product_id=p['id'])}"><button>\U0001f6d2 \ub2f4\uae30</button></form></div>'''
    return f'''<div class="card"><a href="{url_for('product_detail',product_id=p['id'])}"><div class="card-img">{badge}{img}</div><div class="card-body"><span class="tag">{p['brand'] or p['product_type']}</span><div class="card-title">{p['title']}</div><div class="sale">{sale}</div>{original}</div></a><div class="card-body" style="padding-top:0">{actions}</div></div>'''



@app.after_request
def force_utf8_response(response):
    if response.mimetype in ('text/html', 'text/plain', 'application/json'):
        response.headers['Content-Type'] = f"{response.mimetype}; charset=utf-8"
    return response

@app.route('/')
def home():
    conn=db()
    products=conn.execute('SELECT * FROM products WHERE featured=1 ORDER BY id DESC LIMIT 4').fetchall()
    compares=conn.execute('SELECT c.*,(SELECT MIN(o.price+o.shipping) FROM compare_offers o WHERE o.item_id=c.id) lowest FROM compare_items c ORDER BY c.id DESC LIMIT 4').fetchall()
    vendors=conn.execute('SELECT * FROM vendors WHERE active=1 ORDER BY sort_order,id').fetchall()
    conn.close()
    return page('\ud648', '\n    <div class="layout"><main>\n    <section class="hero"><div><h1>\uc88b\uc740 \uc81c\ud488\uc744<br><strong>\uc88b\uc740 \uc0ac\ub78c\ub4e4\uacfc</strong><br>\uc88b\uc740 \uac00\uaca9\uc5d0</h1><p>\uc5c4\ub9c8\uc7a5\ub3c5 \xb7 RUBIE \xb7 \uacf5\ub3d9\uad6c\ub9e4 \xb7 \ucd5c\uc800\uac00 \ube44\uad50\uae4c\uc9c0<br>\ubcf4\ucc0c\ubbf8\uc5d0\uc11c \ud55c \ubc88\uc5d0.</p><a class="hero-btn" href="{{url_for(\'shop\')}}">\uc624\ub298\uc758 \ucc1c \ubcf4\ub7ec\uac00\uae30</a></div><div class="hero-art"><div class="bag">\ubcf4\ucc0c\ubbf8</div></div></section>\n    <div class="shortcuts"><a class="shortcut" href="{{url_for(\'shop\')}}"><div class="ico">\U0001f3f7</div>\uc624\ub298\uc758 \ucc1c</a><a class="shortcut" href="{{url_for(\'brand_page\',brand=\'\uc5c4\ub9c8\uc7a5\ub3c5\')}}"><div class="ico">\U0001f3fa</div>\uc5c4\ub9c8\uc7a5\ub3c5</a><a class="shortcut" href="{{url_for(\'brand_page\',brand=\'RUBIE\')}}"><div class="ico">\U0001f33f</div>RUBIE</a><a class="shortcut" href="{{url_for(\'favorites_page\')}}"><div class="ico">\u2661</div>\ucc1c \ubaa9\ub85d</a><a class="shortcut" href="{{url_for(\'compare\')}}"><div class="ico">\u2315</div>\ucd5c\uc800\uac00 \ucc3e\uae30</a></div>\n    <section class="section"><div class="section-head"><h2>\uc624\ub298\uc758 \ucc1c / \uacf5\ub3d9\uad6c\ub9e4</h2><a href="{{url_for(\'shop\')}}">\uc804\uccb4 \ubcf4\uae30 \u203a</a></div><div class="product-grid">{% for p in products %}{{product_card(p)|safe}}{% endfor %}</div></section>\n    <section class="section"><div class="section-head"><h2>\ucd5c\uc800\uac00 \ucc3e\uae30</h2><a href="{{url_for(\'compare\')}}">\uc804\uccb4 \ubcf4\uae30 \u203a</a></div><div class="compare-grid">{% for x in compares %}<div class="compare-card"><div class="compare-img">\U0001f50e</div><div class="compare-body"><b>{{x[\'title\']}}</b><div class="lowest">{% if x[\'lowest\'] %}{{x[\'lowest\']|money}}\uc6d0~{% endif %}</div><a class="outline-btn" href="{{url_for(\'compare_detail\',item_id=x[\'id\'])}}">\ucd5c\uc800\uac00 \ubcf4\uae30</a></div></div>{% endfor %}</div></section>\n    </main><aside class="sidebar"><div class="vendor-box"><div class="vendor-head"><b>\ubcf4\ucc0c\ubbf8 \uc5f0\uacb0 \ubca4\ub354</b></div>{% for v in vendors %}<div class="vendor-item"><div class="vendor-logo">{{v[\'logo_text\']}}</div><div><h4>{{v[\'name\']}}</h4><p>{{v[\'subtext\']}}</p><a class="vendor-link" href="{{v[\'url\']}}" target="_blank">\ubc14\ub85c\uac00\uae30</a></div></div>{% endfor %}</div><div class="side-card"><b>\ud68c\uc6d0 \uba54\ub274</b><div style="line-height:2;margin-top:8px">{% if session.get(\'user_id\') %}<a href="{{url_for(\'mypage\')}}">\ub9c8\uc774\ud398\uc774\uc9c0</a><br><a href="{{url_for(\'orders\')}}">\uc8fc\ubb38\ub0b4\uc5ed</a><br><a href="{{url_for(\'addresses\')}}">\ubc30\uc1a1\uc9c0 \uad00\ub9ac</a>{% else %}<a href="{{url_for(\'register\')}}">\ud68c\uc6d0\uac00\uc785</a><br><a href="{{url_for(\'login\')}}">\ub85c\uadf8\uc778</a>{% endif %}</div></div></aside></div>\n    ',products=products,compares=compares,vendors=vendors,product_card=product_card)


@app.route('/shop')
def shop():
    conn=db(); products=conn.execute('SELECT * FROM products ORDER BY id DESC').fetchall(); conn.close()
    return page('\uc1fc\ud551','<div class="section-head"><h2>\ubcf4\ucc0c\ubbf8 \uc1fc\ud551</h2></div><div class="product-grid">{% for p in products %}{{product_card(p)|safe}}{% endfor %}</div>',products=products,product_card=product_card)


@app.route('/brand/<brand>')
def brand_page(brand):
    conn=db(); products=conn.execute('SELECT * FROM products WHERE brand=? ORDER BY id DESC',(brand,)).fetchall(); conn.close()
    return page(brand,'<section class="hero" style="min-height:220px"><div><h1>{{brand}}</h1><p>{% if brand=="\uc5c4\ub9c8\uc7a5\ub3c5" %}\uae40\uce58 \xb7 \uc870\uc120\uac04\uc7a5 \xb7 \ub41c\uc7a5{% else %}RUBIE \ub77c\uc774\ud504 \ubdf0\ud2f0 \ube0c\ub79c\ub4dc{% endif %}</p></div><div class="hero-art"><div class="bag">{{brand}}</div></div></section><section class="section"><div class="product-grid">{% for p in products %}{{product_card(p)|safe}}{% endfor %}</div></section>',brand=brand,products=products,product_card=product_card)


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn=db(); p=conn.execute('SELECT * FROM products WHERE id=?',(product_id,)).fetchone(); conn.close()
    if not p:return '\uc0c1\ud488\uc744 \ucc3e\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.',404
    return page(p['title'],'<div class="row"><div class="card-img" style="border-radius:12px;min-height:430px">{% if p[\'image_url\'] %}<img src="{{p[\'image_url\']}}">{% else %}\U0001f381{% endif %}</div><div class="form" style="max-width:none;margin:0"><span class="tag">{{p[\'brand\'] or p[\'product_type\']}}</span><h1>{{p[\'title\']}}</h1><div class="sale" style="font-size:29px">{% if p[\'sale_price\'] %}{{p[\'sale_price\']|money}}\uc6d0{% else %}\uac00\uaca9\ubb38\uc758{% endif %}</div><p>{{p[\'subtitle\'] or \'\'}}</p><div style="white-space:pre-wrap;line-height:1.8">{{p[\'description\'] or \'\'}}</div><div class="actions" style="margin-top:20px">{% if session.get(\'user_id\') %}<form method="post" action="{{url_for(\'favorite_toggle\',product_id=p[\'id\'])}}" style="display:inline"><button class="btn">\u2661 \ucc1c\ud558\uae30</button></form><form method="post" action="{{url_for(\'cart_add\',product_id=p[\'id\'])}}" style="display:inline"><button class="btn pink">\U0001f6d2 \uc7a5\ubc14\uad6c\ub2c8</button></form>{% endif %}{% if p[\'buy_url\'] and p[\'buy_url\']!=\'#\' %}<a class="btn green" href="{{p[\'buy_url\']}}" target="_blank">\uc678\ubd80 \uad6c\ub9e4\ucc98</a>{% endif %}</div></div></div>',p=p)


# \ud68c\uc6d0\uac00\uc785 / \ub85c\uadf8\uc778
@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); nickname=request.form.get('nickname','').strip(); phone=request.form.get('phone','').strip(); pw=request.form.get('password','')
        if not email or not nickname or len(pw)<6:
            flash('\uc774\uba54\uc77c\xb7\ub2c9\ub124\uc784\uc744 \uc785\ub825\ud558\uace0 \ube44\ubc00\ubc88\ud638\ub294 6\uc790 \uc774\uc0c1\uc73c\ub85c \uc124\uc815\ud574\uc8fc\uc138\uc694.'); return redirect(url_for('register'))
        conn=db()
        try:
            cur=conn.execute('INSERT INTO users(email,nickname,phone,password_hash) VALUES(?,?,?,?)',(email,nickname,phone,generate_password_hash(pw))); conn.commit()
            session['user_id']=cur.lastrowid; session['nickname']=nickname
            flash('\ubcf4\ucc0c\ubbf8 \ud68c\uc6d0\uac00\uc785\uc774 \uc644\ub8cc\ub418\uc5c8\uc2b5\ub2c8\ub2e4.'); return redirect(url_for('home'))
        except sqlite3.IntegrityError:
            flash('\uc774\ubbf8 \uac00\uc785\ub41c \uc774\uba54\uc77c\uc785\ub2c8\ub2e4.')
        finally: conn.close()
    return page('\ud68c\uc6d0\uac00\uc785','<div class="form"><h2>\ubcf4\ucc0c\ubbf8 \ud68c\uc6d0\uac00\uc785</h2><form method="post"><div class="field"><label>\uc774\uba54\uc77c</label><input type="email" name="email" required></div><div class="field"><label>\ub2c9\ub124\uc784</label><input name="nickname" required></div><div class="field"><label>\ud734\ub300\ud3f0</label><input name="phone"></div><div class="field"><label>\ube44\ubc00\ubc88\ud638</label><input type="password" name="password" minlength="6" required></div><button class="btn pink" style="width:100%">\ud68c\uc6d0\uac00\uc785</button></form></div>')


@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); pw=request.form.get('password','')
        conn=db(); u=conn.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); conn.close()
        if u and check_password_hash(u['password_hash'],pw):
            session['user_id']=u['id']; session['nickname']=u['nickname']
            flash('\ub85c\uadf8\uc778\ub418\uc5c8\uc2b5\ub2c8\ub2e4.'); return redirect(request.args.get('next') or url_for('home'))
        flash('\uc774\uba54\uc77c \ub610\ub294 \ube44\ubc00\ubc88\ud638\uac00 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.')
    return page('\ub85c\uadf8\uc778','<div class="form"><h2>\ub85c\uadf8\uc778</h2><form method="post"><div class="field"><label>\uc774\uba54\uc77c</label><input type="email" name="email" required></div><div class="field"><label>\ube44\ubc00\ubc88\ud638</label><input type="password" name="password" required></div><button class="btn pink" style="width:100%">\ub85c\uadf8\uc778</button></form><p style="text-align:center"><a href="{{url_for(\'register\')}}">\uc544\uc9c1 \ud68c\uc6d0\uc774 \uc544\ub2c8\uc2e0\uac00\uc694? \ud68c\uc6d0\uac00\uc785</a></p></div>')


@app.route('/logout')
def logout():
    session.pop('user_id',None); session.pop('nickname',None); flash('\ub85c\uadf8\uc544\uc6c3\ub418\uc5c8\uc2b5\ub2c8\ub2e4.'); return redirect(url_for('home'))


@app.route('/mypage')
@user_required
def mypage():
    conn=db(); u=conn.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone(); fav=conn.execute('SELECT COUNT(*) c FROM favorites WHERE user_id=?',(u['id'],)).fetchone()['c']; cartn=conn.execute('SELECT COALESCE(SUM(quantity),0)c FROM cart_items WHERE user_id=?',(u['id'],)).fetchone()['c']; ordersn=conn.execute('SELECT COUNT(*)c FROM orders WHERE user_id=?',(u['id'],)).fetchone()['c']; conn.close()
    return page('\ub9c8\uc774\ud398\uc774\uc9c0','<div class="profile-grid"><nav class="profile-menu"><a href="{{url_for(\'mypage\')}}">\ub9c8\uc774\ud398\uc774\uc9c0</a><a href="{{url_for(\'favorites_page\')}}">\ucc1c \ubaa9\ub85d</a><a href="{{url_for(\'cart\')}}">\uc7a5\ubc14\uad6c\ub2c8</a><a href="{{url_for(\'orders\')}}">\uc8fc\ubb38\ub0b4\uc5ed</a><a href="{{url_for(\'addresses\')}}">\ubc30\uc1a1\uc9c0 \uad00\ub9ac</a><a href="{{url_for(\'change_password\')}}">\ube44\ubc00\ubc88\ud638 \ubcc0\uacbd</a><a href="{{url_for(\'logout\')}}">\ub85c\uadf8\uc544\uc6c3</a></nav><div><div class="panel"><h2>{{u[\'nickname\']}}\ub2d8, \uc548\ub155\ud558\uc138\uc694.</h2><div class="muted">{{u[\'email\']}} \xb7 {{u[\'phone\'] or \'\ud734\ub300\ud3f0 \ubbf8\ub4f1\ub85d\'}}</div></div><div class="summary" style="margin-top:12px"><div class="panel">\ucc1c<strong>{{fav}}</strong></div><div class="panel">\uc7a5\ubc14\uad6c\ub2c8<strong>{{cartn}}</strong></div><div class="panel">\uc8fc\ubb38<strong>{{ordersn}}</strong></div></div><div class="panel" style="margin-top:12px"><h3>\ud68c\uc6d0 \uad00\ub9ac</h3><form method="post" action="{{url_for(\'withdraw\')}}" onsubmit="return confirm(\'\uc815\ub9d0 \ud68c\uc6d0\ud0c8\ud1f4\ud560\uae4c\uc694? \ud68c\uc6d0\xb7\ucc1c\xb7\uc7a5\ubc14\uad6c\ub2c8\xb7\uc8fc\ubb38 \ub370\uc774\ud130\uac00 \uc0ad\uc81c\ub429\ub2c8\ub2e4.\')"><button class="btn danger">\ud68c\uc6d0 \ud0c8\ud1f4</button></form></div></div></div>',u=u,fav=fav,cartn=cartn,ordersn=ordersn)


@app.post('/favorite/<int:product_id>')
@user_required
def favorite_toggle(product_id):
    conn=db(); exists=conn.execute('SELECT 1 FROM favorites WHERE user_id=? AND product_id=?',(session['user_id'],product_id)).fetchone()
    if exists: conn.execute('DELETE FROM favorites WHERE user_id=? AND product_id=?',(session['user_id'],product_id))
    else: conn.execute('INSERT OR IGNORE INTO favorites(user_id,product_id) VALUES(?,?)',(session['user_id'],product_id))
    conn.commit(); conn.close(); return redirect(request.referrer or url_for('shop'))


@app.route('/favorites')
@user_required
def favorites_page():
    conn=db(); items=conn.execute('SELECT p.* FROM products p JOIN favorites f ON f.product_id=p.id WHERE f.user_id=? ORDER BY f.created_at DESC',(session['user_id'],)).fetchall(); conn.close()
    return page('\ucc1c \ubaa9\ub85d','<div class="section-head"><h2>\ucc1c \ubaa9\ub85d</h2></div>{% if items %}<div class="product-grid">{% for p in items %}{{product_card(p)|safe}}{% endfor %}</div>{% else %}<div class="empty">\ucc1c\ud55c \uc0c1\ud488\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.</div>{% endif %}',items=items,product_card=product_card)


@app.post('/cart/add/<int:product_id>')
@user_required
def cart_add(product_id):
    conn=db(); row=conn.execute('SELECT quantity FROM cart_items WHERE user_id=? AND product_id=?',(session['user_id'],product_id)).fetchone()
    if row: conn.execute('UPDATE cart_items SET quantity=quantity+1 WHERE user_id=? AND product_id=?',(session['user_id'],product_id))
    else: conn.execute('INSERT INTO cart_items(user_id,product_id,quantity) VALUES(?,?,1)',(session['user_id'],product_id))
    conn.commit(); conn.close(); flash('\uc7a5\ubc14\uad6c\ub2c8\uc5d0 \ub2f4\uc558\uc2b5\ub2c8\ub2e4.'); return redirect(request.referrer or url_for('cart'))


@app.route('/cart')
@user_required
def cart():
    conn=db(); items=conn.execute('SELECT c.quantity,p.* FROM cart_items c JOIN products p ON p.id=c.product_id WHERE c.user_id=? ORDER BY c.created_at DESC',(session['user_id'],)).fetchall(); conn.close()
    subtotal=sum((x['sale_price'] or 0)*x['quantity'] for x in items)
    return page('\uc7a5\ubc14\uad6c\ub2c8','<div class="section-head"><h2>\uc7a5\ubc14\uad6c\ub2c8</h2></div>{% if items %}<div class="table">{% for x in items %}<div class="tr"><div><b>{{x[\'title\']}}</b><div class="muted">{{x[\'brand\'] or \'\'}}</div></div><div>{{x[\'sale_price\']|money}}\uc6d0</div><div><form method="post" action="{{url_for(\'cart_update\',product_id=x[\'id\'])}}"><input style="width:65px;padding:7px" type="number" min="1" name="quantity" value="{{x[\'quantity\']}}"><button class="btn">\ubcc0\uacbd</button></form></div><div><form method="post" action="{{url_for(\'cart_remove\',product_id=x[\'id\'])}}"><button class="btn danger">\uc0ad\uc81c</button></form></div></div>{% endfor %}</div><div class="panel" style="margin-top:15px;text-align:right"><b>\uc0c1\ud488 \ud569\uacc4 {{subtotal|money}}\uc6d0</b><br><a class="btn pink" style="margin-top:12px" href="{{url_for(\'checkout\')}}">\uc8fc\ubb38\ud558\uae30</a></div>{% else %}<div class="empty">\uc7a5\ubc14\uad6c\ub2c8\uac00 \ube44\uc5b4 \uc788\uc2b5\ub2c8\ub2e4.</div>{% endif %}',items=items,subtotal=subtotal)


@app.post('/cart/update/<int:product_id>')
@user_required
def cart_update(product_id):
    q=max(1,int(request.form.get('quantity',1))); conn=db(); conn.execute('UPDATE cart_items SET quantity=? WHERE user_id=? AND product_id=?',(q,session['user_id'],product_id)); conn.commit(); conn.close(); return redirect(url_for('cart'))


@app.post('/cart/remove/<int:product_id>')
@user_required
def cart_remove(product_id):
    conn=db(); conn.execute('DELETE FROM cart_items WHERE user_id=? AND product_id=?',(session['user_id'],product_id)); conn.commit(); conn.close(); return redirect(url_for('cart'))


@app.route('/addresses',methods=['GET','POST'])
@user_required
def addresses():
    conn=db()
    if request.method=='POST':
        recipient=request.form.get('recipient','').strip(); phone=request.form.get('phone','').strip(); address1=request.form.get('address1','').strip()
        if recipient and phone and address1:
            default=1 if not conn.execute('SELECT 1 FROM addresses WHERE user_id=?',(session['user_id'],)).fetchone() else 0
            conn.execute('INSERT INTO addresses(user_id,label,recipient,phone,postcode,address1,address2,is_default) VALUES(?,?,?,?,?,?,?,?)',(session['user_id'],request.form.get('label','\uae30\ubcf8 \ubc30\uc1a1\uc9c0'),recipient,phone,request.form.get('postcode',''),address1,request.form.get('address2',''),default)); conn.commit(); flash('\ubc30\uc1a1\uc9c0\ub97c \uc800\uc7a5\ud588\uc2b5\ub2c8\ub2e4.')
    rows=conn.execute('SELECT * FROM addresses WHERE user_id=? ORDER BY is_default DESC,id DESC',(session['user_id'],)).fetchall(); conn.close()
    return page('\ubc30\uc1a1\uc9c0 \uad00\ub9ac','<div class="row"><div class="form"><h2>\ubc30\uc1a1\uc9c0 \ucd94\uac00</h2><form method="post"><div class="field"><label>\ubc30\uc1a1\uc9c0 \uc774\ub984</label><input name="label" value="\uae30\ubcf8 \ubc30\uc1a1\uc9c0"></div><div class="row"><div class="field"><label>\ubc1b\ub294 \ubd84</label><input name="recipient" required></div><div class="field"><label>\uc5f0\ub77d\ucc98</label><input name="phone" required></div></div><div class="field"><label>\uc6b0\ud3b8\ubc88\ud638</label><input name="postcode"></div><div class="field"><label>\uc8fc\uc18c</label><input name="address1" required></div><div class="field"><label>\uc0c1\uc138\uc8fc\uc18c</label><input name="address2"></div><button class="btn pink" style="width:100%">\uc800\uc7a5</button></form></div><div><h2>\uc800\uc7a5\ub41c \ubc30\uc1a1\uc9c0</h2>{% for a in rows %}<div class="panel" style="margin-bottom:10px"><b>{{a[\'label\']}} {% if a[\'is_default\'] %}<span class="tag">\uae30\ubcf8</span>{% endif %}</b><p>{{a[\'recipient\']}} \xb7 {{a[\'phone\']}}</p><div>{{a[\'postcode\']}} {{a[\'address1\']}} {{a[\'address2\']}}</div><form method="post" action="{{url_for(\'address_delete\',address_id=a[\'id\'])}}" style="margin-top:10px"><button class="btn danger">\uc0ad\uc81c</button></form></div>{% else %}<div class="empty">\uc800\uc7a5\ub41c \ubc30\uc1a1\uc9c0\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.</div>{% endfor %}</div></div>',rows=rows)


@app.post('/address/<int:address_id>/delete')
@user_required
def address_delete(address_id):
    conn=db(); conn.execute('DELETE FROM addresses WHERE id=? AND user_id=?',(address_id,session['user_id'])); conn.commit(); conn.close(); return redirect(url_for('addresses'))


@app.route('/checkout',methods=['GET','POST'])
@user_required
def checkout():
    conn=db(); cartrows=conn.execute('SELECT c.quantity,p.* FROM cart_items c JOIN products p ON p.id=c.product_id WHERE c.user_id=?',(session['user_id'],)).fetchall(); addr=conn.execute('SELECT * FROM addresses WHERE user_id=? ORDER BY is_default DESC,id DESC LIMIT 1',(session['user_id'],)).fetchone()
    if not cartrows:
        conn.close(); flash('\uc7a5\ubc14\uad6c\ub2c8\uac00 \ube44\uc5b4 \uc788\uc2b5\ub2c8\ub2e4.'); return redirect(url_for('cart'))
    subtotal=sum((x['sale_price'] or 0)*x['quantity'] for x in cartrows); shipping=0; total=subtotal+shipping
    if request.method=='POST':
        recipient=request.form.get('recipient','').strip(); phone=request.form.get('phone','').strip(); address1=request.form.get('address1','').strip()
        if not recipient or not phone or not address1:
            conn.close(); flash('\ubc30\uc1a1 \uc815\ubcf4\ub97c \ubaa8\ub450 \uc785\ub825\ud574\uc8fc\uc138\uc694.'); return redirect(url_for('checkout'))
        order_no=datetime.now().strftime('BJ%Y%m%d%H%M%S')+secrets.token_hex(2).upper()
        cur=conn.execute('INSERT INTO orders(order_no,user_id,recipient,phone,postcode,address1,address2,subtotal,shipping_fee,total) VALUES(?,?,?,?,?,?,?,?,?,?)',(order_no,session['user_id'],recipient,phone,request.form.get('postcode',''),address1,request.form.get('address2',''),subtotal,shipping,total)); oid=cur.lastrowid
        conn.executemany('INSERT INTO order_items(order_id,product_id,title,price,quantity) VALUES(?,?,?,?,?)',[(oid,x['id'],x['title'],x['sale_price'] or 0,x['quantity']) for x in cartrows]); conn.execute('DELETE FROM cart_items WHERE user_id=?',(session['user_id'],)); conn.commit(); conn.close(); flash('\uc8fc\ubb38\uc774 \uc811\uc218\ub418\uc5c8\uc2b5\ub2c8\ub2e4. \ud604\uc7ac \ubc84\uc804\uc740 \uacb0\uc81c \uc5f0\ub3d9 \uc804 \uc8fc\ubb38\uc811\uc218 \ud14c\uc2a4\ud2b8\uc6a9\uc785\ub2c8\ub2e4.'); return redirect(url_for('order_detail',order_id=oid))
    conn.close()
    return page('\uc8fc\ubb38\ud558\uae30','<div class="row"><div class="form"><h2>\ubc30\uc1a1 \uc815\ubcf4</h2><form method="post"><div class="row"><div class="field"><label>\ubc1b\ub294 \ubd84</label><input name="recipient" required value="{{addr[\'recipient\'] if addr else \'\'}}"></div><div class="field"><label>\uc5f0\ub77d\ucc98</label><input name="phone" required value="{{addr[\'phone\'] if addr else \'\'}}"></div></div><div class="field"><label>\uc6b0\ud3b8\ubc88\ud638</label><input name="postcode" value="{{addr[\'postcode\'] if addr else \'\'}}"></div><div class="field"><label>\uc8fc\uc18c</label><input name="address1" required value="{{addr[\'address1\'] if addr else \'\'}}"></div><div class="field"><label>\uc0c1\uc138\uc8fc\uc18c</label><input name="address2" value="{{addr[\'address2\'] if addr else \'\'}}"></div><button class="btn pink" style="width:100%">\uc8fc\ubb38 \uc811\uc218</button></form></div><div class="panel"><h2>\uc8fc\ubb38 \uc694\uc57d</h2>{% for x in items %}<p>{{x[\'title\']}} \xd7 {{x[\'quantity\']}} <b style="float:right">{{((x[\'sale_price\'] or 0)*x[\'quantity\'])|money}}\uc6d0</b></p>{% endfor %}<hr><h3>\ucd1d {{total|money}}\uc6d0</h3><div class="muted">\u203b \uce74\ub4dc/\uac04\ud3b8\uacb0\uc81c\ub294 \ub2e4\uc74c \ub2e8\uacc4\uc5d0\uc11c PG \uc5f0\ub3d9\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.</div></div></div>',items=cartrows,addr=addr,total=total)


@app.route('/orders')
@user_required
def orders():
    conn=db(); rows=conn.execute('SELECT * FROM orders WHERE user_id=? ORDER BY id DESC',(session['user_id'],)).fetchall(); conn.close()
    return page('\uc8fc\ubb38\ub0b4\uc5ed','<div class="section-head"><h2>\uc8fc\ubb38\ub0b4\uc5ed</h2></div>{% if rows %}<div class="table"><div class="tr head"><div>\uc8fc\ubb38\ubc88\ud638</div><div>\uae08\uc561</div><div>\uc0c1\ud0dc</div><div>\uc8fc\ubb38\uc77c</div></div>{% for o in rows %}<a class="tr" href="{{url_for(\'order_detail\',order_id=o[\'id\'])}}"><div><b>{{o[\'order_no\']}}</b></div><div>{{o[\'total\']|money}}\uc6d0</div><div>{{o[\'status\']}}</div><div>{{o[\'created_at\'][:10]}}</div></a>{% endfor %}</div>{% else %}<div class="empty">\uc8fc\ubb38\ub0b4\uc5ed\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.</div>{% endif %}',rows=rows)


@app.route('/order/<int:order_id>')
@user_required
def order_detail(order_id):
    conn=db(); o=conn.execute('SELECT * FROM orders WHERE id=? AND user_id=?',(order_id,session['user_id'])).fetchone(); items=conn.execute('SELECT * FROM order_items WHERE order_id=?',(order_id,)).fetchall(); conn.close()
    if not o:return '\uc8fc\ubb38\uc744 \ucc3e\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.',404
    return page('\uc8fc\ubb38 \uc0c1\uc138','<div class="panel"><h2>\uc8fc\ubb38 {{o[\'order_no\']}}</h2><p><b>\uc0c1\ud0dc</b> {{o[\'status\']}}</p><p><b>\ubc30\uc1a1\uc9c0</b> {{o[\'recipient\']}} \xb7 {{o[\'phone\']}}<br>{{o[\'postcode\']}} {{o[\'address1\']}} {{o[\'address2\']}}</p><hr>{% for x in items %}<p>{{x[\'title\']}} \xd7 {{x[\'quantity\']}} <b style="float:right">{{(x[\'price\']*x[\'quantity\'])|money}}\uc6d0</b></p>{% endfor %}<hr><h3 style="text-align:right">\ucd1d {{o[\'total\']|money}}\uc6d0</h3></div>',o=o,items=items)


@app.route('/password',methods=['GET','POST'])
@user_required
def change_password():
    if request.method=='POST':
        current=request.form.get('current',''); new=request.form.get('new','')
        conn=db(); u=conn.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone()
        if not check_password_hash(u['password_hash'],current): flash('\ud604\uc7ac \ube44\ubc00\ubc88\ud638\uac00 \ub9de\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.')
        elif len(new)<6: flash('\uc0c8 \ube44\ubc00\ubc88\ud638\ub294 6\uc790 \uc774\uc0c1\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4.')
        else: conn.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(new),u['id'])); conn.commit(); flash('\ube44\ubc00\ubc88\ud638\uac00 \ubcc0\uacbd\ub418\uc5c8\uc2b5\ub2c8\ub2e4.')
        conn.close()
    return page('\ube44\ubc00\ubc88\ud638 \ubcc0\uacbd','<div class="form"><h2>\ube44\ubc00\ubc88\ud638 \ubcc0\uacbd</h2><form method="post"><div class="field"><label>\ud604\uc7ac \ube44\ubc00\ubc88\ud638</label><input type="password" name="current" required></div><div class="field"><label>\uc0c8 \ube44\ubc00\ubc88\ud638</label><input type="password" name="new" minlength="6" required></div><button class="btn pink" style="width:100%">\ubcc0\uacbd</button></form></div>')


@app.post('/withdraw')
@user_required
def withdraw():
    uid=session['user_id']; conn=db(); conn.execute('DELETE FROM users WHERE id=?',(uid,)); conn.commit(); conn.close(); session.clear(); flash('\ud68c\uc6d0\ud0c8\ud1f4\uac00 \uc644\ub8cc\ub418\uc5c8\uc2b5\ub2c8\ub2e4.'); return redirect(url_for('home'))


# \uac00\uaca9 \ube44\uad50
@app.route('/compare')
def compare():
    q=request.args.get('q','').strip(); conn=db()
    if q:
        like=f"%{q}%"; items=conn.execute('SELECT c.*,(SELECT MIN(o.price+o.shipping) FROM compare_offers o WHERE o.item_id=c.id) lowest FROM compare_items c WHERE c.title LIKE ? OR c.brand LIKE ? OR c.model_no LIKE ? ORDER BY c.id DESC',(like,like,like)).fetchall()
    else: items=conn.execute('SELECT c.*,(SELECT MIN(o.price+o.shipping) FROM compare_offers o WHERE o.item_id=c.id) lowest FROM compare_items c ORDER BY c.id DESC').fetchall()
    conn.close(); return page('\ucd5c\uc800\uac00 \ucc3e\uae30','<div class="section-head"><h2>\ucd5c\uc800\uac00 \ucc3e\uae30</h2></div><form class="compare-search"><input name="q" value="{{q}}" placeholder="\uc0c1\ud488\uba85, \ube0c\ub79c\ub4dc, \ubaa8\ub378\ubc88\ud638"><button>\uac80\uc0c9</button></form><div class="compare-grid" style="margin-top:15px">{% for x in items %}<div class="compare-card"><div class="compare-img">\U0001f50e</div><div class="compare-body"><b>{{x[\'title\']}}</b><div class="muted">{{x[\'brand\']}} {{x[\'model_no\']}}</div><div class="lowest">{% if x[\'lowest\'] %}{{x[\'lowest\']|money}}\uc6d0~{% endif %}</div><a class="outline-btn" href="{{url_for(\'compare_detail\',item_id=x[\'id\'])}}">\ube44\uad50 \ubcf4\uae30</a></div></div>{% endfor %}</div>',items=items,q=q)


@app.route('/compare/<int:item_id>')
def compare_detail(item_id):
    conn=db(); item=conn.execute('SELECT * FROM compare_items WHERE id=?',(item_id,)).fetchone(); offers=conn.execute('SELECT *,price+shipping total FROM compare_offers WHERE item_id=? ORDER BY total ASC,id ASC',(item_id,)).fetchall(); conn.close()
    if not item:return '\uc0c1\ud488\uc744 \ucc3e\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.',404
    best=offers[0]['total'] if offers else None
    return page(item['title'],'<div class="section-head"><h2>{{item[\'title\']}}</h2></div><div class="table"><div class="tr head"><div>\ud310\ub9e4\ucc98</div><div>\uc0c1\ud488\uac00</div><div>\ubc30\uc1a1\ube44</div><div>\uc2e4\uad6c\ub9e4\uac00</div></div>{% for o in offers %}<div class="tr"><div><b>{{o[\'seller\']}}</b>{% if o[\'total\']==best %} <span class="tag">\ucd5c\uc800\uac00</span>{% endif %}<div class="muted">{{o[\'note\']}}</div></div><div>{{o[\'price\']|money}}\uc6d0</div><div>{% if o[\'shipping\'] %}{{o[\'shipping\']|money}}\uc6d0{% else %}\ubb34\ub8cc{% endif %}</div><div><b>{{o[\'total\']|money}}\uc6d0</b></div></div>{% endfor %}</div>',item=item,offers=offers,best=best)


# \uad00\ub9ac\uc790
@app.route('/admin/login',methods=['GET','POST'])
def admin_login():
    if request.method=='POST':
        conn=db(); a=conn.execute('SELECT * FROM admins WHERE username=?',(request.form.get('username',''),)).fetchone(); conn.close()
        if a and check_password_hash(a['password_hash'],request.form.get('password','')): session['admin']=True; return redirect(url_for('admin_dashboard'))
        flash('\uad00\ub9ac\uc790 \uc544\uc774\ub514 \ub610\ub294 \ube44\ubc00\ubc88\ud638\uac00 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.')
    return page('\uad00\ub9ac\uc790 \ub85c\uadf8\uc778','<div class="form"><h2>\uad00\ub9ac\uc790 \ub85c\uadf8\uc778</h2><form method="post"><div class="field"><label>\uc544\uc774\ub514</label><input name="username"></div><div class="field"><label>\ube44\ubc00\ubc88\ud638</label><input type="password" name="password"></div><button class="btn dark" style="width:100%">\ub85c\uadf8\uc778</button></form></div>')


@app.route('/admin')
@admin_required
def admin_dashboard():
    conn=db(); usersn=conn.execute('SELECT COUNT(*)c FROM users').fetchone()['c']; ordersn=conn.execute('SELECT COUNT(*)c FROM orders').fetchone()['c']; productsn=conn.execute('SELECT COUNT(*)c FROM products').fetchone()['c']; conn.close()
    return page('\uad00\ub9ac\uc790','<div class="section-head"><h2>\ubcf4\ucc0c\ubbf8 \uad00\ub9ac\uc790</h2></div><div class="summary"><div class="panel">\ud68c\uc6d0<strong>{{usersn}}</strong></div><div class="panel">\uc0c1\ud488<strong>{{productsn}}</strong></div><div class="panel">\uc8fc\ubb38<strong>{{ordersn}}</strong></div></div><div class="panel" style="margin-top:15px"><a class="btn pink" href="{{url_for(\'admin_users\')}}">\ud68c\uc6d0\uad00\ub9ac</a> <a class="btn" href="{{url_for(\'shop\')}}">\uc0c1\ud488\ubcf4\uae30</a></div>',usersn=usersn,ordersn=ordersn,productsn=productsn)


@app.route('/admin/users')
@admin_required
def admin_users():
    conn=db(); rows=conn.execute('SELECT u.*,(SELECT COUNT(*) FROM orders o WHERE o.user_id=u.id) order_count FROM users u ORDER BY u.id DESC').fetchall(); conn.close()
    return page('\ud68c\uc6d0\uad00\ub9ac','<div class="section-head"><h2>\ud68c\uc6d0\uad00\ub9ac</h2></div><div class="table"><div class="tr head"><div>\ud68c\uc6d0</div><div>\uc774\uba54\uc77c</div><div>\ud734\ub300\ud3f0</div><div>\uc8fc\ubb38</div></div>{% for u in rows %}<div class="tr"><div><b>{{u[\'nickname\']}}</b></div><div>{{u[\'email\']}}</div><div>{{u[\'phone\'] or \'-\'}}</div><div>{{u[\'order_count\']}}\uac74</div></div>{% endfor %}</div>',rows=rows)


if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')),debug=False)
