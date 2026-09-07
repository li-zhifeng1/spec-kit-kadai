"""SQLite 接続・スキーマ初期化・標準科目シード。"""

import pathlib

from kaikei.accounts import STANDARD_ACCOUNTS

_DEFAULT_DB = "kaikei.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    code     TEXT PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL CHECK (
        category IN ('資産', '負債', '純資産', '収益', '費用')
    )
);

CREATE TABLE IF NOT EXISTS entries (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    date              TEXT NOT NULL,
    description       TEXT NOT NULL,
    reversed_entry_id INTEGER UNIQUE REFERENCES entries(id)
);

CREATE TABLE IF NOT EXISTS lines (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id     INTEGER NOT NULL REFERENCES entries(id),
    side         TEXT NOT NULL CHECK (side IN ('debit', 'credit')),
    account_code TEXT NOT NULL REFERENCES accounts(code),
    amount       INTEGER NOT NULL CHECK (
        amount > 0 AND amount <= 9223372036854775807
    )
);
"""


def get_db_path(path: str | pathlib.Path | None = None) -> pathlib.Path:
    """DB ファイルパスを決定する(引数 > 環境変数 KAIKEI_DB > 既定)。"""
    import os

    if path is not None:
        return pathlib.Path(path)
    env = os.environ.get("KAIKEI_DB")
    if env:
        return pathlib.Path(env)
    return pathlib.Path(_DEFAULT_DB)


def get_connection(path: str | pathlib.Path | None = None) -> "sqlite3.Connection":
    """DB 接続を返す。DB が未初期化なら初期化・シードしてから接続する。"""
    import sqlite3

    p = get_db_path(path)
    conn = sqlite3.connect(p)
    conn.execute("PRAGMA foreign_keys = ON")
    initialized = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
        " AND name = 'accounts'"
    ).fetchone()[0]
    if not initialized:
        conn.executescript(_SCHEMA)
        conn.executemany(
            "INSERT OR IGNORE INTO accounts (code, name, category)"
            " VALUES (?, ?, ?)",
            STANDARD_ACCOUNTS,
        )
        conn.commit()
    return conn


def initialize(path: str | pathlib.Path | None = None) -> pathlib.Path:
    """スキーマを作成し、標準科目を冪等に投入する。パスを返す。"""
    import sqlite3

    p = get_db_path(path)
    conn = sqlite3.connect(p)
    try:
        conn.executescript(_SCHEMA)
        conn.executemany(
            "INSERT OR IGNORE INTO accounts (code, name, category)"
            " VALUES (?, ?, ?)",
            STANDARD_ACCOUNTS,
        )
        conn.commit()
    finally:
        conn.close()
    return p
