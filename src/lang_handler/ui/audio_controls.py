"""Audio source selection and readable signal level display."""

import math

from PySide6.QtWidgets import QComboBox, QProgressBar


class AudioSourceCombo(QComboBox):
    """Show friendly device labels while persisting the underlying source name."""

    def __init__(self, monitor: bool, value: str = ""):
        super().__init__()
        self.monitor = monitor
        self.setEditable(False)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setToolTip("Choose a detected audio device.")
        self.set_sources([])
        self.set_value(value)

    def source_name(self) -> str:
        return self.currentData() or ""

    def set_value(self, value: str):
        index = self.findData(value)
        if index >= 0:
            self.setCurrentIndex(index)
        else:
            self.addItem(f"Unavailable device: {value}", value)
            self.setCurrentIndex(self.count() - 1)

    def set_sources(self, sources: list[dict]):
        selected = self.source_name()
        self.blockSignals(True)
        self.clear()
        self.addItem("Default speaker monitor" if self.monitor else "System default", "")
        seen = set()
        for source in sources:
            name = str(source.get("name", ""))
            is_monitor = source.get("is_monitor", name.endswith(".monitor"))
            if not name or name in seen or bool(is_monitor) != self.monitor:
                continue
            seen.add(name)
            self.addItem(str(source.get("description") or name), name)
        self.set_value(selected)
        self.blockSignals(False)


class AudioLevel(QProgressBar):
    """Show a decibel scale so quiet, valid speech is still visibly active."""

    def __init__(self):
        super().__init__()
        self.setObjectName("audioLevel")
        self.setRange(0, 60)
        self.setFixedHeight(22)
        self.setTextVisible(True)
        self.setToolTip(
            "Incoming audio level. If this stays silent during playback, check the source in Preferences."
        )
        self.set_level(0)

    def set_level(self, amplitude: float):
        if not math.isfinite(amplitude) or amplitude <= 0:
            self.setValue(0)
            self.setFormat("No audio detected")
            return
        decibels = max(-60.0, 20 * math.log10(min(amplitude, 1.0)))
        self.setValue(round(decibels + 60))
        self.setFormat(f"Audio level: {decibels:.0f} dB")
