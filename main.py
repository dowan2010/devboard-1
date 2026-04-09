from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy import text, or_, and_, func
from authlib.integrations.starlette_client import OAuth
from typing import Optional
from dotenv import load_dotenv

import time
import os
import json

load_dotenv()

# ─────────────── 앱 설정 ───────────────
app = FastAPI()

# 절대 경로 사용 (Render 등 배포 환경에서 working directory 문제 방지)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# ─────────────── Google OAuth ───────────────
oauth = OAuth()
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)


# ─────────────── 모델 ───────────────
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str                                  # 구글 email
    google_id: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)  # 미사용 (하위 호환)
    nickname: Optional[str] = Field(default=None)
    failed_attempts: int = Field(default=0)
    locked_until: Optional[float] = Field(default=None)
    is_admin: bool = Field(default=False)
    is_superadmin: bool = Field(default=False)
    is_owner: bool = Field(default=False)
    discord_id: Optional[str] = Field(default=None)
    github_id: Optional[str] = Field(default=None)


class Notice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(default='')
    content: str = Field(default='')
    author_id: str
    author_nickname: str = Field(default='')
    is_pinned: bool = Field(default=False)
    created_at: float = Field(default=0.0)
    updated_at: float = Field(default=0.0)


class NoticeComment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    notice_id: int = Field(index=True)
    author_id: str
    author_nickname: str = Field(default='')
    content: str = Field(default='')
    created_at: float = Field(default=0.0)


class Team(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    leader_id: str
    leader_name: str
    name: str
    description: str = Field(default='')
    dev_field: str = Field(default='')
    max_members: int = Field(default=4)
    team_image: Optional[str] = Field(default=None)
    created_at: float = Field(default=0.0)


class TeamMember(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: int
    user_id: str
    display_name: str
    status: str = Field(default='pending')   # 'pending' | 'accepted' | 'rejected'
    joined_at: float = Field(default=0.0)


class DirectMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sender_id: str
    receiver_id: str
    message: str = Field(default='')
    is_read: bool = Field(default=False)
    created_at: float = Field(default=0.0)


class RecruitInterest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int
    sender_id: str
    created_at: float = Field(default=0.0)


class Notification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str          # 받는 사람
    sender_id: str
    sender_nickname: str
    profile_id: int = Field(default=0)
    profile_name: str = Field(default='')
    notif_type: str = Field(default='interest')  # 'interest' | 'view'
    is_read: bool = Field(default=False)
    created_at: float = Field(default=0.0)


class Profile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field()
    name: str
    class_number: str
    major: str
    bio: str = Field(default='')
    past_languages: str = Field(default='')
    current_languages: str = Field(default='')
    profile_image: Optional[str] = Field(default=None)
    post_type: str = Field(default='recruit')       # 'recruit' | 'job_seek'
    dev_field: Optional[str] = Field(default=None)  # '풀스택' | '백엔드' | '프론트엔드'
    created_at: float = Field(default=0.0)


class GroupMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: int
    sender_id: str
    sender_nickname: str
    message: str = Field(default='')
    created_at: float = Field(default=0.0)


class ShowcaseProject(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str
    author_nickname: str = Field(default='')
    title: str
    description: str = Field(default='')
    url: str = Field(default='')
    thumbnail: Optional[str] = Field(default=None)   # base64
    tech_stack: str = Field(default='')              # comma separated
    category: str = Field(default='기타')            # 웹사이트 | 앱 | 게임 | 기타
    views: int = Field(default=0)
    created_at: float = Field(default=0.0)


class ShowcaseLike(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int
    user_id: str
    created_at: float = Field(default=0.0)


class ShowcaseComment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    author_id: str
    author_nickname: str = Field(default='')
    content: str = Field(default='')
    created_at: float = Field(default=0.0)


# ─────────────── DB 초기화 ───────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///database.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
    )

try:
    SQLModel.metadata.create_all(engine)
except Exception as e:
    print(f"[DB] create_all warning: {e}")

# PostgreSQL 은 "user" 가 예약어이므로 따옴표 필수
# 각 SQL 을 독립된 커넥션으로 실행 → 한 SQL 실패가 다음 SQL 에 영향 없음
_is_pg = "sqlite" not in DATABASE_URL

def _run_migration(sql: str):
    try:
        with engine.connect() as c:
            c.execute(text(sql))
            c.commit()
    except Exception:
        pass

_run_migration('ALTER TABLE "user" ADD COLUMN nickname VARCHAR' if _is_pg else
               'ALTER TABLE user ADD COLUMN nickname VARCHAR')

for idx_name in ('ix_profile_user_id', 'uq_profile_user_id', 'profile_user_id'):
    _run_migration(f"DROP INDEX IF EXISTS {idx_name}")

_user = '"user"' if _is_pg else 'user'
for col_sql in (
    f"ALTER TABLE profile ADD COLUMN post_type VARCHAR DEFAULT 'recruit'",
    f"ALTER TABLE profile ADD COLUMN dev_field VARCHAR",
    f"ALTER TABLE profile ADD COLUMN bio VARCHAR DEFAULT ''",
    f"ALTER TABLE notification ADD COLUMN notif_type VARCHAR DEFAULT 'interest'",
    f"ALTER TABLE {_user} ADD COLUMN is_admin BOOLEAN DEFAULT false",
    f"ALTER TABLE {_user} ADD COLUMN is_superadmin BOOLEAN DEFAULT false",
    f"ALTER TABLE {_user} ADD COLUMN is_owner BOOLEAN DEFAULT false",
    f"ALTER TABLE {_user} ADD COLUMN google_id VARCHAR",
    f"ALTER TABLE team ADD COLUMN team_image TEXT DEFAULT NULL",
    f"ALTER TABLE {_user} ADD COLUMN discord_id VARCHAR DEFAULT NULL",
    f"ALTER TABLE {_user} ADD COLUMN github_id VARCHAR DEFAULT NULL",
):
    _run_migration(col_sql)


# ─────────────── 캐시 ───────────────
_cache: dict = {}
_cache_ts: dict = {}


def get_all_users():
    now = time.time()
    if 'all_users' in _cache and now - _cache_ts.get('all_users', 0) < 60:
        return _cache['all_users']
    with Session(engine) as db_session:
        users = db_session.exec(select(User)).all()
    _cache['all_users'] = users
    _cache_ts['all_users'] = now
    return users


def invalidate_user_cache():
    _cache.pop('all_users', None)
    _cache_ts.pop('all_users', None)


# ─────────────── 권한 헬퍼 ───────────────
def check_admin(sess: dict) -> bool:
    uid = sess.get('user_id')
    if not uid:
        return False
    with Session(engine) as db_session:
        u = db_session.exec(select(User).where(User.username == uid)).first()
        return bool(u and u.is_admin)


def check_superadmin(sess: dict) -> bool:
    uid = sess.get('user_id')
    if not uid:
        return False
    with Session(engine) as db_session:
        u = db_session.exec(select(User).where(User.username == uid)).first()
        return bool(u and u.is_superadmin)


def check_owner(sess: dict) -> bool:
    uid = sess.get('user_id')
    if not uid:
        return False
    with Session(engine) as db_session:
        u = db_session.exec(select(User).where(User.username == uid)).first()
        return bool(u and u.is_owner)


# ─────────────── 전역 예외 핸들러 (에러 원인 로깅용) ───────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    print(f"[ERROR] {request.method} {request.url.path} → {type(exc).__name__}: {exc}")
    print(tb)
    # 디버그용: traceback 전체를 응답에 포함 (원인 파악 후 제거 예정)
    return JSONResponse({
        "error": f"{type(exc).__name__}: {exc}",
        "where": tb.strip().splitlines()[-5:]
    }, status_code=500)


# ─────────────── 미들웨어 ───────────────
# Pure ASGI middleware (BaseHTTPMiddleware 대신 사용 — Starlette 1.0.0에서 세션 접근 순서 문제 방지)
class EnforceLockMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path.startswith("/static"):
            await self.app(scope, receive, send)
            return
        session = scope.get("session", {})
        uid = session.get("user_id")
        if uid:
            with Session(engine) as db_session:
                user = db_session.exec(select(User).where(User.username == uid)).first()
                if user and user.locked_until and time.time() < user.locked_until:
                    session.clear()
                    if path.startswith("/api/"):
                        response = JSONResponse({"error": "계정이 잠금 상태입니다."}, status_code=403)
                    else:
                        response = RedirectResponse("/login_page", status_code=302)
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


# 미들웨어 등록 순서: add_middleware는 LIFO(후입선출)로 스택에 쌓임
# → 마지막에 추가한 것이 가장 바깥(outermost)에서 실행
# SessionMiddleware를 마지막에 추가 → 가장 먼저 실행 → scope["session"] 세팅 후 EnforceLock 실행
app.add_middleware(EnforceLockMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get('SECRET_KEY', 'dev-secret-key'),
    same_site='lax',
    https_only=False,
    max_age=604800,
)


# ─────────────── 기본 라우트 ───────────────
@app.get('/')
def index():
    return RedirectResponse('/main', status_code=302)


@app.get('/login_page')
def login_page(request: Request):
    show_toast = request.session.pop('show_login_toast', False)
    return templates.TemplateResponse(request, 'login.html', {'show_toast': show_toast})


# ─────────────── Google OAuth ───────────────
@app.get('/auth/google')
async def google_login(request: Request):
    redirect_uri = request.url_for('google_callback')
    return await google.authorize_redirect(request, str(redirect_uri))


@app.get('/auth/google/callback', name='google_callback')
async def google_callback(request: Request):
    try:
        token = await google.authorize_access_token(request)
    except Exception:
        request.session.clear()
        return RedirectResponse('/login_page', status_code=302)
    userinfo = token.get('userinfo')
    if not userinfo:
        return RedirectResponse('/login_page', status_code=302)

    google_id = userinfo['sub']
    email = userinfo['email']

    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.google_id == google_id)).first()
        if not user:
            request.session['pending_google_id'] = google_id
            request.session['pending_email'] = email
            return RedirectResponse('/set_nickname', status_code=302)
        if user.locked_until and time.time() < user.locked_until:
            request.session.clear()
            return RedirectResponse('/login_page', status_code=302)
        request.session['user_id'] = user.username
        request.session['nickname'] = user.nickname or user.username
        request.session['show_login_toast'] = True
        return RedirectResponse('/main', status_code=302)


@app.get('/set_nickname')
def set_nickname_page(request: Request):
    if not request.session.get('pending_google_id'):
        return RedirectResponse('/login_page', status_code=302)
    return templates.TemplateResponse(request, 'set-nickname.html')


@app.post('/set_nickname')
async def set_nickname_submit(request: Request):
    google_id = request.session.get('pending_google_id')
    email = request.session.get('pending_email')
    form = await request.form()
    nickname = str(form.get('nickname', '')).strip()

    if not google_id or not email:
        return RedirectResponse('/login_page', status_code=302)
    if not nickname:
        return templates.TemplateResponse(request, 'set-nickname.html', {'error': '닉네임을 입력해주세요.'})
    if len(nickname) > 20:
        return templates.TemplateResponse(request, 'set-nickname.html', {'error': '닉네임은 20자 이하여야 합니다.'})

    with Session(engine) as db_session:
        new_user = User(username=email, google_id=google_id, nickname=nickname)
        db_session.add(new_user)
        db_session.commit()

    invalidate_user_cache()
    request.session.pop('pending_google_id', None)
    request.session.pop('pending_email', None)
    request.session['user_id'] = email
    request.session['nickname'] = nickname
    request.session['show_login_toast'] = True
    return RedirectResponse('/main', status_code=302)


# ─────────────── 홈 / 로그아웃 ───────────────
@app.get('/main')
def home(request: Request):
    show_toast = request.session.pop('show_login_toast', False)
    nickname = request.session.get('nickname', request.session.get('user_id', '게스트'))
    admin_discord = None
    try:
        with Session(engine) as db_session:
            owner = db_session.exec(select(User).where(User.is_owner == True)).first()
            admin_discord = owner.discord_id if owner and owner.discord_id else None
    except Exception as e:
        print(f"[WARN] home DB query failed: {e}")
    return templates.TemplateResponse(request, 'main.html', {
        'user_id': nickname,
        'show_toast': show_toast,
        'is_admin': check_admin(request.session),
        'raw_user_id': request.session.get('user_id', ''),
        'admin_discord': admin_discord,
    })


@app.get('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/', status_code=302)


# ─────────────── 회원 정보 수정 ───────────────
@app.get('/settings')
def settings(request: Request):
    if 'user_id' not in request.session:
        return RedirectResponse('/login_page', status_code=302)
    return RedirectResponse(f"/user/{request.session['user_id']}", status_code=302)


@app.post('/update_social')
async def update_social(request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    form = await request.form()
    discord_id = str(form.get('discord_id', '')).strip()
    github_id = str(form.get('github_id', '')).strip()
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == request.session['user_id'])).first()
        if not user:
            return JSONResponse({"error": "사용자를 찾을 수 없습니다."}, status_code=404)
        user.discord_id = discord_id or None
        user.github_id = github_id or None
        db_session.add(user)
        db_session.commit()
    return {"success": True}


@app.post('/update_nickname')
async def update_nickname(request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    form = await request.form()
    new_nickname = str(form.get('nickname', '')).strip()
    if not new_nickname:
        return JSONResponse({"error": "닉네임을 입력해주세요."}, status_code=400)
    if len(new_nickname) > 20:
        return JSONResponse({"error": "닉네임은 20자 이하여야 합니다."}, status_code=400)
    uid = request.session['user_id']
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == uid)).first()
        if not user:
            return JSONResponse({"error": "사용자를 찾을 수 없습니다."}, status_code=404)
        user.nickname = new_nickname
        db_session.add(user)
        for n in db_session.exec(select(Notice).where(Notice.author_id == uid)).all():
            n.author_nickname = new_nickname
            db_session.add(n)
        for t in db_session.exec(select(Team).where(Team.leader_id == uid)).all():
            t.leader_name = new_nickname
            db_session.add(t)
        for m in db_session.exec(select(TeamMember).where(TeamMember.user_id == uid)).all():
            m.display_name = new_nickname
            db_session.add(m)
        for p in db_session.exec(select(Profile).where(Profile.user_id == uid)).all():
            p.name = new_nickname
            db_session.add(p)
        db_session.commit()
    request.session['nickname'] = new_nickname
    invalidate_user_cache()
    return {"success": True, "nickname": new_nickname}


# ─────────────── 멤버 보기 ───────────────
@app.get('/members')
def members_page(request: Request):
    if 'user_id' not in request.session:
        return RedirectResponse('/login_page', status_code=302)
    current_user = request.session['user_id']
    nickname = request.session.get('nickname', current_user)

    init_members = []
    try:
        with Session(engine) as db_session:
            users = db_session.exec(select(User)).all()
        members = [
            {"username": u.username, "nickname": u.nickname or u.username, "is_self": u.username == current_user}
            for u in users
        ]
        members.sort(key=lambda u: (0 if u['is_self'] else 1))
        init_members = members
    except Exception:
        pass

    return templates.TemplateResponse(request, 'members.html', {
        'user_id': nickname,
        'is_admin': check_admin(request.session),
        'raw_user_id': current_user,
        'init_members': json.dumps(init_members, ensure_ascii=False),
    })


@app.get('/api/session-check')
def session_check(request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"ok": False}, status_code=401)
    return {"ok": True}


@app.get('/api/members')
def get_members(request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_uid = request.session['user_id']
    with Session(engine) as db_session:
        users = db_session.exec(select(User)).all()
        result = [
            {
                "username": u.username,
                "nickname": u.nickname or u.username,
                "is_self": u.username == current_uid,
            }
            for u in users
        ]
    return {"members": result}


# ─────────────── 공지사항 ───────────────
@app.get('/notice')
def notice(request: Request):
    nickname = request.session.get('nickname', request.session.get('user_id', '게스트'))

    init_notices = []
    try:
        with Session(engine) as db_session:
            notices = db_session.exec(
                select(Notice).order_by(Notice.is_pinned.desc(), Notice.created_at.desc())
            ).all()
        init_notices = [
            {"id": n.id, "title": n.title, "content": n.content,
             "author_nickname": n.author_nickname, "is_pinned": n.is_pinned,
             "created_at": n.created_at, "updated_at": n.updated_at}
            for n in notices
        ]
    except Exception:
        pass

    return templates.TemplateResponse(request, 'notice.html', {
        'user_id': nickname,
        'current_user': request.session.get('user_id', ''),
        'is_admin': check_admin(request.session),
        'raw_user_id': request.session.get('user_id', ''),
        'init_notices': json.dumps(init_notices, ensure_ascii=False),
    })


@app.get('/api/notices')
def get_notices(request: Request):
    with Session(engine) as db_session:
        notices = db_session.exec(
            select(Notice).order_by(Notice.is_pinned.desc(), Notice.created_at.desc())
        ).all()
    return {"notices": [
        {
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "author_nickname": n.author_nickname,
            "is_pinned": n.is_pinned,
            "created_at": n.created_at,
            "updated_at": n.updated_at,
        } for n in notices
    ]}


@app.post('/api/notices')
async def create_notice(request: Request):
    if not check_superadmin(request.session):
        return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
    form = await request.form()
    title = str(form.get('title', '')).strip()
    content = str(form.get('content', '')).strip()
    is_pinned = str(form.get('is_pinned', 'false')) == 'true'
    if not title or not content:
        return JSONResponse({"error": "제목과 내용을 입력해주세요."}, status_code=400)
    nickname = request.session.get('nickname', request.session['user_id'])
    with Session(engine) as db_session:
        notice = Notice(
            title=title, content=content,
            author_id=request.session['user_id'], author_nickname=nickname,
            is_pinned=is_pinned,
            created_at=time.time(), updated_at=time.time()
        )
        db_session.add(notice)
        db_session.commit()
        db_session.refresh(notice)
    return {"success": True, "id": notice.id}


@app.put('/api/notices/{notice_id}')
async def update_notice(notice_id: int, request: Request):
    if not check_superadmin(request.session):
        return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
    form = await request.form()
    title = str(form.get('title', '')).strip()
    content = str(form.get('content', '')).strip()
    is_pinned = str(form.get('is_pinned', 'false')) == 'true'
    if not title or not content:
        return JSONResponse({"error": "제목과 내용을 입력해주세요."}, status_code=400)
    with Session(engine) as db_session:
        notice = db_session.get(Notice, notice_id)
        if not notice:
            return JSONResponse({"error": "공지를 찾을 수 없습니다."}, status_code=404)
        notice.title = title
        notice.content = content
        notice.is_pinned = is_pinned
        notice.updated_at = time.time()
        db_session.add(notice)
        db_session.commit()
    return {"success": True}


@app.delete('/api/notices/{notice_id}')
def delete_notice(notice_id: int, request: Request):
    if not check_superadmin(request.session):
        return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
    with Session(engine) as db_session:
        notice = db_session.get(Notice, notice_id)
        if not notice:
            return JSONResponse({"error": "공지를 찾을 수 없습니다."}, status_code=404)
        db_session.delete(notice)
        db_session.commit()
    return {"success": True}


# ─────────────── 공지 댓글 ───────────────
@app.get('/api/notices/{notice_id}/comments')
def get_notice_comments(notice_id: int, request: Request):
    with Session(engine) as db_session:
        comments = db_session.exec(
            select(NoticeComment)
            .where(NoticeComment.notice_id == notice_id)
            .order_by(NoticeComment.created_at.asc())
        ).all()
    current_uid = request.session.get('user_id')
    return {"comments": [
        {
            "id": c.id,
            "author_id": c.author_id,
            "author_nickname": c.author_nickname,
            "content": c.content,
            "created_at": c.created_at,
            "is_mine": c.author_id == current_uid,
        } for c in comments
    ]}


@app.post('/api/notices/{notice_id}/comments')
async def post_notice_comment(notice_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "로그인이 필요합니다."}, status_code=401)
    form = await request.form()
    content = str(form.get('content', '')).strip()
    if not content:
        return JSONResponse({"error": "내용을 입력해주세요."}, status_code=400)
    if len(content) > 100:
        return JSONResponse({"error": "댓글은 100자 이내여야 합니다."}, status_code=400)
    with Session(engine) as db_session:
        notice = db_session.get(Notice, notice_id)
        if not notice:
            return JSONResponse({"error": "공지를 찾을 수 없습니다."}, status_code=404)
        uid = request.session['user_id']
        user = db_session.exec(select(User).where(User.username == uid)).first()
        nickname = (user.nickname or uid) if user else uid
        comment = NoticeComment(
            notice_id=notice_id,
            author_id=uid,
            author_nickname=nickname,
            content=content,
            created_at=time.time(),
        )
        db_session.add(comment)
        db_session.commit()
        db_session.refresh(comment)
    return {"success": True, "id": comment.id, "author_nickname": nickname, "content": content, "created_at": comment.created_at}


@app.delete('/api/notices/{notice_id}/comments/{comment_id}')
def delete_notice_comment(notice_id: int, comment_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "로그인이 필요합니다."}, status_code=401)
    uid = request.session['user_id']
    with Session(engine) as db_session:
        comment = db_session.get(NoticeComment, comment_id)
        if not comment or comment.notice_id != notice_id:
            return JSONResponse({"error": "댓글을 찾을 수 없습니다."}, status_code=404)
        if comment.author_id != uid and not check_admin(request.session):
            return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
        db_session.delete(comment)
        db_session.commit()
    return {"success": True}


# ─────────────── 관리자 페이지 ───────────────
@app.get('/admin')
def admin_page(request: Request):
    if 'user_id' not in request.session:
        return RedirectResponse('/login_page', status_code=302)
    if not check_admin(request.session):
        return RedirectResponse('/main', status_code=302)
    nickname = request.session.get('nickname', request.session['user_id'])

    init_notices, init_users, init_messages = [], [], []
    try:
        users = get_all_users()
        nick_map = {u.username: (u.nickname or u.username) for u in users}
        with Session(engine) as db_session:
            notices  = db_session.exec(select(Notice).order_by(Notice.is_pinned.desc(), Notice.created_at.desc())).all()
            profiles = db_session.exec(select(Profile)).all()
            teams    = db_session.exec(select(Team)).all()
            messages = db_session.exec(select(DirectMessage).order_by(DirectMessage.created_at.desc())).all()

        init_notices = [
            {"id": n.id, "title": n.title, "content": n.content,
             "author_nickname": n.author_nickname, "is_pinned": n.is_pinned,
             "created_at": n.created_at, "updated_at": n.updated_at}
            for n in notices
        ]
        p_cnt = {}
        for p in profiles: p_cnt[p.user_id] = p_cnt.get(p.user_id, 0) + 1
        t_cnt = {}
        for t in teams:    t_cnt[t.leader_id] = t_cnt.get(t.leader_id, 0) + 1
        init_users = [
            {"id": u.id, "username": u.username, "nickname": u.nickname or u.username,
             "is_admin": u.is_admin, "is_owner": u.is_owner,
             "is_locked": bool(u.locked_until and time.time() < u.locked_until),
             "locked_until": u.locked_until, "failed_attempts": u.failed_attempts,
             "profile_count": p_cnt.get(u.username, 0), "team_count": t_cnt.get(u.username, 0)}
            for u in users
        ]
        init_messages = [
            {"id": m.id, "sender_id": m.sender_id, "sender_nick": nick_map.get(m.sender_id, m.sender_id),
             "receiver_id": m.receiver_id, "receiver_nick": nick_map.get(m.receiver_id, m.receiver_id),
             "message": m.message, "created_at": m.created_at}
            for m in messages
        ]
    except Exception:
        pass

    return templates.TemplateResponse(request, 'admin.html', {
        'user_id': nickname,
        'current_user': request.session['user_id'],
        'is_superadmin': check_superadmin(request.session),
        'is_owner': check_owner(request.session),
        'init_notices': json.dumps(init_notices, ensure_ascii=False),
        'init_users': json.dumps(init_users, ensure_ascii=False),
        'init_messages': json.dumps(init_messages, ensure_ascii=False),
    })


@app.get('/admin/setup')
def admin_setup_get(request: Request):
    if 'user_id' not in request.session:
        return RedirectResponse('/login_page', status_code=302)
    # 이미 총괄 관리자가 존재하면 차단
    with Session(engine) as db_session:
        existing = db_session.exec(select(User).where(User.is_superadmin == True)).first()
    if existing:
        return HTMLResponse('''
        <style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#f5f5f5;}
        .box{background:#fff;padding:32px;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);width:320px;text-align:center;}
        a{color:#4f8ef7;}</style>
        <div class="box">🔒 이미 관리자가 등록되어 있습니다.<br><br><a href="/main">홈으로 돌아가기</a></div>''')
    return HTMLResponse('''
    <style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#f5f5f5;}
    .box{background:#fff;padding:32px;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);width:320px;}
    h2{margin:0 0 20px;font-size:18px;}
    input{width:100%;padding:10px;border:1.5px solid #ddd;border-radius:8px;font-size:14px;box-sizing:border-box;margin-bottom:12px;}
    button{width:100%;padding:12px;background:#4f8ef7;color:#fff;border:none;border-radius:8px;font-size:15px;cursor:pointer;}
    .msg{margin-top:12px;font-size:13px;text-align:center;}</style>
    <div class="box"><h2>🛡️ 관리자 등록</h2>
    <form method="POST">
    <input type="password" name="secret" placeholder="시크릿 키 입력" required>
    <button type="submit">관리자로 등록</button>
    </form></div>''')


@app.post('/admin/setup')
async def admin_setup_post(request: Request):
    if 'user_id' not in request.session:
        return RedirectResponse('/login_page', status_code=302)
    form = await request.form()
    secret = str(form.get('secret', ''))
    if secret != os.environ.get('ADMIN_SECRET'):
        return HTMLResponse('''
        <style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#f5f5f5;}
        .box{background:#fff;padding:32px;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);width:320px;text-align:center;}
        a{color:#4f8ef7;}</style>
        <div class="box">❌ 잘못된 시크릿 키입니다.<br><br><a href="/admin/setup">다시 시도</a></div>''')
    with Session(engine) as db_session:
        # 이미 총괄 관리자가 존재하면 차단
        existing = db_session.exec(select(User).where(User.is_superadmin == True)).first()
        if existing:
            return HTMLResponse('''
            <style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#f5f5f5;}
            .box{background:#fff;padding:32px;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);width:320px;text-align:center;}
            a{color:#4f8ef7;}</style>
            <div class="box">🔒 이미 관리자가 등록되어 있습니다.<br><br><a href="/main">홈으로 돌아가기</a></div>''')
        user = db_session.exec(select(User).where(User.username == request.session['user_id'])).first()
        if not user:
            return RedirectResponse('/login_page', status_code=302)
        user.is_admin = True
        user.is_superadmin = True
        user.is_owner = True
        db_session.add(user)
        db_session.commit()
    return RedirectResponse('/admin', status_code=302)


@app.get('/api/admin/users')
def admin_get_users(request: Request):
    if not check_admin(request.session):
        return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
    with Session(engine) as db_session:
        users = db_session.exec(select(User)).all()
        profiles = db_session.exec(select(Profile)).all()
        teams = db_session.exec(select(Team)).all()
    profile_count = {}
    for p in profiles:
        profile_count[p.user_id] = profile_count.get(p.user_id, 0) + 1
    team_count = {}
    for t in teams:
        team_count[t.leader_id] = team_count.get(t.leader_id, 0) + 1
    return {"users": [
        {
            "id": u.id,
            "username": u.username,
            "nickname": u.nickname or u.username,
            "is_admin": u.is_admin,
            "is_owner": u.is_owner,
            "is_locked": bool(u.locked_until and time.time() < u.locked_until),
            "locked_until": u.locked_until,
            "failed_attempts": u.failed_attempts,
            "profile_count": profile_count.get(u.username, 0),
            "team_count": team_count.get(u.username, 0),
        } for u in users
    ]}


@app.post('/api/admin/users/{target_id}/lock')
async def admin_lock_user(target_id: str, request: Request):
    if not check_superadmin(request.session):
        return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
    form = await request.form()
    minutes = int(form.get('minutes', 30))
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == target_id)).first()
        if not user:
            return JSONResponse({"error": "사용자를 찾을 수 없습니다."}, status_code=404)
        user.locked_until = time.time() + minutes * 60
        db_session.add(user)
        db_session.commit()
    return {"success": True}


@app.post('/api/admin/users/{target_id}/unlock')
def admin_unlock_user(target_id: str, request: Request):
    if not check_superadmin(request.session):
        return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == target_id)).first()
        if not user:
            return JSONResponse({"error": "사용자를 찾을 수 없습니다."}, status_code=404)
        user.locked_until = None
        user.failed_attempts = 0
        db_session.add(user)
        db_session.commit()
    return {"success": True}


@app.post('/api/admin/users/{target_id}/toggle-admin')
def admin_toggle_admin(target_id: str, request: Request):
    if not check_superadmin(request.session):
        return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
    if target_id == request.session['user_id']:
        return JSONResponse({"error": "본인의 관리자 권한은 변경할 수 없습니다."}, status_code=400)
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == target_id)).first()
        if not user:
            return JSONResponse({"error": "사용자를 찾을 수 없습니다."}, status_code=404)
        if user.is_admin and not check_owner(request.session):
            return JSONResponse({"error": "관리자 해제는 최고 관리자만 할 수 있습니다."}, status_code=403)
        user.is_admin = not user.is_admin
        user.is_superadmin = user.is_admin
        db_session.add(user)
        db_session.commit()
    return {"success": True, "is_admin": user.is_admin}


@app.delete('/api/admin/users/{target_id}')
def admin_delete_user(target_id: str, request: Request):
    if not check_superadmin(request.session):
        return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
    if target_id == request.session['user_id']:
        return JSONResponse({"error": "본인 계정은 삭제할 수 없습니다."}, status_code=400)
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == target_id)).first()
        if not user:
            return JSONResponse({"error": "사용자를 찾을 수 없습니다."}, status_code=404)
        for profile in db_session.exec(select(Profile).where(Profile.user_id == target_id)).all():
            db_session.delete(profile)
        for notif in db_session.exec(select(Notification).where(
            or_(Notification.user_id == target_id, Notification.sender_id == target_id)
        )).all():
            db_session.delete(notif)
        for dm in db_session.exec(select(DirectMessage).where(
            or_(DirectMessage.sender_id == target_id, DirectMessage.receiver_id == target_id)
        )).all():
            db_session.delete(dm)
        db_session.delete(user)
        db_session.commit()
    return {"success": True}


# ─────────────── 관리자 메시지 관리 ───────────────
@app.get('/api/admin/messages')
def admin_get_messages(request: Request):
    if not check_admin(request.session):
        return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
    with Session(engine) as db_session:
        messages = db_session.exec(
            select(DirectMessage).order_by(DirectMessage.created_at.desc())
        ).all()
        nick_map = {u.username: (u.nickname or u.username)
                    for u in db_session.exec(select(User)).all()}
        result = [{
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_nick": nick_map.get(m.sender_id, m.sender_id),
            "receiver_id": m.receiver_id,
            "receiver_nick": nick_map.get(m.receiver_id, m.receiver_id),
            "message": m.message,
            "created_at": m.created_at,
        } for m in messages]
    return {"messages": result}


@app.delete('/api/admin/messages/{msg_id}')
def admin_delete_message(msg_id: int, request: Request):
    if not check_admin(request.session):
        return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
    with Session(engine) as db_session:
        msg = db_session.get(DirectMessage, msg_id)
        if not msg:
            return JSONResponse({"error": "메시지를 찾을 수 없습니다."}, status_code=404)
        db_session.delete(msg)
        db_session.commit()
    return {"success": True}


# ─────────────── 닉네임 검색 ───────────────
@app.get('/api/search')
def api_search(request: Request):
    q = request.query_params.get('q', '').strip().lower()
    if not q:
        return {"results": []}
    with Session(engine) as db_session:
        users = db_session.exec(
            select(User).where(
                or_(
                    func.lower(User.username).contains(q),
                    func.lower(User.nickname).contains(q)
                )
            ).limit(10)
        ).all()
    results = [{"nickname": u.nickname or u.username, "username": u.username} for u in users]
    return {"results": results}


# ─────────────── 활동 통계 ───────────────
@app.get('/api/stats')
def api_stats(request: Request):
    with Session(engine) as db_session:
        user_count = db_session.exec(select(func.count(User.id))).one()
        profile_count = db_session.exec(select(func.count(Profile.id))).one()
    return {"users": user_count, "profiles": profile_count}


@app.get('/api/new-activity')
def new_activity(request: Request):
    with Session(engine) as db_session:
        profiles = db_session.exec(select(Profile)).all()
        notices  = db_session.exec(select(Notice)).all()
    profile_latest = max((p.created_at for p in profiles), default=0)
    notice_latest  = max((n.created_at for n in notices),  default=0)
    return {"profile_latest": profile_latest, "notice_latest": notice_latest}


# ─────────────── 구인 게시판 ───────────────
@app.get('/user/{target_username}')
def user_profile(target_username: str, request: Request):
    if 'user_id' not in request.session:
        return RedirectResponse('/', status_code=302)
    with Session(engine) as db_session:
        target = db_session.exec(select(User).where(User.username == target_username)).first()
        if not target:
            return RedirectResponse('/main', status_code=302)
        profiles = db_session.exec(select(Profile).where(Profile.user_id == target_username)).all()
        led_teams = db_session.exec(select(Team).where(Team.leader_id == target_username)).all()
        member_teams_rows = db_session.exec(
            select(Team).join(TeamMember, Team.id == TeamMember.team_id)
            .where(TeamMember.user_id == target_username, TeamMember.status == 'accepted')
        ).all()
        nick_map = {u.username: (u.nickname or u.username)
                    for u in db_session.exec(select(User)).all()}

        profile_list = []
        for p in profiles:
            profile_list.append({
                "id": p.id,
                "name": p.name,
                "major": p.major,
                "class_number": p.class_number,
                "bio": p.bio,
                "past_languages": [l.strip() for l in p.past_languages.split(',') if l.strip()],
                "current_languages": [l.strip() for l in p.current_languages.split(',') if l.strip()],
                "profile_image": p.profile_image,
                "post_type": p.post_type,
                "dev_field": p.dev_field or '',
            })

        team_list = []
        for t in led_teams:
            team_list.append({"id": t.id, "name": t.name, "dev_field": t.dev_field, "role": "팀장"})
        for t in member_teams_rows:
            if t.leader_id != target_username:
                team_list.append({"id": t.id, "name": t.name, "dev_field": t.dev_field, "role": "팀원",
                                   "leader_name": nick_map.get(t.leader_id, t.leader_name)})

    is_self = request.session['user_id'] == target_username
    nickname = request.session.get('nickname', request.session['user_id'])
    return templates.TemplateResponse(request, 'user_profile.html', {
        'user_id': nickname,
        'target_username': target_username,
        'target_nickname': target.nickname or target_username,
        'profiles': profile_list,
        'teams': team_list,
        'is_self': is_self,
        'is_admin': check_admin(request.session),
        'discord_id': target.discord_id or '',
        'github_id': target.github_id or '',
        'raw_user_id': request.session.get('user_id', ''),
    })


@app.get('/recruit')
def recruit(request: Request):
    if 'user_id' not in request.session:
        return RedirectResponse('/', status_code=302)
    current_user = request.session['user_id']
    nickname = request.session.get('nickname', current_user)

    init_profiles = []
    try:
        users = get_all_users()
        with Session(engine) as db_session:
            profiles  = db_session.exec(select(Profile).where(Profile.post_type == 'recruit').order_by(Profile.created_at)).all()
            interests = db_session.exec(select(RecruitInterest).where(RecruitInterest.sender_id == current_user)).all()

        nick_map = {u.username: (u.nickname or u.username) for u in users}
        sent_set = {i.profile_id for i in interests}
        mine, others = [], []
        for p in profiles:
            row = {
                "id": p.id, "name": p.name,
                "nickname": nick_map.get(p.user_id, p.user_id),
                "bio": p.bio or '', "class_number": p.class_number, "major": p.major,
                "past_languages":    [l.strip() for l in p.past_languages.split(',')    if l.strip()],
                "current_languages": [l.strip() for l in p.current_languages.split(',') if l.strip()],
                "profile_image": p.profile_image, "post_type": p.post_type, "dev_field": p.dev_field,
                "is_mine": p.user_id == current_user,
                "interest_sent": p.id in sent_set,
                "owner_id": p.user_id,
            }
            (mine if p.user_id == current_user else others).append(row)
        init_profiles = mine + others
    except Exception:
        pass

    return templates.TemplateResponse(request, 'recruit.html', {
        'user_id': nickname,
        'is_admin': check_admin(request.session),
        'raw_user_id': current_user,
        'init_profiles': json.dumps(init_profiles, ensure_ascii=False),
    })


@app.get('/api/profiles')
def get_profiles(request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    ptype = request.query_params.get('type', 'recruit')
    try:
        with Session(engine) as db_session:
            profiles = db_session.exec(
                select(Profile)
                .where(Profile.post_type == ptype)
                .order_by(Profile.created_at)
            ).all()
            users = db_session.exec(select(User)).all()
            interests = db_session.exec(
                select(RecruitInterest).where(RecruitInterest.sender_id == current_user)
            ).all()
        nickname_map = {u.username: (u.nickname or u.username) for u in users}
        sent_set = {i.profile_id for i in interests}
        mine = []
        others = []
        for p in profiles:
            data = {
                "id": p.id,
                "name": p.name,
                "nickname": nickname_map.get(p.user_id, p.user_id),
                "bio": p.bio or '',
                "class_number": p.class_number,
                "major": p.major,
                "past_languages": [l.strip() for l in p.past_languages.split(',') if l.strip()],
                "current_languages": [l.strip() for l in p.current_languages.split(',') if l.strip()],
                "profile_image": p.profile_image,
                "post_type": p.post_type,
                "dev_field": p.dev_field,
                "is_mine": p.user_id == current_user,
                "interest_sent": p.id in sent_set,
                "owner_id": p.user_id
            }
            if p.user_id == current_user:
                mine.append(data)
            else:
                others.append(data)
        return {"profiles": mine + others}
    except Exception:
        return JSONResponse({"error": "데이터를 불러오는 중 오류가 발생했습니다.", "profiles": []}, status_code=500)


@app.post('/api/profiles')
async def create_profile(request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    form = await request.form()
    post_type = str(form.get('post_type', 'recruit')).strip()
    name = request.session.get('nickname', current_user)
    class_number = str(form.get('class_number', '')).strip()
    major = str(form.get('major', '')).strip()
    bio = str(form.get('bio', '')).strip()
    past_languages = str(form.get('past_languages', '')).strip()
    current_languages = str(form.get('current_languages', '')).strip()
    profile_image = str(form.get('profile_image', '')).strip() or None
    dev_field = str(form.get('dev_field', '')).strip() or None
    if not class_number or not major:
        return JSONResponse({"error": "반/번호, 전공은 필수입니다."}, status_code=400)
    if post_type == 'job_seek' and not dev_field:
        return JSONResponse({"error": "개발 분야를 선택해주세요."}, status_code=400)
    try:
        with Session(engine) as db_session:
            existing = db_session.exec(
                select(Profile).where(Profile.user_id == current_user, Profile.post_type == post_type)
            ).first()
            if existing:
                return JSONResponse({"error": "이미 해당 유형의 프로필이 등록되어 있습니다."}, status_code=400)
            profile = Profile(
                user_id=current_user,
                name=name,
                bio=bio,
                class_number=class_number,
                major=major,
                past_languages=past_languages,
                current_languages=current_languages,
                profile_image=profile_image,
                post_type=post_type,
                dev_field=dev_field,
                created_at=time.time()
            )
            db_session.add(profile)
            db_session.commit()
            db_session.refresh(profile)
            return {
                "success": True,
                "profile": {
                    "id": profile.id,
                    "name": profile.name,
                    "class_number": profile.class_number,
                    "major": profile.major,
                    "bio": profile.bio or '',
                    "dev_field": profile.dev_field or '',
                    "post_type": profile.post_type,
                    "past_languages": [l.strip() for l in profile.past_languages.split(',') if l.strip()],
                    "current_languages": [l.strip() for l in profile.current_languages.split(',') if l.strip()],
                    "profile_image": profile.profile_image,
                    "is_mine": True,
                    "interest_sent": False,
                    "owner_id": current_user,
                }
            }
    except Exception:
        return JSONResponse({"error": "프로필 등록 중 오류가 발생했습니다. 다시 시도해주세요."}, status_code=500)


# ─────────────── 팀 게시판 ───────────────
@app.get('/api/teams')
def get_teams(request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    try:
        with Session(engine) as db_session:
            teams = db_session.exec(select(Team).order_by(Team.created_at)).all()
            members_all = db_session.exec(select(TeamMember)).all()
            users = db_session.exec(select(User)).all()
        nick_map = {u.username: (u.nickname or u.username) for u in users}
        mem_map = {}
        for m in members_all:
            mem_map.setdefault(m.team_id, []).append(m)
        result = []
        for t in teams:
            mems = mem_map.get(t.id, [])
            accepted = [m for m in mems if m.status == 'accepted']
            pending  = [m for m in mems if m.status == 'pending']
            my_status = next((m.status for m in mems if m.user_id == current_user), None)
            result.append({
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "dev_field": t.dev_field,
                "max_members": t.max_members,
                "team_image": t.team_image,
                "leader_id": t.leader_id,
                "leader_name": nick_map.get(t.leader_id, t.leader_name),
                "is_mine": t.leader_id == current_user,
                "my_status": my_status,
                "members": [{"id": m.id, "user_id": m.user_id, "display_name": nick_map.get(m.user_id, m.display_name), "status": m.status} for m in accepted],
                "pending_count": len(pending),
                "pending_list": [{"id": m.id, "user_id": m.user_id, "display_name": nick_map.get(m.user_id, m.display_name)} for m in pending] if t.leader_id == current_user else [],
            })
        return {"teams": result}
    except Exception:
        return JSONResponse({"error": "데이터를 불러오는 중 오류가 발생했습니다.", "teams": []}, status_code=500)


@app.post('/api/teams')
async def create_team(request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    nickname = request.session.get('nickname', current_user)
    form = await request.form()
    name = str(form.get('name', '')).strip()
    description = str(form.get('description', '')).strip()
    dev_field = str(form.get('dev_field', '')).strip()
    max_members = int(form.get('max_members', 4))
    team_image = str(form.get('team_image', '')).strip() or None
    if not name:
        return JSONResponse({"error": "팀 이름은 필수입니다."}, status_code=400)
    with Session(engine) as db_session:
        team = Team(leader_id=current_user, leader_name=nickname,
                    name=name, description=description,
                    dev_field=dev_field, max_members=max_members,
                    team_image=team_image,
                    created_at=time.time())
        db_session.add(team)
        db_session.commit()
    return {"success": True}


@app.delete('/api/teams/{team_id}')
def delete_team(team_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team:
            return JSONResponse({"error": "팀을 찾을 수 없습니다."}, status_code=404)
        if team.leader_id != request.session['user_id'] and not check_admin(request.session):
            return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
        for m in db_session.exec(select(TeamMember).where(TeamMember.team_id == team_id)).all():
            db_session.delete(m)
        db_session.delete(team)
        db_session.commit()
    return {"success": True}


@app.put('/api/teams/{team_id}')
async def update_team(team_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    form = await request.form()
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team:
            return JSONResponse({"error": "팀을 찾을 수 없습니다."}, status_code=404)
        if team.leader_id != request.session['user_id']:
            return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
        new_name = str(form.get('name', '')).strip()
        if new_name:
            if len(new_name) > 30:
                return JSONResponse({"error": "팀 이름은 30자 이내여야 합니다."}, status_code=400)
            team.name = new_name
        new_desc = form.get('description')
        if new_desc is not None:
            if len(str(new_desc).strip()) > 50:
                return JSONResponse({"error": "팀 소개는 50자 이내여야 합니다."}, status_code=400)
            team.description = str(new_desc).strip()
        new_field = form.get('dev_field')
        if new_field is not None:
            team.dev_field = str(new_field).strip()
        new_image = form.get('team_image')
        if new_image is not None:
            team.team_image = str(new_image).strip() or None
        new_max = form.get('max_members')
        if new_max:
            new_max = int(new_max)
            accepted_count = db_session.exec(
                select(func.count()).where(TeamMember.team_id == team_id, TeamMember.status == 'accepted')
            ).one()
            if new_max < accepted_count:
                return JSONResponse({"error": f"현재 팀원이 {accepted_count}명이므로 {accepted_count}명 이상으로 설정해야 합니다."}, status_code=400)
            if new_max < 2 or new_max > 20:
                return JSONResponse({"error": "인원은 2~20명 사이여야 합니다."}, status_code=400)
            team.max_members = new_max
        db_session.add(team)
        db_session.commit()
        saved_name = team.name
    return {"success": True, "name": saved_name}


@app.delete('/api/teams/{team_id}/members/{member_id}')
def kick_member(team_id: int, member_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team or team.leader_id != request.session['user_id']:
            return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
        member = db_session.get(TeamMember, member_id)
        if not member or member.team_id != team_id:
            return JSONResponse({"error": "멤버를 찾을 수 없습니다."}, status_code=404)
        db_session.delete(member)
        db_session.commit()
    return {"success": True}


@app.post('/api/teams/{team_id}/leave')
def leave_team(team_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    uid = request.session['user_id']
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team:
            return JSONResponse({"error": "팀을 찾을 수 없습니다."}, status_code=404)
        if team.leader_id == uid:
            return JSONResponse({"error": "팀장은 팀을 나갈 수 없습니다. 팀 삭제를 이용해주세요."}, status_code=400)
        member = db_session.exec(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == uid)
        ).first()
        if not member:
            return JSONResponse({"error": "팀에 참여 중이 아닙니다."}, status_code=404)
        db_session.delete(member)
        db_session.commit()
    return {"success": True}


@app.post('/api/teams/{team_id}/join')
def join_team(team_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    nickname = request.session.get('nickname', current_user)
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team:
            return JSONResponse({"error": "팀을 찾을 수 없습니다."}, status_code=404)
        if team.leader_id == current_user:
            return JSONResponse({"error": "본인 팀에는 신청할 수 없습니다."}, status_code=400)
        existing = db_session.exec(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == current_user)
        ).first()
        if existing:
            return JSONResponse({"error": "이미 신청했습니다."}, status_code=400)
        accepted_count = len(db_session.exec(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.status == 'accepted')
        ).all())
        if accepted_count >= team.max_members:
            return JSONResponse({"error": "팀 정원이 꽉 찼습니다."}, status_code=400)
        member = TeamMember(team_id=team_id, user_id=current_user,
                            display_name=nickname, status='pending',
                            joined_at=time.time())
        db_session.add(member)
        db_session.commit()
    return {"success": True}


@app.post('/api/teams/{team_id}/respond')
async def respond_team(team_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    form = await request.form()
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team or team.leader_id != current_user:
            return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
        member_id = int(form.get('member_id', 0))
        action = str(form.get('action', ''))  # 'accept' | 'reject'
        member = db_session.get(TeamMember, member_id)
        if not member or member.team_id != team_id:
            return JSONResponse({"error": "멤버를 찾을 수 없습니다."}, status_code=404)
        if action == 'accept':
            accepted_count = len(db_session.exec(
                select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.status == 'accepted')
            ).all())
            if accepted_count >= team.max_members:
                return JSONResponse({"error": "팀 정원이 꽉 찼습니다."}, status_code=400)
            member.status = 'accepted'
        elif action == 'reject':
            member.status = 'rejected'
        else:
            return JSONResponse({"error": "잘못된 액션입니다."}, status_code=400)
        db_session.add(member)
        db_session.commit()
    return {"success": True}


# ─────────────── 구인하기 (관심 표현) ───────────────
@app.post('/api/profiles/{profile_id}/interest')
def recruit_interest(profile_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    nickname = request.session.get('nickname', current_user)
    with Session(engine) as db_session:
        profile = db_session.get(Profile, profile_id)
        if not profile:
            return JSONResponse({"error": "프로필을 찾을 수 없습니다."}, status_code=404)
        if profile.user_id == current_user:
            return JSONResponse({"error": "본인 게시글에는 구인할 수 없습니다."}, status_code=400)
        existing = db_session.exec(
            select(RecruitInterest).where(
                RecruitInterest.profile_id == profile_id,
                RecruitInterest.sender_id == current_user
            )
        ).first()
        if existing:
            return JSONResponse({"error": "이미 구인 신청을 보냈습니다."}, status_code=400)
        interest = RecruitInterest(
            profile_id=profile_id,
            sender_id=current_user,
            created_at=time.time()
        )
        db_session.add(interest)
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
            return JSONResponse({"error": "신청 처리 중 오류가 발생했습니다."}, status_code=500)
        try:
            notif = Notification(
                user_id=profile.user_id,
                sender_id=current_user,
                sender_nickname=nickname,
                profile_id=profile_id,
                profile_name=profile.name or '',
                notif_type='interest',
                is_read=False,
                created_at=time.time()
            )
            db_session.add(notif)
            db_session.commit()
        except Exception:
            db_session.rollback()
    return {"success": True}


# ─────────────── 알림 ───────────────
@app.get('/api/notifications')
def get_notifications(request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    with Session(engine) as db_session:
        notifs = db_session.exec(
            select(Notification)
            .where(Notification.user_id == current_user)
            .order_by(Notification.created_at.desc())
        ).all()
        unread = sum(1 for n in notifs if not n.is_read)
    return {
        "notifications": [
            {
                "id": n.id,
                "sender_id": n.sender_id,
                "sender_nickname": n.sender_nickname,
                "profile_name": n.profile_name,
                "notif_type": n.notif_type,
                "is_read": n.is_read,
                "created_at": n.created_at
            } for n in notifs[:20]
        ],
        "unread": unread
    }


@app.post('/api/profiles/{profile_id}/view')
def view_profile(profile_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"success": False}, status_code=401)
    current_user = request.session['user_id']
    nickname = request.session.get('nickname', current_user)
    with Session(engine) as db_session:
        profile = db_session.get(Profile, profile_id)
        if not profile or profile.user_id == current_user:
            return {"success": False}
        existing = db_session.exec(
            select(Notification).where(
                Notification.user_id == profile.user_id,
                Notification.sender_id == current_user,
                Notification.notif_type == 'view',
                Notification.profile_id == profile_id
            )
        ).first()
        if existing:
            return {"success": True}
        notif = Notification(
            user_id=profile.user_id,
            sender_id=current_user,
            sender_nickname=nickname,
            profile_id=profile_id,
            profile_name=profile.name,
            notif_type='view',
            is_read=False,
            created_at=time.time()
        )
        db_session.add(notif)
        db_session.commit()
    return {"success": True}


# ─────────────── DM ───────────────
@app.get('/api/dm/unread')
def dm_unread(request: Request):
    if 'user_id' not in request.session:
        return {"unread": 0}
    current_user = request.session['user_id']
    with Session(engine) as db_session:
        count = len(db_session.exec(
            select(DirectMessage).where(
                DirectMessage.receiver_id == current_user,
                DirectMessage.is_read == False
            )
        ).all())
    return {"unread": count}


@app.get('/api/dm/conversations')
def dm_conversations(request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    with Session(engine) as db_session:
        messages = db_session.exec(
            select(DirectMessage).where(
                or_(DirectMessage.sender_id == current_user,
                    DirectMessage.receiver_id == current_user)
            ).order_by(DirectMessage.created_at.desc())
        ).all()
        users = db_session.exec(select(User)).all()
        nickname_map = {u.username: (u.nickname or u.username) for u in users}
    conv_map = {}
    for msg in messages:
        partner = msg.receiver_id if msg.sender_id == current_user else msg.sender_id
        if partner not in conv_map:
            conv_map[partner] = {
                'user_id': partner,
                'nickname': nickname_map.get(partner, partner),
                'last_message': msg.message,
                'last_time': msg.created_at,
                'unread': 0
            }
        if msg.receiver_id == current_user and not msg.is_read:
            conv_map[partner]['unread'] += 1
    convs = sorted(conv_map.values(), key=lambda x: x['last_time'], reverse=True)
    return {"conversations": convs}


@app.get('/api/dm/{other_user_id}')
def get_dm(other_user_id: str, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    with Session(engine) as db_session:
        messages = db_session.exec(
            select(DirectMessage).where(
                or_(
                    and_(DirectMessage.sender_id == current_user,
                         DirectMessage.receiver_id == other_user_id),
                    and_(DirectMessage.sender_id == other_user_id,
                         DirectMessage.receiver_id == current_user)
                )
            ).order_by(DirectMessage.created_at.asc())
        ).all()
        for msg in messages:
            if msg.receiver_id == current_user and not msg.is_read:
                msg.is_read = True
                db_session.add(msg)
        db_session.commit()
        other_user = db_session.exec(select(User).where(User.username == other_user_id)).first()
        other_nickname = (other_user.nickname or other_user_id) if other_user else other_user_id
        messages_data = [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "message": m.message,
                "created_at": m.created_at,
                "is_mine": m.sender_id == current_user
            } for m in messages
        ]
    return {"messages": messages_data, "other_nickname": other_nickname}


@app.post('/api/dm/{other_user_id}')
async def send_dm(other_user_id: str, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    form = await request.form()
    message_text = str(form.get('message', '')).strip()
    if not message_text:
        return JSONResponse({"error": "메시지를 입력해주세요."}, status_code=400)
    with Session(engine) as db_session:
        other_user = db_session.exec(select(User).where(User.username == other_user_id)).first()
        if not other_user:
            return JSONResponse({"error": "사용자를 찾을 수 없습니다."}, status_code=404)
        dm = DirectMessage(
            sender_id=current_user,
            receiver_id=other_user_id,
            message=message_text,
            created_at=time.time()
        )
        db_session.add(dm)
        db_session.commit()
        db_session.refresh(dm)
    return {"success": True, "message": {
        "id": dm.id, "message": dm.message,
        "created_at": dm.created_at, "is_mine": True
    }}


@app.post('/api/notifications/read-all')
def read_all_notifications(request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    with Session(engine) as db_session:
        notifs = db_session.exec(
            select(Notification).where(
                Notification.user_id == current_user,
                Notification.is_read == False
            )
        ).all()
        for n in notifs:
            n.is_read = True
            db_session.add(n)
        db_session.commit()
    return {"success": True}


@app.put('/api/profiles/{profile_id}')
async def update_profile(profile_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    form = await request.form()
    with Session(engine) as db_session:
        profile = db_session.get(Profile, profile_id)
        if not profile:
            return JSONResponse({"error": "프로필을 찾을 수 없습니다."}, status_code=404)
        if profile.user_id != current_user:
            return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
        name = request.session.get('nickname', current_user)
        class_number = str(form.get('class_number', '')).strip()
        major = str(form.get('major', '')).strip()
        bio = str(form.get('bio', '')).strip()
        past_languages = str(form.get('past_languages', '')).strip()
        current_languages = str(form.get('current_languages', '')).strip()
        profile_image = str(form.get('profile_image', '')).strip()
        if not class_number or not major:
            return JSONResponse({"error": "반/번호, 전공은 필수입니다."}, status_code=400)
        profile.name = name
        profile.class_number = class_number
        profile.major = major
        profile.bio = bio
        profile.past_languages = past_languages
        profile.current_languages = current_languages
        if profile_image:
            profile.profile_image = profile_image
        db_session.add(profile)
        db_session.commit()
    return {"success": True}


@app.delete('/api/profiles/{profile_id}')
def delete_profile(profile_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    with Session(engine) as db_session:
        profile = db_session.get(Profile, profile_id)
        if not profile:
            return JSONResponse({"error": "프로필을 찾을 수 없습니다."}, status_code=404)
        if profile.user_id != current_user:
            return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
        db_session.delete(profile)
        db_session.commit()
    return {"success": True}


@app.get('/api/teams/{team_id}/messages')
def get_group_messages(team_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team:
            return JSONResponse({"error": "팀을 찾을 수 없습니다."}, status_code=404)
        member = db_session.exec(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == current_user,
                TeamMember.status == 'accepted'
            )
        ).first()
        is_leader = team.leader_id == current_user
        if not member and not is_leader:
            return JSONResponse({"error": "팀 멤버만 볼 수 있습니다."}, status_code=403)
        messages = db_session.exec(
            select(GroupMessage).where(GroupMessage.team_id == team_id)
            .order_by(GroupMessage.created_at)
        ).all()
        members = db_session.exec(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.status == 'accepted'
            )
        ).all()
        members_data = [{"user_id": m.user_id, "display_name": m.display_name} for m in members]
        leader_user = db_session.exec(select(User).where(User.username == team.leader_id)).first()
        leader_name = leader_user.nickname if leader_user and leader_user.nickname else team.leader_name
        members_data.insert(0, {"user_id": team.leader_id, "display_name": leader_name + " 👑"})
    return {
        "messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "sender_nickname": m.sender_nickname,
                "message": m.message,
                "created_at": m.created_at,
                "is_mine": m.sender_id == current_user
            } for m in messages
        ],
        "members": members_data,
        "team_name": team.name
    }


@app.post('/api/teams/{team_id}/messages')
async def send_group_message(team_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    form = await request.form()
    message_text = str(form.get('message', '')).strip()
    if not message_text:
        return JSONResponse({"error": "메시지를 입력해주세요."}, status_code=400)
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team:
            return JSONResponse({"error": "팀을 찾을 수 없습니다."}, status_code=404)
        member = db_session.exec(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == current_user,
                TeamMember.status == 'accepted'
            )
        ).first()
        is_leader = team.leader_id == current_user
        if not member and not is_leader:
            return JSONResponse({"error": "팀 멤버만 메시지를 보낼 수 있습니다."}, status_code=403)
        user = db_session.exec(select(User).where(User.username == current_user)).first()
        nickname = user.nickname if user and user.nickname else current_user
        msg = GroupMessage(
            team_id=team_id,
            sender_id=current_user,
            sender_nickname=nickname,
            message=message_text,
            created_at=time.time()
        )
        db_session.add(msg)
        db_session.commit()
        db_session.refresh(msg)
    return {"success": True, "message": {
        "id": msg.id, "sender_id": msg.sender_id,
        "sender_nickname": msg.sender_nickname,
        "message": msg.message, "created_at": msg.created_at, "is_mine": True
    }}


# ─────────────── 쇼케이스 ───────────────
@app.get('/showcase')
def showcase_page(request: Request):
    if 'user_id' not in request.session:
        return RedirectResponse('/login_page', status_code=302)
    current_user = request.session['user_id']
    nickname = request.session.get('nickname', current_user)
    return templates.TemplateResponse(request, 'showcase.html', {
        'user_id': nickname,
        'raw_user_id': current_user,
        'is_admin': check_admin(request.session),
    })


@app.get('/api/showcase')
def showcase_list(request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    category = request.query_params.get('category', '')
    try:
        with Session(engine) as db_session:
            q = select(ShowcaseProject).order_by(ShowcaseProject.created_at.desc())
            if category and category != '전체':
                q = q.where(ShowcaseProject.category == category)
            projects = db_session.exec(q).all()
            result = []
            for p in projects:
                like_count = db_session.exec(
                    select(func.count(ShowcaseLike.id)).where(ShowcaseLike.project_id == p.id)
                ).one()
                comment_count = db_session.exec(
                    select(func.count(ShowcaseComment.id)).where(ShowcaseComment.project_id == p.id)
                ).one()
                liked = db_session.exec(
                    select(ShowcaseLike).where(ShowcaseLike.project_id == p.id, ShowcaseLike.user_id == current_user)
                ).first() is not None
                result.append({
                    "id": p.id, "user_id": p.user_id,
                    "author_nickname": p.author_nickname,
                    "title": p.title, "description": p.description,
                    "url": p.url, "thumbnail": p.thumbnail,
                    "tech_stack": [t.strip() for t in p.tech_stack.split(',') if t.strip()],
                    "category": p.category, "views": p.views,
                    "like_count": like_count, "comment_count": comment_count,
                    "liked": liked, "is_mine": p.user_id == current_user,
                    "created_at": p.created_at,
                })
        return {"projects": result}
    except Exception:
        return JSONResponse({"error": "불러오는 중 오류가 발생했습니다.", "projects": []}, status_code=500)


@app.post('/api/showcase')
async def showcase_create(request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    nickname = request.session.get('nickname', current_user)
    form = await request.form()
    title = str(form.get('title', '')).strip()
    description = str(form.get('description', '')).strip()
    url = str(form.get('url', '')).strip()
    thumbnail = str(form.get('thumbnail', '')).strip() or None
    tech_stack = str(form.get('tech_stack', '')).strip()
    category = str(form.get('category', '기타')).strip()
    if not title:
        return JSONResponse({"error": "제목을 입력해주세요."}, status_code=400)
    if len(title) > 50:
        return JSONResponse({"error": "제목은 50자 이내여야 합니다."}, status_code=400)
    if len(description) > 500:
        return JSONResponse({"error": "설명은 500자 이내여야 합니다."}, status_code=400)
    try:
        with Session(engine) as db_session:
            project = ShowcaseProject(
                user_id=current_user, author_nickname=nickname,
                title=title, description=description, url=url,
                thumbnail=thumbnail, tech_stack=tech_stack,
                category=category, created_at=time.time()
            )
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)
            return {"success": True, "id": project.id}
    except Exception:
        return JSONResponse({"error": "등록 중 오류가 발생했습니다."}, status_code=500)


@app.put('/api/showcase/{project_id}')
async def showcase_update(project_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    form = await request.form()
    try:
        with Session(engine) as db_session:
            p = db_session.get(ShowcaseProject, project_id)
            if not p:
                return JSONResponse({"error": "존재하지 않는 프로젝트입니다."}, status_code=404)
            if p.user_id != current_user and not check_admin(request.session):
                return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
            title = str(form.get('title', '')).strip()
            if not title:
                return JSONResponse({"error": "제목을 입력해주세요."}, status_code=400)
            p.title = title
            p.description = str(form.get('description', '')).strip()
            p.url = str(form.get('url', '')).strip()
            p.tech_stack = str(form.get('tech_stack', '')).strip()
            p.category = str(form.get('category', '기타')).strip()
            thumbnail = str(form.get('thumbnail', '')).strip()
            if thumbnail:
                p.thumbnail = thumbnail
            elif str(form.get('thumbnail_removed', '')) == '1':
                p.thumbnail = None
            db_session.add(p)
            db_session.commit()
            return {"success": True}
    except Exception:
        return JSONResponse({"error": "수정 중 오류가 발생했습니다."}, status_code=500)


@app.delete('/api/showcase/{project_id}')
def showcase_delete(project_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    try:
        with Session(engine) as db_session:
            p = db_session.get(ShowcaseProject, project_id)
            if not p:
                return JSONResponse({"error": "존재하지 않는 프로젝트입니다."}, status_code=404)
            if p.user_id != current_user and not check_admin(request.session):
                return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
            db_session.exec(text(f"DELETE FROM showcaselike WHERE project_id = {project_id}"))
            db_session.exec(text(f"DELETE FROM showcasecomment WHERE project_id = {project_id}"))
            db_session.delete(p)
            db_session.commit()
            return {"success": True}
    except Exception:
        return JSONResponse({"error": "삭제 중 오류가 발생했습니다."}, status_code=500)


@app.post('/api/showcase/{project_id}/like')
def showcase_like(project_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    with Session(engine) as db_session:
        existing = db_session.exec(
            select(ShowcaseLike).where(ShowcaseLike.project_id == project_id, ShowcaseLike.user_id == current_user)
        ).first()
        if existing:
            db_session.delete(existing)
            liked = False
        else:
            db_session.add(ShowcaseLike(project_id=project_id, user_id=current_user, created_at=time.time()))
            liked = True
        db_session.commit()
        count = db_session.exec(
            select(func.count(ShowcaseLike.id)).where(ShowcaseLike.project_id == project_id)
        ).one()
        return {"success": True, "liked": liked, "count": count}


@app.post('/api/showcase/{project_id}/view')
def showcase_view(project_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    with Session(engine) as db_session:
        p = db_session.get(ShowcaseProject, project_id)
        if p:
            p.views += 1
            db_session.add(p)
            db_session.commit()
    return {"success": True}


@app.get('/api/showcase/{project_id}/comments')
def showcase_get_comments(project_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    with Session(engine) as db_session:
        comments = db_session.exec(
            select(ShowcaseComment).where(ShowcaseComment.project_id == project_id)
            .order_by(ShowcaseComment.created_at.asc())
        ).all()
        return {"comments": [
            {"id": c.id, "author_id": c.author_id, "author_nickname": c.author_nickname,
             "content": c.content, "created_at": c.created_at,
             "is_mine": c.author_id == current_user}
            for c in comments
        ]}


@app.post('/api/showcase/{project_id}/comments')
async def showcase_add_comment(project_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    nickname = request.session.get('nickname', current_user)
    form = await request.form()
    content = str(form.get('content', '')).strip()
    if not content:
        return JSONResponse({"error": "내용을 입력해주세요."}, status_code=400)
    if len(content) > 300:
        return JSONResponse({"error": "댓글은 300자 이내여야 합니다."}, status_code=400)
    with Session(engine) as db_session:
        c = ShowcaseComment(
            project_id=project_id, author_id=current_user,
            author_nickname=nickname, content=content, created_at=time.time()
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        return {"success": True, "comment": {
            "id": c.id, "author_id": c.author_id, "author_nickname": c.author_nickname,
            "content": c.content, "created_at": c.created_at, "is_mine": True
        }}


@app.delete('/api/showcase/{project_id}/comments/{comment_id}')
def showcase_delete_comment(project_id: int, comment_id: int, request: Request):
    if 'user_id' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    current_user = request.session['user_id']
    with Session(engine) as db_session:
        c = db_session.get(ShowcaseComment, comment_id)
        if not c or c.project_id != project_id:
            return JSONResponse({"error": "존재하지 않는 댓글입니다."}, status_code=404)
        if c.author_id != current_user and not check_admin(request.session):
            return JSONResponse({"error": "권한이 없습니다."}, status_code=403)
        db_session.delete(c)
        db_session.commit()
        return {"success": True}


if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', 4500))
    uvicorn.run(app, host='0.0.0.0', port=port)
