"""勘定科目マスタ(標準 10 科目)と残高発生側の導出。"""

# (code, name, category) — data-model.md の標準 10 科目
STANDARD_ACCOUNTS = [
    ("101", "現金", "資産"),
    ("102", "普通預金", "資産"),
    ("201", "売掛金", "資産"),
    ("202", "買掛金", "負債"),
    ("203", "借入金", "負債"),
    ("301", "資本金", "純資産"),
    ("401", "売上高", "収益"),
    ("402", "仕入高", "費用"),
    ("501", "給料", "費用"),
    ("502", "通信費", "費用"),
]

_DEBIT_CATEGORIES = {"資産", "費用"}
_CREDIT_CATEGORIES = {"負債", "純資産", "収益"}


def normal_side(category: str) -> str:
    """区分から残高の発生側(debit/credit)を導出する。"""
    if category in _DEBIT_CATEGORIES:
        return "debit"
    if category in _CREDIT_CATEGORIES:
        return "credit"
    raise ValueError(f"不明な区分です: {category}")
