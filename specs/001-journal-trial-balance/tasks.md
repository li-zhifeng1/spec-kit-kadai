# Tasks: 仕訳記録と残高試算表(Kaikei Lite 中核機能)

**Input**: Design documents from `/specs/001-journal-trial-balance/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: 憲法原則 III(テストファースト、NON-NEGOTIABLE)により、
全業務ロジックで「失敗するテストを先に書いてから実装」を必須とする。
各ストーリーのテストタスクは実装タスクより先行し、実装開始前に FAIL を確認する。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project: `src/kaikei/`, `tests/` at repository root (plan.md 構成に従う)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: プロジェクトの初期化

- [X] T001 Create project structure `src/kaikei/` and `tests/` with empty `src/kaikei/__init__.py`, `src/kaikei/__main__.py` (python -m kaikei エントリポイントの雛形) per plan.md
- [X] T002 Configure pytest for src layout (pytest.ini or pyproject.toml with `pythonpath = ["src"]`) and install pytest as the only external dependency
- [X] T003 [P] Create pytest fixture providing a temporary `kaikei.db` path (env `KAIKEI_DB`) in `tests/conftest.py` per data-model.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 全ユーザーストーリーが依存する DB・科目マスタ・出力基盤

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Write FAILING tests for DB initialization & standard account seeding (3 tables `accounts`/`entries`/`lines` per data-model.md, idempotent seed of 標準 10 科目, CHECK 制約 amount > 0, UNIQUE reversed_entry_id) in `tests/test_db.py`
- [X] T005 Implement schema initialization & idempotent account seeding in `src/kaikei/db.py` (CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE, `get_connection()`); make T004 pass
- [X] T006 Write FAILING tests for 標準 10 科目の定義と区分→残高発生側の導出 `normal_side(category)` (資産・費用→debit、負債・純資産・収益→credit) in `tests/test_db.py`
- [X] T007 Implement account constants & `normal_side()` in `src/kaikei/accounts.py`; make T006 pass
- [X] T008 [P] Write FAILING tests then implement dual output formatting (表形式が既定、`--json` で JSON オブジェクト) in `tests/test_output.py` and `src/kaikei/output.py` (標準ライブラリの文字列書式のみ、research D7)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - 仕訳を登録する (Priority: P1) 🎯 MVP

**Goal**: 貸借一致を強制した仕訳の登録(借方/貸方複数行対応、不一致は差額付きエラーで拒否)

**Independent Test**: 貸借一致する仕訳 1 件の登録成功と、不一致仕訳 1 件が差額付きエラーで拒否され保存されないことで、単独で検証できる

### Tests for User Story 1 (write FIRST, ensure they FAIL) ⚠️

- [X] T009 [P] [US1] Write FAILING tests for `journal.add_entry` in `tests/test_journal.py`: 貸借一致登録成功・複数借方/貸方行・貸借不一致の拒否と差額表示(FR-002)・借方/貸方 0 行の拒否・金額 0/負数/小数の拒否(FR-003)・未定義科目の拒否・空文字/空白のみ摘要の拒否(FR-001)・**入力エラー時に仕訳全体が保存されないこと(部分保存なし)**・上限値 9,223,372,036,854,775,807 円ちょうどの登録成功と上限超過の拒否・合法明細のみで合計が上限を超える仕訳の集計正確性(spec US1 シナリオ 5〜7)
- [X] T010 [P] [US1] Write FAILING tests for CLI `entry add` (表形式/`--json` 出力・終了コード 0/1/2・エラーメッセージに差額を含む) in `tests/test_cli.py` per contracts/cli.md

### Implementation for User Story 1

- [X] T011 [US1] Implement `journal.add_entry` (単一保存経路: トランザクション内で貸借一致・入力検証後に commit、research D2) in `src/kaikei/journal.py`; make T009 pass
- [X] T012 [US1] Implement `entry add` subcommand (argparse サブパーサ、`--date/--description/--debit ACCOUNT:AMOUNT(繰返)/--credit ACCOUNT:AMOUNT(繰返)/--json`、日付 YYYY-MM-DD 検証) in `src/kaikei/cli.py`; make T010 pass

**Checkpoint**: User Story 1 (MVP) is fully functional and testable independently

---

## Phase 4: User Story 2 - 登録済みの仕訳を日付順に一覧する (Priority: P2)

**Goal**: 全仕訳の日付順(同日は登録順)一覧表示

**Independent Test**: 日付の異なる仕訳 2 件以上を登録し、一覧が日付順・登録順で全件表示されることで、単独で検証できる

### Tests for User Story 2 (write FIRST, ensure they FAIL) ⚠️

- [X] T013 [P] [US2] Write FAILING tests for `journal.list_entries` in `tests/test_journal.py`: 日付順ソート・同日の登録順(entry_id 順)維持・空一覧がエラーでないこと・取消仕訳の取消元参照表示(FR-006)
- [X] T014 [P] [US2] Write FAILING tests for CLI `entry list` (表形式/`--json`・0 件時も終了コード 0) in `tests/test_cli.py`

### Implementation for User Story 2

- [X] T015 [US2] Implement `journal.list_entries` in `src/kaikei/journal.py`; make T013 pass
- [X] T016 [US2] Implement `entry list` subcommand in `src/kaikei/cli.py`; make T014 pass

**Checkpoint**: User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - 残高試算表を表示する (Priority: P2)

**Goal**: 期間指定の残高試算表(両端包含・繰越高込み・合計行の貸借一致保証)

**Independent Test**: 仕訳を数件登録後、期間を指定して試算表を表示し、科目集計と合計行の貸借一致を手計算と突き合わせることで、単独で検証できる

### Tests for User Story 3 (write FIRST, ensure they FAIL) ⚠️

- [X] T017 [P] [US3] Write FAILING tests for `reports.trial_balance` in `tests/test_reports.py`: 全 10 科目行の常時表示・借方/貸方合計列は期間内のみ・残高列は開始日以前の繰越高込み(spec Q3/Q4)・残高は実額の発生側に正の金額(貸方超過は貸方残高へ、FR-009)・残高 0 は借方残高・貸方残高ともに 0・合計行の貸借一致(FR-010)・存在しない日付/開始日 > 終了日のエラー・集計は Python 多倍長 int(合計が入力上限を超えても正確、FR-003)
- [X] T018 [P] [US3] Write FAILING tests for CLI `trial-balance` (表形式/`--json`・終了コード) in `tests/test_cli.py`

### Implementation for User Story 3

- [X] T019 [US3] Implement `reports.trial_balance` (Python int で集計、research D5) in `src/kaikei/reports.py`; make T017 pass
- [X] T020 [US3] Implement `trial-balance` subcommand in `src/kaikei/cli.py`; make T018 pass

**Checkpoint**: User Stories 1, 2 AND 3 should all work independently

---

## Phase 6: User Story 4 - 総勘定元帳を表示する (Priority: P3)

**Goal**: 科目指定(期間指定可)の総勘定元帳(相手科目・累計残高付き)

**Independent Test**: 同一科目が複数回出る仕訳を登録し、元帳が日付順で相手科目・累計残高(借方/貸方の別)付きで表示されることで、単独で検証できる

### Tests for User Story 4 (write FIRST, ensure they FAIL) ⚠️

- [X] T021 [P] [US4] Write FAILING tests for `reports.ledger` in `tests/test_reports.py`: 日付順(同日は登録順)明細・相手科目(複数はカンマ連結、research D6)・累計残高とその借方/貸方の明示・残高 0 は「残高 0(貸借区分なし)」(FR-011)・`--start/--end` 両端包含と開始日以前の繰越高を累計残高に反映・期間未指定は全期間・存在しない日付/開始日 > 終了日のエラー・対象 0 件は空一覧
- [X] T022 [P] [US4] Write FAILING tests for CLI `ledger` (`--start/--end/--json`・JSON の `balance_side: "debit"|"credit"|null`) in `tests/test_cli.py`

### Implementation for User Story 4

- [X] T023 [US4] Implement `reports.ledger` in `src/kaikei/reports.py`; make T021 pass
- [X] T024 [US4] Implement `ledger` subcommand in `src/kaikei/cli.py`; make T022 pass

**Checkpoint**: User Stories 1〜4 should all work independently

---

## Phase 7: User Story 5 - 逆仕訳で仕訳を訂正する (Priority: P3)

**Goal**: 元の仕訳を削除せず打ち消す逆仕訳(取消日付・既定摘要・二重取消拒否)

**Independent Test**: 仕訳 1 件を登録して逆仕訳を作成し、一覧上の対応表示と試算表での打ち消し、二重取消の拒否で、単独で検証できる

### Tests for User Story 5 (write FIRST, ensure they FAIL) ⚠️

- [X] T025 [P] [US5] Write FAILING tests for `journal.reverse_entry` in `tests/test_journal.py`: 取消元参照(reversed_entry_id)を持つ逆仕訳の作成(FR-007)・既定日付は日本時間(Asia/Tokyo)の当日・`--date` 指定可(spec Q1)・既定摘要「仕訳 #<取消元番号> の取消」(spec Q6)・元仕訳の日付不変・二重取消の拒否(FR-008)・逆仕訳自体の取消可否(spec Q2)・存在しない取消元のエラー
- [X] T026 [P] [US5] Write FAILING tests for CLI `entry reverse` (`--date/--description/--json`・表上の取消元対応表示・終了コード) in `tests/test_cli.py`

### Implementation for User Story 5

- [X] T027 [US5] Implement `journal.reverse_entry` (UNIQUE(reversed_entry_id) による二重取消防止を含む、research D3) in `src/kaikei/journal.py`; make T025 pass
- [X] T028 [US5] Implement `entry reverse` subcommand in `src/kaikei/cli.py`; make T026 pass

**Checkpoint**: All user stories should now be independently functional

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 検収と横断的品質

- [X] T029 Run end-to-end validation per `specs/001-journal-trial-balance/quickstart.md` (シナリオ 1〜8: 科目初期化・登録・不一致拒否・一覧・取消・試算表・元帳・全コマンド `--json`) — `verify_quickstart.py` として自動化
- [X] T030 Write and pass a performance check: 1,000 件の仕訳から残高試算表を 1 秒以内に生成 (SC-003) in `tests/test_reports.py`
- [X] T031 Verify all commands support 表形式 + `--json` dual output (SC-005) and run the full test suite (`pytest`) to green

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 - BLOCKS all user stories
- **User Stories (Phase 3〜7)**: All depend on Phase 2 completion
  - US1 → US2/US3/US4/US5 の順に優先度順で進めるのを推奨(単一開発者前提)
  - 並行作業の場合、US1 以降は仕様上独立しているが、実質的には US1 の
    `journal.add_entry` がテストデータ作成の便宜上先にあると良い
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Foundational 後すぐ開始可。他ストーリーに非依存
- **User Story 2 (P2)**: US1 が登録した仕訳を表示するのみで、実装上は独立
- **User Story 3 (P2)**: US1 の登録データで検証。reports モジュールは独立
- **User Story 4 (P3)**: US1/US3 と同様。reports モジュール内で US3 後に実装推奨
- **User Story 5 (P3)**: `journal.add_entry` を再利用するため US1 に依存

### Within Each User Story

- **テストは必ず先に書き、FAIL を確認してから実装する(憲法原則 III)**
- journal → CLI の順(ロジックを CLI から分離、plan.md 構成)
- Story complete before moving to next priority

### Parallel Opportunities

- T003, T008 (Phase 1/2 内の独立タスク)
- 各ストーリー内のテスト作成タスク([P] 付き)はペアで並行作成可
- US2〜US5 は Foundational 完了後、ファイル競合なしで並行着手可
  (journal.py / reports.py / cli.py への追加はストーリーごとに別関数)

---

## Parallel Example: User Story 1

```text
# T009 と T010 は別ファイルなので並行作成可:
Task: "Write FAILING tests for journal.add_entry in tests/test_journal.py"
Task: "Write FAILING tests for CLI entry add in tests/test_cli.py"

# 実装はテスト確認後:
Task: "Implement journal.add_entry in src/kaikei/journal.py"   (T011)
Task: "Implement entry add subcommand in src/kaikei/cli.py"    (T012)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1(仕訳登録)
4. **STOP and VALIDATE**: 貸借一致の強制(憲法原則 I)をこの時点で確認
5. 以降のストーリーへ

### Incremental Delivery

1. Setup + Foundational → 基盤完成
2. US1 → 検証(仕訳登録 MVP)
3. US2 → 一覧、US3 → 試算表(月次確認の主目的が揃う)
4. US4 → 元帳、US5 → 逆仕訳
5. Polish → quickstart.md で検収

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- すべての業務ロジックタスクはテスト先行(TDD)。テストを書いたら
  まず FAIL を確認し、実装で GREEN にする
- 金額はすべて円単位の整数。入力上限(1 明細 9,223,372,036,854,775,807 円)は
  入力検査のみに適用し、集計は Python int で行う(research D1)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
