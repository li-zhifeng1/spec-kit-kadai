"""CLI 全サブコマンドのテスト(表形式 / --json / 終了コード)。"""

import json

import pytest

from kaikei import db, journal
from kaikei.cli import main

UPPER = 9_223_372_036_854_775_807


@pytest.fixture
def conn(db_path, monkeypatch):
    db.initialize(db_path)
    monkeypatch.setenv("KAIKEI_DB", str(db_path))
    c = db.get_connection(db_path)
    yield c
    c.close()


def run(argv, capsys):
    code = main(argv)
    out = capsys.readouterr().out
    return code, out


def seed_entries(conn):
    journal.add_entry(conn, "2026-09-01", "資本金入金", [("現金", 500_000)], [("資本金", 500_000)])
    journal.add_entry(conn, "2026-09-05", "売上", [("現金", 100_000)], [("売上高", 100_000)])
    journal.add_entry(conn, "2026-09-10", "通信費支払", [("通信費", 5_000)], [("現金", 5_000)])


# --- account list ------------------------------------------------------------

def test_account_list_table(conn, capsys):
    code, out = run(["account", "list"], capsys)
    assert code == 0
    assert "現金" in out and "資産" in out


def test_account_list_json(conn, capsys):
    code, out = run(["account", "list", "--json"], capsys)
    assert code == 0
    payload = json.loads(out)
    assert len(payload["accounts"]) == 10
    assert payload["accounts"][0] == {
        "code": "101", "name": "現金", "category": "資産", "normal_side": "debit",
    }


# --- entry add ---------------------------------------------------------------

def test_entry_add_success_table(conn, capsys):
    code, out = run(
        ["entry", "add", "--date", "2026-09-01", "--description", "開業",
         "--debit", "現金:500000", "--credit", "資本金:500000"],
        capsys,
    )
    assert code == 0
    assert "現金" in out


def test_entry_add_json(conn, capsys):
    code, out = run(
        ["entry", "add", "--date", "2026-09-01", "--description", "開業",
         "--debit", "現金:500000", "--credit", "資本金:500000", "--json"],
        capsys,
    )
    assert code == 0
    payload = json.loads(out)
    assert payload["reversed_entry_id"] is None
    assert payload["lines"][0]["side"] == "debit"


def test_entry_add_unbalanced_error(conn, capsys):
    code, out_err, _ = _run_err(
        ["entry", "add", "--date", "2026-09-01", "--description", "誤り",
         "--debit", "現金:100000", "--credit", "売上高:98000"],
        capsys,
    )
    assert code == 1
    assert "差額" in out_err and "2,000" in out_err


def test_entry_add_over_limit_error(conn, capsys):
    code, out_err, _ = _run_err(
        ["entry", "add", "--date", "2026-09-01", "--description", "x",
         "--debit", f"現金:{UPPER + 1}", "--credit", f"資本金:{UPPER + 1}"],
        capsys,
    )
    assert code == 1
    assert "9,223,372,036,854,775,807" in out_err


def test_entry_add_invalid_date_error(conn, capsys):
    code, out_err, _ = _run_err(
        ["entry", "add", "--date", "2026-02-30", "--description", "x",
         "--debit", "現金:100", "--credit", "売上高:100"],
        capsys,
    )
    assert code == 1


def test_entry_add_usage_error(conn, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["entry", "add"])
    assert exc.value.code == 2


def test_entry_add_no_partial_save_on_error(conn, capsys):
    _run_err(
        ["entry", "add", "--date", "2026-09-01", "--description", "誤り",
         "--debit", "現金:100000", "--credit", "売上高:98000"],
        capsys,
    )
    count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    assert count == 0
    line_count = conn.execute("SELECT COUNT(*) FROM lines").fetchone()[0]
    assert line_count == 0


# --- entry list --------------------------------------------------------------

def test_entry_list_table(conn, capsys):
    seed_entries(conn)
    code, out = run(["entry", "list"], capsys)
    assert code == 0
    assert "資本金入金" in out


def test_entry_list_json(conn, capsys):
    seed_entries(conn)
    code, out = run(["entry", "list", "--json"], capsys)
    assert code == 0
    payload = json.loads(out)
    assert len(payload["entries"]) == 3
    dates = [e["date"] for e in payload["entries"]]
    assert dates == sorted(dates)


def test_entry_list_empty_is_ok(conn, capsys):
    code, out = run(["entry", "list", "--json"], capsys)
    assert code == 0
    assert json.loads(out)["entries"] == []


# --- entry reverse -----------------------------------------------------------

def test_entry_reverse_default_description(conn, capsys):
    seed_entries(conn)
    code, out = run(["entry", "reverse", "3", "--json"], capsys)
    assert code == 0
    payload = json.loads(out)
    assert payload["reversed_entry_id"] == 3
    assert payload["description"] == "仕訳 #3 の取消"
    assert payload["lines"][0]["side"] == "debit"  # 借貸反転


def test_entry_reverse_twice_error(conn, capsys):
    seed_entries(conn)
    run(["entry", "reverse", "3"], capsys)
    code, out_err, _ = _run_err(["entry", "reverse", "3"], capsys)
    assert code == 1
    assert "取消済み" in out_err


def test_entry_reverse_missing_error(conn, capsys):
    code, out_err, _ = _run_err(["entry", "reverse", "999"], capsys)
    assert code == 1


def test_entry_list_shows_reversal_link(conn, capsys):
    seed_entries(conn)
    run(["entry", "reverse", "1", "--json"], capsys)
    code, out = run(["entry", "list", "--json"], capsys)
    payload = json.loads(out)
    rev = [e for e in payload["entries"] if e["reversed_entry_id"] == 1][0]
    assert rev["description"] == "仕訳 #1 の取消"
    assert payload["entries"][0]["reversed_by"] == rev["id"]


# --- trial-balance -----------------------------------------------------------

def test_trial_balance_table(conn, capsys):
    seed_entries(conn)
    code, out = run(
        ["trial-balance", "--start", "2026-09-01", "--end", "2026-09-30"], capsys
    )
    assert code == 0
    assert "現金" in out and "合計" in out


def test_trial_balance_json(conn, capsys):
    seed_entries(conn)
    code, out = run(
        ["trial-balance", "--start", "2026-09-01", "--end", "2026-09-30", "--json"],
        capsys,
    )
    assert code == 0
    payload = json.loads(out)
    assert len(payload["rows"]) == 10
    totals = payload["totals"]
    assert totals["debit_total"] == totals["credit_total"] == 605_000
    cash = payload["rows"][0]
    assert cash["debit_balance"] == 595_000


def test_trial_balance_period_error(conn, capsys):
    code, out_err, _ = _run_err(
        ["trial-balance", "--start", "2026-09-30", "--end", "2026-09-01"], capsys
    )
    assert code == 1


# --- ledger ------------------------------------------------------------------

def test_ledger_table(conn, capsys):
    seed_entries(conn)
    code, out = run(["ledger", "現金"], capsys)
    assert code == 0
    assert "現金" in out
    assert "資本金" in out  # 相手科目


def test_ledger_json(conn, capsys):
    seed_entries(conn)
    code, out = run(["ledger", "現金", "--json"], capsys)
    assert code == 0
    payload = json.loads(out)
    balances = [e["balance"] for e in payload["entries"]]
    assert balances == [500_000, 600_000, 595_000]
    assert payload["entries"][0]["balance_side"] == "debit"


def test_ledger_with_period(conn, capsys):
    seed_entries(conn)
    code, out = run(
        ["ledger", "現金", "--start", "2026-09-05", "--end", "2026-09-30", "--json"],
        capsys,
    )
    assert code == 0
    payload = json.loads(out)
    # 繰越高 500,000 が反映される
    assert payload["entries"][0]["balance"] == 600_000


def test_ledger_period_error(conn, capsys):
    code, out_err, _ = _run_err(
        ["ledger", "現金", "--start", "2026-09-30", "--end", "2026-09-01"], capsys
    )
    assert code == 1


def _run_err(argv, capsys):
    """main を実行し (終了コード, stdout+stderr) を返す。"""
    try:
        code = main(argv)
    except SystemExit as e:
        code = e.code
    captured = capsys.readouterr()
    return code, captured.out + captured.err, captured.err
