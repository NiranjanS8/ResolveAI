"""Plain-text formatting for outbound customer messages.

Models write Markdown; email clients and the chat widget do not render it, so a
customer would see literal ``**bold**``. This module turns any outbound body into
plain text using a real CommonMark parser rather than a pile of regexes, so edge
cases such as ``order_id_123`` and ``5 * 3`` are not damaged (CommonMark only
treats ``*``/``_`` as emphasis when the flanking rules allow it).

The email HTML part is rendered here too, and it is always escaped *before* it is
wrapped, so model output can never inject markup.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.token import Token

# CommonMark plus the two extensions we actually see in model output.
_MD = MarkdownIt("commonmark").enable("table").enable("strikethrough")

_URL_PATTERN = re.compile(r"https?://[^\s<>\"]+")
_TRAILING_URL_PUNCTUATION = ".,;:!?)]}'"
_BLANK_LINE_RUN = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class SanitizeResult:
    """The plain text plus the evidence needed to log a format deviation."""

    text: str
    changed: bool
    markers: list[str]


class _PlainTextRenderer:
    """Walks a markdown-it token stream and emits plain text.

    Emphasis/heading/code markers are dropped while their text is kept, links
    become ``text (url)``, lists keep a ``- `` or ``1. `` prefix, and tables are
    flattened to one ``cell | cell`` line per row.
    """

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._buffer: list[str] = []
        self._markers: set[str] = set()
        self._link_stack: list[tuple[str, int]] = []
        self._list_stack: list[dict[str, object]] = []
        self._pending_prefix = ""
        self._cells_in_row = 0

    def _write(self, text: str) -> None:
        if not text:
            return
        if self._pending_prefix:
            self._buffer.append(self._pending_prefix)
            self._pending_prefix = ""
        self._buffer.append(text)

    def _flush(self) -> None:
        if not self._buffer:
            return
        self._lines.append("".join(self._buffer).strip())
        self._buffer.clear()

    def _blank(self) -> None:
        if self._lines and self._lines[-1] != "":
            self._lines.append("")

    def _append_raw_lines(self, content: str) -> None:
        for line in content.rstrip("\n").split("\n"):
            self._lines.append(line.rstrip())

    def render(self, tokens: list[Token]) -> str:
        self._walk(tokens)
        self._flush()
        return _BLANK_LINE_RUN.sub("\n\n", "\n".join(self._lines)).strip()

    @property
    def markers(self) -> list[str]:
        """The kinds of Markdown markup the walk actually saw."""
        return sorted(self._markers)

    def _walk(self, tokens: list[Token]) -> None:
        for token in tokens:
            handler = getattr(self, f"_on_{token.type}", None)
            if handler is not None:
                handler(token)

    def _on_paragraph_open(self, _token: Token) -> None:
        # List items also carry paragraph tokens; separation there would put a
        # blank line between every bullet.
        if not self._list_stack:
            self._blank()

    def _on_paragraph_close(self, _token: Token) -> None:
        self._flush()

    def _on_heading_open(self, _token: Token) -> None:
        self._markers.add("heading")
        self._blank()

    def _on_heading_close(self, _token: Token) -> None:
        self._flush()

    def _on_hr(self, _token: Token) -> None:
        self._blank()

    def _on_blockquote_open(self, _token: Token) -> None:
        self._blank()

    def _on_fence(self, token: Token) -> None:
        self._markers.add("code")
        self._blank()
        self._append_raw_lines(token.content)
        self._blank()

    _on_code_block = _on_fence

    def _on_html_block(self, token: Token) -> None:
        self._markers.add("html")
        self._blank()
        self._append_raw_lines(token.content)
        self._blank()

    def _on_bullet_list_open(self, _token: Token) -> None:
        self._markers.add("list")
        if not self._list_stack:
            self._blank()
        self._list_stack.append({"kind": "bullet", "index": 1})

    def _on_ordered_list_open(self, token: Token) -> None:
        self._markers.add("list")
        if not self._list_stack:
            self._blank()
        start = token.attrGet("start")
        self._list_stack.append({"kind": "ordered", "index": int(start) if start else 1})

    def _on_list_close(self, _token: Token) -> None:
        if self._list_stack:
            self._list_stack.pop()

    _on_bullet_list_close = _on_list_close
    _on_ordered_list_close = _on_list_close

    def _on_list_item_open(self, _token: Token) -> None:
        self._flush()
        if not self._list_stack:
            return
        frame = self._list_stack[-1]
        if frame["kind"] == "ordered":
            self._pending_prefix = f"{frame['index']}. "
            frame["index"] = int(frame["index"]) + 1
        else:
            self._pending_prefix = "- "

    def _on_list_item_close(self, _token: Token) -> None:
        self._flush()
        self._pending_prefix = ""

    def _on_table_open(self, _token: Token) -> None:
        self._markers.add("table")
        self._blank()

    def _on_table_close(self, _token: Token) -> None:
        self._blank()

    def _on_tr_open(self, _token: Token) -> None:
        self._flush()
        self._cells_in_row = 0

    def _on_tr_close(self, _token: Token) -> None:
        self._flush()

    def _on_cell_open(self, _token: Token) -> None:
        if self._cells_in_row:
            self._buffer.append(" | ")

    _on_th_open = _on_cell_open
    _on_td_open = _on_cell_open

    def _on_cell_close(self, _token: Token) -> None:
        self._cells_in_row += 1

    _on_th_close = _on_cell_close
    _on_td_close = _on_cell_close

    def _on_inline(self, token: Token) -> None:
        self._walk(token.children or [])

    def _on_text(self, token: Token) -> None:
        self._write(token.content)

    def _on_softbreak(self, _token: Token) -> None:
        self._flush()

    _on_hardbreak = _on_softbreak

    def _on_strong_open(self, _token: Token) -> None:
        self._markers.add("strong")

    def _on_em_open(self, _token: Token) -> None:
        self._markers.add("emphasis")

    def _on_s_open(self, _token: Token) -> None:
        self._markers.add("strikethrough")

    def _on_code_inline(self, token: Token) -> None:
        self._markers.add("code")
        self._write(token.content)

    def _on_link_open(self, token: Token) -> None:
        self._markers.add("link")
        self._link_stack.append((token.attrGet("href") or "", len(self._buffer)))

    def _on_link_close(self, _token: Token) -> None:
        if not self._link_stack:
            return
        href, text_start = self._link_stack.pop()
        if not href:
            return
        # An autolink's text is the URL itself; repeating it would be noise.
        if "".join(self._buffer[text_start:]).strip() != href:
            self._write(f" ({href})")

    def _on_image(self, token: Token) -> None:
        self._markers.add("image")
        self._write(token.attrGet("alt") or token.attrGet("src") or "")

    def _on_html_inline(self, token: Token) -> None:
        self._markers.add("html")
        self._write(token.content)


def to_plain_text(body: str | None) -> str:
    """Return ``body`` as plain text, dropping any Markdown markup.

    Runs on every outbound message, on every channel.
    """
    return sanitize_outbound(body).text


def sanitize_outbound(body: str | None) -> SanitizeResult:
    """Sanitize ``body`` and report whether it changed and which markup it had."""
    original = body or ""
    renderer = _PlainTextRenderer()
    text = renderer.render(_MD.parse(original))
    return SanitizeResult(text=text, changed=text != original, markers=renderer.markers)


def plain_text_to_html(text: str) -> str:
    """Render the email HTML part from plain text.

    The text is escaped first and only then wrapped into paragraphs, with line
    breaks preserved and bare URLs auto-linked. Nothing reaches the markup layer
    unescaped, so model output cannot inject HTML.
    """
    if not text:
        return ""

    escaped = html.escape(text, quote=True)
    paragraphs = [block for block in re.split(r"\n{2,}", escaped) if block.strip()]
    rendered = [
        "<p>" + _autolink(block).replace("\n", "<br>\n") + "</p>"
        for block in paragraphs
    ]
    return "\n".join(rendered)


def _autolink(escaped_block: str) -> str:
    """Wrap bare URLs in anchors, leaving trailing sentence punctuation outside."""

    def replace(match: re.Match[str]) -> str:
        label = match.group(0)
        url = label
        trailing = ""
        while url and url[-1] in _TRAILING_URL_PUNCTUATION:
            trailing = url[-1] + trailing
            url = url[:-1]
        if not url:
            return label
        return f'<a href="{url}">{url}</a>{trailing}'

    return _URL_PATTERN.sub(replace, escaped_block)
