import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_MEMBER_DATA_DIR = PROJECT_ROOT / "member"
MEMBER_DIR = Path(os.getenv("MEMBER_DATA_DIR", str(DEFAULT_MEMBER_DATA_DIR))).expanduser()
MEMBER_DB_PATH = MEMBER_DIR / "members.db"
MEMBER_BET_DB_DIR = MEMBER_DIR / "member_bet_dbs"


def hash_password(password: str) -> str:
    """將密碼轉成 SHA256，登入和註冊共用同一套規則。"""

    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def is_valid_email(email: str) -> bool:
    """簡單檢查 email 格式，避免明顯錯誤資料寫入會員庫。"""

    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", (email or "").strip()))


def is_valid_local_phone(phone: str) -> bool:
    """檢查本地電話號碼：只接受 8 位數字，不輸入地區號。"""

    return bool(re.fullmatch(r"\d{8}", (phone or "").strip()))


def _connect_member_db():
    MEMBER_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(MEMBER_DB_PATH)


def init_db():
    """建立會員主資料庫。"""

    with closing(_connect_member_db()) as conn:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT NOT NULL,
                    password TEXT NOT NULL,
                    is_admin INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(members)").fetchall()
            }
            if "created_at" not in columns:
                conn.execute("ALTER TABLE members ADD COLUMN created_at TEXT")


def add_member(email, phone, password, is_admin=0):
    with closing(_connect_member_db()) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO members (email, phone, password, is_admin)
                VALUES (?, ?, ?, ?)
                """,
                (email.strip().lower(), phone.strip(), password, int(is_admin)),
            )


def get_member(email):
    with closing(_connect_member_db()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM members WHERE email = ?", ((email or "").strip().lower(),))
        return cur.fetchone()


def get_member_by_id(member_id: int):
    with closing(_connect_member_db()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM members WHERE id = ?", (member_id,))
        return cur.fetchone()


def get_all_members():
    with closing(_connect_member_db()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, email, phone, is_admin, created_at FROM members ORDER BY id")
        return cur.fetchall()


def delete_member(member_id):
    with closing(_connect_member_db()) as conn:
        with conn:
            conn.execute("DELETE FROM members WHERE id = ?", (member_id,))


def update_member(member_id, new_email, new_phone):
    with closing(_connect_member_db()) as conn:
        with conn:
            conn.execute(
                "UPDATE members SET email = ?, phone = ? WHERE id = ?",
                (new_email.strip().lower(), new_phone.strip(), member_id),
            )


def reset_password(email, phone, new_password):
    with closing(_connect_member_db()) as conn:
        with conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE members SET password = ? WHERE email = ? AND phone = ?",
                (new_password, (email or "").strip().lower(), (phone or "").strip()),
            )
            return cur.rowcount > 0


def ensure_first_admin(email: str, phone: str, password: str):
    """如果系統還沒有指定 admin，就建立第一個管理員帳號。"""

    init_db()
    if not get_member(email):
        add_member(email, phone, hash_password(password), 1)


def _safe_email_db_name(email: str) -> str:
    safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", email.strip().lower()).strip("_")
    return f"{safe_name or 'member'}_bets.db"


def get_member_bet_db_path(email: str) -> Path:
    """每位會員使用一個獨立投注資料庫。"""

    MEMBER_BET_DB_DIR.mkdir(parents=True, exist_ok=True)
    return MEMBER_BET_DB_DIR / _safe_email_db_name(email)


def init_member_bet_db(email: str):
    """建立指定會員的投注紀錄資料庫。"""

    db_path = get_member_bet_db_path(email)
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    bet_date TEXT NOT NULL,
                    bet_source TEXT NOT NULL,
                    bet_type TEXT NOT NULL,
                    numbers TEXT NOT NULL,
                    bankers TEXT DEFAULT '',
                    legs TEXT DEFAULT '',
                    bet_unit INTEGER DEFAULT 10,
                    total_bets INTEGER DEFAULT 1,
                    total_cost INTEGER DEFAULT 10,
                    result_status TEXT DEFAULT 'pending',
                    payout INTEGER DEFAULT 0,
                    notes TEXT DEFAULT ''
                )
                """
            )
    return db_path


def add_member_bet(
    email: str,
    bet_date: str,
    bet_source: str,
    bet_type: str,
    numbers,
    bankers=None,
    legs=None,
    bet_unit: int = 10,
    total_bets: int = 1,
    total_cost: int = 10,
    notes: str = "",
):
    """新增會員投注紀錄；numbers/bankers/legs 以 JSON 儲存。"""

    init_member_bet_db(email)
    db_path = get_member_bet_db_path(email)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO bets (
                    created_at, bet_date, bet_source, bet_type, numbers,
                    bankers, legs, bet_unit, total_bets, total_cost, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    bet_date,
                    bet_source,
                    bet_type,
                    json.dumps(numbers or [], ensure_ascii=False),
                    json.dumps(bankers or [], ensure_ascii=False),
                    json.dumps(legs or [], ensure_ascii=False),
                    int(bet_unit),
                    int(total_bets),
                    int(total_cost),
                    notes,
                ),
            )


def _canonical_numbers(numbers) -> list[int]:
    """投注號碼用排序後的整數清單比較，避免同號碼不同順序造成重複投注。"""

    return sorted(int(num) for num in (numbers or []))


def member_bet_exists(email: str, bet_date: str, bet_source: str, bet_type: str, numbers) -> bool:
    """檢查會員是否已有相同日期、來源、種類、號碼的投注。"""

    init_member_bet_db(email)
    target_numbers = _canonical_numbers(numbers)
    db_path = get_member_bet_db_path(email)

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT numbers FROM bets
            WHERE bet_date = ? AND bet_source = ? AND bet_type = ?
            """,
            (bet_date, bet_source, bet_type),
        )
        for row in cur.fetchall():
            try:
                existing_numbers = _canonical_numbers(json.loads(row["numbers"] or "[]"))
            except (TypeError, ValueError, json.JSONDecodeError):
                existing_numbers = []
            if existing_numbers == target_numbers:
                return True

    return False


def list_member_bets(email: str):
    """讀取會員投注紀錄，最新建立的排最前。"""

    init_member_bet_db(email)
    db_path = get_member_bet_db_path(email)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM bets ORDER BY created_at DESC, id DESC")
        return [dict(row) for row in cur.fetchall()]


def delete_member_bet(email: str, bet_id: int):
    """刪除會員其中一筆投注紀錄。"""

    init_member_bet_db(email)
    db_path = get_member_bet_db_path(email)
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("DELETE FROM bets WHERE id = ?", (int(bet_id),))


def delete_all_member_bets(email: str):
    """刪除會員全部投注紀錄。"""

    init_member_bet_db(email)
    db_path = get_member_bet_db_path(email)
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("DELETE FROM bets")
