from __future__ import annotations

import re

# XML 1.0 disallows these control/surrogate ranges in element text and attributes.
_INVALID_XML_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\uD800-\uDFFF\uFFFE\uFFFF]")


def sanitize_xml_text(value: str) -> str:
    return _INVALID_XML_RE.sub("", value)
