"""集計ロジック(reports)のテスト: US3 試算表・US4 元帳。"""

import pytest

from kaikei import db, reports, journal


@pytest.fixture
def conn(db_path):
    db.initialize(db_path)
    c = db.get_connection(db_path)
    yield c
    c.close()


def seed(conn):
    journal.add_entry(conn, "2026-08-20", "開業資金", [("現金", 100_000)], [("資本金", 100_000)])
    journal.add_entry(conn, "2026-09-01", "売上", [("現金", 50_000)], [("売上高", 50_000)])
    journal.add_entry(conn, "2026-09-15", "仕入", [("仕入高", 20_000)], [("現金", 20_000)])
    journal.add_entry(conn, "2026-10-01", "翌月売上", [("売掛金", 30_000)], [("売上高", 30_000)])


# --- US3: 残高試算表 ---------------------------------------------------------

def test_trial_balance_shows_all_accounts(conn):
    seed(conn)
    tb = reports.trial_balance(conn, "2026-09-01", "2026-09-30")
    names = [r["name"] for r in tb["rows"]]
    assert names == ["現金", "普通預金", "売掛金", "買掛金", "借入金",
                     "資本金", "売上高", "仕入高", "給料", "通信費"]


def test_trial_balance_debit_credit_totals_within_period(conn):
    seed(conn)
    tb = reports.trial_balance(conn, "2026-09-01", "2026-09-30")
    cash = tb["rows"][0]
    assert cash["debit_total"] == 50_000
    assert cash["credit_total"] == 20_000
    sales = tb["rows"][6]
    assert sales["credit_total"] == 50_000


def test_trial_balance_totals_balance(conn):
    seed(conn)
    tb = reports.trial_balance(conn, "2026-09-01", "2026-09-30")
    t = tb["totals"]
    assert t["debit_total"] == t["credit_total"]
    assert t["debit_total"] == 70_000  # 50,000 + 20,000


def test_trial_balance_carries_forward_prior_period(conn):
    seed(conn)
    tb = reports.trial_balance(conn, "2026-09-01", "2026-09-30")
    cash = tb["rows"][0]
    # 借方合計(期間内)は 50,000、残高は繰越高 100,000 を含む 130,000
    assert cash["debit_total"] == 50_000
    assert cash["debit_balance"] == 130_000
    assert cash["credit_balance"] == 0
    # 終了日より後の仕訳は反映されない
    receivable = tb["rows"][2]
    assert receivable["debit_total"] == 0
    assert receivable["debit_balance"] == 0


def test_trial_balance_balance_follows_actual_amount(conn):
    """貸方超過の資産科目は貸方残高に正の金額で出る(US3 シナリオ 7)。"""
    journal.add_entry(conn, "2026-09-01", "仮払", [("売上高", 500)], [("現金", 500)])
    tb = reports.trial_balance(conn, "2026-09-01", "2026-09-30")
    cash = tb["rows"][0]
    assert cash["debit_balance"] == 0
    assert cash["credit_balance"] == 500
    sales = tb["rows"][6]
    assert sales["debit_balance"] == 500
    assert sales["credit_balance"] == 0


def test_trial_balance_zero_balance_is_zero_on_both_sides(conn):
    journal.add_entry(conn, "2026-09-01", "打消", [("現金", 300)], [("売上高", 300)])
    journal.add_entry(conn, "2026-09-02", "逆", [("売上高", 300)], [("現金", 300)])
    tb = reports.trial_balance(conn, "2026-09-01", "2026-09-30")
    cash = tb["rows"][0]
    assert cash["debit_balance"] == 0
    assert cash["credit_balance"] == 0


def test_trial_balance_empty_period(conn):
    tb = reports.trial_balance(conn, "2026-09-01", "2026-09-30")
    assert all(
        r["debit_total"] == 0 and r["credit_total"] == 0
        for r in tb["rows"]
    )
    assert tb["totals"]["debit_total"] == 0
    assert tb["totals"]["credit_total"] == 0


def test_trial_balance_rejects_invalid_date(conn):
    with pytest.raises(reports.ValidationError):
        reports.trial_balance(conn, "2026-02-30", "2026-09-30")


def test_trial_balance_rejects_start_after_end(conn):
    with pytest.raises(reports.ValidationError):
        reports.trial_balance(conn, "2026-09-30", "2026-09-01")


def test_trial_balance_boundaries_inclusive(conn):
    seed(conn)
    # 2026-09-01 と 2026-09-30 の両端の仕訳を含む(9/1 のみで 9/15 は除外される)
    tb = reports.trial_balance(conn, "2026-09-01", "2026-09-01")
    cash = tb["rows"][0]
    assert cash["debit_total"] == 50_000
    tb2 = reports.trial_balance(conn, "2026-09-15", "2026-09-15")
    assert tb2["rows"][0]["credit_total"] == 20_000


# --- US4: 総勘定元帳 ---------------------------------------------------------

def test_ledger_date_order_and_counterpart(conn):
    seed(conn)
    led = reports.ledger(conn, "現金")
    assert [e["description"] for e in led["entries"]] == [
        "開業資金", "売上", "仕入",
    ]
    assert led["entries"][0]["counterpart"] == "資本金"
    assert led["entries"][2]["counterpart"] == "仕入高"


def test_ledger_running_balance_debit_side(conn):
    seed(conn)
    led = reports.ledger(conn, "現金")
    balances = [e["balance"] for e in led["entries"]]
    assert balances == [100_000, 150_000, 130_000]
    sides = [e["balance_side"] for e in led["entries"]]
    assert sides == ["debit", "debit", "debit"]


def test_ledger_credit_side_when_balance_turns(conn):
    journal.add_entry(conn, "2026-09-01", "売上", [("現金", 100)], [("売上高", 100)])
    journal.add_entry(conn, "2026-09-02", "戻し", [("売上高", 200)], [("現金", 200)])
    led = reports.ledger(conn, "現金")
    assert led["entries"][1]["balance"] == 100
    assert led["entries"][1]["balance_side"] == "credit"


def test_ledger_zero_balance_no_side(conn):
    journal.add_entry(conn, "2026-09-01", "a", [("現金", 100)], [("売上高", 100)])
    journal.add_entry(conn, "2026-09-02", "b", [("売上高", 100)], [("現金", 100)])
    led = reports.ledger(conn, "現金")
    last = led["entries"][1]
    assert last["balance"] == 0
    assert last["balance_side"] is None


def test_ledger_with_period_and_carryforward(conn):
    seed(conn)
    led = reports.ledger(conn, "現金", start="2026-09-01", end="2026-09-30")
    # 開始日以前の繰越高 100,000 が最初の明細の累計残高に反映される
    assert [e["balance"] for e in led["entries"]] == [150_000, 130_000]
    assert [e["description"] for e in led["entries"]] == ["売上", "仕入"]


def test_ledger_without_period_shows_all(conn):
    seed(conn)
    led = reports.ledger(conn, "現金")
    assert len(led["entries"]) == 3


def test_ledger_empty_is_empty_list(conn):
    led = reports.ledger(conn, "現金")
    assert led["entries"] == []


def test_ledger_rejects_invalid_period(conn):
    with pytest.raises(reports.ValidationError):
        reports.ledger(conn, "現金", start="2026-09-30", end="2026-09-01")
    with pytest.raises(reports.ValidationError):
        reports.ledger(conn, "現金", start="2026-13-01")


def test_ledger_multiple_counterparts_comma_joined(conn):
    journal.add_entry(
        conn, "2026-09-01", "複合",
        [("売上高", 300)],
        [("現金", 100), ("普通預金", 200)],
    )
    led = reports.ledger(conn, "売上高")
    assert led["entries"][0]["counterpart"] == "現金,普通預金"


# --- 性能(SC-003): 1,000 件の仕訳から試算表を 1 秒以内に生成 -----------------

def test_trial_balance_1000_entries_within_1_second(conn):
    for day in range(1, 501):
        journal.add_entry(
            conn, f"2026-09-{(day % 28) + 1:02d}", f"取引{day}",
            [("現金", 100 + day)], [("売上高", 100 + day)],
        )
        journal.add_entry(
            conn, f"2026-09-{(day % 28) + 1:02d}", f"支払{day}",
            [("仕入高", day)], [("現金", day)],
        )
    import time

    start = time.perf_counter()
    tb = reports.trial_balance(conn, "2026-09-01", "2026-09-30")
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"trial-balance took {elapsed:.3f}s"
    # 集計の正確性も確認(1,000 仕訳 × 平均発生額)
    cash = tb["rows"][0]
    expected_debit = sum(100 + d for d in range(1, 501))
    expected_credit = sum(range(1, 501))
    assert cash["debit_total"] == expected_debit
    assert cash["credit_total"] == expected_credit
    assert tb["totals"]["debit_total"] == tb["totals"]["credit_total"]
