"""Provider selectors retain inactive OpenAI preferences without cluttering Google settings."""

from PySide6.QtCore import Qt

from .common import label, selection_combo


def set_handwriting_language_provider(selector, provider):
    """Keep an existing Auto selection visible, but prevent selecting it for Google."""
    index = selector.findData("")
    if index < 0:
        return
    item = selector.model().item(index, selector.modelColumn())
    item.setEnabled(provider != "google")
    selector.setItemData(
        index,
        "Choose a language for Google handwriting." if provider == "google" else "Detect the written language.",
        Qt.ItemDataRole.ToolTipRole,
    )


class ProviderControls:
    def __init__(self, page, settings, form, key):
        self.form = form
        self.openai_rows = []
        self.language = None
        self.language_requirement = None
        self.selector = selection_combo([], "")
        self.selector.setAccessibleName("Recognition provider" if key == "drawing_provider" else "Translation provider")
        self.selector.addItem("Google", "google")
        self.selector.addItem("OpenAI", "openai")
        self.selector.setCurrentIndex(max(0, self.selector.findData(getattr(settings, key))))
        setattr(page, key, self.selector)
        page.fields.add(
            form, "Provider", key, self.selector,
            read=self.selector.currentData,
            write=lambda value: self.selector.setCurrentIndex(max(0, self.selector.findData(value))),
        )
        self.note = label(
            "Uses Google's public web service without an API key. "
            "It may stop working if the service changes.", True
        )
        form.addRow(self.note)
        if not hasattr(page, "provider_controls"):
            page.provider_controls = {}
        page.provider_controls[key] = self
        self.selector.currentIndexChanged.connect(self.refresh)

    def hide_for_google(self, *widgets):
        for widget in widgets:
            row, _ = self.form.getWidgetPosition(widget)
            if row < 0:
                row, _ = self.form.getWidgetPosition(widget.parentWidget())
            if row < 0:
                raise ValueError("Provider setting is not in this form.")
            self.openai_rows.append(row)
        self.refresh()

    def require_handwriting_language(self, selector):
        self.language = selector
        self.language_requirement = label("Choose a handwriting language for Google.", True)
        self.form.addRow(self.language_requirement)
        selector.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        google = self.selector.currentData() == "google"
        self.form.setRowVisible(self.note, google)
        for row in self.openai_rows:
            self.form.setRowVisible(row, not google)
        if self.language is not None:
            set_handwriting_language_provider(self.language, self.selector.currentData())
            self.form.setRowVisible(
                self.language_requirement,
                google and self.language.currentData() in (None, "", "auto"),
            )
