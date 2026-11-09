"""Normalize HTML reports through per-source mapping configurations.

The adapter knows how to pull embedded JSON out of HTML. Everything specific
to a source tool lives in its ``HtmlMappingConfig``.
"""

import dataclasses
import json
import re
import types
import typing
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from pydantic import BaseModel

from src.adapters.outbound.json_path import PathError, resolve
from src.configs.ingestion.html_mapping import (
    AttributeExtractor,
    Const,
    DictMapping,
    HtmlMappingConfig,
    JsAssignmentExtractor,
    ListMapping,
    Transform,
    Value,
)
from src.domain.gates.performance.performance_gate import PerformanceGate
from src.domain.report import Report


class _AttributeParser(HTMLParser):
    def __init__(self, attribute: str):
        super().__init__()
        self.attribute = attribute
        self.value: str | None = None

    def handle_starttag(self, tag, attrs):
        if self.value is None:
            self.value = dict(attrs).get(self.attribute)


def _extract(
    html: str, extractor: JsAssignmentExtractor | AttributeExtractor
) -> object:
    match extractor:
        case JsAssignmentExtractor(variable=variable):
            match = re.search(rf"{re.escape(variable)}\s*=\s*", html)
            if match is None:
                raise ValueError(f"No assignment to {variable} found")
            data, _ = json.JSONDecoder().raw_decode(html, match.end())
            return data
        case AttributeExtractor(attribute=attribute):
            parser = _AttributeParser(attribute)
            parser.feed(html)
            if parser.value is None:
                raise ValueError(f"No {attribute} attribute found")
            return json.loads(parser.value)


def _utc(value: object) -> datetime:
    return datetime.fromisoformat(str(value)).astimezone(UTC)


def _percent(part, whole):
    if whole == 0:
        raise ValueError("percent: whole is zero")
    return part / whole * 100


_TRANSFORMS: dict[str, Callable[..., object]] = {
    "subtract": lambda a, b: a - b,
    "percent": _percent,
    "seconds_between": lambda start, end: (_utc(end) - _utc(start)).total_seconds(),
    "date_of": lambda value: _utc(value).date().isoformat(),
    "time_of": lambda value: _utc(value).time().isoformat(),
}


def _value(value: Value, item: object, root: object) -> object:
    match value:
        case str():
            return resolve(value, item, root)
        case Const(const=const):
            return const
        case Transform(transform=name, args=args):
            return _TRANSFORMS[name](*(_value(arg, item, root) for arg in args))


def _dataclass_in(hint: object) -> type:
    """Return the dataclass in ``X``, ``X | None``, ``list[X]`` or ``dict[K, X]``."""
    if dataclasses.is_dataclass(hint):
        return typing.cast(type, hint)
    if isinstance(hint, types.UnionType) or typing.get_origin(hint) in (list, dict):
        for arg in reversed(typing.get_args(hint)):
            if dataclasses.is_dataclass(arg):
                return typing.cast(type, arg)
    raise TypeError(f"No dataclass in {hint!r}")


def _field_value(mapping: object, hint: object, item: object, root: object):
    match mapping:
        case str() | Const() | Transform():
            return _value(mapping, item, root)
        case ListMapping():
            target = _dataclass_in(hint)
            return [
                _build(mapping.item, target, element, root)
                for element in _list(mapping.for_each, item, root)
            ]
        case DictMapping():
            target = _dataclass_in(hint)
            return {
                str(_value(mapping.key, element, root)): _build(
                    mapping.item, target, element, root
                )
                for element in _list(mapping.for_each, item, root)
            }
        case dict():
            return {key: _value(value, item, root) for key, value in mapping.items()}
        case BaseModel():
            return _build(mapping, _dataclass_in(hint), item, root)
    raise TypeError(f"Unsupported mapping {mapping!r}")


def _list(path: str, item: object, root: object) -> list:
    elements = resolve(path, item, root)
    if not isinstance(elements, list):
        raise PathError(f"for_each path {path!r} does not resolve to a list")
    return elements


def _build[T](mapping: BaseModel, target: type[T], item: object, root: object) -> T:
    """Build ``target`` from ``mapping``; ``None`` keeps the domain default."""
    hints = typing.get_type_hints(target)
    kwargs = {}
    for field in dataclasses.fields(typing.cast(typing.Any, target)):
        if field.name not in type(mapping).model_fields:
            continue
        value = getattr(mapping, field.name)
        if value is not None:
            kwargs[field.name] = _field_value(value, hints[field.name], item, root)
        elif (
            field.default is dataclasses.MISSING
            and field.default_factory is dataclasses.MISSING
        ):
            kwargs[field.name] = None
    return target(**kwargs)


class HTMLReport:
    def __init__(self, mappings: Mapping[str, HtmlMappingConfig]):
        self.mappings = dict(mappings)

    def ingest(self, report_path: str | Path, source: str) -> Report:
        """Normalize the ``source`` report at ``report_path`` into domain evidence."""

        mapping = self.mappings.get(source)
        if mapping is None:
            raise ValueError(f"No ingestion mapping configured for source {source!r}")
        path = Path(report_path)
        try:
            data = _extract(path.read_text(encoding="utf-8"), mapping.extractor)
            report = _build(mapping.report, Report, data, data)
            report.gates = [
                _build(mapping.performance_gate, PerformanceGate, data, data)
            ]
        except ValueError as error:
            raise ValueError(f"Cannot ingest {path} as {source!r}: {error}") from error
        report.source_path = str(path)
        return report
