# Qt integration architecture

The reusable linguistic core and the optional PyQt6 user interface have a
strict one-way dependency boundary:

```text
Host application (ChordFlow, ChordPages, or another PyQt6 project)
                              │
                              ▼
              pyqt6_linguistic_tools.qt
            ┌───────────┬───────────────┐
            │ decorator │ Qt components │
            └─────┬─────┴───────┬───────┘
                  │             │
                  └──────┬──────┘
                         ▼
               LinguisticService + tokenizer
                         │
                         ▼
       Registry / backends / personal and ignored words
```

Core modules never import the `qt` package. Qt modules may import and compose
the core. Host applications interact with public toolkit APIs and do not import
Spylls, PyThes, or GuitarChordStudio-specific code through this layer.

## Optional installation

Run these installation commands inside an activated virtual environment. The
repository README explains `venv`, externally managed Linux installations,
direct source usage without `pip`, and application packaging in detail.

The core remains installable without Qt:

```bash
python -m pip install pyqt6-linguistic-tools
```

Applications wanting widget integration install the optional dependency:

```bash
python -m pip install 'pyqt6-linguistic-tools[qt]'
```

Importing either `pyqt6_linguistic_tools` or the lightweight
`pyqt6_linguistic_tools.qt` boundary does not eagerly import `PyQt6.QtCore` or
`PyQt6.QtWidgets`. This permits command-line tools, tests, servers, and other
non-GUI consumers to use the same wheel.

`pyqt6_available()` performs discovery without importing Qt. Widget components
will call `require_pyqt6()` when they are constructed. It imports `QtCore` on
demand, checks the required PyQt version, and raises the stable
`QtIntegrationUnavailableError` when the optional runtime is unavailable.

```python
from pyqt6_linguistic_tools.qt import pyqt6_available, require_pyqt6

if pyqt6_available():
    versions = require_pyqt6("6.6")
    print(versions.qt_version, versions.pyqt_version)
```

## Package responsibilities

```text
qt/
├── _compat.py             lazy optional-dependency and version boundary
├── decorator.py           lifecycle and coordination for attached editors
├── spell_highlighter.py   narrow cached spelling visualization
├── context_menu.py        non-destructive, translatable editor actions
├── thesaurus_dialog.py    reusable meanings, navigation, and replacement UI
├── dictionary_manager.py  source/capability display and safe app data actions
└── settings.py            validated Qt integration defaults
```

The feature modules exist now as stable ownership boundaries. Their concrete
widgets are introduced in their corresponding roadmap phases, avoiding empty
or misleading public widget classes before their lifecycle contracts are
implemented and tested.

`decorator.py` is the only coordinator. It must not absorb tokenization,
dictionary discovery, or engine logic. The highlighter queries cached spelling
only. Context-menu code requests suggestions only when a menu is opened. Dialog
and manager code use engine-neutral models from the core.

## Shared settings contract

`QtLinguisticSettings` centralizes validated runtime defaults used by upcoming
components:

- spelling, highlighting, thesaurus, and context-menu enable states;
- eight inline spelling suggestions;
- twelve inline synonyms;
- a 300 ms asynchronous typing debounce.

It is an immutable value object and performs no persistence. Phase 27 will add
a `QSettings` adapter without making core service preferences depend on Qt.

## Translation and host ownership rules

Future library-owned action and widget strings use English source text through
Qt translation contexts. The host continues to own its editor, document,
signals, context-menu actions, application settings, and event loop.

Attaching the toolkit must be reversible. No component may require applications
to subclass `QTextEdit` or `QPlainTextEdit`, replace their documents, or discard
existing context-menu behavior. These lifecycle requirements are implemented
and tested beginning with Phase 20.

## Editor decorator

`LinguisticTextEditDecorator` attaches the integration state to an existing
`QTextEdit` or `QPlainTextEdit`. It does not replace the editor, its document,
its signals, or its context-menu policy:

```python
from PyQt6.QtWidgets import QTextEdit

from pyqt6_linguistic_tools import LinguisticService
from pyqt6_linguistic_tools.qt import LinguisticTextEditDecorator

editor = QTextEdit()
service = LinguisticService(language="es_EC")
integration = LinguisticTextEditDecorator(editor, service)

integration.set_spellcheck_enabled(False)
integration.set_thesaurus_enabled(True)
integration.set_enabled(False)
integration.detach()
```

The host owns `service`. While attached, the editor owns the decorator through
Qt parent ownership. Calling `detach()` removes the event filters and Qt parent
relationship, permitting the same decorator to be attached to another
supported editor. Only one decorator may be attached to an editor at a time.

Enable states belong to the decorator and are intentionally independent of the
service-wide enable states. Consequently, ChordFlow and ChordPages can share a
service while enabling different editor features. The master `set_enabled()`
switch temporarily suspends all integration features without forgetting their
individual preferences.

Applications can register domain-specific `TokenFilter` callbacks with
`add_token_filter()`. `create_tokenizer()` combines them with any filters from
the tokenizer passed to the constructor without mutating that tokenizer. This
allows applications such as GuitarChordStudio to exclude chord notation while
the reusable toolkit remains music-domain neutral.

Applications can also register callbacks with
`add_context_action_provider()`. The decorator retains these callbacks without
altering the host menu. The context-menu component introduced in Phase 25 will
invoke them while additively composing linguistic and application actions.

## Qt text-editor word operations

The decorator exposes synchronous, cursor-oriented building blocks for an
existing `QTextEdit` or `QPlainTextEdit`:

```python
token = integration.word_at_cursor()

if token is not None and integration.check_word_at_cursor() is False:
    suggestions = integration.suggestions_at_cursor()
    if suggestions:
        integration.replace_word_at_cursor(
            suggestions[0],
            expected_word=token.text,
        )
```

`word_at_cursor()` uses `UnicodeTokenizer`, including application token
filters, instead of Qt's simpler `WordUnderCursor` boundary. Apostrophes,
hyphens and multilingual text therefore follow the same rules as the core.
For performance, cursor lookup tokenizes only the current `QTextBlock`; it does
not copy or tokenize the complete document. The returned `WordToken` therefore
contains block-local Python ranges and document-global UTF-16 ranges. The
latter are used for exact `QTextCursor` selections even when preceding text
contains characters outside the Unicode Basic Multilingual Plane.

`cursor_for_word()` returns `None` if a token became stale after an edit.
Likewise, the optional `expected_word` argument prevents a delayed suggestion
from replacing a different word. Replacement is one undoable edit, preserves
the surrounding rich-text document, refuses read-only editors and permits
single-line phrases for future thesaurus replacements.

These operations do not underline text or create menus. The highlighter,
asynchronous scheduler and additive context menu remain isolated in Phases 23,
24 and 25 respectively.

The `QPlainTextEdit` integration is tested with documents containing 20,001
blocks. Read-only cursor queries do not change the document revision, emit
`textChanged`, request viewport updates, or call `toPlainText()` for the full
document. This stable structural assertion is preferred to a fragile
machine-specific wall-clock threshold.

## Spell-check highlighter

`SpellCheckHighlighter` is a reusable `QSyntaxHighlighter` for both supported
editor documents. The decorator creates and owns one automatically, while
applications may also use it directly:

```python
from pyqt6_linguistic_tools.qt import SpellCheckHighlighter

highlighter = SpellCheckHighlighter(editor.document(), service)
highlighter.set_enabled(False)
```

The highlighter tokenizes only the block supplied by Qt, applies registered
filters and underlines rejected words with a red spell-check wave. It never
requests suggestions, scans dictionary directories, selects an engine, or
downloads resources. Linguistic resolution remains behind
`LinguisticService`.

Spelling statuses use a bounded 2,048-entry LRU cache keyed by locale and
normalized word. Rehighlighting unchanged text therefore does not recheck the
same word. Applications can inspect `cache_stats()` and configure the bound
through `cache_size` when constructing a standalone highlighter.

The visual style is a copied `QTextCharFormat` and can be replaced without
sharing mutable format state:

```python
from PyQt6.QtGui import QColor, QTextCharFormat

style = QTextCharFormat()
style.setUnderlineColor(QColor("blue"))
style.setUnderlineStyle(QTextCharFormat.UnderlineStyle.DashUnderline)
integration.highlighter.set_misspelling_format(style)
```

After changing a personal or ignored word, the host calls
`integration.invalidate_spelling(word)`. The cache entry is removed and only
blocks containing that word are passed to `rehighlightBlock()`. Passing no word
clears the complete local cache, which is appropriate after a broader external
dictionary change.

Phase 23 performs cache misses synchronously through the service. Phase 24
replaces that initial work with debounced, cancellable background jobs so a
large dictionary can never delay the user interface while typing.
