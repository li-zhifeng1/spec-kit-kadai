"""教材の合格基準に沿った検証(専用 DB kaikei-textbook-verify.db を使用)。

既存の kaikei.db は一切変更しない。
"""

import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent
DB = ROOT / "kaikei-textbook-verify.db"
env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8",
       "KAIKEI_DB": str(DB)}

if DB.exists():
    DB.unlink()  # 検証用 DB を初期状態から作り直す


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


print("=== 6 仕訳の登録 ===")
entries = [
    ("2026-04-01", "資本金の払込", [("現金", 1_000_000)], [("資本金", 1_000_000)]),
    ("2026-04-02", "普通預金へ預入", [("普通預金", 500_000)], [("現金", 500_000)]),
    ("2026-04-05", "商品仕入", [("仕入高", 300_000)], [("現金", 300_000)]),
    ("2026-04-10", "商品売上", [("売掛金", 450_000)], [("売上高", 450_000)]),
    ("2026-04-25", "給料の支払", [("給料", 200_000)], [("普通預金", 200_000)]),
    ("2026-04-28", "通信費の支払", [("通信費", 12_000)], [("現金", 12_000)]),
]
for date, desc, debits, credits in entries:
    args: list[str] = ["entry", "add", "--date", date, "--description", desc]
    for name, amount in debits:
        args += ["--debit", f"{name}:{amount}"]
    for name, amount in credits:
        args += ["--credit", f"{name}:{amount}"]
    run(*args)
    print(f"  登録成功: {date} {desc}")

print("\n=== 貸借不一致仕訳の拒否確認 ===")
proc = run(
    "entry", "add", "--date", "2026-04-30", "--description", "不一致テスト",
    "--debit", "現金:300000", "--credit", "売上高:290000", expect=1,
)
assert "差額: 10,000" in proc.stderr, proc.stderr
print(f"  拒否メッセージ: {proc.stderr.strip()}")
# 保存されていないこと
listed = json.loads(run("entry", "list", "--json").stdout)["entries"]
assert len(listed) == 6, f"仕訳は 6 件のままのはず: {len(listed)} 件"
print("  保存確認: 仕訳は 6 件のまま(不一致データは保存されない)")

print("\n=== 2026-04-01〜04-30 の残高試算表 ===")
tb = json.loads(
    run("trial-balance", "--start", "2026-04-01", "--end", "2026-04-30", "--json").stdout
)
for r in tb["rows"]:
    print(f"  {r['code']} {r['name']:<6} 借方合計 {r['debit_total']:>9,} "
          f"貸方合計 {r['credit_total']:>9,} 借方残高 {r['debit_balance']:>9,} "
          f"貸方残高 {r['credit_balance']:>9,}")
print(f"  合計       借方合計 {tb['totals']['debit_total']:>9,} "
      f"貸方合計 {tb['totals']['credit_total']:>9,} 借方残高 {tb['totals']['debit_balance']:>9,} "
      f"貸方残高 {tb['totals']['credit_balance']:>9,}")

print("\n=== 合格基準の検証 ===")
checks = [
    ("借方合計 2,462,000", tb["totals"]["debit_total"] == 2_462_000),
    ("貸方合計 2,462,000", tb["totals"]["credit_total"] == 2_462_000),
    ("借方残高合計 1,450,000", tb["totals"]["debit_balance"] == 1_450_000),
    ("貸方残高合計 1,450,000", tb["totals"]["credit_balance"] == 1_450_000),
    ("現金の借方残高 188,000", tb["rows"][0]["debit_balance"] == 188_000),
]
all_ok = True
for label, ok in checks:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    all_ok = all_ok and ok

proc = run("ledger", "現金", "--start", "2026-04-01", "--end", "2026-04-30")
print("\n=== 現金の総勘定元帳(参考) ===")
print(proc.stdout)

print("結果:", "ALL PASS — 教材の合格基準をすべて満たします" if all_ok else "FAIL あり")
