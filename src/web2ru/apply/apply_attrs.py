from __future__ import annotations

from lxml import etree

from web2ru.models import AttributeItem


def apply_attributes(root: etree._Element, attrs: list[AttributeItem]) -> int:
    applied = 0
    for item in attrs:
        value = item.translated_text if item.translated_text is not None else item.text
        if not item.node_ref.attr_name:
            continue
        nodes = root.xpath(item.node_ref.xpath)
        if not nodes:
            continue
        node = nodes[0]
        if not isinstance(node, etree._Element):
            continue
        node.set(item.node_ref.attr_name, value)
        applied += 1
    return applied
