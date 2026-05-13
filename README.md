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

![preview](images/img1.png)
![preview2](images/img2.png)
![preview3](images/img3.png)

### Smart direction

Source language is decided from the input itself, no extra keystrokes:

- Input contains **Cyrillic** characters → translate to **Secondary language** (default `en`)
- Otherwise → translate to **Target language** (default `ru`)

So `tr Привет` → English; `tr hello` → Russian; `tr Bonjour le monde` → Russian.

This avoids a round-trip detect-then-retry call and halves latency for non-Cyrillic input.

### Universal Action

Selected text → Alfred Universal Action → "Translate".

### Configuration

Open the workflow in Alfred preferences to change:

- **Target language** — default destination for non-Cyrillic input (default: `ru`)
- **Secondary language** — destination when Cyrillic is detected (default: `en`)
- **Keyword** — default `tr`

## Backend

Free unauthenticated `translate.googleapis.com/translate_a/single?client=gtx` endpoint. No API key. Subject to silent throttling under heavy use.

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
