"""Language results shared by API, workflows, storage, and presentation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationResult:
    translation: str
    source_pronunciation: str = ""
    translation_pronunciation: str = ""
