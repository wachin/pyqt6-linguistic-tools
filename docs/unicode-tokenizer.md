# Unicode tokenizer

`UnicodeTokenizer` extracts spell-checkable words without relying on ASCII or
Western-European character ranges. It uses Python's Unicode categories and
does not require the third-party `regex` package.

```python
from pyqt6_linguistic_tools import UnicodeTokenizer

source = "Señor d’Artagnan escribió canción para Москва"
tokens = UnicodeTokenizer().tokenize(source)

for token in tokens:
    print(token.text, token.span, token.utf16_span)
```

The default tokenizer supports letters and combining marks from any script,
including Spanish accents, `ñ`, Cyrillic, Greek, Arabic, Devanagari, and
Armenian. It preserves internal straight or typographic apostrophes and the
ASCII, Unicode, and non-breaking hyphens commonly used in compound words.
Connectors are retained only when they occur between letters.

## Source-preserving positions

Every `WordToken` contains:

- `text`: the exact, unmodified source slice.
- `start` and `end`: half-open Python string offsets.
- `utf16_start` and `utf16_end`: half-open UTF-16 offsets suitable for future
  `QTextCursor` integration.
- `normalized`: an NFC view intended for dictionary lookup.

The source is never normalized in place. Therefore decomposed combining marks,
typographic apostrophes, characters outside the Basic Multilingual Plane, and
all later token positions remain exact:

```python
assert source[token.start:token.end] == token.text
```

The `(start, end)` pair is also suitable as the occurrence identifier for
`IgnoredWords.ignore_once()` while the document revision remains unchanged.
An editor must discard those occurrence identifiers after text edits that can
move or replace the token.

## Built-in exclusions

URLs beginning with `http://`, `https://`, `ftp://`, or `www.` and email
addresses are excluded as complete regions by default. Pure numbers such as
`123` and `2026`, and alphanumeric technical tokens such as `x3`, are also
excluded by default rather than partially tokenized.

Behavior is configurable:

```python
from pyqt6_linguistic_tools import TokenizerConfig, tokenize

config = TokenizerConfig(
    include_numbers=True,
    include_alphanumeric=False,
    excluded_tokens=frozenset(("ChordFlow", "ChordPages")),
    excluded_tokens_case_sensitive=False,
)
tokens = tokenize(source, config)
```

`exclude_urls`, `exclude_emails`, `allow_apostrophes`, and `allow_hyphens` can
also be changed explicitly. Exact technical exclusions are NFC-normalized.

## Host-supplied filters

Applications can provide any number of callables with this contract:

```python
def token_filter(token, original_text) -> bool:
    # Return True to retain the token or False to exclude it.
    ...
```

For example, a host can exclude tokens inside ChordPro directives without
adding ChordPro knowledge to the toolkit:

```python
def outside_directive(token, source):
    opening = source.rfind("{", 0, token.start)
    closing = source.rfind("}", 0, token.start)
    return opening <= closing

tokenizer = UnicodeTokenizer(token_filters=(outside_directive,))
```

Filters receive exact positions and the original text. They run after built-in
URL, email, numeric, alphanumeric, and configured-token exclusions. The core
remains independent of GuitarChordStudio and Qt widgets.
