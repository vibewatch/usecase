"""Fetched content to clean text reducer.

HTML uses BeautifulSoup when available for stronger cleanup and main-content
selection, with the original stdlib parser as a fallback. PDFs use pypdf.
Output is markdown-ish text suitable for extraction prompts with minimal tokens.
"""

from __future__ import annotations

import argparse
import io
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

try:  # Optional at import time; requirements.txt pins it for normal use.
    from bs4 import BeautifulSoup, Comment
except ImportError:  # pragma: no cover - exercised only in minimal envs
    BeautifulSoup = None  # type: ignore[assignment]
    Comment = None  # type: ignore[assignment]

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - exercised only in minimal envs
    PdfReader = None  # type: ignore[assignment]

DROP_TAGS = {"script", "style", "noscript", "template", "nav", "footer", "aside", "header", "form", "iframe", "svg", "canvas"}
BLOCK_TAGS = {
    "p", "div", "section", "article", "main", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "td", "th", "table",
    "blockquote", "pre", "figure", "figcaption",
}
HEADING_TAGS = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ", "h5": "##### ", "h6": "###### "}
NOISE_HINT_RE = re.compile(
    r"\b(cookie|cookies|consent|gdpr|privacy[-_\s]?preferences?|newsletter|"
    r"subscribe[-_\s]?(modal|popup|form|box|banner)|sign[-_\s]?up[-_\s]?"
    r"(modal|popup|form|box|banner)|modal|popup|overlay|interstitial|"
    r"ad[-_\s]?(container|slot|banner|unit)|advertisement|social[-_\s]?"
    r"(share|links?)|share[-_\s]?(buttons?|bar|widget)|related[-_\s]?"
    r"(articles?|posts?)|recommended[-_\s]?(articles?|posts?)|recirculation|wm-ipp)\b",
    re.IGNORECASE,
)
BOILERPLATE_LINE_PATTERNS = [
    re.compile(r"^skip to (main )?content$", re.IGNORECASE),
    re.compile(r"^(menu|open menu|close menu)$", re.IGNORECASE),
    re.compile(r"^(sign in|log in)$", re.IGNORECASE),
    re.compile(r"^(accept|reject|allow|deny)( all)? cookies?$", re.IGNORECASE),
    re.compile(r"^(manage|customize|change|set) (cookies?|preferences|privacy settings)$", re.IGNORECASE),
    re.compile(r"^we use cookies\b.{0,220}$", re.IGNORECASE),
    re.compile(r"^this (site|website) uses cookies\b.{0,220}$", re.IGNORECASE),
    re.compile(r"^(subscribe|sign up) (to|for) (our|the) newsletter\.?$", re.IGNORECASE),
    re.compile(r"^share this (article|post|page)$", re.IGNORECASE),
    re.compile(r"^advertisement$", re.IGNORECASE),
    re.compile(r"^sponsored( content)?$", re.IGNORECASE),
    re.compile(r"^(related|recommended) (articles|posts|content)$", re.IGNORECASE),
    re.compile(r"^(read more|learn more)$", re.IGNORECASE),
    re.compile(r"^all rights reserved\.?$", re.IGNORECASE),
]
class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._drop_depth = 0
        self._in_main_depth = 0
        self._title: list[str] = []
        self._in_title = False
        self._buffer: list[str] = []
        self._main_buffer: list[str] = []
        self._current_heading: str = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in DROP_TAGS:
            self._drop_depth += 1
            return
        if tag in ("main", "article"):
            self._in_main_depth += 1
        if tag == "title":
            self._in_title = True
            return
        if self._drop_depth:
            return
        if tag in HEADING_TAGS:
            self._current_heading = HEADING_TAGS[tag]
            self._emit("\n\n" + self._current_heading)
        elif tag == "li":
            self._emit("\n- ")
        elif tag in BLOCK_TAGS:
            self._emit("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in DROP_TAGS:
            if self._drop_depth > 0:
                self._drop_depth -= 1
            return
        if tag in ("main", "article"):
            if self._in_main_depth > 0:
                self._in_main_depth -= 1
        if tag == "title":
            self._in_title = False
            return
        if self._drop_depth:
            return
        if tag in HEADING_TAGS:
            self._emit("\n")
            self._current_heading = ""
        elif tag in BLOCK_TAGS:
            self._emit("\n")

    def handle_data(self, data: str) -> None:
        if self._drop_depth:
            return
        if self._in_title:
            self._title.append(data)
            return
        self._emit(data)

    def _emit(self, chunk: str) -> None:
        self._buffer.append(chunk)
        if self._in_main_depth > 0:
            self._main_buffer.append(chunk)

    @property
    def title(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._title)).strip()

    def text(self) -> str:
        source = self._main_buffer if self._main_buffer else self._buffer
        raw = "".join(source)
        raw = re.sub(r"[ \t\f\v]+", " ", raw)
        raw = re.sub(r" *\n *", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _clean_text(text: str) -> str:
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines: list[str] = []
    seen_short: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if lines and lines[-1]:
                lines.append("")
            continue
        if any(pattern.search(line) for pattern in BOILERPLATE_LINE_PATTERNS):
            continue
        key = re.sub(r"\W+", " ", line.lower()).strip()
        if len(key) <= 80:
            if key in seen_short:
                continue
            seen_short.add(key)
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _stdlib_html_to_text(html: str) -> tuple[str, str]:
    reader = _Reader()
    try:
        reader.feed(html)
    except Exception:  # noqa: BLE001 - malformed HTML is common; fall through with what we have
        pass
    return reader.title, _clean_text(reader.text())


def _attrs_text(tag: object) -> str:
    if getattr(tag, "attrs", None) is None:
        return ""
    get = getattr(tag, "get", None)
    if get is None:
        return ""
    values: list[str] = []
    for name in ("id", "class", "role", "aria-label", "data-testid"):
        value = get(name)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value:
            values.append(str(value))
    return " ".join(values)


def _is_noise_tag(tag: object) -> bool:
    if getattr(tag, "attrs", None) is None:
        return False
    name = getattr(tag, "name", "")
    if name in {"html", "body", "main", "article"}:
        return False
    get = getattr(tag, "get", None)
    if get and str(get("aria-hidden", "")).lower() == "true":
        return True
    return bool(NOISE_HINT_RE.search(_attrs_text(tag)))


def _best_content_root(soup: object) -> object:
    candidates = []
    for tag in soup.find_all(["main", "article"]):  # type: ignore[attr-defined]
        text = tag.get_text(" ", strip=True)
        if len(text) >= 200:
            candidates.append((len(text), tag))
    for tag in soup.find_all(attrs={"role": "main"}):  # type: ignore[attr-defined]
        text = tag.get_text(" ", strip=True)
        if len(text) >= 200:
            candidates.append((len(text), tag))
    if candidates:
        return max(candidates, key=lambda item: item[0])[1]
    return soup.body or soup  # type: ignore[attr-defined]


def _beautifulsoup_html_to_text(html: str) -> tuple[str, str]:
    if BeautifulSoup is None:
        return _stdlib_html_to_text(html)

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    if Comment is not None:
        for comment in soup.find_all(string=lambda value: isinstance(value, Comment)):
            comment.extract()

    for tag in soup.find_all(DROP_TAGS):
        tag.decompose()
    for tag in list(soup.find_all(True)):
        if _is_noise_tag(tag):
            tag.decompose()

    root = _best_content_root(soup)
    for tag in root.find_all("br"):
        tag.replace_with("\n")
    for tag in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        tag.insert_before("\n\n" + HEADING_TAGS.get(tag.name, ""))
        tag.insert_after("\n")
    for tag in root.find_all("li"):
        tag.insert_before("\n- ")
        tag.insert_after("\n")
    for tag in root.find_all(["p", "div", "section", "article", "blockquote", "pre", "figure", "figcaption", "table", "tr"]):
        tag.insert_before("\n")
        tag.insert_after("\n")

    return title, _clean_text(root.get_text("\n"))


def _decode_bytes(body: bytes, content_type: str = "") -> str:
    match = re.search(r"charset=([^;\s]+)", content_type, flags=re.IGNORECASE)
    encoding = match.group(1).strip('"') if match else "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def looks_like_pdf(body: bytes, content_type: str = "") -> bool:
    return "pdf" in content_type.lower() or b"%PDF-" in body[:1024]


def looks_like_html(text: str, content_type: str = "") -> bool:
    if "html" in content_type.lower() or "xml" in content_type.lower():
        return True
    head = text[:2048].lower()
    return any(marker in head for marker in ("<html", "<!doctype html", "<article", "<main", "<body"))


def pdf_to_text(body: bytes, *, max_chars: Optional[int] = None) -> tuple[str, str]:
    if PdfReader is None:
        raise RuntimeError("pypdf is required to extract PDF text")
    reader = PdfReader(io.BytesIO(body))
    metadata = reader.metadata
    title = str(getattr(metadata, "title", "") or "").strip() if metadata else ""
    parts: list[str] = []
    total = 0
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = _clean_text(text)
        if not text:
            continue
        chunk = f"--- Page {index} ---\n{text}"
        parts.append(chunk)
        total += len(chunk)
        if max_chars is not None and total >= max_chars:
            break
    rendered = _clean_text("\n\n".join(parts))
    if max_chars is not None and len(rendered) > max_chars:
        rendered = rendered[:max_chars] + "\n...[truncated]"
    return title, rendered


def content_to_text(body: bytes, *, content_type: str = "", max_chars: Optional[int] = None) -> tuple[str, str, str]:
    """Return (title, body_text, extraction_method) for fetched bytes."""
    if looks_like_pdf(body, content_type):
        title, text = pdf_to_text(body, max_chars=max_chars)
        return title, text, "pdf"
    decoded = _decode_bytes(body, content_type)
    if looks_like_html(decoded, content_type):
        title, text = _beautifulsoup_html_to_text(decoded)
        method = "html-beautifulsoup" if BeautifulSoup is not None else "html-stdlib"
        return title, text, method
    return "", _clean_text(decoded), "text"


def main() -> None:
    parser = argparse.ArgumentParser(description="Reduce fetched HTML/PDF/text to clean text for LLM extraction.")
    parser.add_argument("input", type=Path, help="Path to fetched body")
    parser.add_argument("--output", type=Path, default=None, help="Write to file (default: stdout)")
    parser.add_argument("--content-type", type=str, default="", help="Optional HTTP Content-Type hint")
    args = parser.parse_args()

    raw = args.input.read_bytes()
    title, body, _method = content_to_text(raw, content_type=args.content_type)
    rendered = f"# {title}\n\n{body}\n" if title else body + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {len(rendered)} chars -> {args.output}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
