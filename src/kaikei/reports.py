"""残高試算表・総勘定元帳の集計。

集計はすべて Python の多倍長整数(int)で行う(research D1)。
SQLite の SUM は合計が 64bit を超えるとオーバーフローするため使用しない。
"""

import datetime
import sqlite3

from kaikei.accounts import STANDARD_ACCOUNTS


class ValidationError(Exception):
    """集計パラメータの検証エラー。"""


def _validate_period(
    start: str, end: str
) -> tuple[datetime.date, datetime.date]:
    try:
        s = datetime.date.fromisoformat(start)
    except (TypeError, ValueError):
        raise ValidationError(
            f"開始日は YYYY-MM-DD 形式の実在する日付で指定してください: {start!r}"
        ) from None
    try:
        e = datetime.date.fromisoformat(end)
    except (TypeError, ValueError):
        raise ValidationError(
            f"終了日は YYYY-MM-DD 形式の実在する日付で指定してください: {end!r}"
        ) from None
    if s > e:
        raise ValidationError(
            f"開始日({start})が終了日({end})より後です"
        )
    return s, e


def _acc(conn: sqlite3.Connection, account_code: str, start: str, end: str,
         until_inclusive_end: bool = True) -> dict[str, int]:
    """科目ごとの期間内発生額と繰越高を出す(research D5)。

    - within: [start, end] の発生額(借方/貸方)
    - carried: start より前の累計(借方/貸方)
    集計は SQL SUM を使わず、行をフェッチして Python の int で合計する。
    """
    within_debit = within_credit = 0
    for amount, side in conn.execute(
        "SELECT amount, side FROM lines"
        " WHERE account_code = ? AND entry_id IN"
        " (SELECT id FROM entries WHERE date >= ? AND date <= ?)",
        (account_code, start, end),
    ):
        if side == "debit":
            within_debit += amount
        else:
            within_credit += amount
    carried_debit = carried_credit = 0
    for amount, side in conn.execute(
        "SELECT amount, side FROM lines"
        " WHERE account_code = ? AND entry_id IN"
        " (SELECT id FROM entries WHERE date < ?)",
        (account_code, start),
    ):
        if side == "debit":
            carried_debit += amount
        else:
            carried_credit += amount
    return {
        "within_debit": within_debit,
        "within_credit": within_credit,
        "carried_debit": carried_debit,
        "carried_credit": carried_credit,
    }


def trial_balance(
    conn: sqlite3.Connection, start: str, end: str
) -> dict:
    """残高試算表を返す(FR-009/FR-010)。

    - 借方合計・貸方合計の列は期間内の仕訳のみ
    - 残高列は開始日以前の繰越高を含む
    - 残高は借方と貸方の差額に応じて発生している側に正の金額
    - 残高 0 は借方残高・貸方残高ともに 0
    """
    _validate_period(start, end)
    rows = []
    total_debit_total = total_credit_total = 0
    total_debit_balance = total_credit_balance = 0
    for code, name, _category in STANDARD_ACCOUNTS:
        acc = _acc(conn, code, start, end)
        debit_total = acc["within_debit"]
        credit_total = acc["within_credit"]
        net = (acc["carried_debit"] + debit_total) - (
            acc["carried_credit"] + credit_total
        )
        if net > 0:
            debit_balance, credit_balance = net, 0
        elif net < 0:
            debit_balance, credit_balance = 0, -net
        else:
            debit_balance, credit_balance = 0, 0
        total_debit_total += debit_total
        total_credit_total += credit_total
        total_debit_balance += debit_balance
        total_credit_balance += credit_balance
        rows.append(
            {
                "code": code,
                "name": name,
                "debit_total": debit_total,
                "credit_total": credit_total,
                "debit_balance": debit_balance,
                "credit_balance": credit_balance,
            }
        )
    return {
        "start": start,
        "end": end,
        "rows": rows,
        "totals": {
            "debit_total": total_debit_total,
            "credit_total": total_credit_total,
            "debit_balance": total_debit_balance,
            "credit_balance": total_credit_balance,
        },
    }


def ledger(
    conn: sqlite3.Connection,
    account_name: str,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """総勘定元帳を返す(FR-011)。

    - 期間指定時は両端を含み、開始日以前の累計を繰越高として反映
    - 期間未指定時は全期間
    - 各明細に相手科目(複数はカンマ連結)と累計残高(借方/貸方の別)を付す
    - 残高 0 の明細は balance=0, balance_side=None
    """
    if start is not None or end is not None:
        if start is None or end is None:
            raise ValidationError(
                "開始日と終了日は両方指定するか、両方省略してください"
            )
        _validate_period(start, end)

    row = conn.execute(
        "SELECT code FROM accounts WHERE name = ?", (account_name,)
    ).fetchone()
    if row is None:
        raise ValidationError(f"標準科目に存在しません: {account_name}")
    account_code = row[0]

    # 明細を仕訳単位でフェッチ(日付順・同日は登録順)
    if start is not None and end is not None:
        entries = conn.execute(
            "SELECT id, date, description FROM entries"
            " WHERE date >= ? AND date <= ? ORDER BY date, id",
            (start, end),
        ).fetchall()
    else:
        entries = conn.execute(
            "SELECT id, date, description FROM entries ORDER BY date, id"
        ).fetchall()

    # 開始日以前の繰越高(Python int で集計)
    carried = 0
    if start is not None:
        for amount, side in conn.execute(
            "SELECT amount, side FROM lines"
            " WHERE account_code = ? AND entry_id IN"
            " (SELECT id FROM entries WHERE date < ?)",
            (account_code, start),
        ):
            carried += amount if side == "debit" else -amount

    name_by_code = dict(
        conn.execute("SELECT code, name FROM accounts").fetchall()
    )
    out_entries: list[dict] = []
    balance = carried
    for entry_id, date, description in entries:
        debit = credit = 0
        counterparts: list[str] = []
        for side, code, amount in conn.execute(
            "SELECT side, account_code, amount FROM lines"
            " WHERE entry_id = ? ORDER BY id",
            (entry_id,),
        ):
            if code == account_code:
                if side == "debit":
                    debit += amount
                else:
                    credit += amount
            else:
                cp_name = name_by_code[code]
                if cp_name not in counterparts:
                    counterparts.append(cp_name)
        if debit == 0 and credit == 0:
            continue  # 指定科目が登場しない仕訳
        balance += debit - credit
        if balance > 0:
            balance_side: str | None = "debit"
        elif balance < 0:
            balance_side = "credit"
        else:
            balance_side = None
        out_entries.append(
            {
                "date": date,
                "description": description,
                "debit": debit,
                "credit": credit,
                "counterpart": ",".join(counterparts),
                "balance": abs(balance),
                "balance_side": balance_side,
            }
        )
    return {
        "account": account_name,
        "start": start,
        "end": end,
        "entries": out_entries,
    }
