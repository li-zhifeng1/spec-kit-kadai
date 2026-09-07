"""quickstart.md のエンドツーエンド検証(T029/T031)。

一時 DB で CLI を subprocess 実行し、quickstart.md のシナリオ 1〜8 を検証する。
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).parent
env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}

with tempfile.TemporaryDirectory() as td:
    env["KAIKEI_DB"] = str(pathlib.Path(td) / "kaikei-verify.db")

    def run(*args, expect=0):
        proc = subprocess.run(
            [sys.executable, "-m", "kaikei", *args],
            capture_output=True, text=True, encoding="utf-8", env=env,
        )
        assert proc.returncode == expect, (
            f"{args}: expected exit {expect}, got {proc.returncode}\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
        return proc

    # 1. account list
    proc = run("account", "list")
    assert "現金" in proc.stdout and "資産" in proc.stdout
    print("1. account list OK")

    # 2. entry add x3
    run("entry", "add", "--date", "2026-09-01", "--description", "資本金入金",
        "--debit", "現金:500000", "--credit", "資本金:500000")
    run("entry", "add", "--date", "2026-09-05", "--description", "売上",
        "--debit", "現金:100000", "--credit", "売上高:100000")
    run("entry", "add", "--date", "2026-09-10", "--description", "通信費支払",
        "--debit", "通信費:5000", "--credit", "現金:5000")
    print("2. entry add x3 OK")

    # 3. unbalanced rejected with diff, nothing saved
    proc = run("entry", "add", "--date", "2026-09-11", "--description", "誤り",
               "--debit", "現金:100000", "--credit", "売上高:98000", expect=1)
    assert "差額: 2,000" in proc.stderr
    print("3. unbalanced rejection OK (差額: 2,000 円)")

    # 4. entry list (table + json)
    proc = run("entry", "list")
    assert "資本金入金" in proc.stdout
    entries = json.loads(run("entry", "list", "--json").stdout)["entries"]
    assert len(entries) == 3
    print("4. entry list OK (table + JSON)")

    # 5. reverse 3, twice rejected
    payload = json.loads(run("entry", "reverse", "3", "--json").stdout)
    assert payload["reversed_entry_id"] == 3
    assert payload["description"] == "仕訳 #3 の取消"
    proc = run("entry", "reverse", "3", expect=1)
    assert "取消済み" in proc.stderr
    print("5. reverse + double-cancel rejection OK")

    # 6. trial-balance
    proc = run("trial-balance", "--start", "2026-09-01", "--end", "2026-09-30")
    assert "合計" in proc.stdout
    tb = json.loads(run("trial-balance", "--start", "2026-09-01",
                        "--end", "2026-09-30", "--json").stdout)
    assert len(tb["rows"]) == 10
    assert tb["totals"]["debit_total"] == tb["totals"]["credit_total"]
    assert tb["rows"][0]["debit_balance"] == 600_000  # 500,000+100,000-5,000+取消5,000
    print("6. trial-balance OK (貸借一致:", tb["totals"]["debit_total"], ")")

    # 7. ledger with period
    proc = run("ledger", "現金", "--start", "2026-09-01", "--end", "2026-09-30")
    assert "総勘定元帳: 現金" in proc.stdout
    led = json.loads(run("ledger", "現金", "--start", "2026-09-01",
                         "--end", "2026-09-30", "--json").stdout)
    assert [e["balance"] for e in led["entries"]] == [500_000, 600_000, 605_000, 600_000]
    assert led["entries"][0]["balance_side"] == "debit"
    print("7. ledger OK (繰越高込み・balance_side)")

    # 8. all commands emit valid JSON
    for args in (("account", "list", "--json"), ("entry", "list", "--json"),
                 ("entry", "add", "--date", "2026-09-20", "--description", "給料支払",
                  "--debit", "給料:80000", "--credit", "現金:80000", "--json"),
                 ("trial-balance", "--start", "2026-09-01", "--end", "2026-09-30", "--json"),
                 ("ledger", "現金", "--json")):
        payload = json.loads(run(*args).stdout)
    print("8. all commands --json valid OK")

print("\nAll quickstart scenarios PASSED")
