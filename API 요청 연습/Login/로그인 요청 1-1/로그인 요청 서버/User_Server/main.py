from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from pathlib import Path
import sqlite3
from datetime import datetime
import hashlib
from pydantic import BaseModel

# ===== 프로젝트 기준 경로 =====
BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "db"
DB_PATH = DB_DIR / "UserDB.sqlite"

# ===== DB 커넥션 함수 =====
def get_db():
    DB_DIR.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)

# ===== 비밀번호 해시 함수 =====
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# ===== Pydantic 모델 =====
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

# ===== DB 초기화 =====
def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# ===== FastAPI Lifespan 이벤트로 DB 초기화 =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

# ===== 전체 유저 조회 =====
@app.get("/users")
def get_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email, created_at FROM users")
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "username": r[1], "email": r[2], "created_at": r[3]}
        for r in rows
    ]

# ===== 단일 유저 조회 =====
@app.get("/users/{user_id}")
def get_user(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, email, created_at FROM users WHERE id = ?",
        (user_id,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": row[0], "username": row[1], "email": row[2], "created_at": row[3]}

# ===== 유저 생성 (회원가입) =====
@app.post("/users")
def create_user(user: UserCreate):
    conn = get_db()
    cur = conn.cursor()
    try:
        hashed_pw = hash_password(user.password)
        cur.execute(
            "INSERT INTO users (username, email, password, created_at) VALUES (?, ?, ?, ?)",
            (user.username, user.email, hashed_pw, datetime.utcnow().isoformat())
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="이미 존재하는 유저입니다.")
    conn.close()
    return {"message": "회원가입 성공!"}

# ===== 로그인 =====
@app.post("/login")
def login(user: UserLogin):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT password FROM users WHERE username = ?",
        (user.username,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="아이디 또는 비밀번호가 다릅니다.")

    hashed_input = hash_password(user.password)
    if hashed_input != row[0]:
        raise HTTPException(status_code=400, detail="비밀번호가 다릅니다.")

    return {"message": f"{user.username}님 환영합니다."}
