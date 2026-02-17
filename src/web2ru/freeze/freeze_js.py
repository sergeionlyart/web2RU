from __future__ import annotations

import hashlib
from copy import deepcopy

from lxml import etree


def freeze_html(
    root: etree._Element,
    *,
    freeze_js_enabled: bool,
    drop_noscript_mode: str,
    block_iframe_enabled: bool,
) -> dict[str, int]:
    counters = {
        "scripts_disabled_count": 0,
        "integrity_stripped_count": 0,
        "iframes_blocked_count": 0,
        "csp_meta_removed_count": 0,
        "resource_hints_removed_count": 0,
    }
    if not freeze_js_enabled:
        return counters

    _disable_scripts(root, counters)
    _strip_inline_handlers(root)
    _neutralize_javascript_hrefs(root)
    _remove_meta_refresh_and_csp(root, counters)
    _remove_resource_hints(root, counters)
    _handle_base(root)
    if block_iframe_enabled:
        _block_iframes(root, counters)
    _lazy_image_fix(root)
    _strip_integrity_and_cors(root, counters)
    _handle_noscript(root, mode=drop_noscript_mode)
    return counters


def _disable_scripts(root: etree._Element, counters: dict[str, int]) -> None:
    allowed_types = {"application/ld+json", "application/json"}
    for script in list(root.xpath("//script")):
        if not isinstance(script, etree._Element):
            continue
        typ = (script.get("type") or "").lower().strip()
        if typ in allowed_types:
            continue
        src = script.get("src")
        if src:
            script.set("data-web2ru-src", src)
            script.attrib.pop("src", None)
            script.set("type", "application/x-web2ru-disabled")
            counters["scripts_disabled_count"] += 1
            continue
        if script.text:
            digest = hashlib.sha256(script.text.encode("utf-8")).hexdigest()
            script.set("data-web2ru-inline-sha256", digest)
        script.text = ""
        script.set("type", "application/x-web2ru-disabled")
        counters["scripts_disabled_count"] += 1


def _strip_inline_handlers(root: etree._Element) -> None:
    for element in root.iterdescendants():
        if not isinstance(element, etree._Element):
            continue
        for attr in list(element.attrib.keys()):
            if attr.lower().startswith("on"):
                element.attrib.pop(attr, None)


def _neutralize_javascript_hrefs(root: etree._Element) -> None:
    for element in root.iterdescendants():
        if not isinstance(element, etree._Element):
            continue
        href = element.get("href")
        if href and href.strip().lower().startswith("javascript:"):
            element.set("data-web2ru-href", href)
            element.set("href", "#")


def _remove_meta_refresh_and_csp(root: etree._Element, counters: dict[str, int]) -> None:
    for meta in list(root.xpath("//meta[@http-equiv]")):
        if not isinstance(meta, etree._Element):
            continue
        equiv = (meta.get("http-equiv") or "").lower()
        if equiv in {"refresh", "content-security-policy"}:
            if equiv == "content-security-policy":
                counters["csp_meta_removed_count"] += 1
            parent = meta.getparent()
            if parent is not None:
                parent.remove(meta)


def _remove_resource_hints(root: etree._Element, counters: dict[str, int]) -> None:
    removable = {"preconnect", "dns-prefetch", "prefetch", "prerender"}
    for link in list(root.xpath("//link[@rel]")):
        if not isinstance(link, etree._Element):
            continue
        rel_values = {part.strip().lower() for part in (link.get("rel") or "").split()}
        if rel_values & removable:
            parent = link.getparent()
            if parent is not None:
                parent.remove(link)
                counters["resource_hints_removed_count"] += 1
            continue
        if "preload" in rel_values:
            href = link.get("href") or ""
            if not href.startswith("./assets/"):
                parent = link.getparent()
                if parent is not None:
                    parent.remove(link)
                    counters["resource_hints_removed_count"] += 1


def _handle_base(root: etree._Element) -> None:
    for base in list(root.xpath("//base")):
        if not isinstance(base, etree._Element):
            continue
        parent = base.getparent()
        if parent is not None:
            parent.remove(base)


def _block_iframes(root: etree._Element, counters: dict[str, int]) -> None:
    for iframe in root.xpath("//iframe"):
        if not isinstance(iframe, etree._Element):
            continue
        src = iframe.get("src")
        if src:
            iframe.set("data-web2ru-src", src)
        iframe.set("src", "about:blank")
        srcdoc = iframe.get("srcdoc")
        if srcdoc:
            iframe.set("data-web2ru-srcdoc", srcdoc)
            iframe.set("srcdoc", "")
        counters["iframes_blocked_count"] += 1


def _lazy_image_fix(root: etree._Element) -> None:
    for img in root.xpath("//img|//source"):
        if not isinstance(img, etree._Element):
            continue
        src = img.get("src")
        if not src or src in {"", "#"}:
            for candidate in ("data-src", "data-lazy-src"):
                val = img.get(candidate)
                if val:
                    img.set("src", val)
                    break
        srcset = img.get("srcset")
        if not srcset:
            lazy_srcset = img.get("data-srcset")
            if lazy_srcset:
                img.set("srcset", lazy_srcset)


def _strip_integrity_and_cors(root: etree._Element, counters: dict[str, int]) -> None:
    for element in root.xpath("//link|//script"):
        if not isinstance(element, etree._Element):
            continue
        if element.get("integrity") is not None:
            element.attrib.pop("integrity", None)
            counters["integrity_stripped_count"] += 1
        if element.get("crossorigin") is not None:
            element.attrib.pop("crossorigin", None)


def _handle_noscript(root: etree._Element, mode: str) -> None:
    if mode not in {"auto", "on"}:
        return
    for ns in list(root.xpath("//noscript")):
        if not isinstance(ns, etree._Element):
            continue
        parent = ns.getparent()
        if parent is None:
            continue

        contains_promotable = bool(ns.xpath(".//img|.//link"))
        if contains_promotable:
            for child in list(ns):
                parent.insert(parent.index(ns), deepcopy(child))
        parent.remove(ns)
