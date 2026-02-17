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

CODE_CONTAINER_TAGS = {"pre", "code"}
PROSE_PRE_LANGS = {"markdown", "md", "txt", "text", "plaintext", "plain"}

_LANG_TOKEN_RE = re.compile(r"(?:^|\s)(?:language|lang)-([a-z0-9_+-]+)")
_CODE_SIGNAL_RE = re.compile(
    r"([{};]|=>|\b(def|class|function|return|import|from|const|let|var|if|for|while|switch|case)\b|^\s*[$>])"
)
_PROSE_SIGNAL_RE = re.compile(r"[.!?]|\b(the|and|with|from|that|this|when|where)\b", re.IGNORECASE)
_BLOCK_COMMENT_RE = re.compile(r"/\*([\s\S]*?)\*/")
_HTML_COMMENT_RE = re.compile(r"<!--([\s\S]*?)-->")
_LINE_COMMENT_RE = re.compile(r"^\s*(#|//|--)\s?(.*)$")

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
    allow_code_blocks: bool = False,
) -> list[tuple[etree._Element, str, str]]:
    slots: list[tuple[etree._Element, str, str]] = []

    def walk(current: etree._Element) -> None:
        if _is_excluded(current, excluded_ids):
            return
        if (
            should_skip_element(current, allow_code_blocks=allow_code_blocks)
            and not is_template_shadow_root(current)
        ):
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


def _pre_language_hint(pre_node: etree._Element) -> str | None:
    data_lang = (pre_node.get("data-language") or "").strip().lower()
    if data_lang:
        return data_lang

    classes: list[str] = []
    classes.append(pre_node.get("class") or "")
    for code in pre_node.xpath(".//code"):
        if isinstance(code, etree._Element):
            code_lang = (code.get("data-language") or "").strip().lower()
            if code_lang:
                return code_lang
            classes.append(code.get("class") or "")
    all_classes = " ".join(classes).lower()
    match = _LANG_TOKEN_RE.search(all_classes)
    if match:
        return match.group(1)
    return None


def _is_prose_pre_block(pre_node: etree._Element, slots: list[tuple[etree._Element, str, str]]) -> bool:
    lang = _pre_language_hint(pre_node)
    if lang in PROSE_PRE_LANGS:
        return True
    if lang is not None:
        return False

    lines: list[str] = []
    for _, _, raw in slots:
        lines.extend(raw.splitlines())
    non_empty = [line.strip() for line in lines if line.strip()]
    if not non_empty:
        return False

    code_score = sum(1 for line in non_empty if _CODE_SIGNAL_RE.search(line))
    prose_score = sum(1 for line in non_empty if _PROSE_SIGNAL_RE.search(line))
    if code_score == 0:
        return True
    return not (code_score >= max(2, len(non_empty) // 2) and code_score > prose_score)


def _comment_spans(raw: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []

    for pattern in (_BLOCK_COMMENT_RE, _HTML_COMMENT_RE):
        for match in pattern.finditer(raw):
            start, end = match.span(1)
            if start < end:
                spans.append((start, end))

    cursor = 0
    for line in raw.splitlines(keepends=True):
        line_no_nl = line.rstrip("\r\n")
        line_start = cursor
        cursor += len(line)
        line_match = _LINE_COMMENT_RE.match(line_no_nl)
        if line_match:
            comment = line_match.group(2)
            if comment:
                comment_offset = line_no_nl.find(comment)
                spans.append(
                    (
                        line_start + comment_offset,
                        line_start + comment_offset + len(comment),
                    )
                )
            continue

        idx = line_no_nl.find("//")
        if idx > 0 and line_no_nl[idx - 1] != ":":
            start = line_start + idx + 2
            end = line_start + len(line_no_nl)
            if start < end:
                spans.append((start, end))
            continue

        idx = line_no_nl.find(" #")
        if idx >= 0:
            start = line_start + idx + 2
            end = line_start + len(line_no_nl)
            if start < end:
                spans.append((start, end))
            continue

        idx = line_no_nl.find(" --")
        if idx >= 0:
            start = line_start + idx + 3
            end = line_start + len(line_no_nl)
            if start < end:
                spans.append((start, end))

    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if not merged:
            merged.append((start, end))
            continue
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _make_full_part(
    *,
    raw: str,
    slot_node: etree._Element,
    field: str,
    root_tree: etree._ElementTree,
    part_counter: count[int],
) -> Part | None:
    if should_skip_text_content(raw):
        return None
    lead, core, trail = split_whitespace(raw)
    if not core or is_punctuation_or_ws(core):
        return None
    return Part(
        id=f"t_{next(part_counter):06d}",
        raw=raw,
        lead_ws=lead,
        core=core,
        trail_ws=trail,
        node_ref=NodeRef(xpath=root_tree.getpath(slot_node), field=field),
        block_id="",
    )


def _make_comment_parts(
    *,
    raw: str,
    slot_node: etree._Element,
    field: str,
    root_tree: etree._ElementTree,
    part_counter: count[int],
) -> list[Part]:
    parts: list[Part] = []
    for start, end in _comment_spans(raw):
        segment = raw[start:end]
        lead, core, trail = split_whitespace(segment)
        if not core or is_punctuation_or_ws(core):
            continue
        parts.append(
            Part(
                id=f"t_{next(part_counter):06d}",
                raw=segment,
                lead_ws=lead,
                core=core,
                trail_ws=trail,
                node_ref=NodeRef(
                    xpath=root_tree.getpath(slot_node),
                    field=field,
                    start_offset=start + len(lead),
                    end_offset=end - len(trail),
                ),
                block_id="",
            )
        )
    return parts


def _extract_pre_blocks(
    *,
    scope_root: etree._Element,
    excluded_ids: set[int],
    root_tree: etree._ElementTree,
    part_counter: count[int],
    block_counter: count[int],
) -> list[Block]:
    blocks: list[Block] = []
    for pre in scope_root.iterdescendants():
        if not isinstance(pre.tag, str) or pre.tag.lower() != "pre":
            continue
        if _is_excluded(pre, excluded_ids):
            continue
        if should_skip_element(pre, allow_code_blocks=True):
            continue

        slots = _iter_text_slots(pre, excluded_ids=excluded_ids, allow_code_blocks=True)
        if not slots:
            continue

        prose_mode = _is_prose_pre_block(pre, slots)
        parts: list[Part] = []
        for slot_node, field, raw in slots:
            if prose_mode:
                part = _make_full_part(
                    raw=raw,
                    slot_node=slot_node,
                    field=field,
                    root_tree=root_tree,
                    part_counter=part_counter,
                )
                if part is not None:
                    parts.append(part)
            else:
                parts.extend(
                    _make_comment_parts(
                        raw=raw,
                        slot_node=slot_node,
                        field=field,
                        root_tree=root_tree,
                        part_counter=part_counter,
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
            part = _make_full_part(
                raw=raw,
                slot_node=slot_node,
                field=field,
                root_tree=root_tree,
                part_counter=part_counter,
            )
            if part is not None:
                parts.append(part)

        if not parts:
            continue
        block_id = f"b_{next(block_counter):06d}"
        context = " ".join(part.core for part in parts)
        for part in parts:
            part.block_id = block_id
        blocks.append(Block(block_id=block_id, context=context, parts=parts))

    blocks.extend(
        _extract_pre_blocks(
            scope_root=scope_root,
            excluded_ids=excluded_ids,
            root_tree=root_tree,
            part_counter=part_counter,
            block_counter=block_counter,
        )
    )
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
