from __future__ import annotations

from collections import defaultdict

from lxml import etree

from web2ru.apply.xml_sanitize import sanitize_xml_text
from web2ru.models import Block, Part


def apply_blocks(root: etree._Element, blocks: list[Block]) -> int:
    applied = 0
    ranged_parts: defaultdict[tuple[str, str], list[tuple[Part, str]]] = defaultdict(list)

    for block in blocks:
        for part in block.parts:
            translated = part.translated_core if part.translated_core is not None else part.core
            new_text = sanitize_xml_text(f"{part.lead_ws}{translated}{part.trail_ws}")
            if (
                part.node_ref.start_offset is not None
                and part.node_ref.end_offset is not None
                and part.node_ref.field in {"text", "tail"}
            ):
                ranged_parts[(part.node_ref.xpath, part.node_ref.field)].append((part, new_text))
                continue

            nodes = root.xpath(part.node_ref.xpath)
            if not nodes:
                continue
            node = nodes[0]
            if not isinstance(node, etree._Element):
                continue
            if part.node_ref.field == "text":
                node.text = new_text
                applied += 1
            elif part.node_ref.field == "tail":
                node.tail = new_text
                applied += 1

    for (xpath, field), items in ranged_parts.items():
        nodes = root.xpath(xpath)
        if not nodes:
            continue
        node = nodes[0]
        if not isinstance(node, etree._Element):
            continue
        current = node.text if field == "text" else node.tail
        if current is None:
            continue
        updated = current
        for part, replacement in sorted(
            items, key=lambda entry: int(entry[0].node_ref.start_offset or 0), reverse=True
        ):
            start = part.node_ref.start_offset
            end = part.node_ref.end_offset
            if start is None or end is None:
                continue
            if start < 0 or end > len(updated) or start >= end:
                continue
            updated = f"{updated[:start]}{replacement}{updated[end:]}"
            applied += 1

        if field == "text":
            node.text = sanitize_xml_text(updated)
        else:
            node.tail = sanitize_xml_text(updated)

    return applied
