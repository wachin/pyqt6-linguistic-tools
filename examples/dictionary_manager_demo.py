"""Embeddable Dictionary Manager demo.

Shows the large :class:`DictionaryManagerWidget` embedded in a window and a
button that opens the same manager as a dialog. The widget uses the catalog
shipped with the toolkit and delegates verified downloads through
``download_requested``.

Usage:
    python examples/dictionary_manager_demo.py
    LIBREOFFICE_DICTIONARIES_PATH=/path/to/dicts python examples/dictionary_manager_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


import _bootstrap  # noqa: E402,F401

from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyqt6_linguistic_tools import (  # noqa: E402
    DictionaryCatalog,
    DictionaryRegistry,
    DictionarySourcePriority,
    DirectoryDictionaryProvider,
    LinguisticService,
    LinuxSystemDictionaryProvider,
    ManagedDictionaryProvider,
    UserDictionaryProvider,
    load_bundled_dictionary_catalog,
    normalize_locale,
)
from pyqt6_linguistic_tools.qt import (  # noqa: E402
    DictionaryManagerDialog,
    DictionaryManagerWidget,
    install_toolkit_translations,
    require_pyqt6,
)


require_pyqt6()


def _discover_registry() -> DictionaryRegistry:
    providers: list = [LinuxSystemDictionaryProvider()]
    corpus = os.environ.get("LIBREOFFICE_DICTIONARIES_PATH")
    if corpus:
        corpus_path = Path(corpus).expanduser().resolve()
        if corpus_path.is_dir():
            providers.append(
                DirectoryDictionaryProvider(
                    corpus_path,
                    source="corpus",
                    priority=DictionarySourcePriority.MANAGED,
                )
            )
    providers.extend(
        [
            ManagedDictionaryProvider(),
            UserDictionaryProvider(),
        ]
    )
    return DictionaryRegistry(tuple(providers))


def _pick_language(registry: DictionaryRegistry) -> str:
    entries = registry.discover()
    if entries:
        return entries[0].locale
    import locale as _locale

    lang, _encoding = _locale.getdefaultlocale()
    if lang:
        return normalize_locale(lang)
    return "en_US"


class DictionaryManagerDemo(QMainWindow):
    """Demo showing the embeddable Dictionary Manager widget."""

    def __init__(
        self,
        service: LinguisticService,
        catalog: DictionaryCatalog,
    ) -> None:
        super().__init__()
        self._service = service
        self._catalog = catalog
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Dictionary Manager Demo")
        self.resize(1200, 760)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        header = QHBoxLayout()
        header.addWidget(
            QLabel(
                "Embedded DictionaryManagerWidget — search, filter and inspect "
                "spelling and thesaurus bundles."
            ),
            1,
        )
        open_button = QPushButton("Open as dialog")
        open_button.clicked.connect(self._open_manager)
        header.addWidget(open_button)
        layout.addLayout(header)

        self.manager = DictionaryManagerWidget(
            self._service,
            catalog=self._catalog,
            parent=self,
        )
        layout.addWidget(self.manager, 1)
        self.manager.download_requested.connect(self._download_requested)

        self.statusBar().showMessage(
            "Downloads are delegated to the host; this demo only reports them."
        )

    def _download_requested(self, entry: object) -> None:
        self.statusBar().showMessage(
            f"Download requested for {entry!r}; the host would verify and install it."
        )

    def _open_manager(self) -> None:
        dialog = DictionaryManagerDialog(
            self._service,
            catalog=self._catalog,
            parent=self,
        )
        dialog.exec()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Dictionary Manager Demo")
    install_toolkit_translations(app, None)

    registry = _discover_registry()
    language = _pick_language(registry)
    service = LinguisticService(language, registry=registry)
    catalog = load_bundled_dictionary_catalog()

    window = DictionaryManagerDemo(service, catalog)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
