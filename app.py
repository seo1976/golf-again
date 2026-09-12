from flask import Flask, request, redirect, url_for, session, flash, render_template_string
import sqlite3, os, hashlib
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ai-hr-lab-dev-change-me')
DB = os.path.join(os.path.dirname(__file__), 'ai_hr_lab.db')

SERVICES = {
    'start': {'name':'START','price':290000,'desc':'소규모 채용을 위한 핵심 면접 설계','items':['직무 핵심요건 정리','핵심역량 4개','구조화 질문 10개','기본 평가표']},
    'pro': {'name':'PRO','price':590000,'desc':'AI HR LAB의 표준 구조화 면접 시스템','items':['직무분석','핵심역량 모델','구조화 질문 20개','Evidence Check™ 추가질문','행동평가기준','면접관 기록지','지원자 평가표','종합의견서']},
    'custom': {'name':'CUSTOM','price':990000,'desc':'중요직무·관리직용 맞춤 채용 프로젝트','items':['PRO 전체','맞춤 채용공고','서류평가기준','면접 진행 프로토콜','면접관 Quick Guide','공정채용 체크리스트','1회 수정']},
    'partner': {'name':'HR PARTNER','price':290000,'desc':'반복채용 기업을 위한 월 구독형 파트너십','items':['월 1개 직무 면접세트','기존 자료 업데이트','질문·평가기준 보완','기업별 프로젝트 보관']}
}

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def pw_hash(p):
    return hashlib.sha256(('AIHRLAB::'+p).encode()).hexdigest()

def init_db():
    con=db(); cur=con.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
      company TEXT NOT NULL, contact_name TEXT NOT NULL,
      phone TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS diagnoses(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      company TEXT, industry TEXT, role TEXT, headcount TEXT,
      hiring_issue TEXT, email TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS projects(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL, service_key TEXT NOT NULL,
      role TEXT NOT NULL, headcount TEXT, experience TEXT,
      duties TEXT, competencies TEXT, concern TEXT,
      status TEXT NOT NULL DEFAULT '접수완료',
      created_at TEXT NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
    ''')
    con.commit(); con.close()
init_db()

def user_required(fn):
    @wraps(fn)
    def wrapper(*a,**k):
        if not session.get('user_id'):
            flash('기업회원 로그인이 필요합니다.')
            return redirect(url_for('login', next=request.path))
        return fn(*a,**k)
    return wrapper

def current_user():
    if not session.get('user_id'): return None
    con=db(); u=con.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone(); con.close(); return u

def money(v): return f'{int(v):,}원'
app.jinja_env.filters['money']=money

BASE='''
<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} | AI HR LAB</title>
<style>
*{box-sizing:border-box} :root{--navy:#101b33;--blue:#315eea;--sky:#eef3ff;--line:#e5e9f2;--ink:#172033;--muted:#697386;--bg:#f7f9fc;--green:#14a47b}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR',Arial,sans-serif;line-height:1.55}
a{text-decoration:none;color:inherit}.top{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}.topin{max-width:1180px;margin:auto;height:76px;display:flex;align-items:center;gap:28px;padding:0 22px}.logo{font-size:24px;font-weight:900;letter-spacing:-1px;color:var(--navy)}.logo span{color:var(--blue)}.tag{font-size:12px;color:var(--muted)}nav{margin-left:auto;display:flex;gap:24px;align-items:center;font-size:14px;font-weight:700}.btn{display:inline-block;background:var(--blue);color:#fff;padding:12px 18px;border-radius:10px;border:0;font-weight:800;cursor:pointer}.btn.ghost{background:#fff;color:var(--blue);border:1px solid #c9d5ff}.btn.dark{background:var(--navy)}.page{max-width:1180px;margin:auto;padding:38px 22px 80px}.hero{display:grid;grid-template-columns:1.15fr .85fr;gap:34px;align-items:center;padding:42px 0 54px}.eyebrow{color:var(--blue);font-weight:900;font-size:14px}.hero h1{font-size:48px;line-height:1.14;letter-spacing:-2px;margin:10px 0 18px}.hero p{font-size:19px;color:var(--muted);max-width:720px}.hero-card{background:linear-gradient(150deg,#162341,#315eea);color:#fff;border-radius:26px;padding:30px;box-shadow:0 20px 55px #1c3d8a2b}.hero-card h3{font-size:23px;margin-top:0}.flow{display:grid;gap:10px}.flow div{background:#ffffff14;border:1px solid #ffffff22;padding:12px 14px;border-radius:12px}.section{padding:34px 0}.section h2{font-size:32px;letter-spacing:-1px;margin:0 0 10px}.lead{color:var(--muted);margin:0 0 24px}.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:0 8px 22px #2f4b7a0a}.card h3{margin:0 0 8px}.price{font-size:28px;font-weight:900;margin:14px 0}.muted{color:var(--muted)}.badge{display:inline-block;padding:5px 9px;border-radius:999px;background:var(--sky);color:var(--blue);font-size:12px;font-weight:900}.badge.green{background:#e9faf5;color:var(--green)}ul.clean{padding-left:18px;color:#3e4a60}.feature{font-size:14px}.feature b{display:block;font-size:16px;margin-bottom:5px}.steps{counter-reset:s}.step{position:relative;padding-left:52px}.step:before{counter-increment:s;content:counter(s);position:absolute;left:0;top:0;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:var(--navy);color:#fff;font-weight:900}.formbox{max-width:760px;margin:auto;background:#fff;border:1px solid var(--line);border-radius:20px;padding:28px}.row{display:grid;grid-template-columns:1fr 1fr;gap:14px}.field{margin-bottom:15px}.field label{display:block;font-size:13px;font-weight:800;margin-bottom:6px}.field input,.field textarea,.field select{width:100%;padding:12px 13px;border:1px solid #dbe1eb;border-radius:10px;background:#fff;font:inherit}.field textarea{min-height:110px}.flash{max-width:1180px;margin:12px auto 0;padding:12px 22px;background:#fff7d9;border:1px solid #f4de8b;border-radius:10px}.kpi{font-size:30px;font-weight:900}.project{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center}.status{padding:6px 10px;border-radius:999px;background:#edf7f4;color:#118363;font-size:12px;font-weight:900}.evidence{background:#0f1b33;color:#fff;border-radius:20px;padding:28px}.evidence .cols{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.evidence .cols div{background:#ffffff10;padding:16px;border-radius:12px}.footer{background:#0d172d;color:#c5ccda;padding:40px 22px}.footerin{max-width:1180px;margin:auto;display:flex;justify-content:space-between;gap:30px}.footer b{color:#fff}.small{font-size:12px}.center{text-align:center}.notice{background:#fff;border-left:4px solid var(--blue);padding:14px 16px;border-radius:8px;color:#4c5870}
@media(max-width:820px){.hero{grid-template-columns:1fr}.hero h1{font-size:38px}.grid4,.grid3{grid-template-columns:1fr}.row{grid-template-columns:1fr}nav a.hide-m{display:none}.tag{display:none}.topin{gap:12px}.page{padding-top:24px}.evidence .cols{grid-template-columns:1fr}.footerin{display:block}}
</style></head><body>
<div class="top"><div class="topin"><a class="logo" href="{{url_for('home')}}">AI <span>HR</span> LAB</a><span class="tag">Evidence-Based Hiring System</span><nav><a class="hide-m" href="{{url_for('services')}}">서비스</a><a class="hide-m" href="{{url_for('diagnosis')}}">무료 채용진단</a>{% if user %}<a href="{{url_for('dashboard')}}">기업 대시보드</a><a href="{{url_for('logout')}}">로그아웃</a>{% else %}<a href="{{url_for('login')}}">로그인</a><a class="btn" href="{{url_for('diagnosis')}}">무료 진단</a>{% endif %}</nav></div></div>
{% with msgs=get_flashed_messages() %}{% for m in msgs %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}
<div class="page">{{body|safe}}</div>
<div class="footer"><div class="footerin"><div><b>AI HR LAB</b><br><span class="small">답변의 화려함이 아니라 직무역량을 보여주는 행동증거를 평가합니다.</span></div><div class="small">기업용 구조화 채용·면접 솔루션<br>© 2026 AI HR LAB</div></div></div>
</body></html>'''

def page(title, body, **ctx):
    return render_template_string(BASE,title=title,body=body,user=current_user(),**ctx)

@app.route('/')
def home():
    body=render_template_string('''
<section class="hero"><div><div class="eyebrow">STRUCTURED INTERVIEW · EVIDENCE CHECK™</div><h1>감(感)이 아니라<br>근거로 채용하세요.</h1><p>전문 HR 인력이 부족한 기업을 위해 직무분석부터 구조화 면접, 행동증거 확인, 지원자 평가까지 한 번에 설계합니다.</p><p><a class="btn" href="{{url_for('diagnosis')}}">5분 무료 채용진단</a> <a class="btn ghost" href="{{url_for('services')}}">서비스 보기</a></p></div><div class="hero-card"><h3>기업이 받는 결과물</h3><div class="flow"><div>01. 직무분석 & 핵심역량 모델</div><div>02. 구조화 면접 질문 + 추가확인 질문</div><div>03. Evidence Check™ 행동증거 검증</div><div>04. 면접관 기록지 & 지원자 평가표</div><div>05. 종합의견서 & 채용 의사결정 근거</div></div></div></section>
<section class="section"><span class="badge">WHY AI HR LAB</span><h2>질문을 파는 회사가 아닙니다.</h2><p class="lead">기업이 더 일관되고 설명 가능한 채용판단을 할 수 있도록 ‘면접 의사결정 시스템’을 제공합니다.</p><div class="grid3"><div class="card feature"><b>직무 기반</b>추상적인 인재상이 아니라 실제 업무에서 필요한 행동을 기준으로 설계합니다.</div><div class="card feature"><b>Evidence Check™</b>지원자의 주장과 확인된 사실을 분리하고 추가확인 질문으로 행동증거를 찾습니다.</div><div class="card feature"><b>사람이 최종 판단</b>AI는 질문·기록·근거정리를 보조하고 최종 채용판단은 기업의 면접관이 합니다.</div></div></section>
<section class="section evidence"><span class="badge green">EVIDENCE CHECK™</span><h2>“고객 만족도를 크게 높였습니다.”</h2><div class="cols"><div><b>CLAIM</b><br>고객 만족도가 크게 향상됨</div><div><b>EVIDENCE</b><br>불만접수 12건 → 5건<br>절차 개선 실행 참여</div><div><b>GAP</b><br>만족도 자체의 직접 측정자료는 미확인</div></div></section>
<section class="section"><h2>서비스</h2><p class="lead">첫 채용부터 반복채용까지 필요한 만큼 선택하세요.</p><div class="grid4">{% for key,s in services.items() %}<div class="card"><span class="badge">{{s.name}}</span><h3>{{s.desc}}</h3><div class="price">{{s.price|money}}{{' /월' if key=='partner' else ''}}</div><a class="btn {{'dark' if key=='pro' else 'ghost'}}" href="{{url_for('order_service',service_key=key)}}">의뢰하기</a></div>{% endfor %}</div></section>
<section class="section"><h2>이용 방식</h2><div class="grid4"><div class="card step"><b>기업정보 입력</b><br><span class="muted">직무·인원·업무·채용 고민</span></div><div class="card step"><b>직무 분석</b><br><span class="muted">역량과 평가요소 설계</span></div><div class="card step"><b>맞춤 제작</b><br><span class="muted">질문·평가기준·기록지</span></div><div class="card step"><b>기업 납품</b><br><span class="muted">바로 면접에 사용</span></div></div></section>
''',services=SERVICES)
    return page('기업 채용을 설계하다',body)

@app.route('/services')
def services():
    body=render_template_string('''<section class="section center"><span class="badge">SERVICES</span><h2>기업 상황에 맞는 채용 솔루션</h2><p class="lead">현재 가격은 초기 시장검증용 제안가이며 실제 판매 데이터를 기반으로 조정됩니다.</p></section><div class="grid4">{% for key,s in services.items() %}<div class="card"><span class="badge">{{s.name}}</span><h3>{{s.desc}}</h3><div class="price">{{s.price|money}}{{' /월' if key=='partner' else ''}}</div><ul class="clean">{% for i in s['items'] %}<li>{{i}}</li>{% endfor %}</ul><a class="btn {{'dark' if key=='pro' else 'ghost'}}" href="{{url_for('order_service',service_key=key)}}">{{s.name}} 시작하기</a></div>{% endfor %}</div><div class="notice" style="margin-top:24px">※ AI HR LAB은 채용 의사결정을 자동으로 대신하지 않습니다. 직무 관련 질문 설계, 면접 기록, 행동증거 확인과 평가근거 정리를 지원합니다.</div>''',services=SERVICES)
    return page('서비스',body)

@app.route('/diagnosis',methods=['GET','POST'])
def diagnosis():
    if request.method=='POST':
        con=db(); con.execute('INSERT INTO diagnoses(company,industry,role,headcount,hiring_issue,email,created_at) VALUES(?,?,?,?,?,?,?)',(
            request.form.get('company'),request.form.get('industry'),request.form.get('role'),request.form.get('headcount'),request.form.get('hiring_issue'),request.form.get('email'),datetime.now().isoformat(timespec='minutes'))); con.commit(); con.close()
        return redirect(url_for('diagnosis_result',role=request.form.get('role','채용직무')))
    body='''<div class="formbox"><span class="badge">FREE DIAGNOSIS</span><h2>5분 채용진단</h2><p class="muted">현재 면접방식과 채용 고민을 알려주세요. 구조화가 필요한 지점을 확인합니다.</p><form method="post"><div class="row"><div class="field"><label>기업명</label><input name="company" required></div><div class="field"><label>업종</label><input name="industry" placeholder="예: 건강검진센터"></div></div><div class="row"><div class="field"><label>채용 직무</label><input name="role" required placeholder="예: 고객상담"></div><div class="field"><label>채용 인원</label><input name="headcount" placeholder="예: 2명"></div></div><div class="field"><label>현재 가장 어려운 점</label><textarea name="hiring_issue" placeholder="예: 면접관마다 평가가 다르고 질문이 즉흥적입니다."></textarea></div><div class="field"><label>결과 받을 이메일</label><input type="email" name="email" required></div><button class="btn" type="submit">무료 진단 결과 보기</button></form></div>'''
    return page('무료 채용진단',body)

@app.route('/diagnosis/result')
def diagnosis_result():
    role=request.args.get('role','해당 직무')
    body=render_template_string('''<div class="formbox"><span class="badge green">DIAGNOSIS COMPLETE</span><h2>{{role}} 채용의 구조화가 필요합니다.</h2><p>무료진단 단계에서는 아래 4가지를 우선 점검합니다.</p><ul class="clean"><li>모든 지원자에게 공통 핵심질문이 있는가</li><li>질문이 실제 직무역량과 연결되는가</li><li>면접관이 동일한 행동기준으로 점수를 주는가</li><li>지원자의 주장과 확인된 행동증거를 구분하는가</li></ul><p class="notice">다음 단계에서는 실제 직무정보를 기반으로 질문·추가확인·행동평가기준을 맞춤 설계합니다.</p><a class="btn dark" href="{{url_for('order_service',service_key='pro')}}">PRO 면접시스템 의뢰하기</a> <a class="btn ghost" href="{{url_for('services')}}">상품 비교</a></div>''',role=role)
    return page('진단 결과',body)

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        try:
            con=db(); con.execute('INSERT INTO users(email,password,company,contact_name,phone,created_at) VALUES(?,?,?,?,?,?)',(
                request.form['email'].strip().lower(),pw_hash(request.form['password']),request.form['company'],request.form['contact_name'],request.form.get('phone',''),datetime.now().isoformat(timespec='minutes'))); con.commit(); con.close(); flash('기업회원 가입이 완료되었습니다. 로그인해 주세요.'); return redirect(url_for('login'))
        except sqlite3.IntegrityError: flash('이미 가입된 이메일입니다.')
    body='''<div class="formbox"><h2>기업회원 가입</h2><form method="post"><div class="field"><label>기업명</label><input name="company" required></div><div class="field"><label>담당자명</label><input name="contact_name" required></div><div class="field"><label>이메일</label><input type="email" name="email" required></div><div class="field"><label>연락처</label><input name="phone"></div><div class="field"><label>비밀번호</label><input type="password" name="password" required minlength="6"></div><button class="btn" type="submit">가입하기</button></form></div>'''
    return page('기업회원 가입',body)

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        con=db(); u=con.execute('SELECT * FROM users WHERE email=? AND password=?',(request.form['email'].strip().lower(),pw_hash(request.form['password']))).fetchone(); con.close()
        if u:
            session['user_id']=u['id']; flash(f"{u['company']} 담당자님, 환영합니다."); return redirect(request.args.get('next') or url_for('dashboard'))
        flash('이메일 또는 비밀번호를 확인해 주세요.')
    body='''<div class="formbox"><h2>기업회원 로그인</h2><form method="post"><div class="field"><label>이메일</label><input type="email" name="email" required></div><div class="field"><label>비밀번호</label><input type="password" name="password" required></div><button class="btn" type="submit">로그인</button> <a class="btn ghost" href="{{url_for('register')}}">기업회원 가입</a></form></div>'''
    return page('로그인',render_template_string(body))

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('home'))

@app.route('/order/<service_key>',methods=['GET','POST'])
def order_service(service_key):
    if service_key not in SERVICES: return redirect(url_for('services'))
    if not session.get('user_id'): return redirect(url_for('login',next=request.path))
    s=SERVICES[service_key]
    if request.method=='POST':
        con=db(); con.execute('INSERT INTO projects(user_id,service_key,role,headcount,experience,duties,competencies,concern,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(
            session['user_id'],service_key,request.form['role'],request.form.get('headcount'),request.form.get('experience'),request.form.get('duties'),request.form.get('competencies'),request.form.get('concern'),'접수완료',datetime.now().isoformat(timespec='minutes'))); con.commit(); con.close(); flash('프로젝트가 접수되었습니다. 현재 프로토타입에서는 결제 대신 주문접수까지 진행됩니다.'); return redirect(url_for('dashboard'))
    body=render_template_string('''<div class="formbox"><span class="badge">{{s.name}}</span><h2>{{s.desc}}</h2><div class="price">{{s.price|money}}{{' /월' if service_key=='partner' else ''}}</div><form method="post"><div class="row"><div class="field"><label>채용 직무</label><input name="role" required></div><div class="field"><label>채용 인원</label><input name="headcount"></div></div><div class="field"><label>경력 조건</label><input name="experience" placeholder="예: 신입·경력 모두 가능"></div><div class="field"><label>주요 업무</label><textarea name="duties" placeholder="실제 수행할 업무를 가능한 구체적으로 입력해 주세요."></textarea></div><div class="field"><label>특히 보고 싶은 역량</label><input name="competencies" placeholder="예: 고객응대, 문제해결, 정확성"></div><div class="field"><label>현재 채용의 고민</label><textarea name="concern"></textarea></div><button class="btn dark" type="submit">프로젝트 접수</button></form></div>''',s=s,service_key=service_key)
    return page(f'{s["name"]} 의뢰',body)

@app.route('/dashboard')
@user_required
def dashboard():
    u=current_user(); con=db(); projects=con.execute('SELECT * FROM projects WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall(); con.close()
    body=render_template_string('''<section class="section"><span class="badge">COMPANY DASHBOARD</span><h2>{{u.company}} 채용 프로젝트</h2><p class="lead">주문한 직무별 면접시스템의 제작·납품 상태를 관리합니다.</p><div class="grid3"><div class="card"><div class="muted">진행 프로젝트</div><div class="kpi">{{projects|length}}</div></div><div class="card"><div class="muted">Evidence Check™</div><div class="kpi">ON</div></div><div class="card"><div class="muted">담당자</div><div class="kpi" style="font-size:20px">{{u.contact_name}}</div></div></div></section><section class="section"><h2>프로젝트 목록</h2>{% if projects %}{% for p in projects %}<div class="card project" style="margin-bottom:12px"><div><b>#{{p.id}} · {{p.role}}</b><br><span class="muted">{{services[p.service_key].name}} · {{p.created_at}}</span></div><span class="status">{{p.status}}</span></div>{% endfor %}{% else %}<div class="card center"><p>아직 프로젝트가 없습니다.</p><a class="btn" href="{{url_for('services')}}">첫 프로젝트 시작</a></div>{% endif %}</section>''',u=u,projects=projects,services=SERVICES)
    return page('기업 대시보드',body)

if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=True)

