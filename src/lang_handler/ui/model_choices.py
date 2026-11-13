"""Model discovery updates only selectors owned by the current settings panel."""


def update_model_choices(models, model_ids):
    for key, widget in models.items():
        selected = widget.currentText()
        if key in ("input_model", "output_model"):
            filtered = [m for m in model_ids if "transcribe" in m or "whisper" in m]
            filtered = [m for m in filtered if "realtime" not in m and "live" not in m]
        elif key == "tts_model":
            filtered = [m for m in model_ids if "tts" in m or "realtime" in m]
            filtered = [
                m for m in filtered
                if not any(part in m for part in ("translate", "whisper", "transcribe"))
            ]
        else:
            excluded = ("audio", "realtime", "transcribe", "tts", "image", "embedding", "search", "live")
            filtered = [
                m for m in model_ids
                if m.startswith(("gpt-", "o1", "o3", "o4"))
                and not any(x in m for x in excluded)
            ]
        widget.blockSignals(True)
        widget.clear()
        widget.addItems(sorted({*filtered, selected}))
        widget.setCurrentText(selected)
        widget.blockSignals(False)
