"""仕訳の登録・一覧・逆仕訳。

貸借一致の検証はこのモジュールの ``add_entry`` / ``reverse_entry`` が
単一の保存経路(research D2)。トランザクション内で検証し、
不一致・入力エラー時は commit 前に中断するため、
一部の明細だけが保存されることはない。
"""

import datetime
import sqlite3
from collections.abc import Sequence

#: 1 明細の入力金額の上限(64bit 符号付き整数の最大値)
AMOUNT_UPPER_LIMIT = 9_223_372_036_854_775_807


class ValidationError(Exception):
    """仕訳の入力検証エラー。"""


def _validate_amount(amount: int, where: str) -> None:
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise ValidationError(
            f"{where}の金額は円単位の整数で指定してください: {amount!r}"
        )
    if amount <= 0:
        raise ValidationError(f"{where}の金額は 1 円以上にしてください: {amount}")
    if amount > AMOUNT_UPPER_LIMIT:
        raise ValidationError(
            f"{where}の金額は {AMOUNT_UPPER_LIMIT:,} 円以下にしてください: {amount:,}"
        )


def _resolve_account(conn: sqlite3.Connection, name: str) -> str:
    row = conn.execute(
        "SELECT code FROM accounts WHERE name = ?", (name,)
    ).fetchone()
    if row is None:
        raise ValidationError(f"標準科目に存在しません: {name}")
    return row[0]


def _validate_date(date: str) -> None:
    try:
        datetime.date.fromisoformat(date)
    except (TypeError, ValueError):
        raise ValidationError(
            f"日付は YYYY-MM-DD 形式の実在する日付で指定してください: {date!r}"
        )


def _insert_entry(
    conn: sqlite3.Connection,
    date: str,
    description: str,
    debit_lines: Sequence[tuple[str, int]],
    credit_lines: Sequence[tuple[str, int]],
    reversed_entry_id: int | None,
) -> int:
    """検証済みの仕訳をトランザクション内で保存し、id を返す。"""
    cur = conn.execute(
        "INSERT INTO entries (date, description, reversed_entry_id)"
        " VALUES (?, ?, ?)",
        (date, description, reversed_entry_id),
    )
    entry_id = cur.lastrowid
    for name, amount in debit_lines:
        code = _resolve_account(conn, name)
        conn.execute(
            "INSERT INTO lines (entry_id, side, account_code, amount)"
            " VALUES (?, 'debit', ?, ?)",
            (entry_id, code, amount),
        )
    for name, amount in credit_lines:
        code = _resolve_account(conn, name)
        conn.execute(
            "INSERT INTO lines (entry_id, side, account_code, amount)"
            " VALUES (?, 'credit', ?, ?)",
            (entry_id, code, amount),
        )
    return entry_id


def add_entry(
    conn: sqlite3.Connection,
    date: str,
    description: str,
    debit_lines: Sequence[tuple[str, int]],
    credit_lines: Sequence[tuple[str, int]],
) -> int:
    """貸借一致する仕訳を 1 件登録し、id を返す。

    不一致・入力エラー時は例外を送出し、何も保存しない。
    """
    _validate_date(date)
    if not description or not description.strip():
        raise ValidationError("摘要は必須です(空文字・空白のみは不可)")
    if not debit_lines:
        raise ValidationError("借方行が 1 行以上必要です")
    if not credit_lines:
        raise ValidationError("貸方行が 1 行以上必要です")
    for name, amount in debit_lines:
        _validate_amount(amount, f"借方({name})")
    for name, amount in credit_lines:
        _validate_amount(amount, f"貸方({name})")

    debit_total = sum(a for _, a in debit_lines)
    credit_total = sum(a for _, a in credit_lines)
    if debit_total != credit_total:
        diff = abs(debit_total - credit_total)
        raise ValidationError(
            f"借方合計と貸方合計が一致しません(差額: {diff:,} 円)"
        )

    try:
        entry_id = _insert_entry(
            conn, date, description, debit_lines, credit_lines, None
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return entry_id


def list_entries(conn: sqlite3.Connection) -> list[dict]:
    """全仕訳を日付順(同日は登録順)で返す。"""
    name_by_code = dict(
        conn.execute("SELECT code, name FROM accounts").fetchall()
    )
    reversed_by = dict(
        conn.execute(
            "SELECT reversed_entry_id, id FROM entries WHERE reversed_entry_id"
            " IS NOT NULL"
        ).fetchall()
    )
    entries: list[dict] = []
    for entry_id, date, description, reversed_entry_id in conn.execute(
        "SELECT id, date, description, reversed_entry_id FROM entries"
        " ORDER BY date, id"
    ):
        lines = [
            {"side": side, "account": name_by_code[code], "amount": amount}
            for side, code, amount in conn.execute(
                "SELECT side, account_code, amount FROM lines"
                " WHERE entry_id = ? ORDER BY id",
                (entry_id,),
            )
        ]
        entries.append(
            {
                "id": entry_id,
                "date": date,
                "description": description,
                "lines": lines,
                "reversed_entry_id": reversed_entry_id,
                "reversed_by": reversed_by.get(entry_id),
            }
        )
    return entries


def reverse_entry(
    conn: sqlite3.Connection,
    entry_id: int,
    date: str | None = None,
    description: str | None = None,
) -> int:
    """既存仕訳を打ち消す逆仕訳(取消仕訳)を作成し、id を返す。

    - 日付の既定値は日本時間(Asia/Tokyo)の当日(spec Q5)
    - 摘要の既定値は「仕訳 #<取消元番号> の取消」(spec Q6)
    """
    target = conn.execute(
        "SELECT date, description FROM entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if target is None:
        raise ValidationError(f"存在しない仕訳です: id={entry_id}")

    already = conn.execute(
        "SELECT id FROM entries WHERE reversed_entry_id = ?", (entry_id,)
    ).fetchone()
    if already is not None:
        raise ValidationError(
            f"仕訳 id={entry_id} はすでに取消済みです(取消仕訳: id={already[0]})"
        )

    if date is None:
        date = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=9))
        ).strftime("%Y-%m-%d")
    else:
        _validate_date(date)
    if description is None:
        description = f"仕訳 #{entry_id} の取消"

    debit_lines: list[tuple[str, int]] = []
    credit_lines: list[tuple[str, int]] = []
    name_by_code = dict(
        conn.execute("SELECT code, name FROM accounts").fetchall()
    )
    for side, code, amount in conn.execute(
        "SELECT side, account_code, amount FROM lines WHERE entry_id = ?"
        " ORDER BY id",
        (entry_id,),
    ):
        if side == "debit":
            credit_lines.append((name_by_code[code], amount))
        else:
            debit_lines.append((name_by_code[code], amount))

    try:
        new_id = _insert_entry(
            conn, date, description, debit_lines, credit_lines, entry_id
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValidationError(
            f"仕訳 id={entry_id} はすでに取消済みです"
        ) from None
    except Exception:
        conn.rollback()
        raise
    return new_id
