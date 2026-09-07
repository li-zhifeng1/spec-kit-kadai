# Implementation Plan: 仕訳記録と残高試算表(Kaikei Lite 中核機能)

**Branch**: `001-journal-trial-balance` | **Date**: 2026-09-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-journal-trial-balance/spec.md`

## Summary

個人事業主・小規模事業者の経理担当者が日々の取引を複式簿記の仕訳として記録し、
残高試算表・総勘定元帳を確認できる CLI ツールを構築する。Python 3.11 標準
ライブラリ中心で実装し、データは SQLite(sqlite3)の単一ファイル `kaikei.db` に
保存。貸借一致の検証は仕訳保存の単一経路で強制し、金額はすべて円単位の
整数として扱う。

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: Python 標準ライブラリ(sqlite3, argparse, json, datetime,
datetime.timezone)+ テスト用に pytest(外部依存は pytest のみ — 下記
Constitution Check に導入理由を記録)

**Storage**: SQLite 単一ファイル `kaikei.db`(標準の sqlite3 モジュール)。
初回起動時に標準科目 10 科目を投入する。

**Testing**: pytest

**Target Platform**: Windows / macOS / Linux のローカル環境(単一ユーザー)

**Project Type**: CLI

**Performance Goals**: 1,000 件の仕訳から残高試算表を 1 秒以内に生成する

**Constraints**: 経理担当者 1 名のローカル利用。ログイン・同時実行制御・
消費税・決算処理は対象外(spec の Assumptions 参照)

**Scale/Scope**: 仕訳数千件規模・標準科目 10 科目・CLI サブコマンド 6 種

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原則 | 判定 | 根拠 |
|------|------|------|
| I. 貸借一致の不変条件 | PASS | 仕訳の保存経路は `journal.add_entry()` の単一関数に限定し、
  トランザクション内で貸借一致を検証してから commit する。不一致データは
  commit 前に例外で中断され、保存されない。Phase 1 の data-model.md で
  スキーマ制約としても確認済み |
| II. 円整数 | PASS | 金額カラムは SQLite の INTEGER(64bit)。
  **上限検査(1 円以上 9,223,372,036,854,775,807 円以下)は 1 明細の
  入力金額にのみ適用する**。合計・繰越高・残高の集計は Python の
  多倍長整数(`int`)で行うため、集計結果が 64bit を超えても
  正確に計算・表示できる。SQLite への保存は明細単位で行い、集計値を
  再保存しないので集計値の 64bit 制約を受けない。float に触れる
  経路を持たない |
| III. テストファースト | PASS | tasks.md で全業務ロジック(仕訳登録・取消・試算表・
  元帳)について「失敗するテスト→実装」の順序をタスク化する |
| IV. シンプル優先 | PASS(記録済み) | 外部依存は pytest のみ。理由: 標準 unittest でも
  実現可能だが、pytest のfixture とアサーションによりテストコードの可読性が
  大幅に向上し、テストファースト(原則 III)の運用負担を下げるため。
  テーブル整形・DB・CLI 解析はすべて標準ライブラリで行う |
| V. CLI + 表形式/JSON | PASS | argparse のサブコマンド 6 種。全コマンドに `--json`
  オプションを提供し、表形式が既定出力 |

**結果: すべてのゲートを通過。Complexity Tracking は不要(違反なし)。**

## Project Structure

### Documentation (this feature)

```text
specs/001-journal-trial-balance/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── cli.md           # CLI インターフェース契約
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/kaikei/
├── __init__.py
├── __main__.py          # python -m kaikei エントリポイント
├── cli.py               # argparse によるサブコマンド定義
├── db.py                # SQLite 接続・スキーマ初期化・標準科目シード
├── accounts.py          # 勘定科目マスタ(区分→残高発生側の判定)
├── journal.py           # 仕訳の登録・取消(貸借一致検証の単一保存経路)
├── reports.py           # 残高試算表・総勘定元帳の集計
└── output.py            # 表形式 / JSON の共通出力整形

tests/
├── conftest.py          # 一時 DB を用いる pytest fixture
├── test_db.py           # スキーマ初期化・科目シード
├── test_journal.py      # 仕訳登録・貸借一致検証・逆仕訳
├── test_reports.py      # 試算表(繰越高込み)・元帳(相手科目・累計残高)
└── test_cli.py          # サブコマンド動作・--json 出力・終了コード
```

**Structure Decision**: ユーザー指定の単一パッケージ構成 `src/kaikei/` +
`tests/` を採用。業務ロジック(journal, reports)は CLI 入出力から分離し、
テストファースト(原則 III)を適用しやすい構成とする。

## Complexity Tracking

> 違反なしのため記載なし。
