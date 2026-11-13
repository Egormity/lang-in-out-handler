# Lang In/Out

A Linux desktop app for dictation, live bilingual captions, translation, and text to speech. Built with Python, PySide6, and SQLite. All language processing uses your OpenAI API key; no local model downloads or other providers are required.

## What it does

| Tool | Behavior |
| --- | --- |
| Voice input | Record the microphone once and transcribe on Stop, or transcribe consecutive chunks. Copy, speak, or paste each result into the active application. |
| Live captions | Capture the default speaker output, including browser and media-player audio. Show a minimal floating transcript and translation side by side, with Copy and Speak on every segment. |
| Translate | Translate text and read the original or translated text aloud. Shared playback controls let you replay, stop, or save generated audio from any tool. |
| Handwriting | Draw with a mouse or tablet pen, in the main window or an always-on-top floating canvas. Recognize automatically or use Send to transcribe, then copy or speak individual candidate readings. |
| History | Search, browse, copy, or speak locally saved text; delete history from the app. |

Each tool page has a collapsible **Settings** section for its model, language, instructions, and behavior. **Preferences** contains only the API connection, shared speech playback settings, and global shortcuts. Speech settings apply to every **Speak** button. Recognition instructions supply vocabulary/context to the speech model; they are not a general text-editing instruction.

Dropdowns accept selections only. Use **Refresh models** in Connection to load model choices available to your account. Number fields support direct typing plus large **− / +** buttons; opacity is displayed as a percentage. Every option has a **Reset** button. **Reset section** restores the current tool; **Save settings** applies its edits. Global **Reset all** stages defaults for every tool; **Save preferences** applies them. Resetting preferences keeps the API key and history; the separate Remove key and Delete history actions control those.

Floating windows contain content and actions only. Configure transcript/translation visibility, opacity, text size, and pinning under **Live captions → Settings**. Turning off **Show translation** also stops translation of new audio. Hiding the caption window does not stop capture; use **Stop**, the capture shortcut, or the tray menu.

## Install on Ubuntu / GNOME

Requires Python 3.12+, a graphical session, and PipeWire (`pw-record`, `pw-play`) or PulseAudio (`parec`, `paplay`). The installer uses `uv`; install it from [Astral's instructions](https://docs.astral.sh/uv/getting-started/installation/) if needed.

```sh
git clone https://github.com/Egormity/lang-in-out-handler.git
cd lang-in-out-handler
uv sync --locked --python 3.12
./scripts/install-desktop.sh
lang-in-out
```

The installer creates a user-local launcher and applications-menu entry. On Debian/Ubuntu it can download and extract missing Qt X11 cursor libraries into the virtual environment without sudo. FFmpeg for file conversion is included through `imageio-ffmpeg`.

Open **Preferences**, save your OpenAI API key, and use **Test connection / Refresh models**. Model discovery checks authentication; a successful paid transcription or translation also requires available API credit. Choose source languages, translation targets, models, and devices in each tool’s Settings section. Configure shared speech and shortcuts in Preferences.

If your desktop launcher does not inherit the terminal's proxy settings, set **Proxy URL** in Preferences. The saved HTTP(S)/SOCKS proxy applies to every mode, including Realtime speech; leaving it blank uses the process environment. Test connection uses the key and proxy currently entered in the form and saves them before checking, without discarding other pending preferences. Region/network restrictions are reported separately from invalid API keys.

Defaults: `gpt-transcribe` for speech recognition, `gpt-6-luna` for text translation, and `gpt-realtime-2.1-mini` for speech generation. Model choices depend on your API account and can be refreshed in Connection. The app uses bounded audio uploads for both once and chunk modes; live-only transcription models are not selectable suggestions.

### Translation and pronunciation

Translation returns three separate fields: translated text, a pronunciation guide for the original, and a pronunciation guide for the translation. Japanese uses romaji; other languages use appropriate romanization or IPA. Each guide can be selected or copied. The same guides accompany translated caption chunks and remain available in History.

**Reasoning** offers Low, Medium, and High on Translate and Handwriting, with **Medium** as the default. The control is disabled for models without reasoning support. Caption translation shares its model, target language, instructions, and reasoning with Translate; edit these from either page.

### Handwriting

Open **Handwriting** and draw with your mouse or tablet pen. Use **Undo** and **Clear** as needed. **Send to transcribe** works with automatic recognition turned off. Possible readings appear below the canvas, most likely first, with individual **Copy** and **Speak** buttons.

Choose **Float window** to keep handwriting above other applications. Configure **Keep on top** under **Handwriting → Settings**. **Dock** (or closing the floating window) returns the same canvas to the main window without losing strokes, recognized text, or a pending recognition. You can reopen it from the tray or with `lang-in-out --action drawing`. GNOME may ask you to click an unfocused window once before it can be pinned.

Pen handling supports Qt tablet events and driver-emulated mouse events. Pressure contact can start a stroke when a driver omits the initial tip-press event; hovering does not draw. Tablet behavior depends on the installed tablet driver and desktop session.

In **Handwriting → Settings**, choose the model, reasoning level, and writing language (or Auto detect), enable/disable automatic recognition, and set the pause from 0.2 to 10 seconds (1.2 seconds by default). Only the latest canvas snapshot is queued while recognition is busy, blank canvases are never sent, and results for an older drawing cannot overwrite newer content. Each automatic recognition is a billable image request.

Handwriting defaults to `gpt-6-luna`. The model returns a strict JSON object containing an array of candidate strings; the app validates, deduplicates, and displays that array as individual readings. A blank or unreadable image returns no candidates. Recognition accuracy depends on handwriting and model choice. Canvas images are not retained in history; recognized candidates are.

### Keyboard controls

| Default shortcut | Action |
| --- | --- |
| Super + Alt + I | Toggle microphone dictation |
| Super + Alt + O | Toggle output captions |
| Super + Alt + T | Translate clipboard text |
| Super + Alt + V | Read clipboard text aloud |

Shortcuts are registered through GNOME custom bindings, preserving other applications' bindings and checking for conflicts. On other desktops, map these commands using your desktop's shortcut settings:

```sh
lang-in-out --action input
lang-in-out --action output
lang-in-out --action translate
lang-in-out --action tts
lang-in-out --action drawing
```

Under **Voice input → Settings → After transcription**, choose **Copy to clipboard**, **Paste to selection**, or **Copy and paste**. Paste replaces selected text or inserts at the focused cursor. Paste-only temporarily uses the clipboard, then restores its previous preferred format; multi-format clipboard items retain one rich representation. Delivery runs in order without blocking the interface. When this app has focus, paste-only leaves the clipboard unchanged and keeps the transcript in the app.

The app uses a local single-instance connection, so shortcuts work whether the window is open or hidden. Closing the main window keeps the app in the system tray when a tray is available. Quit from the tray or run `lang-in-out --action quit`. Without a tray, closing the main window quits the app.

For background clipboard access and automatic insertion on Wayland, install `wl-clipboard` and configure `ydotool` with an accessible user socket. On X11, install `xdotool`. If insertion is unavailable, your transcript remains on the clipboard for Ctrl+V. Input launched with a shortcut does not activate the main window. If the app itself has focus, it copies instead of pasting into its own controls.

## Audio and captions

- The default microphone and speaker devices are never changed. Select a specific device in the corresponding capture tool’s Settings if desired.
- Chunk duration is independently configurable for voice input and captions from 2–30 seconds (5 seconds by default). Captions appear after each chunk and API processing. Chunks are processed in order; silence is skipped.
- Transcription and translation have separate queues, so recognized text can appear before its translation. If either queue falls too far behind, capture stops with a visible error rather than building an unbounded backlog.
- Stop flushes the last partial chunk. A single recording/import is limited to 10 minutes; use chunks for longer audio. A single upload must be below 25 MB.
- Chunk boundaries can split speech, and live requests have less context than complete recordings. Longer chunks trade latency for more context.
- Wayland sessions use native Qt Wayland so tablet input works throughout the interface. On GNOME, pinning uses the desktop's window menu and verifies its checked Always on Top state. This needs `ydotool` with an accessible user socket and system Python's GI/AT-SPI bindings (`python3-gi`, `gir1.2-atspi-2.0`). The helper targets only this app's active caption/handwriting window; it does not change global shortcuts or Shell settings. If pinning cannot be verified, the app reports the failure instead of claiming the window is pinned. X11 sessions use the normal keep-above window flag.
- Speech playback also appears in system-output capture when both are enabled. Stop captions if you do not want generated speech transcribed.

## Storage and privacy

Preferences and text history live in `$XDG_DATA_HOME/lang-in-out-handler/history.sqlite3` (normally `~/.local/share/lang-in-out-handler/`). Audio recordings are processed in memory or temporary files; they are not retained in history. Generated speech is temporary unless you save it.

The API key is stored in the desktop keyring. If the keyring is unavailable, the app uses a private `0600` credentials file in its application data directory and identifies that storage method in Preferences. API keys are never stored in SQLite or the repository. Remove the saved key in Preferences.

Starting capture or importing audio sends it to OpenAI for recognition. Translation sends text, speech generation sends the text you choose to read, and handwriting sends a snapshot of the canvas. Text and handwriting Responses requests disable server-side response storage with `store=False`; OpenAI's API data policies still apply. Requests use the official OpenAI endpoints. Existing HTTP(S)/SOCKS proxy settings are supported.

API charges are separate from app installation. The app does not purchase credit or configure automatic recharge. No user credentials, personal recordings, or transcript databases are distributed in this repository.

## Development and verification

```sh
uv sync --locked --python 3.12
QT_QPA_PLATFORM=offscreen uv run pytest -q
uv run ruff check src tests scripts
uv run python -m lang_handler
```

Tests cover storage, secret permissions, API payloads and errors, audio chunk boundaries, shutdown flushing, queue ordering and cancellation, handwriting debounce/stale results, UI settings, and desktop integration. They do not use a network API key.

For an explicit paid integration test using `OPENAI_API_KEY` or the app's saved key:

```sh
uv run python scripts/verify-api.py --allow-api-charge
```

This generates a short Japanese sample, transcribes it both whole and in chunks, and translates the transcript. It prints results without printing the key. Account errors are reported rather than silently switching credentials or models.

The initial version was verified on Ubuntu 26.04 / GNOME Wayland with a real OpenAI speech → transcription → translation round trip and actual default-output capture.

## Uninstall

Use `./scripts/uninstall-desktop.sh` to remove the app's launcher, desktop entry, and GNOME shortcuts. Your preferences/history/key remain available for reinstalling. To remove personal data, delete history and the saved key in Preferences before uninstalling.

## API references

- [OpenAI transcription](https://developers.openai.com/api/docs/guides/speech-to-text)
- [OpenAI text generation](https://developers.openai.com/api/docs/guides/text)
- [OpenAI Realtime audio](https://developers.openai.com/api/docs/guides/realtime)
- [OpenAI image recognition](https://developers.openai.com/api/docs/guides/images-vision)

