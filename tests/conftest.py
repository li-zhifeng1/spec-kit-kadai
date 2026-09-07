"""テスト用 pytest fixture: 一時 DB パスを提供する。"""

import pathlib

import pytest


@pytest.fixture
def db_path(tmp_path: pathlib.Path) -> pathlib.Path:
    """各テストに独立した一時 kaikei.db のパスを与える。"""
    return tmp_path / "kaikei.db"
