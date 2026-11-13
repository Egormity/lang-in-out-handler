"""Keep Google phrase batches intact while OpenAI revises a sliding window."""

from .caption_context import MAX_CONTEXT_SEGMENTS, trim_context
from .google_inputs import GOOGLE_TRANSLATION_MAX_CHARS


def translation_configuration(settings):
    values = (settings.translation_provider, settings.target_language,
              settings.translation_enabled, settings.api_proxy_url, settings.output_language)
    if settings.translation_provider == "openai":
        values += (settings.translation_model, settings.translation_instructions,
                   settings.translation_reasoning)
    return values


def next_context(context, segment, provider):
    if any(identifier == segment[0] for identifier, _ in context):
        return [segment if identifier == segment[0] else (identifier, text)
                for identifier, text in context]
    if provider != "google":
        return trim_context([*context, segment])
    # Google translates a continuous passage, without stable per-chunk IDs.
    # Freeze a complete batch before starting another; sliding an aggregate
    # translation across overlapping batches would duplicate earlier words.
    combined = [*context, segment]
    if (len(combined) > MAX_CONTEXT_SEGMENTS
            or sum(len(text) + 1 for _, text in combined) > GOOGLE_TRANSLATION_MAX_CHARS):
        return [segment]
    return combined
