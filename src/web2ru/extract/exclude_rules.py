from __future__ import annotations

from lxml import etree

HARD_SKIP_TAGS = {
    "script",
    "style",
    "noscript",
    "code",
    "pre",
    "textarea",
    "input",
    "select",
    "option",
    "svg",
    "math",
}


def is_template_shadow_root(element: etree._Element) -> bool:
    return (
        isinstance(element.tag, str)
        and element.tag.lower() == "template"
        and element.get("shadowrootmode") is not None
    )


def should_skip_element(element: etree._Element, *, allow_code_blocks: bool = False) -> bool:
    if not isinstance(element.tag, str):
        return True
    tag = element.tag.lower()
    if tag == "template" and is_template_shadow_root(element):
        return False
    hard_skip = HARD_SKIP_TAGS if not allow_code_blocks else (HARD_SKIP_TAGS - {"code", "pre"})
    if tag in hard_skip or tag == "template":
        return True

    if (element.get("aria-hidden") or "").strip().lower() == "true":
        return True
    if element.get("hidden") is not None:
        return True
    if (element.get("translate") or "").strip().lower() == "no":
        return True
    if element.get("data-no-translate") is not None:
        return True

    class_name = (element.get("class") or "").lower()
    return "notranslate" in class_name


def should_skip_text_content(value: str) -> bool:
    if not value:
        return True
    return bool(not value.strip())
