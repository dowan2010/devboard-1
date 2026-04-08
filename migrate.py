import sqlite3
import psycopg2

SQLITE_PATH = "database.db"
PG_URL = "postgresql://postgres.repjrxivnhguyczuwgjd:kimdw1220**@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"

sqlite_conn = sqlite3.connect(SQLITE_PATH)
sqlite_conn.row_factory = sqlite3.Row
pg_conn = psycopg2.connect(PG_URL)
pg_cur = pg_conn.cursor()

def b(v):
    return bool(v) if v is not None else False

def f(v):
    return float(v) if v is not None else 0.0

# 기존 데이터 초기화
for t in ["notification","recruitinterest","directmessage","teammember","team","noticecomment","notice",'"user"',"profile"]:
    pg_cur.execute(f'DELETE FROM {t}')
pg_conn.commit()

# user
rows = sqlite_conn.execute("SELECT * FROM user").fetchall()
for r in rows:
    pg_cur.execute("""
        INSERT INTO "user" (id,username,google_id,password,nickname,failed_attempts,locked_until,is_admin,is_superadmin,is_owner,discord_id,github_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (r['id'],r['username'],r['google_id'],r['password'],r['nickname'],r['failed_attempts'],r['locked_until'],b(r['is_admin']),b(r['is_superadmin']),b(r['is_owner']),r['discord_id'],r['github_id']))
pg_conn.commit()
print(f"✅ user: {len(rows)}개 완료")

# notice
rows = sqlite_conn.execute("SELECT * FROM notice").fetchall()
for r in rows:
    pg_cur.execute("""
        INSERT INTO notice (id,title,content,author_id,author_nickname,is_pinned,created_at,updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (r['id'],r['title'],r['content'],r['author_id'],r['author_nickname'],b(r['is_pinned']),f(r['created_at']),f(r['updated_at'])))
pg_conn.commit()
print(f"✅ notice: {len(rows)}개 완료")

# noticecomment
rows = sqlite_conn.execute("SELECT * FROM noticecomment").fetchall()
for r in rows:
    pg_cur.execute("""
        INSERT INTO noticecomment (id,notice_id,author_id,author_nickname,content,created_at)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (r['id'],r['notice_id'],r['author_id'],r['author_nickname'],r['content'],f(r['created_at'])))
pg_conn.commit()
print(f"✅ noticecomment: {len(rows)}개 완료")

# team
rows = sqlite_conn.execute("SELECT * FROM team").fetchall()
for r in rows:
    pg_cur.execute("""
        INSERT INTO team (id,leader_id,leader_name,name,description,dev_field,max_members,team_image,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (r['id'],r['leader_id'],r['leader_name'],r['name'],r['description'],r['dev_field'],r['max_members'],r['team_image'],f(r['created_at'])))
pg_conn.commit()
print(f"✅ team: {len(rows)}개 완료")

# teammember
rows = sqlite_conn.execute("SELECT * FROM teammember").fetchall()
for r in rows:
    pg_cur.execute("""
        INSERT INTO teammember (id,team_id,user_id,display_name,status,joined_at)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (r['id'],r['team_id'],r['user_id'],r['display_name'],r['status'],f(r['joined_at'])))
pg_conn.commit()
print(f"✅ teammember: {len(rows)}개 완료")

# directmessage
rows = sqlite_conn.execute("SELECT * FROM directmessage").fetchall()
for r in rows:
    pg_cur.execute("""
        INSERT INTO directmessage (id,sender_id,receiver_id,message,is_read,created_at)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (r['id'],r['sender_id'],r['receiver_id'],r['message'],b(r['is_read']),f(r['created_at'])))
pg_conn.commit()
print(f"✅ directmessage: {len(rows)}개 완료")

# recruitinterest
rows = sqlite_conn.execute("SELECT * FROM recruitinterest").fetchall()
for r in rows:
    pg_cur.execute("""
        INSERT INTO recruitinterest (id,profile_id,sender_id,created_at)
        VALUES (%s,%s,%s,%s)
    """, (r['id'],r['profile_id'],r['sender_id'],f(r['created_at'])))
pg_conn.commit()
print(f"✅ recruitinterest: {len(rows)}개 완료")

# notification
rows = sqlite_conn.execute("SELECT * FROM notification").fetchall()
for r in rows:
    pg_cur.execute("""
        INSERT INTO notification (id,user_id,sender_id,sender_nickname,profile_id,profile_name,notif_type,is_read,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (r['id'],r['user_id'],r['sender_id'],r['sender_nickname'],r['profile_id'],r['profile_name'],r['notif_type'],b(r['is_read']),f(r['created_at'])))
pg_conn.commit()
print(f"✅ notification: {len(rows)}개 완료")

# profile
rows = sqlite_conn.execute("SELECT * FROM profile").fetchall()
for r in rows:
    pg_cur.execute("""
        INSERT INTO profile (id,user_id,name,class_number,major,bio,past_languages,current_languages,profile_image,post_type,dev_field,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (r['id'],r['user_id'],r['name'],r['class_number'],r['major'],r['bio'],r['past_languages'],r['current_languages'],r['profile_image'],r['post_type'],r['dev_field'],f(r['created_at'])))
pg_conn.commit()
print(f"✅ profile: {len(rows)}개 완료")

sqlite_conn.close()
pg_conn.close()
print("\n마이그레이션 완료!")
