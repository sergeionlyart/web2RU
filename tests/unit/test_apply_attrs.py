from __future__ import annotations

from lxml import html

from web2ru.apply.apply_attrs import apply_attributes
from web2ru.models import AttributeItem, NodeRef


def test_apply_attributes_strips_invalid_xml_control_chars() -> None:
    root = html.fromstring("<html><body><img alt='x'></body></html>")
    img = root.xpath("//img")[0]
    xpath = root.getroottree().getpath(img)
    item = AttributeItem(
        id="a_000001",
        text="x",
        hint="attr:alt",
        node_ref=NodeRef(xpath=xpath, field="attr", attr_name="alt"),
        translated_text="line\x00break",
    )
    applied = apply_attributes(root, [item])
    assert applied == 1
    assert img.get("alt") == "linebreak"
