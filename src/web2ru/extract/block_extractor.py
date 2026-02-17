from __future__ import annotations

import re
from itertools import count

from lxml import etree

from web2ru.extract.exclude_rules import (
    is_template_shadow_root,
    should_skip_element,
    should_skip_text_content,
)
from web2ru.extract.normalize_ws import is_punctuation_or_ws, split_whitespace
from web2ru.models import AttributeItem, Block, NodeRef, Part

PRIMARY_BLOCK_TAGS = {
    "p",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "figcaption",
    "caption",
    "dd",
    "dt",
    "td",
    "th",
    "summary",
}

# Scope selection already narrows content; default exclusions are empty to avoid dropping article text
# on sites that semantically overuse `nav`/`header` wrappers.
DEFAULT_MAIN_EXCLUDES: list[str] = []


def _mark_excluded(scope_root: etree._Element, selectors: list[str]) -> set[int]:
    excluded: set[int] = set()
    for selector in selectors:
        try:
            nodes = scope_root.cssselect(selector)
        except Exception:
            continue
        for node in nodes:
            if not isinstance(node, etree._Element):
                continue
            for descendant in node.iter():
                excluded.add(id(descendant))
    return excluded


def _is_excluded(node: etree._Element, excluded_ids: set[int]) -> bool:
    current: etree._Element | None = node
    while current is not None:
        if id(current) in excluded_ids:
            return True
        current = current.getparent()
    return False


def _visible_text_len(node: etree._Element, excluded_ids: set[int]) -> int:
    total = 0
    for el in node.iter():
        if not isinstance(el, etree._Element):
            continue
        if _is_excluded(el, excluded_ids):
            continue
        if should_skip_element(el):
            continue
        if el.text:
            total += len(el.text.strip())
    return total


def _has_nested_primary(node: etree._Element) -> bool:
    for el in node.iterdescendants():
        if isinstance(el.tag, str) and el.tag.lower() in PRIMARY_BLOCK_TAGS:
            return True
    return False


def _iter_text_slots(
    node: etree._Element,
    *,
    excluded_ids: set[int],
) -> list[tuple[etree._Element, str, str]]:
    slots: list[tuple[etree._Element, str, str]] = []

    def walk(current: etree._Element) -> None:
        if _is_excluded(current, excluded_ids):
            return
        if should_skip_element(current) and not is_template_shadow_root(current):
            return
        if current.text:
            slots.append((current, "text", current.text))
        for child in current:
            if isinstance(child, etree._Element):
                walk(child)
                if child.tail:
                    slots.append((child, "tail", child.tail))

    walk(node)
    return slots


def extract_blocks(
    scope_root: etree._Element,
    *,
    scope_mode: str,
    translation_unit: str,
    exclude_selectors: list[str],
) -> tuple[list[Block], set[int]]:
    selectors = list(exclude_selectors)
    if scope_mode in {"main", "auto"}:
        selectors.extend(DEFAULT_MAIN_EXCLUDES)
    excluded_ids = _mark_excluded(scope_root, selectors)

    if translation_unit == "textnode":
        return _extract_textnode_blocks(scope_root, excluded_ids), excluded_ids
    return _extract_block_mode(scope_root, excluded_ids), excluded_ids


def _extract_block_mode(scope_root: etree._Element, excluded_ids: set[int]) -> list[Block]:
    block_nodes: list[etree._Element] = []
    for element in scope_root.iterdescendants():
        if not isinstance(element.tag, str):
            continue
        if _is_excluded(element, excluded_ids):
            continue
        if should_skip_element(element):
            continue
        if element.tag.lower() in PRIMARY_BLOCK_TAGS:
            block_nodes.append(element)

    if not block_nodes:
        fallback_candidates: list[etree._Element] = []
        for element in scope_root.iterdescendants():
            if not isinstance(element.tag, str):
                continue
            if element.tag.lower() not in {"div", "section"}:
                continue
            if _is_excluded(element, excluded_ids):
                continue
            if should_skip_element(element):
                continue
            if _has_nested_primary(element):
                continue
            if _visible_text_len(element, excluded_ids) >= 120:
                fallback_candidates.append(element)
        block_nodes = fallback_candidates or [scope_root]

    part_counter = count(1)
    block_counter = count(1)
    root_tree = scope_root.getroottree()
    blocks: list[Block] = []

    for block_node in block_nodes:
        parts: list[Part] = []
        for slot_node, field, raw in _iter_text_slots(block_node, excluded_ids=excluded_ids):
            if should_skip_text_content(raw):
                continue
            lead, core, trail = split_whitespace(raw)
            if not core:
                continue
            if is_punctuation_or_ws(core):
                continue
            part_id = f"t_{next(part_counter):06d}"
            parts.append(
                Part(
                    id=part_id,
                    raw=raw,
                    lead_ws=lead,
                    core=core,
                    trail_ws=trail,
                    node_ref=NodeRef(xpath=root_tree.getpath(slot_node), field=field),
                    block_id="",  # set below
                )
            )

        if not parts:
            continue
        block_id = f"b_{next(block_counter):06d}"
        context = " ".join(part.core for part in parts)
        for part in parts:
            part.block_id = block_id
        blocks.append(Block(block_id=block_id, context=context, parts=parts))

    return blocks


def _extract_textnode_blocks(scope_root: etree._Element, excluded_ids: set[int]) -> list[Block]:
    root_tree = scope_root.getroottree()
    part_counter = count(1)
    block_counter = count(1)
    blocks: list[Block] = []

    for node in scope_root.iterdescendants():
        if not isinstance(node, etree._Element):
            continue
        if _is_excluded(node, excluded_ids):
            continue
        if should_skip_element(node):
            continue
        slots = _iter_text_slots(node, excluded_ids=excluded_ids)
        for slot_node, field, raw in slots:
            if should_skip_text_content(raw):
                continue
            lead, core, trail = split_whitespace(raw)
            if not core:
                continue
            block_id = f"b_{next(block_counter):06d}"
            part_id = f"t_{next(part_counter):06d}"
            part = Part(
                id=part_id,
                raw=raw,
                lead_ws=lead,
                core=core,
                trail_ws=trail,
                node_ref=NodeRef(xpath=root_tree.getpath(slot_node), field=field),
                block_id=block_id,
            )
            blocks.append(Block(block_id=block_id, context=core, parts=[part]))
    return blocks


_ALT_TECH_RE = re.compile(
    r"(https?://|www\.|/|\\|\b[a-f0-9]{8,}\b|\.png\b|\.jpg\b|\.svg\b|\.webp\b)",
    re.IGNORECASE,
)


def extract_attribute_items(
    scope_root: etree._Element,
    *,
    translate_attrs: bool,
    translate_alt: str,
    excluded_ids: set[int],
) -> list[AttributeItem]:
    if not translate_attrs:
        return []

    attr_counter = count(1)
    root_tree = scope_root.getroottree()
    items: list[AttributeItem] = []

    for element in scope_root.iterdescendants():
        if not isinstance(element.tag, str):
            continue
        if _is_excluded(element, excluded_ids):
            continue
        if should_skip_element(element):
            continue
        xpath = root_tree.getpath(element)

        for attr_name in ("title", "aria-label", "placeholder"):
            value = element.get(attr_name)
            if value and value.strip():
                attr_id = f"a_{next(attr_counter):06d}"
                items.append(
                    AttributeItem(
                        id=attr_id,
                        text=value,
                        hint=f"attr:{attr_name}",
                        node_ref=NodeRef(xpath=xpath, field="attr", attr_name=attr_name),
                    )
                )

        alt = element.get("alt")
        if alt is None:
            continue
        if translate_alt == "off":
            continue
        if translate_alt == "auto":
            if not alt.strip():
                continue
            if len(alt) > 180:
                continue
            if _ALT_TECH_RE.search(alt):
                continue
        attr_id = f"a_{next(attr_counter):06d}"
        items.append(
            AttributeItem(
                id=attr_id,
                text=alt,
                hint="attr:alt",
                node_ref=NodeRef(xpath=xpath, field="attr", attr_name="alt"),
            )
        )
    return items
