"""HTML to clean text reducer (stdlib only).

Drops script/style/nav/footer/aside/header tags, collapses whitespace, prefers
the contents of <main> or <article> when present. Output is markdown-ish text
suitable for shipping into an LLM extraction prompt with minimal tokens.
"""

from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path

DROP_TAGS = {"script", "style", "noscript", "nav", "footer", "aside", "header", "form", "iframe", "svg"}
BLOCK_TAGS = {
    "p", "div", "section", "article", "main", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "td", "th", "table",
    "blockquote", "pre", "figure", "figcaption",
}
HEADING_TAGS = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ", "h5": "##### ", "h6": "###### "}


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


def html_to_text(html: str) -> tuple[str, str]:
    """Return (title, body_text)."""
    reader = _Reader()
    try:
        reader.feed(html)
    except Exception:  # noqa: BLE001 - malformed HTML is common; fall through with what we have
        pass
    return reader.title, reader.text()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reduce raw HTML to clean text for LLM extraction.")
    parser.add_argument("input", type=Path, help="Path to .html file")
    parser.add_argument("--output", type=Path, default=None, help="Write to file (default: stdout)")
    args = parser.parse_args()

    html = args.input.read_text(encoding="utf-8", errors="replace")
    title, body = html_to_text(html)
    rendered = f"# {title}\n\n{body}\n" if title else body + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {len(rendered)} chars -> {args.output}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
