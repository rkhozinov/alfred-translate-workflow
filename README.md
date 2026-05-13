# Alfred Quick Translation

Inline translation in Alfred. No browser. Press <kbd>↩</kbd> to copy the translated text to the clipboard.

## Usage

Trigger with the `tr` keyword:

```
tr <text>
```

- <kbd>↩</kbd> — copy translation to clipboard
- <kbd>⇧</kbd><kbd>↩</kbd> — paste translation to the frontmost app
- <kbd>⌥</kbd><kbd>↩</kbd> — show translation in the Text View
- <kbd>⌘</kbd><kbd>↩</kbd> — copy back-translation (round-trip sanity check)
- <kbd>⌃</kbd><kbd>↩</kbd> — speak translation via macOS `say` (voice picked per target lang)

### Force target language

Prefix the query with `:<lang>` to override the smart detection:

```
tr :de hello world     → Hallo Welt
tr :es bonjour          → hola
tr :ja Привет           → こんにちは
```

If the lang code is unknown, the prefix is treated as plain text.

Each row's subtitle shows `<detected_src> → <target>`. Alternatives and dictionary entries appear as extra rows below the main translation when the source is a single word or short phrase.

### Smart direction

Source language is decided from the input itself, no extra keystrokes:

- Input contains **Cyrillic** characters → translate AWAY from `ru` (to the non-`ru` slot)
- Otherwise → translate TO `ru` (whichever slot is set to `ru`)

So `tr Привет` → English; `tr hello` → Russian; `tr Bonjour le monde` → Russian. If neither slot is `ru`, falls back to: Cyrillic→`input_language`, else `output_language`.

### Universal Action

Selected text → Alfred Universal Action → "Translate".

### Configuration

Open the workflow in Alfred preferences to change:

- **Target language** — default destination for non-Cyrillic input (default: `ru`)
- **Secondary language** — destination when Cyrillic is detected (default: `en`)
- **Keyword** — default `tr`

## Backend

Free unauthenticated `translate.googleapis.com/translate_a/single?client=gtx` endpoint with `dt=t&dt=at&dt=bd` for translation + alternatives + bilingual dictionary. No API key. Subject to silent throttling under heavy use.

### Cache

Translations are cached to `~/Library/Caches/gtranslate/` (7-day TTL, SHA256 key over `target | text`). Cache hits are ~1ms. Capped at 1000 entries by default — oldest entries are evicted probabilistically when the cap is exceeded. Override via `GTRANSLATE_CACHE_MAX` env var. Wipe with `rm -rf ~/Library/Caches/gtranslate`.

### Latency

| | cold (first request) | warm (cache hit) |
|---|---|---|
| p95 | ~800ms | ~1ms |

Cold doubles cost vs. forward-only because the back-translation (for ⌘↩) is fetched sequentially. Both calls land in cache, so repeats are instant.

## Requirements

- Alfred 5
- Python 3 (system Python on macOS works)

## Tests

```bash
python3 -m unittest discover tests -v                 # offline, < 1s
LIVE_TESTS=1 python3 -m unittest tests.test_live -v   # hits real endpoint
python3 tests/bench.py                                # p50 / p95 latency
```

## Credits

Forked from [meshchaninov/alfred-translate-workflow](https://github.com/meshchaninov/alfred-translate-workflow).
