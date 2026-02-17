from __future__ import annotations

import re
from urllib.parse import urldefrag, urljoin, urlparse

import tinycss2
from lxml import etree, html

_URL_FUNC_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)


def _is_ignored_url(url: str) -> bool:
    low = url.lower().strip()
    return (
        not low
        or low.startswith("#")
        or low.startswith("data:")
        or low.startswith("blob:")
        or low.startswith("javascript:")
        or low.startswith("mailto:")
        or low.startswith("tel:")
        or low.startswith("about:")
    )


def normalize_url(base_url: str, value: str) -> str | None:
    raw = value.strip()
    if _is_ignored_url(raw):
        return None
    normalized, _ = urldefrag(urljoin(base_url, raw))
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        return None
    return normalized


def _extract_srcset_urls(value: str) -> list[str]:
    urls: list[str] = []
    for part in value.split(","):
        src = part.strip().split(" ", 1)[0]
        if src:
            urls.append(src)
    return urls


def _extract_css_urls(css_text: str) -> list[str]:
    out: list[str] = []
    values = tinycss2.parse_component_value_list(css_text)
    for token in values:
        if token.type == "url":
            out.append(token.value)
        elif token.type == "function" and token.lower_name == "url":
            raw = tinycss2.serialize(token.arguments).strip().strip("\"'")
            if raw:
                out.append(raw)
    # Fallback for edge cases the parser leaves untouched.
    for _, candidate in _URL_FUNC_RE.findall(css_text):
        if candidate:
            out.append(candidate)
    return out


def scan_needed_urls(
    tree: html.HtmlElement, final_url: str, css_by_source_url: dict[str, str]
) -> set[str]:
    needed: set[str] = set()

    for el in tree.iterdescendants():
        if not isinstance(el.tag, str):
            continue
        tag = el.tag.lower()
        for attr, value in el.attrib.items():
            if attr == "srcset":
                if tag not in {"img", "source"}:
                    continue
                for item in _extract_srcset_urls(value):
                    normalized = normalize_url(final_url, item)
                    if normalized:
                        needed.add(normalized)
                continue
            if attr == "style":
                for item in _extract_css_urls(value):
                    normalized = normalize_url(final_url, item)
                    if normalized:
                        needed.add(normalized)
                continue
            if attr == "src":
                if tag not in {"img", "source", "script", "video", "audio", "iframe", "embed"}:
                    continue
                normalized = normalize_url(final_url, value)
                if normalized:
                    needed.add(normalized)
                continue
            if attr == "href":
                if tag != "link":
                    continue
                normalized = normalize_url(final_url, value)
                if normalized:
                    needed.add(normalized)
                continue
            if attr == "poster":
                if tag != "video":
                    continue
                normalized = normalize_url(final_url, value)
                if normalized:
                    needed.add(normalized)
                continue
            if attr == "data":
                if tag != "object":
                    continue
                normalized = normalize_url(final_url, value)
                if normalized:
                    needed.add(normalized)
                continue
            if attr == "xlink:href":
                if tag != "use":
                    continue
                normalized = normalize_url(final_url, value)
                if normalized:
                    needed.add(normalized)
                continue
            if attr == "content":
                if tag != "meta":
                    continue
                if not value.strip().startswith(("http://", "https://", "//")):
                    continue
                normalized = normalize_url(final_url, value)
                if normalized:
                    needed.add(normalized)

        if tag == "style" and el.text:
            for item in _extract_css_urls(el.text):
                normalized = normalize_url(final_url, item)
                if normalized:
                    needed.add(normalized)

    for css_source_url, css_text in css_by_source_url.items():
        for item in _extract_css_urls(css_text):
            normalized = normalize_url(css_source_url, item)
            if normalized:
                needed.add(normalized)

    return needed


def parse_html(html_dump: str) -> html.HtmlElement:
    parser = html.HTMLParser(encoding="utf-8")
    return html.fromstring(html_dump, parser=parser)


def safe_xpath_one(root: etree._Element, expr: str) -> etree._Element | None:
    result = root.xpath(expr)
    if not result:
        return None
    first = result[0]
    if isinstance(first, etree._Element):
        return first
    return None
