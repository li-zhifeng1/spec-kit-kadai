"""共通出力整形: 表形式(既定)と JSON。標準ライブラリのみ(research D7)。"""

import json
import sys
from collections.abc import Sequence


def _display_width(text: str) -> int:
    """東アジア文字を 2 桁とみなした表示幅を返す。"""
    import unicodedata

    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def format_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """単純な整列テキスト表を返す。"""
    widths = [_display_width(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], _display_width(cell))

    def line(cells: Sequence[str]) -> str:
        return " | ".join(_pad(c, widths[i]) for i, c in enumerate(cells))

    sep = "-+-".join("-" * w for w in widths)
    lines = [line(headers), sep]
    lines.extend(line(row) for row in rows)
    return "\n".join(lines)


def emit_json(payload: object) -> None:
    """JSON を stdout へ 1 オブジェクト出力する(ensure_ascii=False, UTF-8)。"""
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
