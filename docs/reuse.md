# Reuse procedure

This document describes how to integrate `pyqt6-linguistic-tools` into a
PyQt6 application as a Git submodule or as a pip-installed dependency.

## Option A: Git submodule

Recommended for active development alongside the toolkit.

```bash
# Add the toolkit as a submodule
cd your-project
git submodule add https://github.com/wachin/pyqt6-linguistic-tools.git libs/pyqt6-linguistic-tools

# Initialize nested engine submodules
git submodule update --init --recursive libs/pyqt6-linguistic-tools
```

Add the toolkit source directories to your Python path. In your application's
entry point or bootstrap code:

```python
import sys
from pathlib import Path

toolkit = Path(__file__).resolve().parent / "libs" / "pyqt6-linguistic-tools"
for path in [
    str(toolkit / "src"),
    str(toolkit / "libs" / "spylls"),
    str(toolkit / "libs" / "pythes"),
]:
    if path not in sys.path:
        sys.path.insert(0, path)
```

Then import and use the toolkit:

```python
from pyqt6_linguistic_tools import LinguisticService
from pyqt6_linguistic_tools.qt import LinguisticTextEditDecorator

service = LinguisticService(language="en_US")
decorator = LinguisticTextEditDecorator(editor, service)
```

## Option B: pip install

Recommended for released versions.

```bash
pip install pyqt6-linguistic-tools
```

The toolkit bundles Spylls and PyThes, so no additional engine installation
is needed.

## Option C: OS package or AppImage

The packager bundles the toolkit, Spylls, and PyThes in the distribution.
End users should not need to run `pip` or create a virtual environment.

## Configuration

### Dictionary providers

By default, the toolkit discovers dictionaries from:

1. Linux system paths (`/usr/share/hunspell`, `/usr/share/mythes`)
2. Application-managed storage (`QStandardPaths::AppLocalDataLocation`)
3. User-imported dictionaries

To add a custom dictionary corpus:

```python
from pyqt6_linguistic_tools import (
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    LinguisticService,
    LinuxSystemDictionaryProvider,
    ManagedDictionaryProvider,
    UserDictionaryProvider,
)

registry = DictionaryRegistry((
    LinuxSystemDictionaryProvider(),
    DirectoryDictionaryProvider(
        "/path/to/your/dictionaries",
        source="your-app",
        priority=DictionarySourcePriority.MANAGED,
    ),
    ManagedDictionaryProvider(namespace="your-app"),
    UserDictionaryProvider(namespace="your-app"),
))

service = LinguisticService("en_US", registry=registry)
```

### Token filter

To exclude custom token types (e.g., chord symbols) from spell checking:

```python
from pyqt6_linguistic_tools import TokenFilter, WordToken

def my_token_filter(token: WordToken, text: str) -> bool:
    # Return False to exclude the token from spell checking
    return True  # keep all tokens by default

decorator.add_token_filter(my_token_filter)
```

## Verification

After integrating, verify with:

```bash
# Run the toolkit's fast suite
cd libs/pyqt6-linguistic-tools
QT_QPA_PLATFORM=offscreen python3 -m pytest -c pyproject.toml \
  -m 'not corpus and not platform'

# Run the examples
QT_QPA_PLATFORM=offscreen python3 -m pyqt6_linguistic_tools.compatibility_report --help
```

## What NOT to do

- Do not import Spylls or PyThes directly in your application code.
- Do not hard-code dictionary paths that may differ between platforms.
- Do not require native Hunspell or MyThes libraries.
- Do not subclass `QTextEdit` solely for spell checking; use the decorator.
- Do not modify the toolkit's source files directly; submit changes upstream.