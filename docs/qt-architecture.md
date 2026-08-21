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

When used directly, `SpellCheckHighlighter` can resolve cache misses
synchronously for small standalone integrations. The decorator disables that
fallback and routes every miss through `AsyncSpellCheckController`.

## Asynchronous spelling checks

The decorator-owned controller collects unique unknown words emitted by the
highlighter. A single-shot `QTimer` restarts after each edit and uses the
configured `QtLinguisticSettings.debounce_ms` value, which defaults to 300 ms.
No engine work occurs in `highlightBlock()` when this integration is active.

After the debounce interval, one `QRunnable` checks the complete pending batch
sequentially through `LinguisticService` on `QThreadPool`. It never creates a
thread or runnable per word. The GUI thread only receives the final mapping,
places it in the highlighter cache and requests a new highlight pass.

Every request has a monotonically increasing generation. Editing, detaching,
disabling highlighting or switching documents signals cancellation to the
active worker. A check already executing is allowed to finish safely, while
remaining words observe the cancellation flag. Results are applied only when
their generation, locale, document and component lifetimes are still current.

Queued results temporarily retain the owning editor until delivery. This
closes the narrow Qt destruction window where an editor could otherwise vanish
between validating a worker result and repainting its document. Explicitly
deleting an editor with an active job is tested and safely disconnects the
queued receiver.

`AsyncSpellCheckController` exposes job, discard and idle signals plus small
read-only counters for diagnostics and tests. Applications normally interact
with it through `integration.async_controller`; they do not need to manage a
thread pool themselves. A strict-mode service exception is returned through
`job_failed`, restores the controller to idle and never modifies the document.

## Context-menu integration

`LinguisticContextMenu` augments the editor's standard menu and preserves
actions already registered by the host. Misspelled words receive bounded
suggestions plus `Ignore`, `Ignore All` and `Add to Dictionary`. Correctly
spelled words never manufacture a spelling error merely to expose `Synonyms`,
`Open Thesaurus…` or `Language`.

```python
integration.context_menu.set_action_enabled("ignore_all", False)
integration.context_menu.open_thesaurus_requested.connect(open_thesaurus)
```

`Ignore` records only the selected UTF-16 occurrence. `Ignore All` records the
word for the current document, and adding to the dictionary writes to the
separate persistent personal dictionary. Each operation invalidates the
relevant visual cache without attempting to edit an installed system
dictionary.

Suggestions and synonyms use `suggestion_limit` and `synonym_limit` from
`QtLinguisticSettings`. Additional synonyms are represented by the translatable
`More synonyms…` action and `more_synonyms_requested` signal; Phase 26 connects
that signal to the complete reusable thesaurus dialog.

Every toolkit-owned label uses English source text through the
`PyQt6LinguisticTools` Qt translation context. Dictionary suggestions, synonyms
and localized language display names remain source data and are not translated
again.

Applications using Qt's `CustomContextMenu` policy remain in complete control:
the decorator does not consume their event. They call `populate_menu()` with
their menu and cursor to append the same linguistic actions to their own
`QMenu`. For other policies, right-click and keyboard context-menu events are
integrated automatically. Registered context-action providers receive the
editor, menu and current `WordToken`, and may return additional `QAction`
objects.

## Thesaurus dialog

`ThesaurusDialog` is a modeless, reusable browser over engine-neutral
`ThesaurusEntry` and `ThesaurusMeaning` values. It displays the current query,
parts of speech, meanings and nested synonyms, with an explicit no-results
state. Search, Search Selected, Back and Forward maintain a branching history:
a new search after navigating backward discards the obsolete forward branch.

```python
from pyqt6_linguistic_tools.qt import ThesaurusDialog

dialog = ThesaurusDialog(service, "bright")
dialog.replacement_requested.connect(replace_word)
dialog.show()
```

The context-menu component opens this dialog automatically for both
`Open Thesaurus…` and `More synonyms…`. It saves a copy of the exact editor
cursor and the original word. Navigation changes only the thesaurus query;
replacement continues to validate the original source through
`replace_word_at_cursor()`. If the document changed meanwhile, no text is
replaced.

`preserve_simple_capitalization()` handles only unambiguous patterns:
lowercase remains unchanged, title-case source text capitalizes an all-lowercase
replacement, and uppercase source text uppercases the replacement. Mixed-case
source words and already mixed-case replacements remain untouched. The toolkit
does not guess inflection, conjugation, number, gender or other morphological
transformations.

All labels and status messages use English source text in the
`PyQt6LinguisticTools.ThesaurusDialog` Qt translation context. Words, meanings,
parts of speech and synonyms originate in the selected dictionary and are not
translated by the widget.
