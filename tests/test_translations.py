"""Tests for the toolkit-owned Qt translations."""

from __future__ import annotations

import os
from importlib.resources import files

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6", reason="PyQt6 is an optional dependency")

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication

from pyqt6_linguistic_tools.qt import (
    install_toolkit_translations,
    installed_toolkit_translator,
    translation_candidates,
    uninstall_toolkit_translations,
)


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def test_translation_candidates_prefer_the_region_then_the_base_language() -> None:
    assert translation_candidates("es_EC") == ("es_EC", "es")
    assert translation_candidates("en") == ("en",)
    assert translation_candidates("pt-BR") == ("pt_BR", "pt")


def test_translation_files_are_packaged() -> None:
    translations = files("pyqt6_linguistic_tools").joinpath("translations")
    for name in (
        "pyqt6_linguistic_tools_es.ts",
        "pyqt6_linguistic_tools_es.qm",
        "pyqt6_linguistic_tools_en.ts",
        "pyqt6_linguistic_tools_en.qm",
    ):
        assert translations.joinpath(name).is_file()


def test_spanish_translation_is_installed_and_removed(application) -> None:
    translator = install_toolkit_translations(application, "es_EC")
    try:
        assert translator is not None
        assert installed_toolkit_translator(application) is translator
        assert (
            QCoreApplication.translate("DictionaryManagerWidget", "Spelling")
            == "Ortografía"
        )
        assert (
            QCoreApplication.translate(
                "DictionaryManagerWidget", "Dictionary Download Manager"
            )
            == "Gestor de descargas de diccionarios"
        )
        assert (
            QCoreApplication.translate(
                "DictionaryManagerDialog", "Dictionary Download Manager"
            )
            == "Gestor de descargas de diccionarios"
        )
        assert (
            QCoreApplication.translate("DictionaryManagerWidget", "Download")
            == "Descargar"
        )
        assert (
            QCoreApplication.translate(
                "PyQt6LinguisticTools.ThesaurusDialog", "Thesaurus"
            )
            == "Tesauro"
        )
        assert QCoreApplication.translate("PyQt6LinguisticTools", "Ignore") == "Ignorar"
        assert (
            QCoreApplication.translate(
                "PyQt6LinguisticTools.ThesaurusDialog",
                "This dictionary does not provide grammatical categories.",
            )
            == "Este diccionario no incluye categorías gramaticales."
        )
        assert (
            QCoreApplication.translate("PyQt6LinguisticTools.ThesaurusDialog", "Copy")
            == "Copiar"
        )
        assert (
            QCoreApplication.translate(
                "PyQt6LinguisticTools.ThesaurusDialog", "Current word:"
            )
            == "Palabra actual:"
        )
        assert (
            QCoreApplication.translate(
                "PyQt6LinguisticTools.ThesaurusDialog", "Replace with:"
            )
            == "Reemplazar por:"
        )
        assert (
            QCoreApplication.translate("PyQt6LinguisticTools.ThesaurusDialog", "Cancel")
            == "Cancelar"
        )
    finally:
        assert uninstall_toolkit_translations(application)
        assert installed_toolkit_translator(application) is None


def test_english_translation_keeps_the_source_text(application) -> None:
    translator = install_toolkit_translations(application, "en")
    try:
        assert translator is not None
        assert (
            QCoreApplication.translate("DictionaryManagerWidget", "Spelling")
            == "Spelling"
        )
    finally:
        uninstall_toolkit_translations(application)


def test_unknown_language_falls_back_to_english_source(application) -> None:
    assert install_toolkit_translations(application, "zz") is None
    assert installed_toolkit_translator(application) is None
    assert (
        QCoreApplication.translate("DictionaryManagerWidget", "Spelling") == "Spelling"
    )
