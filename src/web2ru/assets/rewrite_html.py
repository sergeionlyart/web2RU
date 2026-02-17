from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import urljoin

from lxml import html

from web2ru.assets.rewrite_css import rewrite_css_urls
from web2ru.assets.scan import normalize_url

_SRCSET_SPLIT_RE = re.compile(r"\s*,\s*")
_URL_FUNC_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)


def _rewrite_srcset(value: str, *, base_url: str, map_url: Callable[[str], str]) -> str:
    parts: list[str] = []
    for entry in _SRCSET_SPLIT_RE.split(value):
        item = entry.strip()
        if not item:
            continue
        url_and_desc = item.split(maxsplit=1)
        src = url_and_desc[0]
        desc = f" {url_and_desc[1]}" if len(url_and_desc) > 1 else ""
        normalized = normalize_url(base_url, src)
        if normalized:
            parts.append(f"{map_url(normalized)}{desc}")
        else:
            parts.append(item)
    return ", ".join(parts)


def _rewrite_inline_style(value: str, *, base_url: str, map_url: Callable[[str], str]) -> str:
    def repl(match: re.Match[str]) -> str:
        raw = match.group(2)
        normalized = normalize_url(base_url, raw)
        if not normalized:
            return match.group(0)
        return f'url("{map_url(normalized)}")'

    return _URL_FUNC_RE.sub(repl, value)


def rewrite_html_urls(
    tree: html.HtmlElement,
    *,
    final_url: str,
    map_url: Callable[[str], str],
    rewrite_style_blocks: bool = True,
) -> None:
    for element in tree.iterdescendants():
        if not isinstance(element.tag, str):
            continue
        tag = element.tag.lower()
        attrs = dict(element.attrib)

        for attr_name, value in attrs.items():
            if attr_name == "srcset":
                element.set(attr_name, _rewrite_srcset(value, base_url=final_url, map_url=map_url))
                continue
            if attr_name == "style":
                element.set(
                    attr_name, _rewrite_inline_style(value, base_url=final_url, map_url=map_url)
                )
                continue

            if attr_name not in {"src", "href", "poster", "data", "xlink:href", "content"}:
                continue

            if tag == "a" and attr_name == "href":
                continue
            if tag == "script" and attr_name == "src":
                continue
            if tag == "link":
                rel = (element.get("rel") or "").lower()
                keep = {"stylesheet", "preload", "icon", "shortcut icon"}
                if not any(item in rel for item in keep):
                    continue

            normalized = normalize_url(final_url, value)
            if not normalized:
                continue
            element.set(attr_name, map_url(normalized))

        if rewrite_style_blocks and tag == "style" and element.text:
            element.text = rewrite_css_urls(
                element.text,
                css_base_url=final_url,
                map_url=map_url,
            )


def rewrite_css_asset_records(
    *,
    css_text_by_url: dict[str, str],
    map_url: Callable[[str], str],
) -> dict[str, str]:
    rewritten: dict[str, str] = {}
    for source_url, css_text in css_text_by_url.items():
        rewritten[source_url] = rewrite_css_urls(
            css_text,
            css_base_url=source_url,
            map_url=map_url,
        )
    return rewritten


def absolutize_href(base: str, href: str) -> str:
    return urljoin(base, href)
