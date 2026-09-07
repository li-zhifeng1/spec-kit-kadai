"""DB 初期化・標準科目シード・科目区分のテスト。"""

import sqlite3

import pytest

from kaikei import accounts, db


def test_initialize_creates_tables(db_path):
    db.initialize(db_path)
    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        conn.close()
    assert {"accounts", "entries", "lines"} <= tables


def test_initialize_is_idempotent(db_path):
    db.initialize(db_path)
    db.initialize(db_path)  # 2 回呼んでもエラーにならず、重複シードもしない


def test_seed_standard_accounts(db_path):
    db.initialize(db_path)
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT code, name, category FROM accounts").fetchall()
    finally:
        conn.close()
    assert len(rows) == 10
    by_name = {name: (code, category) for code, name, category in rows}
    expected = {
        "現金": ("101", "資産"),
        "普通預金": ("102", "資産"),
        "売掛金": ("201", "資産"),
        "買掛金": ("202", "負債"),
        "借入金": ("203", "負債"),
        "資本金": ("301", "純資産"),
        "売上高": ("401", "収益"),
        "仕入高": ("402", "費用"),
        "給料": ("501", "費用"),
        "通信費": ("502", "費用"),
    }
    for name, (code, category) in expected.items():
        assert by_name[name] == (code, category)


def test_seed_is_idempotent(db_path):
    db.initialize(db_path)
    conn = sqlite3.connect(db_path)
    try:
        count1 = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    finally:
        conn.close()
    db.initialize(db_path)
    conn = sqlite3.connect(db_path)
    try:
        count2 = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    finally:
        conn.close()
    assert count1 == count2 == 10


def test_lines_amount_must_be_positive(db_path):
    db.initialize(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO entries (id, date, description) VALUES (1, '2026-09-07', 'x')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO lines (entry_id, side, account_code, amount)"
                " VALUES (1, 'debit', '101', 0)"
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO lines (entry_id, side, account_code, amount)"
                " VALUES (1, 'debit', '101', -100)"
            )
    finally:
        conn.close()


def test_reversed_entry_id_is_unique(db_path):
    db.initialize(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO entries (id, date, description, reversed_entry_id)"
            " VALUES (2, '2026-09-07', 'cancel', 1)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO entries (id, date, description, reversed_entry_id)"
                " VALUES (3, '2026-09-07', 'cancel twice', 1)"
            )
    finally:
        conn.close()


def test_standard_accounts_constant():
    assert len(accounts.STANDARD_ACCOUNTS) == 10


def test_normal_side_debit_categories():
    assert accounts.normal_side("資産") == "debit"
    assert accounts.normal_side("費用") == "debit"


def test_normal_side_credit_categories():
    assert accounts.normal_side("負債") == "credit"
    assert accounts.normal_side("純資産") == "credit"
    assert accounts.normal_side("収益") == "credit"


def test_normal_side_rejects_unknown_category():
    with pytest.raises(ValueError):
        accounts.normal_side("不明")
