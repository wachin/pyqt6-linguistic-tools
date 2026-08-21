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
