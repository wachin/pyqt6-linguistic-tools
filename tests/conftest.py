import os
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--dictionary-corpus",
        action="store",
        default=None,
        help="Path to the LibreOffice dictionaries collection (the dicts directory)",
    )


@pytest.fixture(scope="session")
def dictionary_corpus(request) -> Path:
    configured = request.config.getoption("--dictionary-corpus")
    configured = configured or os.environ.get("LIBREOFFICE_DICTIONARIES_PATH")
    if not configured:
        pytest.skip(
            "set LIBREOFFICE_DICTIONARIES_PATH or use --dictionary-corpus"
        )

    root = Path(configured).expanduser().resolve()
    if not root.is_dir():
        pytest.fail(f"dictionary corpus is not a directory: {root}")
    return root
