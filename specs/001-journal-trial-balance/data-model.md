# Data Model: 仕訳記録と残高試算表

**Feature**: specs/001-journal-trial-balance | **Date**: 2026-09-07

## 概要

SQLite 単一ファイル `kaikei.db`。3 テーブル構成。金額はすべて INTEGER
(円・正)、日付は ISO 8601 テキスト(YYYY-MM-DD)。

## エンティティ

### accounts(勘定科目)

| 項目 | 型 | 制約 |
|------|----|------|
| code | TEXT | PRIMARY KEY(例: `'101'`) |
| name | TEXT | NOT NULL, UNIQUE(例: `'現金'`) |
| category | TEXT | NOT NULL, CHECK IN ('資産','負債','純資産','収益','費用') |

- 標準 10 科目は DB 初期化時に冪等に投入(`INSERT OR IGNORE`):

| code | name | category | 発生側(導出) |
|------|------|----------|----------------|
| 101 | 現金 | 資産 | 借方 |
| 102 | 普通預金 | 資産 | 借方 |
| 201 | 売掛金 | 資産 | 借方 |
| 202 | 買掛金 | 負債 | 貸方 |
| 203 | 借入金 | 負債 | 貸方 |
| 301 | 資本金 | 純資産 | 貸方 |
| 401 | 売上高 | 収益 | 貸方 |
| 402 | 仕入高 | 費用 | 借方 |
| 501 | 給料 | 費用 | 借方 |
| 502 | 通信費 | 費用 | 借方 |

- **導出関数** `normal_side(category)`: 資産・費用 → `'debit'`、
  負債・純資産・収益 → `'credit'`。発生側は保存しない(research D4)。

### entries(仕訳)

| 項目 | 型 | 制約 |
|------|----|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT(一覧・元帳の安定ソートに使用) |
| date | TEXT | NOT NULL, ISO 8601(YYYY-MM-DD) |
| description | TEXT | NOT NULL(摘要) |
| reversed_entry_id | INTEGER | NULL 許可, UNIQUE, REFERENCES entries(id) |

- 取消仕訳は `reversed_entry_id` に取消元を設定。UNIQUE 制約により
  同一仕訳への 2 件目の取消(FR-008)は DB レベルでも拒否される。
- 取消仕訳の日付は取消実行日を既定値とし利用者が指定可能(spec Q1)。

### lines(明細行)

| 項目 | 型 | 制約 |
|------|----|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| entry_id | INTEGER | NOT NULL, REFERENCES entries(id) |
| side | TEXT | NOT NULL, CHECK IN ('debit','credit') |
| account_code | TEXT | NOT NULL, REFERENCES accounts(code) |
| amount | INTEGER | NOT NULL, CHECK (amount > 0 AND amount <= 9223372036854775807) |

- 各仕訳は `side='debit'` の行 1 件以上と `side='credit'` の行 1 件以上を持つ
  (FR-001)。これはコードレベルの検証で保証(research D2)。

## 不変条件(Invariants)

1. **貸借一致**(憲法原則 I / FR-002): 仕訳ごとに
   `SUM(debit amounts) == SUM(credit amounts)`。
   `journal.add_entry()` がトランザクション内で検証し、不一致なら
   commit 前に中断する。差額(絶対値)を例外メッセージに含める。
   入力エラー時は仕訳全体(全明細行)が保存されず、一部の明細だけが
   残ることはない。
2. **金額の整合**(原則 II / FR-003): `amount` は常に正の整数。
   CHECK 制約 + 入力検査の二重防御。入力上限は 1 明細あたり
   9,223,372,036,854,775,807 円(spec チェックリスト review 案 B)。
   合計・繰越高・残高の集計には上限を適用しない(Python の多倍長 int で
   集計し、集計値を DB に再保存しない)。
3. **二重取消の禁止**(FR-008): `reversed_entry_id` の UNIQUE 制約。
4. **削除の禁止**(FR-007): 仕訳・明細に対する DELETE 文をコードベースで
   発行しない。

## ライフサイクル・状態遷移

```text
entry: registered ──(逆仕訳作成)──> reversed(取消済み)
                                    │ 逆仕訳自体も registered として存在し、
                                    │ さらに取消可能(spec Q2)
reversed への再取消: 拒否(FR-008)
```

## 検証ルール一覧(実装時にテスト化)

| ルール | 場所 |
|--------|------|
| 借方行 0 行 / 貸方行 0 行の拒否 | journal.add_entry |
| 貸借不一致の拒否 + 差額表示 | journal.add_entry |
| amount ≤ 0 / 非整数の拒否 | CLI 入力検査 + CHECK 制約 |
| amount が 9,223,372,036,854,775,807 円超過の拒否(1 明細の入力金額のみ) | CLI 入力検査 + CHECK 制約 |
| 入力エラー時に仕訳全体が保存されない(部分保存なし) | journal.add_entry(トランザクション) |
| 合計・繰越高・残高が入力上限を超えても集計が正確(Python 多倍長 int) | reports.trial_balance / reports.ledger |
| 未定義科目の拒否 | journal.add_entry(FK) |
| 二重取消の拒否 | UNIQUE(reversed_entry_id) |
| 存在しない取消元の拒否 | journal.reverse_entry |
| 開始日 > 終了日の拒否 | reports.trial_balance / reports.ledger |
| 存在しない日付(例: 2026-02-30)の拒否 | CLI 入力検査 |
| 摘要が空文字・空白のみの拒否 | journal.add_entry |
| 取消実行日の既定値は日本時間(Asia/Tokyo)の当日 | journal.reverse_entry |
| 逆仕訳の既定摘要「仕訳 #<取消元番号> の取消」 | journal.reverse_entry |
