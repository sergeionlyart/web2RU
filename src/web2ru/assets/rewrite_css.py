from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import tinycss2

from web2ru.assets.scan import normalize_url

TokenSeq = Sequence[Any]


def _rewrite_component_values(
    tokens: TokenSeq,
    *,
    base_url: str,
    map_url: Callable[[str], str],
) -> str:
    out: list[str] = []
    for token in tokens:
        ttype = token.type
        if ttype == "url":
            normalized = normalize_url(base_url, token.value)
            if normalized:
                out.append(f'url("{map_url(normalized)}")')
            else:
                out.append(token.serialize())
            continue
        if ttype == "function":
            if token.lower_name == "url":
                raw = tinycss2.serialize(token.arguments).strip().strip("\"'")
                normalized = normalize_url(base_url, raw)
                if normalized:
                    out.append(f'url("{map_url(normalized)}")')
                else:
                    out.append(token.serialize())
            else:
                rendered_args = _rewrite_component_values(
                    token.arguments,
                    base_url=base_url,
                    map_url=map_url,
                )
                out.append(f"{token.name}({rendered_args})")
            continue
        if ttype in {"() block", "[] block", "{} block"}:
            left, right = {
                "() block": ("(", ")"),
                "[] block": ("[", "]"),
                "{} block": ("{", "}"),
            }[ttype]
            rendered = _rewrite_component_values(
                token.content,
                base_url=base_url,
                map_url=map_url,
            )
            out.append(f"{left}{rendered}{right}")
            continue
        out.append(token.serialize())
    return "".join(out)


def _rewrite_import_prelude(
    tokens: TokenSeq,
    *,
    base_url: str,
    map_url: Callable[[str], str],
) -> str:
    rewritten: list[str] = []
    changed = False
    for token in tokens:
        if changed:
            rewritten.append(token.serialize())
            continue
        if token.type == "url":
            normalized = normalize_url(base_url, token.value)
            if normalized:
                rewritten.append(f'url("{map_url(normalized)}")')
                changed = True
                continue
        if token.type == "string":
            normalized = normalize_url(base_url, token.value)
            if normalized:
                rewritten.append(f'"{map_url(normalized)}"')
                changed = True
                continue
        if token.type == "function" and token.lower_name == "url":
            raw = tinycss2.serialize(token.arguments).strip().strip("\"'")
            normalized = normalize_url(base_url, raw)
            if normalized:
                rewritten.append(f'url("{map_url(normalized)}")')
                changed = True
                continue
        rewritten.append(token.serialize())
    return "".join(rewritten)


def rewrite_css_urls(
    css_text: str,
    *,
    css_base_url: str,
    map_url: Callable[[str], str],
) -> str:
    nodes = tinycss2.parse_stylesheet(css_text, skip_whitespace=False, skip_comments=False)
    out: list[str] = []

    for node in nodes:
        if node.type in {"whitespace", "comment"}:
            out.append(node.serialize())
            continue

        if node.type == "at-rule":
            keyword = node.at_keyword
            prelude = node.prelude or []
            if node.lower_at_keyword == "import":
                rendered_prelude = _rewrite_import_prelude(
                    prelude,
                    base_url=css_base_url,
                    map_url=map_url,
                )
            else:
                rendered_prelude = _rewrite_component_values(
                    prelude,
                    base_url=css_base_url,
                    map_url=map_url,
                )
            if node.content is None:
                out.append(f"@{keyword} {rendered_prelude};")
            else:
                rendered_content = _rewrite_component_values(
                    node.content,
                    base_url=css_base_url,
                    map_url=map_url,
                )
                out.append(f"@{keyword} {rendered_prelude}{{{rendered_content}}}")
            continue

        if node.type == "qualified-rule":
            rendered_prelude = _rewrite_component_values(
                node.prelude,
                base_url=css_base_url,
                map_url=map_url,
            )
            rendered_content = _rewrite_component_values(
                node.content,
                base_url=css_base_url,
                map_url=map_url,
            )
            out.append(f"{rendered_prelude}{{{rendered_content}}}")
            continue

        out.append(node.serialize())

    return "".join(out)
