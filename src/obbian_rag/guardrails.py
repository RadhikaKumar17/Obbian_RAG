import re
import unicodedata

INJECTION = re.compile(
    r"ignore.{0,50}(?:instruction|rule|policy|previous)|system\s*(?:prompt|message)|"
    r"developer\s*message|reveal.{0,30}(?:secret|key|prompt)|jailbreak|"
    r"<\s*/?\s*(?:script|system)|(?:execute|run).{0,20}(?:shell|code|command)|"
    r"pretend.{0,30}(?:admin|system)|override.{0,30}(?:policy|rule)|"
    r"disregard.{0,30}(?:instruction|policy)",
    re.IGNORECASE,
)
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")
PHONE = re.compile(r"(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)")
SECRET = re.compile(r"\b(?:(?:sk-|gsk_)[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{15,})\b")
LIVE = re.compile(
    r"\b(?:find|show|search|book|reserve|track|cancel|reschedule)\b.{0,70}"
    r"\b(?:me|my|booking|reservation|suv|car|vehicle|trip)\b|"
    r"\b(?:where is|status of|available).{0,40}(?:my|tomorrow|today)|"
    r"\b(?:calculate|quote).{0,40}(?:rental|price|trip)|\bnear me\b",
    re.IGNORECASE,
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(c for c in text if unicodedata.category(c) not in {"Cf", "Cc"} or c in "\n\t")
    return re.sub(r"\s+", " ", text).strip()


def redact(text: str) -> str:
    return SECRET.sub("[secret]", PHONE.sub("[phone]", EMAIL.sub("[email]", text)))


def inspect_query(text: str) -> tuple[str, str | None]:
    text = normalize(text)
    if len(text) < 3:
        return text, "blocked"
    if INJECTION.search(text):
        return text, "blocked"
    if LIVE.search(text) and not re.search(
        r"\b(?:policy|rules|fee|refund|how|what happens)\b", text, re.IGNORECASE
    ):
        return redact(text), "requires_backend"
    return redact(text), None
