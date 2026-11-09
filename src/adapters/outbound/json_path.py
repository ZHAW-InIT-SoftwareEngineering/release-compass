"""Resolve the small path language used by ingestion mappings.

Syntax, segment by segment:

- ``name`` or ``.name``: object key (letters, digits, ``_``, ``-``)
- ``["any key"]``: object key that contains other characters, such as dots
- ``[0]``: list index
- ``[field=value]``: the single list item whose ``field`` equals ``value``
- ``[field!=value]``: all list items whose ``field`` differs from ``value``

Paths resolve against the current item. A ``$.`` prefix resolves against the
document root instead. A filter value starting with ``@`` is a path resolved
against the current item, e.g. ``$.stats[name=@name]``.
"""

import re

_SEGMENT = re.compile(
    r"""
    \.?(?P<key>[A-Za-z0-9_-]+)
    | \["(?P<quoted>[^"]*)"\]
    | \[(?P<index>\d+)\]
    | \[(?P<field>[A-Za-z0-9_-]+)(?P<op>!?=)(?P<value>[^\]]*)\]
    """,
    re.VERBOSE,
)


class PathError(ValueError):
    pass


def resolve(path: str, item: object, root: object) -> object:
    current = item
    remaining = path
    if path.startswith("$."):
        current, remaining = root, path[2:]
    position = 0
    while position < len(remaining):
        match = _SEGMENT.match(remaining, position)
        if match is None:
            raise PathError(
                f"Invalid path syntax at {remaining[position:]!r} in {path!r}"
            )
        current = _step(match, current, item, root, path)
        position = match.end()
    return current


def _step(match: re.Match, current: object, item: object, root: object, path: str):
    key = match["key"] if match["key"] is not None else match["quoted"]
    if key is not None:
        if not isinstance(current, dict) or key not in current:
            raise PathError(f"Key {key!r} not found for {path!r}")
        return current[key]
    if not isinstance(current, list):
        raise PathError(f"Expected a list at {match[0]!r} in {path!r}")
    if match["index"] is not None:
        index = int(match["index"])
        if index >= len(current):
            raise PathError(f"Index {index} out of range for {path!r}")
        return current[index]

    field, value = match["field"], match["value"]
    if value.startswith("@"):
        value = str(resolve(value[1:], item, root))
    if match["op"] == "!=":
        return [
            element
            for element in current
            if not isinstance(element, dict) or str(element.get(field)) != value
        ]
    selected = [
        element
        for element in current
        if isinstance(element, dict) and str(element.get(field)) == value
    ]
    if len(selected) != 1:
        raise PathError(
            f"Expected one item with {field}={value!r} for {path!r}, "
            f"found {len(selected)}"
        )
    return selected[0]
