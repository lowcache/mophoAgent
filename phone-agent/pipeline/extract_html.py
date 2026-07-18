"""Main-content extraction on stdlib html.parser (Phase 3).

Every established readability library (readability-lxml, justext,
trafilatura, goose3, newspaper4k, resiliparse) pulls in lxml or Cython
C extensions, which cannot be installed into the bionic Python 3.14
venv (Termux's prebuilt python-lxml targets the system interpreter).
Hand-rolled block scorer instead: link density + class/id hints +
length thresholds. Verified approach via tether research 2026-07-18.
"""

import re
from html.parser import HTMLParser

IGNORE_TAGS = {"script", "style", "head", "noscript", "iframe", "form",
               "svg", "nav", "footer", "aside", "header", "button"}
BLOCK_TAGS = {"p", "div", "section", "article", "li", "h1", "h2", "h3",
              "h4", "h5", "h6", "br", "blockquote", "td", "pre"}
HEADING_TAGS = {"h1", "h2", "h3", "h4"}
NEGATIVE_HINTS = ("comment", "sidebar", "widget", "footer", "nav",
                  "menu", "ad-", "promo", "related", "share", "social")
POSITIVE_HINTS = ("post", "article", "content", "entry", "body", "main",
                  "story")


class _BlockParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, dict]] = []
        self.blocks: list[dict] = []
        self._buf: list[str] = []
        self._text_len = 0
        self._link_len = 0
        self._link_depth = 0
        self._ignore_depth = 0
        self.title = ""
        self.og_title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("property") == "og:title":
            self.og_title = a.get("content", "")
        if tag == "title":
            self._in_title = True
        if tag in IGNORE_TAGS:
            self._ignore_depth += 1
        if tag == "a":
            self._link_depth += 1
        if tag in BLOCK_TAGS:
            self._flush()
        self.stack.append((tag, a))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in BLOCK_TAGS:
            self._flush()
        if tag in IGNORE_TAGS and self._ignore_depth:
            self._ignore_depth -= 1
        if tag == "a" and self._link_depth:
            self._link_depth -= 1
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if self._ignore_depth:
            return
        if not data.strip():
            return
        self._buf.append(data)
        n = len(re.sub(r"\s+", " ", data))
        self._text_len += n
        if self._link_depth:
            self._link_len += n

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        if text:
            weight = 1.0
            for _, a in self.stack:
                hint = (a.get("class", "") + " " + a.get("id", "")).lower()
                if any(k in hint for k in NEGATIVE_HINTS):
                    weight = 0.1
                    break
                if any(k in hint for k in POSITIVE_HINTS):
                    weight = 1.5
            self.blocks.append({
                "text": text,
                "link_ratio": self._link_len / max(self._text_len, 1),
                "words": len(text.split()),
                "weight": weight,
                "tags": {t for t, _ in self.stack},
            })
        self._buf = []
        self._text_len = 0
        self._link_len = 0


def extract_main_content(html: str) -> dict:
    """{"title": str | None, "text": str} — boilerplate-filtered body."""
    parser = _BlockParser()
    parser.feed(html)
    parser.close()
    parser._flush()

    kept = []
    for b in parser.blocks:
        if b["link_ratio"] > 0.4 or b["weight"] < 0.2:
            continue
        if (b["words"] >= 10
                or (b["tags"] & HEADING_TAGS and b["words"] >= 3)
                or (b["weight"] > 1.0 and b["words"] >= 5)):
            kept.append(b["text"])

    title = (parser.og_title or parser.title).strip() or None
    if title:
        for sep in (" | ", " - ", " – ", " — "):
            if sep in title:
                title = title.split(sep)[0].strip()
                break
    return {"title": title, "text": "\n\n".join(kept)}
