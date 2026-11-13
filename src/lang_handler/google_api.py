"""Google's undocumented translation and ordered-ink web services.

These services require no OpenAI key. They are experimental web endpoints,
not a supported Google Cloud SDK; failures never trigger a provider fallback.
"""

import httpx

from .caption_context import validate_segments
from .errors import ServiceError
from .google_inputs import GOOGLE_TRANSLATION_MAX_CHARS, handwriting_payload, language_code
from .google_results import handwriting_candidates, translation_result
from .ink import InkSnapshot
from .network import proxy_url
from .results import CaptionRevision, TranslationResult
from .text_utils import flowing_text

GOOGLE_HANDWRITING_URL = "https://www.google.com/inputtools/request"
GOOGLE_TRANSLATION_URL = "https://translate.googleapis.com/translate_a/single"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class GoogleService:
    def __init__(self, proxy: str | None = None, *, client: httpx.Client | None = None):
        self._proxy = proxy
        self._injected_client = client
        self._clients = {}
        self._closed = False

    def _client_for(self, endpoint):
        if self._closed:
            raise ServiceError("The Google connection is closed. Start a new request.")
        if self._injected_client is not None:
            return self._injected_client
        resolved_proxy = proxy_url(self._proxy, target=endpoint)
        key = (endpoint, resolved_proxy)
        if key not in self._clients:
            self._clients[key] = httpx.Client(
                proxy=resolved_proxy,
                trust_env=False,
                follow_redirects=False,
                timeout=httpx.Timeout(25, connect=10, write=10, pool=5),
                headers={"User-Agent": "LangInOut/GoogleWebServices", "Accept": "application/json"},
            )
        return self._clients[key]

    def _request(self, method, endpoint, **options):
        try:
            client = self._client_for(endpoint)
            client.cookies.clear()
            request = client.build_request(method, endpoint, **options)
            request.headers.pop("cookie", None)
            request.headers.pop("authorization", None)
            response = client.send(request, auth=None, follow_redirects=False)
            if response.status_code in (401, 403):
                raise ServiceError("Google denied this request. Check your network or choose another provider.")
            if response.status_code == 429:
                raise ServiceError("Google is limiting requests. Wait briefly before trying again.")
            if response.status_code >= 500:
                raise ServiceError("Google is temporarily unavailable. Try again later.")
            if 300 <= response.status_code < 400:
                raise ServiceError("Google redirected this request to an unsupported page. Try again later.")
            if response.status_code != 200:
                raise ServiceError("Google rejected the request. Check its language and size.")
            if len(response.content) > MAX_RESPONSE_BYTES:
                raise ServiceError("Google returned an unexpectedly large response.")
            try:
                return response.json()
            except (ValueError, UnicodeError):
                raise ServiceError("Google returned an unreadable response. Try again later.") from None
        except ServiceError:
            raise
        except httpx.TimeoutException:
            raise ServiceError("The Google request timed out. Check your connection and try again.") from None
        except httpx.RequestError:
            raise ServiceError("Cannot connect to Google. Check your connection and proxy settings.") from None
        except Exception:  # noqa: BLE001 - proxy and HTTP errors must not expose private request data
            raise ServiceError("The Google request failed. Check your connection and try again.") from None

    def recognize_handwriting(self, ink: InkSnapshot, language: str) -> list[str]:
        payload = handwriting_payload(ink, language)
        response = self._request(
            "POST", GOOGLE_HANDWRITING_URL,
            params={"ime": "handwriting", "app": "mobilesearch", "cs": "1", "oe": "UTF-8"},
            json=payload,
        )
        return handwriting_candidates(response)

    def translate(self, text: str, target_language: str) -> TranslationResult:
        if not isinstance(text, str):
            raise ServiceError("Enter text to translate.")
        if not text.strip():
            return TranslationResult("")
        if len(text) > GOOGLE_TRANSLATION_MAX_CHARS:
            raise ServiceError("Google translation is limited to 5,000 characters. Translate a shorter passage.")
        target = language_code(target_language)
        response = self._request(
            "GET", GOOGLE_TRANSLATION_URL,
            params=[("client", "gtx"), ("sl", "auto"), ("tl", target),
                    ("dt", "t"), ("dt", "rm"), ("dt", "ss"), ("dj", "1"), ("q", text)],
        )
        return translation_result(response)

    def revise_translation(
        self, segments: list[tuple[int, str]], target_language: str, previous: str = ""
    ) -> list[CaptionRevision]:
        """Retranslate a nonoverlapping source batch; earlier target text is not an input.

        The caller must freeze completed batches, rather than slide this anchor
        through previous segments. Google supplies no reliable segment alignment.
        """
        segments = validate_segments(segments)
        result = self.translate(flowing_text(text for _, text in segments), target_language)
        return [
            CaptionRevision(segment_id, text, result if index == 0 else TranslationResult(""))
            for index, (segment_id, text) in enumerate(segments)
        ]

    def close(self):
        for client in self._clients.values():
            client.close()
        self._clients.clear()
        if self._injected_client is not None:
            self._injected_client.close()
        self._closed = True


__all__ = ["GOOGLE_TRANSLATION_MAX_CHARS", "GoogleService"]
