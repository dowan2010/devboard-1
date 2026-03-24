from flask import Flask, render_template, request, redirect, url_for, session
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy import text, or_, and_, func
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
from typing import Optional
from dotenv import load_dotenv

import time
import os
import json

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)


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


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///database.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,    # 절전 후 재연결 시 끊긴 커넥션 자동 교체
        pool_recycle=300,      # 5분마다 커넥션 갱신
    )

with app.app_context():
    SQLModel.metadata.create_all(engine)
    # 기존 DB에 nickname 컬럼 없을 경우 추가
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE user ADD COLUMN nickname VARCHAR"))
            conn.commit()
        except Exception:
            pass
        # Profile.user_id unique 제약 제거 (다중 프로필 허용)
        for idx_name in ('ix_profile_user_id', 'uq_profile_user_id', 'profile_user_id'):
            try:
                conn.execute(text(f"DROP INDEX IF EXISTS {idx_name}"))
                conn.commit()
            except Exception:
                pass
        # 구직 컬럼 추가
        for col_sql in (
            "ALTER TABLE profile ADD COLUMN post_type VARCHAR DEFAULT 'recruit'",
            "ALTER TABLE profile ADD COLUMN dev_field VARCHAR",
            "ALTER TABLE profile ADD COLUMN bio VARCHAR DEFAULT ''",
            "ALTER TABLE notification ADD COLUMN notif_type VARCHAR DEFAULT 'interest'",
            "ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0",
            "ALTER TABLE user ADD COLUMN is_superadmin BOOLEAN DEFAULT 0",
            "ALTER TABLE user ADD COLUMN is_owner BOOLEAN DEFAULT 0",
            "ALTER TABLE user ADD COLUMN google_id VARCHAR",
            "CREATE TABLE IF NOT EXISTS noticecomment (id INTEGER PRIMARY KEY AUTOINCREMENT, notice_id INTEGER NOT NULL, author_id VARCHAR NOT NULL, author_nickname VARCHAR DEFAULT '', content VARCHAR DEFAULT '', created_at REAL DEFAULT 0.0)",
            "ALTER TABLE team ADD COLUMN team_image TEXT DEFAULT NULL",
            "ALTER TABLE user ADD COLUMN discord_id VARCHAR DEFAULT NULL",
            "ALTER TABLE user ADD COLUMN github_id VARCHAR DEFAULT NULL",
        ):
            try:
                conn.execute(text(col_sql))
                conn.commit()
            except Exception:
                pass


def check_admin():
    """현재 로그인 유저가 관리자(일반 or 총괄)인지 확인"""
    uid = session.get('user_id')
    if not uid:
        return False
    with Session(engine) as db_session:
        u = db_session.exec(select(User).where(User.username == uid)).first()
        return bool(u and u.is_admin)


def check_superadmin():
    """현재 로그인 유저가 총괄 관리자인지 확인"""
    uid = session.get('user_id')
    if not uid:
        return False
    with Session(engine) as db_session:
        u = db_session.exec(select(User).where(User.username == uid)).first()
        return bool(u and u.is_superadmin)


def check_owner():
    """현재 로그인 유저가 최초 소유자인지 확인"""
    uid = session.get('user_id')
    if not uid:
        return False
    with Session(engine) as db_session:
        u = db_session.exec(select(User).where(User.username == uid)).first()
        return bool(u and u.is_owner)


@app.before_request
def enforce_lock():
    """이미 로그인된 유저가 잠금 상태이면 즉시 세션 만료"""
    if request.path.startswith('/static'):
        return
    uid = session.get('user_id')
    if not uid:
        return
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == uid)).first()
        if user and user.locked_until and time.time() < user.locked_until:
            session.clear()
            if request.path.startswith('/api/'):
                return {"error": "계정이 잠금 상태입니다."}, 403
            return redirect(url_for('login_page'))


@app.route('/')
def index():
    return redirect(url_for('home'))


@app.route('/login_page')
def login_page():
    show_toast = session.pop('show_login_toast', False)
    return render_template('login.html', show_toast=show_toast)


# ───────────── Google OAuth ─────────────
@app.route('/auth/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route('/auth/google/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
    except Exception:
        session.clear()
        return redirect(url_for('login_page'))
    userinfo = token.get('userinfo')
    if not userinfo:
        return redirect(url_for('login_page'))

    google_id = userinfo['sub']
    email = userinfo['email']

    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.google_id == google_id)).first()
        if not user:
            # 신규 유저 → 닉네임 설정 페이지로
            session['pending_google_id'] = google_id
            session['pending_email'] = email
            return redirect(url_for('set_nickname_page'))
        # 잠금 확인
        if user.locked_until and time.time() < user.locked_until:
            session.clear()
            return redirect(url_for('login_page'))
        # 기존 유저 → 바로 로그인
        session['user_id'] = user.username
        session['nickname'] = user.nickname or user.username
        session['show_login_toast'] = True
        return redirect(url_for('home'))


@app.route('/set_nickname')
def set_nickname_page():
    if not session.get('pending_google_id'):
        return redirect(url_for('login_page'))
    return render_template('set-nickname.html')


@app.route('/set_nickname', methods=['POST'])
def set_nickname_submit():
    google_id = session.get('pending_google_id')
    email = session.get('pending_email')
    nickname = request.form.get('nickname', '').strip()

    if not google_id or not email:
        return redirect(url_for('login_page'))
    if not nickname:
        return render_template('set-nickname.html', error='닉네임을 입력해주세요.')
    if len(nickname) > 20:
        return render_template('set-nickname.html', error='닉네임은 20자 이하여야 합니다.')

    with Session(engine) as db_session:
        new_user = User(username=email, google_id=google_id, nickname=nickname)
        db_session.add(new_user)
        db_session.commit()

    session.pop('pending_google_id', None)
    session.pop('pending_email', None)
    session['user_id'] = email
    session['nickname'] = nickname
    session['show_login_toast'] = True
    return redirect(url_for('home'))


# ───────────── 홈 / 로그아웃 ─────────────
@app.route('/main')
def home():
    show_toast = session.pop('show_login_toast', False)
    nickname = session.get('nickname', session.get('user_id', '게스트'))
    with Session(engine) as db_session:
        owner = db_session.exec(select(User).where(User.is_owner == True)).first()
        admin_discord = owner.discord_id if owner and owner.discord_id else None
    return render_template('main.html', user_id=nickname, show_toast=show_toast, is_admin=check_admin(), raw_user_id=session.get('user_id',''), admin_discord=admin_discord)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))




# ───────────── 회원 정보 수정 ─────────────
@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return redirect(url_for('user_profile', target_username=session['user_id']))


@app.route('/update_social', methods=['POST'])
def update_social():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    discord_id = request.form.get('discord_id', '').strip()
    github_id  = request.form.get('github_id',  '').strip()
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == session['user_id'])).first()
        if not user:
            return {"error": "사용자를 찾을 수 없습니다."}, 404
        user.discord_id = discord_id or None
        user.github_id  = github_id  or None
        db_session.add(user)
        db_session.commit()
    return {"success": True}


@app.route('/update_nickname', methods=['POST'])
def update_nickname():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    new_nickname = request.form.get('nickname', '').strip()
    if not new_nickname:
        return {"error": "닉네임을 입력해주세요."}, 400
    if len(new_nickname) > 20:
        return {"error": "닉네임은 20자 이하여야 합니다."}, 400
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == session['user_id'])).first()
        if not user:
            return {"error": "사용자를 찾을 수 없습니다."}, 404
        user.nickname = new_nickname
        db_session.add(user)
        uid = session['user_id']
        # 공지 닉네임 업데이트
        for n in db_session.exec(select(Notice).where(Notice.author_id == uid)).all():
            n.author_nickname = new_nickname
            db_session.add(n)
        # 팀 leader_name 업데이트
        for t in db_session.exec(select(Team).where(Team.leader_id == uid)).all():
            t.leader_name = new_nickname
            db_session.add(t)
        # 팀원 display_name 업데이트
        for m in db_session.exec(select(TeamMember).where(TeamMember.user_id == uid)).all():
            m.display_name = new_nickname
            db_session.add(m)
        # 구인 프로필 name 업데이트
        for p in db_session.exec(select(Profile).where(Profile.user_id == uid)).all():
            p.name = new_nickname
            db_session.add(p)
        db_session.commit()
    session['nickname'] = new_nickname
    return {"success": True, "nickname": new_nickname}


# ───────────── 멤버 보기 ─────────────
@app.route('/members')
def members_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    current_user = session['user_id']
    nickname = session.get('nickname', current_user)

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

    return render_template(
        'members.html',
        user_id=nickname, is_admin=check_admin(), raw_user_id=current_user,
        init_members=json.dumps(init_members, ensure_ascii=False),
    )


@app.route('/api/session-check')
def session_check():
    if 'user_id' not in session:
        return {"ok": False}, 401
    return {"ok": True}


@app.route('/api/members', methods=['GET'])
def get_members():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_uid = session['user_id']
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


# ───────────── 공지사항 ─────────────
@app.route('/notice')
def notice():
    nickname = session.get('nickname', session.get('user_id', '게스트'))

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

    return render_template(
        'notice.html',
        user_id=nickname, current_user=session.get('user_id', ''),
        is_admin=check_admin(), raw_user_id=session.get('user_id',''),
        init_notices=json.dumps(init_notices, ensure_ascii=False),
    )


@app.route('/api/notices', methods=['GET'])
def get_notices():
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


@app.route('/api/notices', methods=['POST'])
def create_notice():
    if not check_superadmin():
        return {"error": "권한이 없습니다."}, 403
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    is_pinned = request.form.get('is_pinned', 'false') == 'true'
    if not title or not content:
        return {"error": "제목과 내용을 입력해주세요."}, 400
    nickname = session.get('nickname', session['user_id'])
    with Session(engine) as db_session:
        notice = Notice(
            title=title, content=content,
            author_id=session['user_id'], author_nickname=nickname,
            is_pinned=is_pinned,
            created_at=time.time(), updated_at=time.time()
        )
        db_session.add(notice)
        db_session.commit()
        db_session.refresh(notice)
    return {"success": True, "id": notice.id}


@app.route('/api/notices/<int:notice_id>', methods=['PUT'])
def update_notice(notice_id):
    if not check_superadmin():
        return {"error": "권한이 없습니다."}, 403
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    is_pinned = request.form.get('is_pinned', 'false') == 'true'
    if not title or not content:
        return {"error": "제목과 내용을 입력해주세요."}, 400
    with Session(engine) as db_session:
        notice = db_session.get(Notice, notice_id)
        if not notice:
            return {"error": "공지를 찾을 수 없습니다."}, 404
        notice.title = title
        notice.content = content
        notice.is_pinned = is_pinned
        notice.updated_at = time.time()
        db_session.add(notice)
        db_session.commit()
    return {"success": True}


@app.route('/api/notices/<int:notice_id>', methods=['DELETE'])
def delete_notice(notice_id):
    if not check_superadmin():
        return {"error": "권한이 없습니다."}, 403
    with Session(engine) as db_session:
        notice = db_session.get(Notice, notice_id)
        if not notice:
            return {"error": "공지를 찾을 수 없습니다."}, 404
        db_session.delete(notice)
        db_session.commit()
    return {"success": True}


# ───────────── 공지 댓글 ─────────────
@app.route('/api/notices/<int:notice_id>/comments', methods=['GET'])
def get_notice_comments(notice_id):
    with Session(engine) as db_session:
        comments = db_session.exec(
            select(NoticeComment)
            .where(NoticeComment.notice_id == notice_id)
            .order_by(NoticeComment.created_at.asc())
        ).all()
    current_uid = session.get('user_id')
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


@app.route('/api/notices/<int:notice_id>/comments', methods=['POST'])
def post_notice_comment(notice_id):
    if 'user_id' not in session:
        return {"error": "로그인이 필요합니다."}, 401
    content = request.form.get('content', '').strip()
    if not content:
        return {"error": "내용을 입력해주세요."}, 400
    if len(content) > 100:
        return {"error": "댓글은 100자 이내여야 합니다."}, 400
    with Session(engine) as db_session:
        notice = db_session.get(Notice, notice_id)
        if not notice:
            return {"error": "공지를 찾을 수 없습니다."}, 404
        uid = session['user_id']
        user = db_session.exec(select(User).where(User.username == uid)).first()
        nickname = user.nickname or uid if user else uid
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


@app.route('/api/notices/<int:notice_id>/comments/<int:comment_id>', methods=['DELETE'])
def delete_notice_comment(notice_id, comment_id):
    if 'user_id' not in session:
        return {"error": "로그인이 필요합니다."}, 401
    uid = session['user_id']
    with Session(engine) as db_session:
        comment = db_session.get(NoticeComment, comment_id)
        if not comment or comment.notice_id != notice_id:
            return {"error": "댓글을 찾을 수 없습니다."}, 404
        # 본인 또는 관리자만 삭제 가능
        if comment.author_id != uid and not check_admin():
            return {"error": "권한이 없습니다."}, 403
        db_session.delete(comment)
        db_session.commit()
    return {"success": True}


# ───────────── 관리자 페이지 ─────────────
@app.route('/admin')
def admin_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    if not check_admin():
        return redirect(url_for('home'))
    nickname = session.get('nickname', session['user_id'])

    init_notices, init_users, init_messages = [], [], []
    try:
        with Session(engine) as db_session:
            notices  = db_session.exec(select(Notice).order_by(Notice.is_pinned.desc(), Notice.created_at.desc())).all()
            users    = db_session.exec(select(User)).all()
            profiles = db_session.exec(select(Profile)).all()
            teams    = db_session.exec(select(Team)).all()
            messages = db_session.exec(select(DirectMessage).order_by(DirectMessage.created_at.desc())).all()
            nick_map = {u.username: (u.nickname or u.username) for u in users}

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

    return render_template(
        'admin.html',
        user_id=nickname, current_user=session['user_id'],
        is_superadmin=check_superadmin(), is_owner=check_owner(),
        init_notices=json.dumps(init_notices, ensure_ascii=False),
        init_users=json.dumps(init_users, ensure_ascii=False),
        init_messages=json.dumps(init_messages, ensure_ascii=False),
    )


@app.route('/admin/setup', methods=['GET', 'POST'])
def admin_setup():
    """첫 관리자 설정"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    if request.method == 'GET':
        return '''
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
        </form></div>'''
    secret = request.form.get('secret', '')
    if secret != os.environ.get('ADMIN_SECRET'):
        return '''<style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#f5f5f5;}
        .box{background:#fff;padding:32px;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);width:320px;text-align:center;}
        a{color:#4f8ef7;}</style>
        <div class="box">❌ 잘못된 시크릿 키입니다.<br><br><a href="/admin/setup">다시 시도</a></div>'''
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == session['user_id'])).first()
        if not user:
            return redirect(url_for('login_page'))
        user.is_admin = True
        user.is_superadmin = True
        user.is_owner = True
        db_session.add(user)
        db_session.commit()
    return redirect(url_for('admin_page'))


@app.route('/api/admin/users', methods=['GET'])
def admin_get_users():
    if not check_admin():
        return {"error": "권한이 없습니다."}, 403
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


@app.route('/api/admin/users/<target_id>/lock', methods=['POST'])
def admin_lock_user(target_id):
    if not check_superadmin():
        return {"error": "권한이 없습니다."}, 403
    minutes = int(request.form.get('minutes', 30))
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == target_id)).first()
        if not user:
            return {"error": "사용자를 찾을 수 없습니다."}, 404
        user.locked_until = time.time() + minutes * 60
        db_session.add(user)
        db_session.commit()
    return {"success": True}


@app.route('/api/admin/users/<target_id>/unlock', methods=['POST'])
def admin_unlock_user(target_id):
    if not check_superadmin():
        return {"error": "권한이 없습니다."}, 403
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == target_id)).first()
        if not user:
            return {"error": "사용자를 찾을 수 없습니다."}, 404
        user.locked_until = None
        user.failed_attempts = 0
        db_session.add(user)
        db_session.commit()
    return {"success": True}


@app.route('/api/admin/users/<target_id>/toggle-admin', methods=['POST'])
def admin_toggle_admin(target_id):
    if not check_superadmin():
        return {"error": "권한이 없습니다."}, 403
    if target_id == session['user_id']:
        return {"error": "본인의 관리자 권한은 변경할 수 없습니다."}, 400
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == target_id)).first()
        if not user:
            return {"error": "사용자를 찾을 수 없습니다."}, 404
        # 관리자 해제는 owner만 가능
        if user.is_admin and not check_owner():
            return {"error": "관리자 해제는 최고 관리자만 할 수 있습니다."}, 403
        user.is_admin = not user.is_admin
        user.is_superadmin = user.is_admin
        db_session.add(user)
        db_session.commit()
    return {"success": True, "is_admin": user.is_admin}


@app.route('/api/admin/users/<target_id>', methods=['DELETE'])
def admin_delete_user(target_id):
    if not check_superadmin():
        return {"error": "권한이 없습니다."}, 403
    if target_id == session['user_id']:
        return {"error": "본인 계정은 삭제할 수 없습니다."}, 400
    with Session(engine) as db_session:
        user = db_session.exec(select(User).where(User.username == target_id)).first()
        if not user:
            return {"error": "사용자를 찾을 수 없습니다."}, 404
        # 관련 데이터 삭제
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


# ───────────── 관리자 메시지 관리 ─────────────
@app.route('/api/admin/messages', methods=['GET'])
def admin_get_messages():
    if not check_admin():
        return {"error": "권한이 없습니다."}, 403
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


@app.route('/api/admin/messages/<int:msg_id>', methods=['DELETE'])
def admin_delete_message(msg_id):
    if not check_admin():
        return {"error": "권한이 없습니다."}, 403
    with Session(engine) as db_session:
        msg = db_session.get(DirectMessage, msg_id)
        if not msg:
            return {"error": "메시지를 찾을 수 없습니다."}, 404
        db_session.delete(msg)
        db_session.commit()
    return {"success": True}


# ───────────── 닉네임 검색 ─────────────
@app.route('/api/search')
def api_search():
    q = request.args.get('q', '').strip().lower()
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


# ───────────── 활동 통계 ─────────────
@app.route('/api/stats')
def api_stats():
    with Session(engine) as db_session:
        user_count = db_session.exec(select(func.count(User.id))).one()
        profile_count = db_session.exec(select(func.count(Profile.id))).one()
    return {"users": user_count, "profiles": profile_count}


# ───────────── 새 글 확인용 최신 타임스탬프 ─────────────
@app.route('/api/new-activity')
def new_activity():
    with Session(engine) as db_session:
        profiles = db_session.exec(select(Profile)).all()
        notices  = db_session.exec(select(Notice)).all()
    profile_latest = max((p.created_at for p in profiles), default=0)
    notice_latest  = max((n.created_at for n in notices),  default=0)
    return {"profile_latest": profile_latest, "notice_latest": notice_latest}


# ───────────── 구인 게시판 ─────────────
@app.route('/user/<target_username>')
def user_profile(target_username):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    with Session(engine) as db_session:
        target = db_session.exec(select(User).where(User.username == target_username)).first()
        if not target:
            return redirect(url_for('home'))
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
            })

        team_list = []
        for t in led_teams:
            team_list.append({"id": t.id, "name": t.name, "dev_field": t.dev_field, "role": "팀장"})
        for t in member_teams_rows:
            if t.leader_id != target_username:
                team_list.append({"id": t.id, "name": t.name, "dev_field": t.dev_field, "role": "팀원",
                                   "leader_name": nick_map.get(t.leader_id, t.leader_name)})

    is_self = session['user_id'] == target_username
    nickname = session.get('nickname', session['user_id'])
    return render_template('user_profile.html',
        user_id=nickname,
        target_username=target_username,
        target_nickname=target.nickname or target_username,
        profiles=profile_list,
        teams=team_list,
        is_self=is_self,
        is_admin=check_admin(),
        discord_id=target.discord_id or '',
        github_id=target.github_id or '',
        raw_user_id=session.get('user_id', ''))


@app.route('/recruit')
def recruit():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    current_user = session['user_id']
    nickname = session.get('nickname', current_user)

    # 초기 데이터를 서버에서 미리 조회 → JS API 호출 왕복 제거
    init_profiles, init_teams = [], []
    try:
        with Session(engine) as db_session:
            profiles   = db_session.exec(select(Profile).where(Profile.post_type == 'recruit').order_by(Profile.created_at)).all()
            teams      = db_session.exec(select(Team).order_by(Team.created_at)).all()
            users      = db_session.exec(select(User)).all()
            interests  = db_session.exec(select(RecruitInterest).where(RecruitInterest.sender_id == current_user)).all()
            members_all = db_session.exec(select(TeamMember)).all()

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

        mem_map = {}
        for m in members_all:
            mem_map.setdefault(m.team_id, []).append(m)
        for t in teams:
            mems     = mem_map.get(t.id, [])
            accepted = [m for m in mems if m.status == 'accepted']
            pending  = [m for m in mems if m.status == 'pending']
            my_status = next((m.status for m in mems if m.user_id == current_user), None)
            init_teams.append({
                "id": t.id, "name": t.name, "description": t.description,
                "dev_field": t.dev_field, "max_members": t.max_members,
                "team_image": t.team_image, "leader_id": t.leader_id,
                "leader_name": nick_map.get(t.leader_id, t.leader_name),
                "is_mine": t.leader_id == current_user, "my_status": my_status,
                "members":      [{"id": m.id, "user_id": m.user_id, "display_name": nick_map.get(m.user_id, m.display_name), "status": m.status} for m in accepted],
                "pending_count": len(pending),
                "pending_list":  [{"id": m.id, "user_id": m.user_id, "display_name": nick_map.get(m.user_id, m.display_name)} for m in pending] if t.leader_id == current_user else [],
            })

        # 팀 채팅: 내가 속한 팀(팀장 or 승인 멤버)의 메시지 사전 조회
        my_team_ids = {
            t.id for t in teams
            if t.leader_id == current_user
            or any(m.user_id == current_user and m.status == 'accepted' for m in mem_map.get(t.id, []))
        }
        with Session(engine) as db_session:
            group_msgs_all = db_session.exec(
                select(GroupMessage)
                .where(GroupMessage.team_id.in_(my_team_ids))
                .order_by(GroupMessage.created_at)
            ).all() if my_team_ids else []

        # { teamId: { team_name, members, messages } }
        init_team_chats = {}
        for t_row in init_teams:
            tid = t_row["id"]
            if tid not in my_team_ids:
                continue
            leader_display = t_row["leader_name"] + " 👑"
            members_data = [{"user_id": t_row["leader_id"], "display_name": leader_display}] + [
                {"user_id": m["user_id"], "display_name": nick_map.get(m["user_id"], m["display_name"])}
                for m in t_row["members"]
            ]
            init_team_chats[tid] = {
                "team_name": t_row["name"],
                "members":   members_data,
                "messages":  [
                    {"id": gm.id, "sender_id": gm.sender_id,
                     "sender_nickname": gm.sender_nickname,
                     "message": gm.message, "created_at": gm.created_at,
                     "is_mine": gm.sender_id == current_user}
                    for gm in group_msgs_all if gm.team_id == tid
                ],
            }
    except Exception:
        pass  # 실패 시 빈 데이터로 시작, JS가 API로 재시도

    return render_template(
        'recruit.html',
        user_id=nickname, is_admin=check_admin(), raw_user_id=current_user,
        init_profiles=json.dumps(init_profiles, ensure_ascii=False),
        init_teams=json.dumps(init_teams, ensure_ascii=False),
        init_team_chats=json.dumps(init_team_chats, ensure_ascii=False),
    )


@app.route('/api/profiles', methods=['GET'])
def get_profiles():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
    ptype = request.args.get('type', 'recruit')
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
    except Exception as e:
        return {"error": "데이터를 불러오는 중 오류가 발생했습니다.", "profiles": []}, 500


@app.route('/api/profiles', methods=['POST'])
def create_profile():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
    with Session(engine) as db_session:
        post_type = request.form.get('post_type', 'recruit').strip()
        existing = db_session.exec(
            select(Profile).where(Profile.user_id == current_user, Profile.post_type == post_type)
        ).first()
        if existing:
            return {"error": "이미 해당 유형의 프로필이 등록되어 있습니다."}, 400
        name = session.get('nickname', current_user)
        class_number = request.form.get('class_number', '').strip()
        major = request.form.get('major', '').strip()
        bio = request.form.get('bio', '').strip()
        past_languages = request.form.get('past_languages', '').strip()
        current_languages = request.form.get('current_languages', '').strip()
        profile_image = request.form.get('profile_image', '').strip()
        dev_field = request.form.get('dev_field', '').strip() or None
        if not class_number or not major:
            return {"error": "반/번호, 전공은 필수입니다."}, 400
        if post_type == 'job_seek' and not dev_field:
            return {"error": "개발 분야를 선택해주세요."}, 400
        profile = Profile(
            user_id=current_user,
            name=name,
            bio=bio,
            class_number=class_number,
            major=major,
            past_languages=past_languages,
            current_languages=current_languages,
            profile_image=profile_image if profile_image else None,
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
                "past_languages": [l.strip() for l in profile.past_languages.split(',') if l.strip()],
                "current_languages": [l.strip() for l in profile.current_languages.split(',') if l.strip()],
                "profile_image": profile.profile_image,
                "is_mine": True
            }
        }


# ───────────── 팀 게시판 ─────────────
@app.route('/api/teams', methods=['GET'])
def get_teams():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
    try:
        with Session(engine) as db_session:
            teams = db_session.exec(select(Team).order_by(Team.created_at)).all()
            members_all = db_session.exec(select(TeamMember)).all()
            users = db_session.exec(select(User)).all()
        # 실시간 닉네임 맵 (user_id → 현재 닉네임)
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
    except Exception as e:
        return {"error": "데이터를 불러오는 중 오류가 발생했습니다.", "teams": []}, 500


@app.route('/api/teams', methods=['POST'])
def create_team():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
    nickname = session.get('nickname', current_user)
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    dev_field = request.form.get('dev_field', '').strip()
    max_members = int(request.form.get('max_members', 4))
    team_image = request.form.get('team_image', '').strip() or None
    if not name:
        return {"error": "팀 이름은 필수입니다."}, 400
    with Session(engine) as db_session:
        team = Team(leader_id=current_user, leader_name=nickname,
                    name=name, description=description,
                    dev_field=dev_field, max_members=max_members,
                    team_image=team_image,
                    created_at=time.time())
        db_session.add(team)
        db_session.commit()
    return {"success": True}


@app.route('/api/teams/<int:team_id>', methods=['DELETE'])
def delete_team(team_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team:
            return {"error": "팀을 찾을 수 없습니다."}, 404
        if team.leader_id != session['user_id']:
            return {"error": "권한이 없습니다."}, 403
        for m in db_session.exec(select(TeamMember).where(TeamMember.team_id == team_id)).all():
            db_session.delete(m)
        db_session.delete(team)
        db_session.commit()
    return {"success": True}


@app.route('/api/teams/<int:team_id>', methods=['PUT'])
def update_team(team_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team:
            return {"error": "팀을 찾을 수 없습니다."}, 404
        if team.leader_id != session['user_id']:
            return {"error": "권한이 없습니다."}, 403
        new_name = request.form.get('name', '').strip()
        if new_name:
            if len(new_name) > 30:
                return {"error": "팀 이름은 30자 이내여야 합니다."}, 400
            team.name = new_name
        new_desc = request.form.get('description')
        if new_desc is not None:
            if len(new_desc.strip()) > 50:
                return {"error": "팀 소개는 50자 이내여야 합니다."}, 400
            team.description = new_desc.strip()
        new_field = request.form.get('dev_field')
        if new_field is not None:
            team.dev_field = new_field.strip()
        new_image = request.form.get('team_image')
        if new_image is not None:
            team.team_image = new_image.strip() or None
        new_max = request.form.get('max_members')
        if new_max:
            new_max = int(new_max)
            accepted_count = db_session.exec(
                select(func.count()).where(TeamMember.team_id == team_id, TeamMember.status == 'accepted')
            ).one()
            if new_max < accepted_count:
                return {"error": f"현재 팀원이 {accepted_count}명이므로 {accepted_count}명 이상으로 설정해야 합니다."}, 400
            if new_max < 2 or new_max > 20:
                return {"error": "인원은 2~20명 사이여야 합니다."}, 400
            team.max_members = new_max
        db_session.add(team)
        db_session.commit()
        saved_name = team.name
    return {"success": True, "name": saved_name}


@app.route('/api/teams/<int:team_id>/members/<int:member_id>', methods=['DELETE'])
def kick_member(team_id, member_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team or team.leader_id != session['user_id']:
            return {"error": "권한이 없습니다."}, 403
        member = db_session.get(TeamMember, member_id)
        if not member or member.team_id != team_id:
            return {"error": "멤버를 찾을 수 없습니다."}, 404
        db_session.delete(member)
        db_session.commit()
    return {"success": True}


@app.route('/api/teams/<int:team_id>/leave', methods=['POST'])
def leave_team(team_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    uid = session['user_id']
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team:
            return {"error": "팀을 찾을 수 없습니다."}, 404
        if team.leader_id == uid:
            return {"error": "팀장은 팀을 나갈 수 없습니다. 팀 삭제를 이용해주세요."}, 400
        member = db_session.exec(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == uid)
        ).first()
        if not member:
            return {"error": "팀에 참여 중이 아닙니다."}, 404
        db_session.delete(member)
        db_session.commit()
    return {"success": True}


@app.route('/api/teams/<int:team_id>/join', methods=['POST'])
def join_team(team_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
    nickname = session.get('nickname', current_user)
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team:
            return {"error": "팀을 찾을 수 없습니다."}, 404
        if team.leader_id == current_user:
            return {"error": "본인 팀에는 신청할 수 없습니다."}, 400
        existing = db_session.exec(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == current_user)
        ).first()
        if existing:
            return {"error": "이미 신청했습니다."}, 400
        accepted_count = len(db_session.exec(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.status == 'accepted')
        ).all())
        if accepted_count >= team.max_members:
            return {"error": "팀 정원이 꽉 찼습니다."}, 400
        member = TeamMember(team_id=team_id, user_id=current_user,
                            display_name=nickname, status='pending',
                            joined_at=time.time())
        db_session.add(member)
        db_session.commit()
    return {"success": True}


@app.route('/api/teams/<int:team_id>/respond', methods=['POST'])
def respond_team(team_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team or team.leader_id != current_user:
            return {"error": "권한이 없습니다."}, 403
        member_id = int(request.form.get('member_id', 0))
        action = request.form.get('action', '')  # 'accept' | 'reject'
        member = db_session.get(TeamMember, member_id)
        if not member or member.team_id != team_id:
            return {"error": "멤버를 찾을 수 없습니다."}, 404
        if action == 'accept':
            accepted_count = len(db_session.exec(
                select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.status == 'accepted')
            ).all())
            if accepted_count >= team.max_members:
                return {"error": "팀 정원이 꽉 찼습니다."}, 400
            member.status = 'accepted'
        elif action == 'reject':
            member.status = 'rejected'
        else:
            return {"error": "잘못된 액션입니다."}, 400
        db_session.add(member)
        db_session.commit()
    return {"success": True}


# ───────────── 구인하기 (관심 표현) ─────────────
@app.route('/api/profiles/<int:profile_id>/interest', methods=['POST'])
def recruit_interest(profile_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
    nickname = session.get('nickname', current_user)
    with Session(engine) as db_session:
        profile = db_session.get(Profile, profile_id)
        if not profile:
            return {"error": "프로필을 찾을 수 없습니다."}, 404
        if profile.user_id == current_user:
            return {"error": "본인 게시글에는 구인할 수 없습니다."}, 400
        existing = db_session.exec(
            select(RecruitInterest).where(
                RecruitInterest.profile_id == profile_id,
                RecruitInterest.sender_id == current_user
            )
        ).first()
        if existing:
            return {"error": "이미 구인 신청을 보냈습니다."}, 400
        interest = RecruitInterest(
            profile_id=profile_id,
            sender_id=current_user,
            created_at=time.time()
        )
        db_session.add(interest)
        notif = Notification(
            user_id=profile.user_id,
            sender_id=current_user,
            sender_nickname=nickname,
            profile_id=profile_id,
            profile_name=profile.name,
            is_read=False,
            created_at=time.time()
        )
        db_session.add(notif)
        try:
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            return {"error": "신청 처리 중 오류가 발생했습니다."}, 500
    return {"success": True}


# ───────────── 알림 ─────────────
@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
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
                "sender_nickname": n.sender_nickname,
                "profile_name": n.profile_name,
                "notif_type": n.notif_type,
                "is_read": n.is_read,
                "created_at": n.created_at
            } for n in notifs[:20]
        ],
        "unread": unread
    }


@app.route('/api/profiles/<int:profile_id>/view', methods=['POST'])
def view_profile(profile_id):
    if 'user_id' not in session:
        return {"success": False}, 401
    current_user = session['user_id']
    nickname = session.get('nickname', current_user)
    with Session(engine) as db_session:
        profile = db_session.get(Profile, profile_id)
        if not profile or profile.user_id == current_user:
            return {"success": False}
        # 이미 같은 사람이 같은 프로필에 view 알림을 보낸 경우 중복 방지
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


# ───────────── DM ─────────────
@app.route('/api/dm/unread', methods=['GET'])
def dm_unread():
    if 'user_id' not in session:
        return {"unread": 0}
    current_user = session['user_id']
    with Session(engine) as db_session:
        count = len(db_session.exec(
            select(DirectMessage).where(
                DirectMessage.receiver_id == current_user,
                DirectMessage.is_read == False
            )
        ).all())
    return {"unread": count}


@app.route('/api/dm/conversations', methods=['GET'])
def dm_conversations():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
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


@app.route('/api/dm/<other_user_id>', methods=['GET'])
def get_dm(other_user_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
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


@app.route('/api/dm/<other_user_id>', methods=['POST'])
def send_dm(other_user_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
    message_text = request.form.get('message', '').strip()
    if not message_text:
        return {"error": "메시지를 입력해주세요."}, 400
    with Session(engine) as db_session:
        other_user = db_session.exec(select(User).where(User.username == other_user_id)).first()
        if not other_user:
            return {"error": "사용자를 찾을 수 없습니다."}, 404
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


@app.route('/api/notifications/read-all', methods=['POST'])
def read_all_notifications():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
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


@app.route('/api/profiles/<int:profile_id>', methods=['PUT'])
def update_profile(profile_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
    with Session(engine) as db_session:
        profile = db_session.get(Profile, profile_id)
        if not profile:
            return {"error": "프로필을 찾을 수 없습니다."}, 404
        if profile.user_id != current_user:
            return {"error": "권한이 없습니다."}, 403
        name = session.get('nickname', current_user)
        class_number = request.form.get('class_number', '').strip()
        major = request.form.get('major', '').strip()
        bio = request.form.get('bio', '').strip()
        past_languages = request.form.get('past_languages', '').strip()
        current_languages = request.form.get('current_languages', '').strip()
        profile_image = request.form.get('profile_image', '').strip()
        if not class_number or not major:
            return {"error": "반/번호, 전공은 필수입니다."}, 400
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


@app.route('/api/profiles/<int:profile_id>', methods=['DELETE'])
def delete_profile(profile_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
    with Session(engine) as db_session:
        profile = db_session.get(Profile, profile_id)
        if not profile:
            return {"error": "프로필을 찾을 수 없습니다."}, 404
        if profile.user_id != current_user:
            return {"error": "권한이 없습니다."}, 403
        db_session.delete(profile)
        db_session.commit()
    return {"success": True}


@app.route('/api/teams/<int:team_id>/messages', methods=['GET'])
def get_group_messages(team_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team:
            return {"error": "팀을 찾을 수 없습니다."}, 404
        # 팀 멤버 확인
        member = db_session.exec(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == current_user,
                TeamMember.status == 'accepted'
            )
        ).first()
        is_leader = team.leader_id == current_user
        if not member and not is_leader:
            return {"error": "팀 멤버만 볼 수 있습니다."}, 403
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
        # 팀장 추가
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


@app.route('/api/teams/<int:team_id>/messages', methods=['POST'])
def send_group_message(team_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    current_user = session['user_id']
    message_text = request.form.get('message', '').strip()
    if not message_text:
        return {"error": "메시지를 입력해주세요."}, 400
    with Session(engine) as db_session:
        team = db_session.get(Team, team_id)
        if not team:
            return {"error": "팀을 찾을 수 없습니다."}, 404
        member = db_session.exec(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == current_user,
                TeamMember.status == 'accepted'
            )
        ).first()
        is_leader = team.leader_id == current_user
        if not member and not is_leader:
            return {"error": "팀 멤버만 메시지를 보낼 수 있습니다."}, 403
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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 4500))
    app.run(host='0.0.0.0', port=port, debug=False)
