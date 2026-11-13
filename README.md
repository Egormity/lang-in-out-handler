# Lang In/Out

A Linux desktop app for dictation, live bilingual captions, translation, and text to speech. Built with Python, PySide6, and SQLite. All language processing uses your OpenAI API key; no local model downloads or other providers are required.

## What it does

| Tool | Behavior |
| --- | --- |
| Voice input | Record the microphone once and transcribe on Stop, or transcribe consecutive chunks. Copy the result or paste it into the active application. |
| Live captions | Capture the default speaker output, including browser and media-player audio. Show a floating transcript and translation side by side. |
| Translate | Translate typed, pasted, or clipboard text into your chosen language. |
| Text to speech | Generate and play AI speech from text; save the generated WAV file. |
| Handwriting | Draw with a mouse or pen; recognize automatically after a configurable pause or use Send to transcribe. |
| History | Browse and copy locally saved transcripts and translations; delete history from the app. |

Each mode has an instructions field. Recognition instructions supply vocabulary/context to the speech model; they are not a general text-editing instruction. Translation and speech instructions control language style and delivery.

The floating caption window has independent **Transcript** and **Translation** visibility controls. **Translate audio** switches translation API requests on/off. Hiding the window or a pane does not stop capture. Use **Stop**, the capture shortcut, or the tray menu to stop.

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

Open **Preferences**, save your OpenAI API key, and use **Test connection / Refresh models**. Model discovery checks authentication; a successful paid transcription or translation also requires available API credit. Set the source language, translation target, models, devices, and shortcuts, then save preferences.

If your desktop launcher does not inherit the terminal's proxy settings, set **Proxy URL** in Preferences. The saved HTTP(S)/SOCKS proxy applies to every mode, including Realtime speech; leaving it blank uses the process environment. Test connection uses the key and proxy currently entered in the form and saves them before checking, without discarding other pending preferences. Region/network restrictions are reported separately from invalid API keys.

Defaults: `gpt-transcribe` for speech recognition, `gpt-6-luna` for text translation, and `gpt-realtime-2.1-mini` for speech generation. Model fields are editable. Available models depend on your API account. The app uses bounded audio uploads for both once and chunk modes; live-only transcription models are not selectable suggestions.

### Handwriting

Open **Handwriting** and draw with your mouse or tablet pen. Use **Undo stroke** and **Clear canvas** as needed. **Send to transcribe** works with automatic recognition turned off. Copy or edit the recognized text below the canvas.

In **Preferences**, choose the handwriting model, enable/disable automatic recognition, and set the pause from 0.2 to 10 seconds (1.2 seconds by default). Only the latest canvas snapshot is queued while recognition is busy, blank canvases are never sent, and results for an older drawing cannot overwrite newer content. Each automatic recognition is a billable image request.

Handwriting defaults to `gpt-6.1-sol`, which correctly recognized the Japanese sample used in live verification. Recognition accuracy still depends on handwriting and model choice. Canvas images are not retained in history; recognized text is.

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
```

The app uses a local single-instance connection, so shortcuts work whether the window is open or hidden. Closing the main window keeps the app in the system tray when a tray is available. Quit from the tray or run `lang-in-out --action quit`. Without a tray, closing the main window quits the app.

For automatic insertion on Wayland, install/configure `ydotool` with an accessible user socket. On X11, install `xdotool`. If insertion is unavailable, your transcript remains on the clipboard for Ctrl+V. Input launched with a shortcut does not activate the main window. If the app itself has focus, it copies instead of pasting into its own controls.

## Audio and captions

- The default microphone and speaker devices are never changed. Select a specific device in Preferences if desired.
- Chunk duration is configurable from 2–30 seconds (5 seconds by default). Captions appear after each chunk and API processing. Chunks are processed in order; silence is skipped.
- Transcription and translation have separate queues, so recognized text can appear before its translation. If either queue falls too far behind, capture stops with a visible error rather than building an unbounded backlog.
- Stop flushes the last partial chunk. A single recording/import is limited to 10 minutes; use chunks for longer audio. A single upload must be below 25 MB.
- Chunk boundaries can split speech, and live requests have less context than complete recordings. Longer chunks trade latency for more context.
- On GNOME Wayland, the app uses XWayland to support a real keep-above caption window. The window remains movable and resizable. Set `QT_QPA_PLATFORM=wayland` explicitly to use native Wayland, where keep-above depends on the compositor.
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

