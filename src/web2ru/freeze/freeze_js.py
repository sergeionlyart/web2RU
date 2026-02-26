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
        "overlays_neutralized_count": 0,
        "scroll_unlocks_count": 0,
    }
    if not freeze_js_enabled:
        _neutralize_known_overlays(root, counters)
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
    _neutralize_known_overlays(root, counters)
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


def _neutralize_known_overlays(root: etree._Element, counters: dict[str, int]) -> None:
    if not _looks_like_linkedin_document(root):
        return

    overlay_xpaths = (
        "//*[@id='base-contextual-sign-in-modal']",
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' contextual-sign-in-modal ')]",
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' top-level-modal-container ')]",
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' modal__overlay ')]",
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' artdeco-global-alert ')]",
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' artdeco-global-alert-container ')]",
    )

    touched: set[int] = set()
    for xpath in overlay_xpaths:
        for node in root.xpath(xpath):
            if not isinstance(node, etree._Element):
                continue
            marker = id(node)
            if marker in touched:
                continue
            touched.add(marker)
            _append_inline_style(
                node,
                "display:none !important; visibility:hidden !important; opacity:0 !important; pointer-events:none !important;",
            )
            node.set("aria-hidden", "true")
            node.attrib.pop("inert", None)

    if touched:
        counters["overlays_neutralized_count"] += len(touched)

    for node in root.xpath("//html|//body"):
        if not isinstance(node, etree._Element):
            continue
        _append_inline_style(node, "overflow:auto !important; position:static !important;")
        _strip_class_tokens(
            node,
            banned={
                "artdeco-modal-open",
                "modal-open",
                "overflow-hidden",
                "no-scroll",
                "scroll-lock",
            },
        )
        node.attrib.pop("inert", None)
        counters["scroll_unlocks_count"] += 1


def _looks_like_linkedin_document(root: etree._Element) -> bool:
    og_linkedin = root.xpath(
        "boolean(//meta[translate(@property, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='og:site_name' "
        "and contains(translate(@content, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'linkedin')])"
    )
    if bool(og_linkedin):
        return True
    host_signals = root.xpath(
        "boolean(//*[@src and (contains(@src, 'linkedin.com') or contains(@src, 'licdn.com'))] "
        "| //*[@href and contains(@href, 'linkedin.com')] "
        "| //*[@data-impression-id and contains(translate(@data-impression-id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
        "'abcdefghijklmnopqrstuvwxyz'), 'contextual-sign-in-modal')])"
    )
    return bool(host_signals)


def _append_inline_style(node: etree._Element, extra: str) -> None:
    current = (node.get("style") or "").strip()
    if not current:
        node.set("style", extra)
        return
    if not current.endswith(";"):
        current = f"{current};"
    node.set("style", f"{current} {extra}")


def _strip_class_tokens(node: etree._Element, *, banned: set[str]) -> None:
    raw = node.get("class")
    if not raw:
        return
    kept = [token for token in raw.split() if token.lower() not in banned]
    if kept:
        node.set("class", " ".join(kept))
    else:
        node.attrib.pop("class", None)
