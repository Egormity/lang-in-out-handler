"""Language results shared by API, workflows, storage, and presentation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationResult:
    translation: str
    source_pronunciation: str = ""
    translation_pronunciation: str = ""
    source_correction: str = ""


@dataclass(frozen=True)
class CaptionRevision:
    segment_id: int
    source_text: str
    result: TranslationResult
