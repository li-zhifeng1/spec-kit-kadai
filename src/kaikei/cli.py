"""Kaikei Lite CLI(argparse サブパーサ、contracts/cli.md に準拠)。"""

import argparse
import sys
from collections.abc import Sequence

from kaikei import accounts, db, journal, reports
from kaikei.output import emit_json, format_table

_EXIT_OK = 0
_EXIT_VALIDATION_ERROR = 1
_EXIT_USAGE_ERROR = 2


def _fmt_amount(n: int) -> str:
    return f"{n:,}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaikei", description="Kaikei Lite: 小規模事業者向け財務会計 CLI"
    )
    parser.add_argument("--db", help="DB ファイルパス(既定 kaikei.db)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_acct = sub.add_parser("account", help="勘定科目の操作")
    acct_sub = p_acct.add_subparsers(dest="account_command", required=True)
    p_list = acct_sub.add_parser("list", help="標準科目一覧")
    p_list.add_argument("--json", action="store_true")

    p_entry = sub.add_parser("entry", help="仕訳の操作")
    entry_sub = p_entry.add_subparsers(dest="entry_command", required=True)

    p_add = entry_sub.add_parser("add", help="仕訳を登録する")
    p_add.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_add.add_argument("--description", required=True, help="摘要")
    p_add.add_argument(
        "--debit", action="append", default=[], metavar="科目:金額",
        help="借方明細(繰り返し指定可)",
    )
    p_add.add_argument(
        "--credit", action="append", default=[], metavar="科目:金額",
        help="貸方明細(繰り返し指定可)",
    )
    p_add.add_argument("--json", action="store_true")

    p_el = entry_sub.add_parser("list", help="仕訳を一覧表示する")
    p_el.add_argument("--json", action="store_true")

    p_rev = entry_sub.add_parser("reverse", help="逆仕訳(取消仕訳)を作成する")
    p_rev.add_argument("entry_id", type=int)
    p_rev.add_argument("--date", default=None, help="取消日付(既定: 取消実行日)")
    p_rev.add_argument("--description", default=None, help="摘要")
    p_rev.add_argument("--json", action="store_true")

    p_tb = sub.add_parser("trial-balance", help="残高試算表を表示する")
    p_tb.add_argument("--start", required=True, help="開始日 YYYY-MM-DD")
    p_tb.add_argument("--end", required=True, help="終了日 YYYY-MM-DD")
    p_tb.add_argument("--json", action="store_true")

    p_led = sub.add_parser("ledger", help="総勘定元帳を表示する")
    p_led.add_argument("account", help="科目名")
    p_led.add_argument("--start", default=None, help="開始日 YYYY-MM-DD")
    p_led.add_argument("--end", default=None, help="終了日 YYYY-MM-DD")
    p_led.add_argument("--json", action="store_true")

    return parser


def _parse_lines(specs: list[str], side: str) -> list[tuple[str, int]]:
    lines: list[tuple[str, int]] = []
    for spec in specs:
        name, sep, amount_str = spec.rpartition(":")
        if not sep or not name or not amount_str:
            raise journal.ValidationError(
                f"{side}明細は 科目:金額 の形式で指定してください: {spec}"
            )
        try:
            amount = int(amount_str, 10)
        except ValueError:
            raise journal.ValidationError(
                f"{side}の金額は円単位の整数で指定してください: {amount_str!r}"
            ) from None
        lines.append((name, amount))
    return lines


def _cmd_account_list(args: argparse.Namespace) -> int:
    payload = {
        "accounts": [
            {
                "code": code,
                "name": name,
                "category": category,
                "normal_side": accounts.normal_side(category),
            }
            for code, name, category in accounts.STANDARD_ACCOUNTS
        ]
    }
    if args.json:
        emit_json(payload)
        return _EXIT_OK
    rows = [
        [a["code"], a["name"], a["category"], a["normal_side"]]
        for a in payload["accounts"]
    ]
    print(format_table(["コード", "科目名", "区分", "発生側"], rows))
    return _EXIT_OK


def _cmd_entry_add(args: argparse.Namespace) -> int:
    conn = db.get_connection(db.get_db_path(args.db))
    try:
        debit_lines = _parse_lines(args.debit, "借方")
        credit_lines = _parse_lines(args.credit, "貸方")
        entry_id = journal.add_entry(
            conn,
            date=args.date,
            description=args.description,
            debit_lines=debit_lines,
            credit_lines=credit_lines,
        )
        entries = journal.list_entries(conn)
        payload = next(e for e in entries if e["id"] == entry_id)
    finally:
        conn.close()
    if args.json:
        emit_json(payload)
        return _EXIT_OK
    rows = [
        ["日付", payload["date"]],
        ["摘要", payload["description"]],
        ["仕訳番号", str(payload["id"])],
    ]
    rows += [
        [
            "借方" if ln["side"] == "debit" else "貸方",
            f"{ln['account']} {_fmt_amount(ln['amount'])}",
        ]
        for ln in payload["lines"]
    ]
    print(format_table(["項目", "内容"], rows))
    return _EXIT_OK


def _cmd_entry_list(args: argparse.Namespace) -> int:
    conn = db.get_connection(db.get_db_path(args.db))
    try:
        payload = {"entries": journal.list_entries(conn)}
    finally:
        conn.close()
    if args.json:
        emit_json(payload)
        return _EXIT_OK
    rows = []
    for e in payload["entries"]:
        for i, ln in enumerate(e["lines"]):
            label = f"{e['date']} #{e['id']} {e['description']}" if i == 0 else ""
            rows.append(
                [
                    label,
                    "借方" if ln["side"] == "debit" else "貸方",
                    ln["account"],
                    _fmt_amount(ln["amount"]),
                ]
            )
        if e["reversed_entry_id"] is not None:
            rows.append(
                [f"  ↑ 取消元: 仕訳 #{e['reversed_entry_id']}", "", "", ""]
            )
        if e["reversed_by"] is not None:
            rows.append([f"  ↓ 取消仕訳: #{e['reversed_by']}", "", "", ""])
    print(format_table(["日付 #番号 摘要", "区分", "科目", "金額"], rows))
    return _EXIT_OK


def _cmd_entry_reverse(args: argparse.Namespace) -> int:
    conn = db.get_connection(db.get_db_path(args.db))
    try:
        new_id = journal.reverse_entry(
            conn, args.entry_id, date=args.date, description=args.description
        )
        entries = journal.list_entries(conn)
        payload = next(e for e in entries if e["id"] == new_id)
    finally:
        conn.close()
    if args.json:
        emit_json(payload)
        return _EXIT_OK
    rows = [
        ["日付", payload["date"]],
        ["摘要", payload["description"]],
        ["取消元", f"仕訳 #{payload['reversed_entry_id']}"],
    ]
    rows += [
        [
            "借方" if ln["side"] == "debit" else "貸方",
            f"{ln['account']} {_fmt_amount(ln['amount'])}",
        ]
        for ln in payload["lines"]
    ]
    print(format_table(["項目", "内容"], rows))
    return _EXIT_OK


def _cmd_trial_balance(args: argparse.Namespace) -> int:
    conn = db.get_connection(db.get_db_path(args.db))
    try:
        payload = reports.trial_balance(conn, args.start, args.end)
    finally:
        conn.close()
    if args.json:
        emit_json(payload)
        return _EXIT_OK
    rows = []
    for r in payload["rows"]:
        rows.append(
            [
                f"{r['code']} {r['name']}",
                _fmt_amount(r["debit_total"]),
                _fmt_amount(r["credit_total"]),
                _fmt_amount(r["debit_balance"]),
                _fmt_amount(r["credit_balance"]),
            ]
        )
    t = payload["totals"]
    rows.append(
        [
            "合計",
            _fmt_amount(t["debit_total"]),
            _fmt_amount(t["credit_total"]),
            _fmt_amount(t["debit_balance"]),
            _fmt_amount(t["credit_balance"]),
        ]
    )
    print(
        format_table(
            ["科目", "借方合計", "貸方合計", "借方残高", "貸方残高"], rows
        )
    )
    return _EXIT_OK


def _cmd_ledger(args: argparse.Namespace) -> int:
    conn = db.get_connection(db.get_db_path(args.db))
    try:
        payload = reports.ledger(
            conn, args.account, start=args.start, end=args.end
        )
    finally:
        conn.close()
    if args.json:
        emit_json(payload)
        return _EXIT_OK
    rows = []
    for e in payload["entries"]:
        balance_label = (
            f"{_fmt_amount(e['balance'])} (借方)"
            if e["balance_side"] == "debit"
            else f"{_fmt_amount(e['balance'])} (貸方)"
            if e["balance_side"] == "credit"
            else "残高 0(貸借区分なし)"
        )
        rows.append(
            [
                e["date"],
                e["description"],
                _fmt_amount(e["debit"]),
                _fmt_amount(e["credit"]),
                e["counterpart"],
                balance_label,
            ]
        )
    period = (
        f"期間: {payload['start']} 〜 {payload['end']}"
        if payload["start"] and payload["end"]
        else "期間: 全期間"
    )
    print(f"総勘定元帳: {payload['account']}({period})")
    print(
        format_table(
            ["日付", "摘要", "借方", "貸方", "相手科目", "累計残高"], rows
        )
    )
    return _EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "account": lambda a: _cmd_account_list(a),
        "trial-balance": _cmd_trial_balance,
        "ledger": _cmd_ledger,
    }
    try:
        if args.command == "account":
            return _cmd_account_list(args)
        if args.command == "entry":
            if args.entry_command == "add":
                return _cmd_entry_add(args)
            if args.entry_command == "list":
                return _cmd_entry_list(args)
            if args.entry_command == "reverse":
                return _cmd_entry_reverse(args)
            parser.error("不明な entry サブコマンド")
        if args.command in handlers:
            return handlers[args.command](args)
        parser.error("不明なサブコマンド")
    except journal.ValidationError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return _EXIT_VALIDATION_ERROR
    except reports.ValidationError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return _EXIT_VALIDATION_ERROR
    return _EXIT_OK
