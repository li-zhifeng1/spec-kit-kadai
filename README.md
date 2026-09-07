# spec-kit 課題 — Kaikei Lite

Spec Kit(仕様駆動開発)の課題として作成した、小規模事業者向けの複式簿記 CLI ツールです。
個人事業主の経理担当者が日々の取引を仕訳として記録し、残高試算表・総勘定元帳を確認できます。

## 特徴

- **複式簿記の不変条件を強制**: 借方合計と貸方合計が一致しない仕訳は登録不可(差額を表示)
- **金額は円単位の整数のみ**(1 明細あたり最大 9,223,372,036,854,775,807 円)
- **テストファースト**: 仕様 → 明確化 → 計画 → 実装の Spec Kit ワークフローで、80 テストをすべて通過
- **標準ライブラリのみ**: 外部依存は pytest のみ(憲法「シンプル優先」)

## セットアップ

```powershell
Set-Location "spec-kit 課題"
$env:PYTHONPATH = "$PWD\src"
$env:KAIKEI_DB = "$PWD\kaikei.db"   # 初回実行時に自動作成・標準 10 科目を投入
```

Python 3.11 以降が必要です。

## 使い方

```powershell
python -m kaikei account list                          # 標準 10 科目の一覧
python -m kaikei entry add --date 2026-09-07 `
  --description "資本金の払込" --debit "現金:100000" --credit "資本金:100000"
python -m kaikei entry list                            # 仕訳一覧(日付順)
python -m kaikei entry reverse 1                       # 逆仕訳(取消)の作成
python -m kaikei trial-balance --start 2026-09-01 --end 2026-09-30
python -m kaikei ledger "現金"                          # 総勘定元帳
```

すべてのコマンドに `--json` を付けると JSON でも出力できます。

## 構成

```text
.specify/   Spec Kit のテンプレート・スクリプト・憲法
specs/      仕様・計画・タスク・設計文書(001-journal-trial-balance)
src/kaikei/ 実装(CLI・仕訳帳・集計)
tests/      pytest テスト(80 件)
```

## 開発の流れ

`/speckit-constitution`(憲法作成)→ `/speckit-specify`(仕様)→ `/speckit-clarify`(明確化)
→ `/speckit-checklist`(要求品質チェック)→ `/speckit-plan`(計画)→ `/speckit-tasks`(タスク分解)
→ `/speckit-implement`(TDD 実装)→ `/speckit-converge`(収束判定: 残差課題ゼロ)

## テスト実行

```powershell
pip install pytest
python -m pytest
```
