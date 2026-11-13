"""Audio source selection using detected desktop devices."""

from .dropdown import CompactComboBox


class AudioSourceCombo(CompactComboBox):
    """Show friendly device labels while persisting the underlying source name."""

    def __init__(self, monitor: bool, value: str = ""):
        super().__init__()
        self.monitor = monitor
        self.setEditable(False)
        self.setMinimumContentsLength(16)
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
