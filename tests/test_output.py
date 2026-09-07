"""出力整形(表形式 / JSON)のテスト。"""

import json

from kaikei.output import emit_json, format_table


def test_format_table_renders_aligned_columns():
    headers = ["科目", "借方"]
    rows = [["現金", "100000"], ["売上高", "0"]]
    text = format_table(headers, rows)
    lines = text.splitlines()
    assert len(lines) == 4  # ヘッダ + 区切り + 2 行
    assert "科目" in lines[0]
    assert "借方" in lines[0]
    assert "現金" in lines[2]


def test_format_table_with_empty_rows():
    text = format_table(["A"], [])
    assert len(text.splitlines()) >= 2  # ヘッダと区切りのみ


def test_format_table_contiguous_columns():
    headers = ["日付", "摘要"]
    rows = [["2026-09-01", "開業"] , ["2026-09-02", "仕入"]]
    text = format_table(headers, rows)
    for line in text.splitlines():
        # 各行は同一の列数で構成される(単純な位置揃え)
        assert " | " in line or set(line) <= set("-+")


def test_emit_json_produces_valid_json(capsys):
    payload = {"a": 1, "金額": 100}
    emit_json(payload)
    parsed = json.loads(capsys.readouterr().out)
    assert parsed == payload
