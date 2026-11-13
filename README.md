# Lang In/Out

A Linux desktop app for dictation, live bilingual captions, translation, and text to speech. Built with Python, PySide6, and SQLite. Draw and Translate use Google by default, without an API key. Dictation, audio transcription, and read-aloud use your OpenAI API key. No local model downloads are required.

## What it does

| Tool | Behavior |
| --- | --- |
| Dictate | Record the microphone once and transcribe on Stop, or transcribe consecutive chunks. Each recognition appears separately, with Copy and Speak actions. Short sounds confirm recording start and end. |
| Captions | Capture the default speaker output, including browser and media-player audio. Show one continuous transcript and translation side by side. New context can revise recent translations in place. |
| Translate | Translate text with pronunciation guides and optional “Did you mean?” suggestions. Choose Use to apply a correction and translate it. Original text stays unchanged otherwise. |
| Draw | Draw with a mouse or tablet pen, in the main window or an always-on-top floating canvas. Recognize automatically or use Recognize, then copy or speak individual candidate readings. |
| History | Each Dictate or Captions recording/import appears as one combined entry. Search, copy, or speak the full session; delete history from the app. |

The sidebar keeps Dictate, Captions, Translate, and Draw one click away. Primary actions sit at the top of each page. Each tool’s **settings gear** opens its settings inside the app; **Back** returns to the tool. Source and target language selectors sit directly above their text panes; Draw has its language selector above the canvas. **Preferences** contains only the API connection, shared speech playback settings, and global shortcuts. Speech settings apply to every **Speak** button. Recognition instructions supply vocabulary/context to the speech model; they are not a general text-editing instruction.

Dropdowns accept selections only and show at most eight scrollable rows in a menu no wider than 360 logical pixels, including at high display scaling. Use **Refresh models** in Connection to load model choices available to your account. Number fields support direct typing plus large **− / +** buttons; opacity is displayed as a percentage. Every option has a compact **Reset** icon with a tooltip. **Reset section** restores the current tool; **Save** applies its edits. **Discard changes** restores saved values; reopening a settings page also reloads saved values. Active drafts survive unrelated background updates. Global **Reset all** stages defaults for every tool; **Save preferences** applies them. Resetting preferences keeps the API key and history; the separate Remove key and Delete history actions control those.

Floating windows contain content and actions only. Configure transcript/translation visibility, opacity, text size, and pinning under **Captions → settings gear**. Turning off **Show translation** also stops translation of new audio. Hiding the caption window does not stop capture; use **Stop**, the capture shortcut, or the tray menu.

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

Draw and Translate work immediately with Google; select a writing language before drawing. For speech features or the optional OpenAI provider, open **Preferences**, save your OpenAI API key, and use **Test connection / Refresh models**. Model discovery checks authentication; a successful paid transcription or translation also requires available API credit. Choose source languages, translation targets, models, and devices in each tool’s Settings section. Configure shared speech and shortcuts in Preferences.

The proxy field is optional. With **Proxy override** empty, the app uses the environment's HTTPS/ALL proxy when set, otherwise your GNOME system proxy. Desktop launches therefore pick up Ubuntu's configured proxy automatically. GNOME's resolver handles manual settings, exclusions, and automatic/PAC configuration when supported by the installed GIO backend. With no configured proxy, requests connect directly. Proxy rules and exclusions are resolved for each provider’s destination; Realtime speech uses the OpenAI HTTPS route.

Set **Proxy override** only to use a different HTTP(S)/SOCKS5 proxy for this app. An override takes precedence over automatic proxy and bypass settings. System proxy lookup uses the system Python's GIO integration (`python3-gi` and `glib-networking`, normally present on GNOME); when that integration is unavailable, only environment/override discovery is available. Resolution failures are reported instead of silently bypassing a configured proxy. System settings are re-read for new requests. Test connection uses the key and override currently entered in the form and saves them without discarding other pending preferences.

Defaults: Google for handwriting and translation, `gpt-transcribe` for speech recognition, and `gpt-realtime-2.1-mini` for speech generation. Each Draw/Translate settings page offers Google or OpenAI; caption translation shares the Translate provider. Model choices depend on your API account and can be refreshed in Connection. The app uses bounded audio uploads for both once and chunk modes; live-only transcription models are not selectable suggestions.

### Translation and pronunciation

Google translation returns text and any pronunciation guides or correction suggestions supplied by the service; it does not synthesize missing guides. OpenAI translation additionally supports custom instructions and requests pronunciation guides for both sides, using romaji for Japanese and appropriate romanization or IPA for other languages. Guides remain selectable for copying with the keyboard; the extra pronunciation copy buttons are omitted. The same guides accompany continuous captions and remain available in History. Select text before clicking Speak to read only that passage; otherwise Speak reads the pane. Speech requests are limited to 4,096 characters. Once audio is generated, its Speak button becomes an inline player with play/pause, seeking, and 0.5–2× playback speed. Replay and speed changes use the existing file without another API request. Editing the source text clears its outdated player. You can save the last generated WAV under Preferences → Shared speech.

**Reasoning** offers Low, Medium, and High when OpenAI is selected on Translate and Handwriting. Model, reasoning, and instruction controls are hidden for Google, which does not accept custom prompts. Translation defaults to **Medium**; handwriting defaults to **Low**. The control is disabled for models without reasoning support. Caption translation shares its model, target language, instructions, and reasoning with Translate; edit these from either page.

### Handwriting

Open **Draw** and draw with your mouse or tablet pen. Under **Draw → settings gear → Canvas theme**, choose **Light** or **Dark** and Save. Ink automatically contrasts with the background; the choice applies to both docked and floating views and preserves the drawing and undo/redo history. Google receives ordered pen coordinates and timing, independent of canvas colors. Optional OpenAI recognition uses a black-on-white image in either theme. Use **Undo** (**Ctrl+Z**), **Redo** (**Ctrl+Shift+Z**), and **Clear** as needed. Clear can also be undone. The shortcuts work in the main and floating canvas; settings text fields keep their normal text undo. Drawing a new stroke after Undo starts a new history branch. **Recognize** works with automatic recognition turned off. Possible readings appear below the canvas, most likely first, with individual **Copy** and **Speak** buttons.

Choose **Float** to keep handwriting above other applications. Configure **Keep on top** under **Draw → settings gear**. **Dock** (or closing the floating window) returns the same canvas to the main window without losing strokes, recognized text, or a pending recognition. You can reopen it from the tray or with `lang-in-out --action drawing`. GNOME may ask you to click an unfocused window once before it can be pinned.

Pen handling supports Qt tablet events and driver-emulated mouse events. Pressure contact can start a stroke when a driver omits the initial tip-press event; hovering does not draw. Tablet behavior depends on the installed tablet driver and desktop session.

In **Draw → settings gear**, choose the provider and writing language (Japanese by default; Google requires an explicit language), enable/disable automatic recognition, and set the pause from 0.2 to 10 seconds (1.2 seconds by default). Progress appears on the Recognize button. Repeated sends of the same active snapshot share one request. Only the latest canvas snapshot is queued while recognition is busy, blank canvases are never sent, and results for an older drawing cannot overwrite newer content. Google sends stroke data without an OpenAI request. With OpenAI selected, each recognition is a billable image request.

Handwriting defaults to Google Input Tools, sending stroke boundaries, coordinates, and elapsed timing and displaying its ranked candidates. The optional OpenAI provider defaults to `gpt-6.1-sol` with Low reasoning. Recognition images are cropped to the ink with a white margin and retain their aspect ratio, with a maximum dimension of 1,280 pixels. The prompt favors complete words and adds alternatives only when the strokes are genuinely ambiguous; it does not force three guesses. The model returns a strict JSON object containing an array of candidate strings; the app validates, deduplicates, and displays that array as individual readings. A blank or unreadable image returns no candidates. Recognition accuracy depends on handwriting and model choice. Canvas images are not retained in history; recognized candidates are.

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

Under **Dictate → settings gear → After transcription**, choose **Copy to clipboard**, **Paste to selection**, or **Copy and paste**. Paste replaces selected text or inserts at the focused cursor. Paste-only temporarily uses the clipboard, then restores its previous preferred format; multi-format clipboard items retain one rich representation. Delivery runs in order without blocking the interface. When this app has focus, paste-only leaves the clipboard unchanged and keeps the transcript in the app.

The app uses a local single-instance connection, so shortcuts work whether the window is open or hidden. Closing the main window keeps the app in the system tray when a tray is available. Quit from the tray or run `lang-in-out --action quit`. Without a tray, closing the main window quits the app.

For background clipboard access and automatic insertion on Wayland, install `wl-clipboard` and configure `ydotool` with an accessible user socket. On X11, install `xdotool`. If insertion is unavailable, your transcript remains on the clipboard for Ctrl+V. Input launched with a shortcut does not activate the main window. If the app itself has focus, it copies instead of pasting into its own controls.

## Audio and captions

Captions are continuous documents. Audio still arrives in bounded chunks internally, but the translator receives recent source context and can revise earlier wording. The main and floating windows replace the affected text in place, while preserving selection and scroll position. History combines each recording or imported file into one entry, while revisions update its underlying segments in place. Separate recordings stay separate. Older history lacks session identifiers, so those existing entries remain unchanged.

With OpenAI, the revision window contains the last six recognized segments, with about 6,000 source characters maximum (a single longer recording remains intact). Google retranslates a continuous batch of up to six segments / 5,000 characters, then freezes that batch and starts the next. These batches do not overlap, so text is neither repeated nor dropped as new audio arrives. Google reports an error for a single passage exceeding its request limit instead of truncating it. Older translated text stays visible and saved, but stops being reconsidered once it leaves this window. At most one revision request runs with one newest snapshot waiting. Newer snapshots replace redundant waiting requests. A new capture session or translation-configuration change starts a fresh context. File imports use the same revision behavior.

- The default microphone and speaker devices are never changed. Select a specific device in the corresponding capture tool’s Settings if desired.
- Chunk duration is independently configurable for voice input and captions from 2–30 seconds (5 seconds by default). Captions appear after each chunk and API processing. Chunks are processed in order; silence is skipped.
- Transcription and translation run independently, so recognized text appears immediately and is saved even if translation fails. If processing falls too far behind, capture stops with a visible error instead of silently losing untranslated text.
- Stop flushes the last partial chunk. A single recording/import is limited to 10 minutes; use chunks for longer audio. A single upload must be below 25 MB.
- Chunk boundaries can split speech. Recent context lets translation correct earlier interpretations, but transcription itself stays faithful to the speech-recognition result. Longer chunks trade latency for more audio context.
- Wayland sessions use native Qt Wayland so tablet input works throughout the interface. On GNOME, pinning uses the desktop's window menu and verifies its checked Always on Top state. This needs `ydotool` with an accessible user socket and system Python's GI/AT-SPI bindings (`python3-gi`, `gir1.2-atspi-2.0`). The helper targets only this app's active caption/handwriting window; it does not change global shortcuts or Shell settings. If pinning cannot be verified, the app reports the failure instead of claiming the window is pinned. X11 sessions use the normal keep-above window flag.
- Speech playback also appears in system-output capture when both are enabled. Stop captions if you do not want generated speech transcribed.

Copy buttons briefly show a checkmark when copying succeeds. Status and error messages appear as dismissible toasts without shifting the page.

OpenAI custom instructions start empty. Its settings show the app’s required instructions above the optional custom field, read-only and scrollable. Custom preferences can refine style or vocabulary while the app keeps its required task and output format.

## Storage and privacy

Preferences and text history live in `$XDG_DATA_HOME/lang-in-out-handler/history.sqlite3` (normally `~/.local/share/lang-in-out-handler/`). Audio recordings are processed in memory or temporary files; they are not retained in history. Generated speech is temporary unless you save it.

The API key is stored in the desktop keyring. If the keyring is unavailable, the app uses a private `0600` credentials file in its application data directory and identifies that storage method in Preferences. API keys are never stored in SQLite or the repository. Remove the saved key in Preferences.

Starting capture or importing audio sends it to OpenAI for recognition, and speech generation sends the text you choose to read. Google translation sends text to Google; Google handwriting sends pen strokes to Google. These public web services are unofficial interfaces, separate from the paid Google Cloud Translation API; they can change, rate-limit, or become unavailable. No Google account, API key, or browser cookies are used. Failures are shown explicitly, without automatically falling back to a paid OpenAI request. The optional OpenAI translation and image-recognition paths use official OpenAI endpoints and disable Responses storage with `store=False`; each provider’s data policies still apply. Existing HTTP(S)/SOCKS proxy settings are supported.

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

