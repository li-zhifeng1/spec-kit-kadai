# Quickstart: 仕訳記録と残高試算表

**Feature**: specs/001-journal-trial-balance | **Date**: 2026-09-07

エンドツーエンドの検証手順。実装完了後、このシナリオがすべて通ることで
機能の動作を証明する。詳細なインターフェースは [contracts/cli.md](./contracts/cli.md)、
データ構造は [data-model.md](./data-model.md) を参照。

## 前提

- Python 3.11 がインストール済みであること
- リポジトリルートで作業(`src/` レイアウトのため `PYTHONPATH=src` を指定、
  または `pip install -e .` を想定 — tasks.md で確定)

## セットアップとテスト

```powershell
pip install pytest
pytest                # 全テストが緑であること
```

## 検証シナリオ

一時 DB を使うため環境変数でパスを指定する。

```powershell
$env:KAIKEI_DB = "$PWD\kaikei-verify.db"
```

### 1. 科目マスタの初期化

```powershell
python -m kaikei account list
```

→ 標準 10 科目(現金・普通預金・売掛金・買掛金・借入金・資本金・売上高・
仕入高・給料・通信費)が区分付きで表形式で表示される。

### 2. 仕訳の登録

```powershell
python -m kaikei entry add --date 2026-09-01 --description "資本金入金" `
  --debit 現金:500000 --credit 資本金:500000
python -m kaikei entry add --date 2026-09-05 --description "売上" `
  --debit 現金:100000 --credit 売上高:100000
python -m kaikei entry add --date 2026-09-10 --description "通信費支払" `
  --debit 通信費:5000 --credit 現金:5000
```

→ 各回、登録内容が表示され終了コード 0。

### 3. 貸借不一致の拒否

```powershell
python -m kaikei entry add --date 2026-09-11 --description "誤り" `
  --debit 現金:100000 --credit 売上高:98000; echo "exit=$LASTEXITCODE"
```

→ `差額: 2,000 円` を含むエラーが出て終了コード 1。
`entry list` にこの仕訳は現れない(保存されない)。

### 4. 一覧表示

```powershell
python -m kaikei entry list
python -m kaikei entry list --json
```

→ 3 件が日付順に表示され、`--json` では同じ内容が JSON で得られる。

### 5. 逆仕訳による訂正

```powershell
python -m kaikei entry reverse 3
```

→ 取消実行日付で、仕訳 3 を `reversed_entry_id` に持つ逆仕訳が作成される。
二度目の実行は「すでに取消済み」で終了コード 1。

### 6. 残高試算表

```powershell
python -m kaikei trial-balance --start 2026-09-01 --end 2026-09-30
```

→ 全 10 科目の行 + 合計行。現金は借方残高 595,000
(500,000 + 100,000 − 5,000 − 5,000 の取消分)、売上高は貸方残高 100,000、
通信費は取消で 0。合計行の借方・貸方合計が一致する。

### 7. 総勘定元帳

```powershell
python -m kaikei ledger 現金 --start 2026-09-01 --end 2026-09-30
python -m kaikei ledger 現金
```

→ 期間指定時は開始日以前の繰越高を累計残高に反映。現金の 5 明細(取消含む)が
日付順で、相手科目と累計残高(借方・貸方の別、残高 0 は貸借区分なし)付きで
表示される。期間未指定時は全期間が対象。

### 8. JSON 出力の全コマンド確認

`account list` / `entry list` / `trial-balance` / `ledger` に `--json` を付け、
出力が `python -c "import json,sys; json.load(sys.stdin)"` で妥当な JSON と
して読めることを確認(FR-012)。

## 期待される成果(成功基準との対応)

- SC-001: シナリオ 3 で不一致仕訳が 100% 拒否され差額が表示される
- SC-003: シナリオ 6 で貸借一致と集計の正しさを確認
- SC-004: シナリオ 5 で取消の対応表示と二重取消の拒否を確認
- SC-005: シナリオ 8 で全機能の CLI・両出力形式を確認
