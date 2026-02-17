from __future__ import annotations

from lxml import etree, html

from web2ru.extract.exclude_rules import should_skip_element


def _first_xpath(root: html.HtmlElement, expr: str) -> etree._Element | None:
    nodes = root.xpath(expr)
    if not nodes:
        return None
    first = nodes[0]
    if isinstance(first, etree._Element):
        return first
    return None


def _visible_text_len(el: etree._Element) -> int:
    total = 0
    for descendant in el.iter():
        if should_skip_element(descendant):
            continue
        if descendant.text:
            total += len(descendant.text.strip())
        if descendant.tail:
            total += len(descendant.tail.strip())
    return total


def select_scope(root: html.HtmlElement, scope: str) -> etree._Element:
    body = _first_xpath(root, "//body")
    if body is None:
        return root

    if scope == "page":
        return body

    if scope in {"main", "auto"}:
        for expr in ["//main", "//article", "//*[@role='main']"]:
            node = _first_xpath(root, expr)
            if node is not None:
                return node

        candidates = root.xpath("//section|//div")
        best = body
        best_score = _visible_text_len(best)
        for candidate in candidates:
            if not isinstance(candidate, etree._Element):
                continue
            score = _visible_text_len(candidate)
            if score > best_score:
                best = candidate
                best_score = score
        return best

    return body
