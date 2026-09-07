"""仕訳ロジック(journal)のテスト: US1 登録・US2 一覧・US5 逆仕訳。"""

import sqlite3

import pytest

from kaikei import db, journal

UPPER = 9_223_372_036_854_775_807


@pytest.fixture
def conn(db_path):
    db.initialize(db_path)
    c = db.get_connection(db_path)
    yield c
    c.close()


# --- US1: 仕訳登録 -----------------------------------------------------------

def test_add_entry_simple(conn):
    entry_id = journal.add_entry(
        conn,
        date="2026-09-01",
        description="資本金入金",
        debit_lines=[("現金", 500_000)],
        credit_lines=[("資本金", 500_000)],
    )
    assert isinstance(entry_id, int)
    rows = conn.execute(
        "SELECT side, account_code, amount FROM lines WHERE entry_id = ?"
        " ORDER BY id",
        (entry_id,),
    ).fetchall()
    assert ("debit", "101", 500_000) in rows
    assert ("credit", "301", 500_000) in rows


def test_add_entry_multi_lines(conn):
    entry_id = journal.add_entry(
        conn,
        date="2026-09-02",
        description="複合取引",
        debit_lines=[("現金", 30_000), ("普通預金", 20_000)],
        credit_lines=[("売上高", 50_000)],
    )
    count = conn.execute(
        "SELECT COUNT(*) FROM lines WHERE entry_id = ?", (entry_id,)
    ).fetchone()[0]
    assert count == 3


def test_add_entry_rejects_unbalanced(conn):
    with pytest.raises(journal.ValidationError) as exc:
        journal.add_entry(
            conn,
            date="2026-09-03",
            description="誤り",
            debit_lines=[("現金", 100_000)],
            credit_lines=[("売上高", 98_000)],
        )
    assert "2,000" in str(exc.value)
    count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    assert count == 0  # 仕訳全体が保存されない


def test_add_entry_rejects_missing_debit_lines(conn):
    with pytest.raises(journal.ValidationError):
        journal.add_entry(
            conn, date="2026-09-03", description="x",
            debit_lines=[], credit_lines=[("売上高", 100)],
        )


def test_add_entry_rejects_missing_credit_lines(conn):
    with pytest.raises(journal.ValidationError):
        journal.add_entry(
            conn, date="2026-09-03", description="x",
            debit_lines=[("現金", 100)], credit_lines=[],
        )


@pytest.mark.parametrize("amount", [0, -100])
def test_add_entry_rejects_non_positive_amount(conn, amount):
    with pytest.raises(journal.ValidationError):
        journal.add_entry(
            conn, date="2026-09-03", description="x",
            debit_lines=[("現金", amount)], credit_lines=[("売上高", amount)],
        )


def test_add_entry_rejects_float_amount(conn):
    with pytest.raises(journal.ValidationError):
        journal.add_entry(
            conn, date="2026-09-03", description="x",
            debit_lines=[("現金", 100.5)], credit_lines=[("売上高", 100.5)],
        )


def test_add_entry_rejects_unknown_account(conn):
    with pytest.raises(journal.ValidationError):
        journal.add_entry(
            conn, date="2026-09-03", description="x",
            debit_lines=[("存在しない科目", 100)],
            credit_lines=[("売上高", 100)],
        )


@pytest.mark.parametrize("description", ["", "   "])
def test_add_entry_rejects_blank_description(conn, description):
    with pytest.raises(journal.ValidationError):
        journal.add_entry(
            conn, date="2026-09-03", description=description,
            debit_lines=[("現金", 100)], credit_lines=[("売上高", 100)],
        )


def test_add_entry_accepts_upper_limit_amount(conn):
    entry_id = journal.add_entry(
        conn,
        date="2026-09-04",
        description="上限値",
        debit_lines=[("現金", UPPER)],
        credit_lines=[("資本金", UPPER)],
    )
    amount = conn.execute(
        "SELECT amount FROM lines WHERE entry_id = ? AND side = 'debit'",
        (entry_id,),
    ).fetchone()[0]
    assert amount == UPPER


def test_add_entry_rejects_over_limit_amount(conn):
    with pytest.raises(journal.ValidationError):
        journal.add_entry(
            conn, date="2026-09-04", description="x",
            debit_lines=[("現金", UPPER + 1)], credit_lines=[("資本金", UPPER + 1)],
        )
    count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    assert count == 0


def test_add_entry_sum_over_limit_is_allowed_and_correct(conn):
    """合法明細のみで合計が上限を超える仕訳(US1 シナリオ 7)。"""
    per_line = 3_074_457_345_618_258_669
    debits = [("普通預金", per_line)] * 3
    credits = [("資本金", per_line)] * 3
    entry_id = journal.add_entry(
        conn, date="2026-09-05", description="合計上限超",
        debit_lines=debits, credit_lines=credits,
    )
    # 集計は SQL SUM ではなく Python の多倍長 int で行う(research D1:
    # SQLite の SUM は 64bit オーバーフローするため集計に使わない)
    amounts = [
        row[0]
        for row in conn.execute(
            "SELECT amount FROM lines WHERE entry_id = ? AND side = 'debit'",
            (entry_id,),
        )
    ]
    assert sum(amounts) == per_line * 3  # 64bit を超えるが正確


# --- US2: 仕訳一覧 -----------------------------------------------------------

def test_list_entries_empty(conn):
    assert journal.list_entries(conn) == []


def test_list_entries_date_order(conn):
    journal.add_entry(conn, "2026-09-05", "後", [("現金", 100)], [("売上高", 100)])
    journal.add_entry(conn, "2026-09-01", "先", [("現金", 200)], [("売上高", 200)])
    entries = journal.list_entries(conn)
    dates = [e["date"] for e in entries]
    assert dates == sorted(dates)
    assert entries[0]["description"] == "先"


def test_list_entries_same_date_keeps_registration_order(conn):
    journal.add_entry(conn, "2026-09-01", "1件目", [("現金", 100)], [("売上高", 100)])
    journal.add_entry(conn, "2026-09-01", "2件目", [("現金", 200)], [("売上高", 200)])
    entries = journal.list_entries(conn)
    assert [e["description"] for e in entries] == ["1件目", "2件目"]


def test_list_entries_shape(conn):
    journal.add_entry(conn, "2026-09-01", "開業", [("現金", 500)], [("資本金", 500)])
    entries = journal.list_entries(conn)
    e = entries[0]
    assert e["id"] == 1
    assert e["reversed_entry_id"] is None
    assert e["reversed_by"] is None
    assert e["lines"] == [
        {"side": "debit", "account": "現金", "amount": 500},
        {"side": "credit", "account": "資本金", "amount": 500},
    ]


# --- US5: 逆仕訳 -------------------------------------------------------------

def test_reverse_entry_creates_cancel_entry(conn):
    original_id = journal.add_entry(
        conn, "2026-09-01", "売上", [("現金", 100_000)], [("売上高", 100_000)]
    )
    rev_id = journal.reverse_entry(conn, original_id)
    rev = conn.execute(
        "SELECT date, description, reversed_entry_id FROM entries WHERE id = ?",
        (rev_id,),
    ).fetchone()
    assert rev[2] == original_id
    assert rev[1] == f"仕訳 #{original_id} の取消"
    rev_lines = conn.execute(
        "SELECT side, account_code, amount FROM lines WHERE entry_id = ?",
        (rev_id,),
    ).fetchall()
    assert ("debit", "401", 100_000) in rev_lines  # 借貸が反転
    assert ("credit", "101", 100_000) in rev_lines
    # 元の仕訳は消えない
    orig = conn.execute(
        "SELECT COUNT(*) FROM entries WHERE id = ?", (original_id,)
    ).fetchone()[0]
    assert orig == 1


def test_reverse_entry_rejects_twice(conn):
    original_id = journal.add_entry(
        conn, "2026-09-01", "売上", [("現金", 100)], [("売上高", 100)]
    )
    journal.reverse_entry(conn, original_id)
    with pytest.raises(journal.ValidationError):
        journal.reverse_entry(conn, original_id)


def test_reverse_entry_rejects_missing_target(conn):
    with pytest.raises(journal.ValidationError):
        journal.reverse_entry(conn, 999)


def test_reverse_entry_can_cancel_a_reversal(conn):
    original_id = journal.add_entry(
        conn, "2026-09-01", "売上", [("現金", 100)], [("売上高", 100)]
    )
    rev_id = journal.reverse_entry(conn, original_id)
    rev_rev_id = journal.reverse_entry(conn, rev_id)  # 逆仕訳自体も取消可能
    rev_rev = conn.execute(
        "SELECT reversed_entry_id FROM entries WHERE id = ?", (rev_rev_id,)
    ).fetchone()[0]
    assert rev_rev == rev_id


def test_reverse_entry_with_explicit_date(conn):
    original_id = journal.add_entry(
        conn, "2026-09-01", "売上", [("現金", 100)], [("売上高", 100)]
    )
    rev_id = journal.reverse_entry(conn, original_id, date="2026-10-01")
    d = conn.execute(
        "SELECT date FROM entries WHERE id = ?", (rev_id,)
    ).fetchone()[0]
    assert d == "2026-10-01"
