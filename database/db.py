import sqlite3
import os
from datetime import datetime

DB_FILE = "./data/question_bank.db"


def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            subject     TEXT    NOT NULL,
            unit        TEXT,
            question    TEXT    NOT NULL,
            bloom_level TEXT,
            course_outcome TEXT,
            marks       INTEGER DEFAULT 2,
            status      TEXT    DEFAULT 'draft',
            validation  TEXT,
            created_at  TEXT,
            updated_at  TEXT
        )
    ''')
    conn.commit()
    conn.close()


def _connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def save_question(subject, unit, question, bloom_level, course_outcome, marks, validation):
    conn = _connect()
    now = datetime.now().isoformat()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO questions
            (subject, unit, question, bloom_level, course_outcome, marks, status, validation, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)
    ''', (subject, unit, question, bloom_level, course_outcome, marks, validation, now, now))
    conn.commit()
    qid = cursor.lastrowid
    conn.close()
    return qid


def get_questions(subject=None, unit=None, bloom_level=None, course_outcome=None,
                  marks=None, status=None):
    conn = _connect()
    query = "SELECT * FROM questions WHERE 1=1"
    params = []

    if subject:
        query += " AND subject = ?"
        params.append(subject)
    if unit:
        query += " AND unit = ?"
        params.append(unit)
    if bloom_level:
        query += " AND bloom_level = ?"
        params.append(bloom_level)
    if course_outcome:
        query += " AND course_outcome = ?"
        params.append(course_outcome)
    if marks is not None:
        query += " AND marks = ?"
        params.append(marks)
    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_question_by_id(question_id):
    conn = _connect()
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_question_status(question_id, status):
    conn = _connect()
    conn.execute(
        "UPDATE questions SET status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.now().isoformat(), question_id)
    )
    conn.commit()
    conn.close()


def update_question(question_id, **fields):
    allowed = {"question", "marks", "bloom_level", "course_outcome", "unit", "status"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [question_id]
    conn = _connect()
    conn.execute(f"UPDATE questions SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_question(question_id):
    conn = _connect()
    conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    conn.commit()
    conn.close()


def get_question_stats(subject=None):
    conn = _connect()
    base = "WHERE 1=1"
    params = []
    if subject:
        base += " AND subject = ?"
        params.append(subject)

    total = conn.execute(f"SELECT COUNT(*) FROM questions {base}", params).fetchone()[0]
    approved = conn.execute(f"SELECT COUNT(*) FROM questions {base} AND status='approved'", params).fetchone()[0]
    draft = conn.execute(f"SELECT COUNT(*) FROM questions {base} AND status='draft'", params).fetchone()[0]
    rejected = conn.execute(f"SELECT COUNT(*) FROM questions {base} AND status='rejected'", params).fetchone()[0]

    by_bt = conn.execute(
        f"SELECT bloom_level, COUNT(*) as cnt FROM questions {base} GROUP BY bloom_level", params
    ).fetchall()
    by_co = conn.execute(
        f"SELECT course_outcome, COUNT(*) as cnt FROM questions {base} GROUP BY course_outcome", params
    ).fetchall()
    by_marks = conn.execute(
        f"SELECT marks, COUNT(*) as cnt FROM questions {base} GROUP BY marks", params
    ).fetchall()

    conn.close()
    return {
        "total": total,
        "approved": approved,
        "draft": draft,
        "rejected": rejected,
        "by_bt": {r["bloom_level"]: r["cnt"] for r in by_bt},
        "by_co": {r["course_outcome"]: r["cnt"] for r in by_co},
        "by_marks": {r["marks"]: r["cnt"] for r in by_marks},
    }
