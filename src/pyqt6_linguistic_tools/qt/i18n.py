"""Toolkit-owned Qt translations for the optional widget layer."""

from __future__ import annotations

from importlib.resources import as_file, files

from PyQt6.QtCore import QCoreApplication, QLocale, QTranslator

from pyqt6_linguistic_tools.qt._compat import require_pyqt6


require_pyqt6()


TRANSLATION_BASENAME = "pyqt6_linguistic_tools"
_TRANSLATOR_PROPERTY = "_pyqt6_linguistic_tools_translator"


def translation_candidates(language: str | None = None) -> tuple[str, ...]:
    """Return locale candidates from most specific to broadest.

    ``None`` and ``"system"`` resolve through :class:`QLocale`. A language such
    as ``es_EC`` yields ``("es_EC", "es")`` so a regional variant falls back to
    its base translation.
    """
    if language is None or language.strip().lower() in {"system", "c", "posix"}:
        language = QLocale.system().name()
    normalized = language.strip().replace("-", "_")
    if not normalized:
        return ()
    candidates = [normalized]
    base = normalized.split("_", 1)[0]
    if base and base not in candidates:
        candidates.append(base)
    return tuple(candidates)


def install_toolkit_translations(
    app: QCoreApplication,
    language: str | None = None,
) -> QTranslator | None:
    """Install the toolkit's ``.qm`` matching *language* on *app*.

    The translator covers only toolkit-owned widget strings. Host applications
    keep their own translator and can install it before or after this one; Qt
    searches installed translators in reverse order, so a later host
    translator can override overlapping messages. Returns ``None`` when no
    ``.qm`` matches, which leaves the English source strings in place.
    """
    if not isinstance(app, QCoreApplication):
        raise TypeError("app must be a QCoreApplication")

    uninstall_toolkit_translations(app)

    for candidate in translation_candidates(language):
        resource = (
            files("pyqt6_linguistic_tools")
            .joinpath("translations")
            .joinpath(f"{TRANSLATION_BASENAME}_{candidate}.qm")
        )
        try:
            with as_file(resource) as path:
                if not path.is_file():
                    continue
                translator = QTranslator(app)
                if translator.load(str(path)):
                    app.installTranslator(translator)
                    setattr(app, _TRANSLATOR_PROPERTY, translator)
                    return translator
        except (FileNotFoundError, OSError):
            continue
    return None


def uninstall_toolkit_translations(app: QCoreApplication) -> bool:
    """Remove the toolkit translator from *app*, returning whether one existed."""
    if not isinstance(app, QCoreApplication):
        raise TypeError("app must be a QCoreApplication")
    translator = getattr(app, _TRANSLATOR_PROPERTY, None)
    if isinstance(translator, QTranslator):
        app.removeTranslator(translator)
        setattr(app, _TRANSLATOR_PROPERTY, None)
        return True
    return False


def installed_toolkit_translator(
    app: QCoreApplication,
) -> QTranslator | None:
    """Return the toolkit translator currently installed on *app*, if any."""
    if not isinstance(app, QCoreApplication):
        raise TypeError("app must be a QCoreApplication")
    translator = getattr(app, _TRANSLATOR_PROPERTY, None)
    return translator if isinstance(translator, QTranslator) else None


__all__ = [
    "TRANSLATION_BASENAME",
    "install_toolkit_translations",
    "installed_toolkit_translator",
    "translation_candidates",
    "uninstall_toolkit_translations",
]
