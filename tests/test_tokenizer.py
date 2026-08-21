from __future__ import annotations

import unicodedata

import pytest

from pyqt6_linguistic_tools import (
    TokenizerConfig,
    UnicodeTokenizer,
    tokenize,
)


def _texts(source: str, **kwargs) -> tuple[str, ...]:
    return tuple(token.text for token in tokenize(source, **kwargs))


def test_multilingual_words_are_preserved_without_ascii_ranges():
    source = "Señor creación Straße français Москва Ελληνικά"

    assert _texts(source) == (
        "Señor",
        "creación",
        "Straße",
        "français",
        "Москва",
        "Ελληνικά",
    )


def test_additional_scripts_and_combining_marks_are_supported():
    source = "العَرَبِيَّة हिन्दी հայերեն"

    assert _texts(source) == ("العَرَبِيَّة", "हिन्दी", "հայերեն")


def test_apostrophes_and_linguistic_hyphens_are_internal_only():
    source = "d’Artagnan O'Connor co-operar no‑break fin- 'inicio word--word"

    assert _texts(source) == (
        "d’Artagnan",
        "O'Connor",
        "co-operar",
        "no‑break",
        "fin",
        "inicio",
        "word",
        "word",
    )


def test_connectors_can_be_disabled():
    config = TokenizerConfig(allow_apostrophes=False, allow_hyphens=False)

    assert _texts("d’Artagnan O'Connor co-operar", config=config) == (
        "d",
        "Artagnan",
        "O",
        "Connor",
        "co",
        "operar",
    )


def test_source_and_utf16_offsets_remain_exact():
    decomposed = unicodedata.normalize("NFD", "creación")
    source = f"😀 canción {decomposed} d’Artagnan"
    tokens = tokenize(source)

    assert tuple(token.text for token in tokens) == (
        "canción",
        decomposed,
        "d’Artagnan",
    )
    for token in tokens:
        assert source[token.start : token.end] == token.text
        assert token.span == (token.start, token.end)
        assert token.utf16_span == (token.utf16_start, token.utf16_end)
    assert tokens[0].start == 2
    assert tokens[0].utf16_start == 3
    assert tokens[1].normalized == "creación"
    assert len(tokens[1].text) > len(tokens[1].normalized)


def test_urls_www_addresses_and_emails_are_excluded_as_complete_regions():
    source = (
        "Visita https://example.com/ruta?x=uno, www.example.org/path y "
        "escribe a usuario.nombre+tag@example.ec ahora"
    )

    assert _texts(source) == ("Visita", "y", "escribe", "a", "ahora")


def test_url_and_email_exclusion_is_configurable():
    config = TokenizerConfig(exclude_urls=False, exclude_emails=False)
    words = _texts("https://example.com user@example.org www.site.ec", config=config)

    assert "https" in words
    assert "example" in words
    assert "user" in words
    assert "www" in words


def test_numbers_and_alphanumeric_technical_tokens_are_excluded_by_default():
    assert _texts("123 2026 x3 version2 palabra") == ("palabra",)


def test_numbers_and_alphanumeric_tokens_can_be_enabled_independently():
    numbers = TokenizerConfig(include_numbers=True)
    alphanumeric = TokenizerConfig(include_alphanumeric=True)
    both = TokenizerConfig(include_numbers=True, include_alphanumeric=True)

    assert _texts("123 2026 x3", config=numbers) == ("123", "2026")
    assert _texts("123 2026 x3", config=alphanumeric) == ("x3",)
    assert _texts("123 2026 x3", config=both) == ("123", "2026", "x3")


def test_configurable_technical_tokens_support_case_policy():
    exact = TokenizerConfig(excluded_tokens=frozenset(("ChordFlow", "x3")))
    folded = TokenizerConfig(
        excluded_tokens=frozenset(("ChordFlow",)),
        excluded_tokens_case_sensitive=False,
    )

    assert _texts("ChordFlow chordflow canción", config=exact) == (
        "chordflow",
        "canción",
    )
    assert _texts("ChordFlow CHORDFLOW canción", config=folded) == ("canción",)


def test_host_filters_receive_token_and_original_source():
    source = "{title: Canción} verso ChordFlow"
    seen = []

    def outside_braces(token, original):
        seen.append((token.text, original is source))
        return not (original.rfind("{", 0, token.start) > original.rfind("}", 0, token.start))

    def exclude_product_names(token, original):
        return not token.text.startswith("Chord")

    tokenizer = UnicodeTokenizer(
        token_filters=(outside_braces, exclude_product_names)
    )

    assert tuple(token.text for token in tokenizer.tokenize(source)) == ("verso",)
    assert seen
    assert all(same_source for _, same_source in seen)


def test_token_positions_cover_lines_and_repeated_words():
    source = "hola\n  hola, mundo"
    tokens = tokenize(source)

    assert tuple((token.text, token.span) for token in tokens) == (
        ("hola", (0, 4)),
        ("hola", (7, 11)),
        ("mundo", (13, 18)),
    )


def test_empty_text_and_isolated_marks_or_connectors_produce_no_tokens():
    assert tokenize("") == ()
    assert _texts("\u0301 - ‐ ‑ ' ’") == ()


@pytest.mark.parametrize(
    "config_kwargs",
    [
        {"include_numbers": 1},
        {"exclude_urls": "yes"},
        {"excluded_tokens_case_sensitive": None},
        {"excluded_tokens": "ChordFlow"},
        {"excluded_tokens": frozenset((1,))},
    ],
)
def test_invalid_configuration_is_rejected(config_kwargs):
    with pytest.raises(TypeError):
        TokenizerConfig(**config_kwargs)


def test_invalid_text_config_and_filters_are_rejected():
    with pytest.raises(TypeError):
        tokenize(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        UnicodeTokenizer(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        UnicodeTokenizer(token_filters=(None,))  # type: ignore[arg-type]
