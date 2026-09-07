# CLI Contract: Kaikei Lite

**Feature**: specs/001-journal-trial-balance | **Date**: 2026-09-07

コマンドラインインターフェースの契約。全コマンド共通:

- 既定出力は人が読める表形式(stdout)。`--json` 指定時は
  1 個の JSON オブジェクト(stdout, UTF-8)。
- 検証エラー(貸借不一致・未定義科目など)は stderr にメッセージを出し
  **終了コード 1**。コマンド書式の誤りは argparse による **終了コード 2**。
- 金額は 1 円以上 9,223,372,036,854,775,807 円以下の整数のみ
  (1 明細あたり。超過は終了コード 1 の明確なエラー)。
  合計・繰越高・残高の集計値にはこの上限を適用しない。
  科目は標準科目名で指定する。
- DB ファイルは環境変数 `KAIKEI_DB` で指定(既定 `kaikei.db`)。
  存在しない場合は初期化し標準 10 科目を投入する。

## 共通オプション

| オプション | 意味 |
|-----------|------|
| `--json` | JSON で出力 |
| `--db PATH` | DB ファイルパス(既定 `kaikei.db`) |

## `account list`

標準科目一覧を表示する。

```text
kaikei account list [--json]
```

JSON: `{"accounts": [{"code": "101", "name": "現金", "category": "資産", "normal_side": "debit"}, ...]}`

## `entry add`

仕訳を 1 件登録する。借方・貸方の明細はフラグの繰り返しで指定する。

```text
kaikei entry add --date YYYY-MM-DD --description TEXT \
  --debit ACCOUNT:AMOUNT [--debit ACCOUNT:AMOUNT ...] \
  --credit ACCOUNT:AMOUNT [--credit ACCOUNT:AMOUNT ...] [--json]
```

- 成功: 表形式は登録内容の確認、JSON は
  `{"id": 1, "date": "2026-09-07", "description": "...", "lines": [...], "reversed_entry_id": null}`
- 失敗(貸借不一致): `エラー: 借方合計と貸方合計が一致しません(差額: 2,000 円)`、終了コード 1
  (貸借のどちらが多いかの表示は必須としない)
- 失敗(未定義科目・0 以下の金額・金額が 9,223,372,036,854,775,807 円超過・
  明細 0 行・摘要が空文字/空白のみ・存在しない日付): それぞれ日本語の
  エラーメッセージ、終了コード 1。**入力エラー時は仕訳全体が保存されず、
  一部の明細だけが残ることはない**

## `entry list`

登録済みの全仕訳を日付順(同日は登録順)で一覧表示する。

```text
kaikei entry list [--json]
```

JSON: `{"entries": [{"id": 1, "date": "...", "description": "...", "reversed_entry_id": null, "lines": [{"side": "debit", "account": "現金", "amount": 100000}, ...], "reversed_by": null}, ...]}`

- 取消仕訳は取消元への参照(`reversed_entry_id`)を表示する(FR-007)。
- 0 件時: 空一覧(正常終了、終了コード 0)。

## `entry reverse`

既存仕訳の逆仕訳(取消仕訳)を作成する。

```text
kaikei entry reverse ENTRY_ID [--date YYYY-MM-DD] [--description TEXT] [--json]
```

- `--date` 省略時は取消実行日(日本時間(Asia/Tokyo)の当日)を既定値とする(spec Q1)。
- `--description` 省略時の摘要は「仕訳 #<取消元番号> の取消」とする。
- 成功: 取消元への参照を持つ新規仕訳が作成される。
  JSON: `entry add` と同形式 + `"reversed_entry_id": ENTRY_ID`
- 失敗(対象なし / すでに取消済み): 日本語エラーメッセージ、終了コード 1

## `trial-balance`

残高試算表を表示する。

```text
kaikei trial-balance --start YYYY-MM-DD --end YYYY-MM-DD [--json]
```

- 期間は両端を含む(spec Q3)。存在しない日付・開始日 > 終了日は終了コード 1。
- 借方合計・貸方合計の列は期間内仕訳のみ、残高列は開始日以前の繰越高込み(spec Q4)。
- 残高は借方と貸方の差額に応じて発生している側に正の金額で表示する
  (発生側と一致しない残高も実額の側に表示)。残高 0 は借方残高・貸方残高ともに 0。
- 全 10 科目を常に表示し、最後に合計行を付す(FR-009/FR-010)。
- JSON: `{"start": "...", "end": "...", "rows": [{"code": "101", "name": "現金", "debit_total": 100000, "credit_total": 0, "debit_balance": 100000, "credit_balance": 0}, ...], "totals": {"debit_total": 100000, "credit_total": 100000, "debit_balance": 100000, "credit_balance": 100000}}`

## `ledger`

総勘定元帳を表示する。

```text
kaikei ledger ACCOUNT [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--json]
```

- `--start` / `--end` は省略可(省略時は全期間)。指定時は両端を含み、
  開始日より前の仕訳の累計を繰越高として累計残高に反映する(spec Q12)。
  存在しない日付・開始日 > 終了日は終了コード 1。
- 指定科目の明細を日付順(同日は登録順)で表示。各行に相手科目と
  累計残高(借方・貸方の別を明示。残高 0 は「残高 0(貸借区分なし)」)を付す(FR-011)。
- 対象明細 0 件: 空一覧(正常終了)。
- JSON: `{"account": "現金", "start": null, "end": null, "entries": [{"date": "...", "description": "...", "debit": 100000, "credit": 0, "counterpart": "売上高", "balance": 100000, "balance_side": "debit"}, ...]}`

  - `balance_side`: 累計残高の発生側(`"debit"` / `"credit"` / 残高 0 の場合は `null`)

## 終了コード一覧

| コード | 意味 |
|--------|------|
| 0 | 成功(空一覧を含む) |
| 1 | 検証エラー(貸借不一致・未定義科目・二重取消・期間不正など) |
| 2 | コマンド書式の誤り(argparse) |
