# Research: 仕訳記録と残高試算表

**Feature**: specs/001-journal-trial-balance | **Date**: 2026-09-07

Technical Context に NEEDS CLARIFICATION は発生しなかった(ユーザーが技術選定を
明示)。以下は設計判断の記録。

## D1. 金額表現と桁あふれ

- **Decision**: 金額は Python の `int`、SQLite の `INTEGER`(64bit 符号付き、
  最大 9,223,372,036,854,775,807 円)のみで扱う。入力検査で「1 明細の
  入力金額は 1 円以上 9,223,372,036,854,775,807 円以下」を検証し、範囲外は
  明確なエラーメッセージで拒否する(spec チェックリスト review 案 B)。
  **上限検査は入力明細のみに適用し、合計・繰越高・残高の集計には適用しない**。
  集計は Python の多倍長整数(`int`)で実施するため、集計値が 64bit を
  超えても正確に計算・表示できる(SQLite へは明細単位で保存し、集計値を
  再保存しない)。
- **Rationale**: 憲法原則 II。float に触れる経路を持たない。
  Python 側の int は多倍長なので集計の桁あふれは起きない。
- **テスト対象(spec FR-003 / US1 シナリオ 5〜7)**: ①上限値ちょうどの
  明細の登録成功、②上限超過明細の拒否と全明細が保存されないこと、
  ③合法な明細のみで構成される貸借一致仕訳の合計が上限を超えるケースの
  登録成功と集計の正確性。
- **Alternatives considered**: `decimal.Decimal`(小数金額への拡張性があるが、
  円未満を扱わない本仕様では不要で複雑化)— 却下。金額を TEXT 保存して
  真の無制限にする案 — 原則 IV に反して複雑化するため却下。
  集計値を SQLite で SUM する案 — 合計が 64bit を超えると
  オーバーフローするため却下(Python 側で集計)。

## D2. 貸借一致の強制方法

- **Decision**: 保存経路を `journal.add_entry()` 1 関数に限定し、
  SQLite トランザクション内で借方合計 == 貸方合計を検証してから commit。
  不一致・明細 0 行・金額 0 以下・科目未定義・取消済み仕訳への再取消は
  すべて commit 前に例外として中断する。
- **Rationale**: 憲法原則 I(一致しないデータを保存する経路があってはならない)。
  単一の保存関数 + トランザクション中断により、この条件をテスト可能な
  1 箇所で保証できる。
- **Alternatives considered**: DB トリガで行単位に検証する案 — 部分挿入状態の
  判定が複雑になり原則 IV に反するため採用せず。テストで保存経路の単一性を
  検証することで担保する。

## D3. 逆仕訳の表現

- **Decision**: `entries.reversed_entry_id`(NULL 許可、UNIQUE)で取消元を
  参照する。取消済み判定は「当該 entry を `reversed_entry_id` に持つ行の
  存在」で行う。逆仕訳自体も取消可能(spec Q2)なので、参照先が逆仕訳である
  ことへの制限は設けない。
- **Rationale**: 仕訳は削除せず参照で結ぶ(原則 I の精神・spec FR-007)。
  UNIQUE 制約により二重取消(FR-008)を DB レベルでも防げる。
- **Alternatives considered**: 削除フラグ方式(打ち消し対象を無効化)—
  「元の仕訳は削除されない」という要件に反し、集計の複雑化を招くため却下。

## D4. 科目マスタと残高発生側

- **Decision**: 科目はコード・名称・区分(資産/負債/純資産/収益/費用)のみを
  保存し、残高の発生側(借方/貸方)は区分から導出する関数で計算して
  保存しない。初回起動(DB 初期化時)に標準 10 科目を INSERT する。
- **Rationale**: 発生側は区分の関数なので重複保持は不整合の温床。
  `CREATE TABLE IF NOT EXISTS` + `INSERT OR IGNORE` で冪等にシードできる。
- **Alternatives considered**: 発生側を列として保存 — 導出可能な値の重複保持。

## D5. 試算表の繰越高(spec Q4)

- **Decision**: 借方合計・貸方合計の列は `[start, end]` の期間内仕訳のみで
  集計。残高列は「開始日より前の全仕訳 + 期間内仕訳」の累計で計算する。
  残高は区分の発生側にのみ表示する(発生側以外は 0)。
- **Rationale**: spec の Clarifications(Q3 両端包含・Q4 繰越高)に準拠。
  SQL では条件集計 2 回(期間内・開始日以降全件)で得られる。

## D6. 元帳の累計残高

- **Decision**: 指定科目の明細を日付順(同日は登録順 = entry_id 順)で並べ、
  借方発生 − 貸方発生を累計する。各行に相手科目(対抗明細の科目名。
  複数ある場合はカンマ連結)と、累計残高の発生側(借方/貸方、0 の場合は
  貸借区分なし)を付す。開始日・終了日の指定を設け(省略時は全期間)、
  指定時は開始日より前の仕訳の累計を繰越高として最初の明細の累計残高に
  反映する(spec チェックリスト review の決定)。
- **Rationale**: spec FR-011・US4。登録順の安定ソートには自作の
  entry_id 連番を使用する。

## D7. CLI 設計

- **Decision**: argparse のサブパーサで `account list` / `entry add` /
  `entry list` / `entry reverse` / `trial-balance` / `ledger` を提供。
  複数の借方・貸方明細は `--debit 科目:金額` / `--credit 科目:金額` の
  繰り返しフラグで表現する。全コマンドに `--json` を用意し、既定は
  標準ライブラリの文字列書式によるテキスト表で出力する。検証エラーは
  stderr に日本語メッセージ + 終了コード 1、argparse の使用方法エラーは
  終了コード 2。
- **Rationale**: spec FR-012 とユーザー指定のサブコマンド一覧にそのまま対応。
  表整形を外部ライブラリ(tabulate 等)に頼らず原則 IV を遵守。
- **Alternatives considered**: 明細を位置引数のリストで渡す方式 —
  借方/貸方の区別が暗黙になり入力ミスを誘発するため却下。

## D8. pytest の導入(憲法原則 IV の記録)

- **Decision**: 外部依存は pytest のみに限定する。
- **Rationale**: 標準 unittest でも TDD(原則 III)は可能だが、pytest の
  fixture(conftest での一時 DB 貼り替え)と素直な assert 構文により、
  集計ロジックの多様な期待値テストを短く書ける。テストファーストの
  運用負担軽減効果が依存追加に値すると判断した。plan.md の
  Constitution Check に記録済み。
- **Alternatives considered**: unittest + tempfile — 記述量が増えテストの
  可読性が下がる。

## D9. JSON 出力構造

- **Decision**: 各コマンドの JSON スキーマを contracts/cli.md で固定する。
  金額は JSON number(整数)、日付は ISO 8601 文字列。
- **Rationale**: spec FR-012。スキーマを固定すると受入テストで
  構造そのものを検証できる。
