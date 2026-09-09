"""Parser registry."""

from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeAlias, TypeVar

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, TypeAdapter

from bonsai_libs.parse.core.base import BaseParser, StreamOrPath
from bonsai_libs.parse.exceptions import (
    InvalidDataFormat,
    UnsupportedSoftwareError,
    UnsupportedVersionError,
)
from bonsai_libs.parse.models.enums import AnalysisSoftware, AnalysisType

ParserClass: TypeAlias = type[BaseParser]
ParserFn: TypeAlias = Callable[..., "ParserOutput"]
ParserRegistryEntry: TypeAlias = ParserClass | ParserFn
ModelClass: TypeAlias = type[BaseModel]
TEntry = TypeVar("TEntry")


@dataclass(order=True, slots=True)
class VersionRange(Generic[TEntry]):
    """Maps a registry entry to an inclusive software-version interval."""

    min_version: Version
    max_version: Version
    entry: TEntry


_PARSER_REGISTRY: dict[str, list[VersionRange[ParserRegistryEntry]]] = {}
_RESULT_MODEL_REGISTRY: dict[tuple[AnalysisSoftware, AnalysisType], ModelClass] = {}
_RESULT_ELEMENT_MODEL_REGISTRY: dict[tuple[str, str], dict[str, ModelClass | TypeAdapter]] = {}


def _normalize_version(version: str | Version) -> Version:
    """Normalize a user supplied version to a packaging.version object."""
    if isinstance(version, Version):
        return version
    if isinstance(version, str):
        try:
            return Version(version)
        except InvalidVersion as exc:
            raise InvalidDataFormat(f"Invalid version format: {version!r}") from exc
    raise TypeError(f"Version must be str or Version, got {type(version).__name__}")


def _registry_key(software: str, subcommand: str | None) -> str:
    """Build the registry lookup key from software and optional subcommand.

    When a subcommand is given the key becomes 'software.subcommand'
    (e.g. 'samtools.coverage', 'samtools.stats'), forming a single composite
    key — not two separate registrations — so multiple parsers can share the
    same software name without colliding.
    """
    return f"{software}.{subcommand}" if subcommand else software


def register_parser(
    software: str,
    min_version: str | None = None,
    max_version: str | None = None,
    *,
    subcommand: str | None = None,
):
    """Decorator to register a parser for a range of versions.

    Null values means either undefined or no upper range.
    Ensures version ranges do not overlap for a given software.
    """

    min_version = min_version or "0.0.0"
    max_version = max_version or "99999.0.0"

    def wrapper(cls: ParserRegistryEntry):
        new_min = _normalize_version(min_version)
        new_max = _normalize_version(max_version)

        key = _registry_key(software, subcommand)

        # Fetch existing ranges for this software
        existing_ranges = _PARSER_REGISTRY.get(key, [])

        # Check for overlapping version ranges
        for span in existing_ranges:
            if not (new_max < span.min_version or new_min > span.max_version):
                # Ranges overlap → safety error
                raise ValueError(
                    f"Cannot register parser {cls.__name__} for software '{key}' "
                    f"with version range [{new_min}, {new_max}] because it overlaps "
                    f"with existing parser {span.entry.__name__} range "
                    f"[{span.min_version}, {span.max_version}]."
                )

        # Safe to register
        v_range = VersionRange(
            min_version=new_min,
            max_version=new_max,
            entry=cls,
        )
        _PARSER_REGISTRY.setdefault(key, []).append(v_range)

        return cls

    return wrapper


def get_parser(
    software: str, *, version: str, subcommand: str | None = None
) -> ParserRegistryEntry:
    """Get parser from registry."""
    if not isinstance(software, str):
        raise TypeError(f"`software` must be str, got {type(software).__name__}")

    key = _registry_key(software, subcommand)

    if key not in registered_softwares():
        raise UnsupportedSoftwareError(f"No parser registered for software: {key}")

    # Normalize version to PkgVersion
    v = _normalize_version(version)

    for span in sorted(_PARSER_REGISTRY[key], key=lambda r: (r.min_version, r.max_version)):
        if span.min_version <= v <= span.max_version:
            return span.entry

    # Return the correct error.
    raise UnsupportedVersionError(f"No parser available for software '{key}' version {v}")


def registered_softwares() -> list[str]:
    """Get registered softwares."""

    return list(_PARSER_REGISTRY.keys())


def registered_version_ranges(software: str) -> list[VersionRange]:
    """Get ranges for registered software."""

    return _PARSER_REGISTRY.get(software, [])


def resolve_parser(entry, **init_kwargs) -> Callable[..., "ParserOutput"]:
    """Resolve registry entry to a callable parse function.

    If works with both parser classes and parse functions.
    """

    if isinstance(entry, type) and issubclass(entry, BaseParser):
        return entry(**init_kwargs).parse
    if callable(entry):
        return entry
    raise TypeError(f"Unsupported registry entry: {entry!r}")


def run_parser(
    software: str | AnalysisSoftware,
    *,
    version: str,
    data: StreamOrPath,
    subcommand: str | None = None,
    want: set[AnalysisType] | None = None,
    parser_init: dict[str, Any] | None = None,
    **parse_kwargs: Any,
) -> "ParserOutput":
    """Run parser for given software, version and data."""

    if not isinstance(software, (AnalysisSoftware, str)):
        raise ValueError(f"Invalid input for 'run_parser', got {type(software)}")

    entry = get_parser(software, version=version, subcommand=subcommand)
    parse_fn = resolve_parser(entry, **(parser_init or {}))
    ev = parse_fn(data, want=want, **parse_kwargs)
    # add version to results
    return ev.model_copy(update={"software_version": version})


def register_result_model(
    software: str | AnalysisSoftware,
    analysis_type: str | AnalysisType,
):
    """Decorator to register a result model.

    Prevents duplicate registration for the same (software, analysis_type) key.
    """
    # Normalize to strings to keep the registry consistent.
    software_key = str(software)
    analysis_type_key = str(analysis_type)

    def wrapper(cls: ModelClass) -> ModelClass:
        key = (software_key, analysis_type_key)

        if key in _RESULT_MODEL_REGISTRY:
            existing = _RESULT_MODEL_REGISTRY[key].__name__
            new = cls.__name__
            raise ValueError(
                f"Result model already registered for software={software_key!r}, "
                f"analysis_type={analysis_type_key!r}. "
                f"Existing model: {existing}, attempted new model: {new}"
            )

        _RESULT_MODEL_REGISTRY[key] = cls
        return cls

    return wrapper


def get_result_model(
    software: str | AnalysisSoftware,
    analysis_type: str | AnalysisType,
) -> ModelClass | None:
    """Return the registered result model class for software/type/version, or None."""
    software_key = str(software)
    analysis_type_key = str(analysis_type)
    key = (software_key, analysis_type_key)

    model_cls = _RESULT_MODEL_REGISTRY.get(key)
    if model_cls:
        return model_cls

    return None  # No result model registered for this software/type


def register_result_element_models(
    software: str | AnalysisSoftware,
    analysis_type: str | AnalysisType,
    *,
    field_models: dict[str, ModelClass | TypeAdapter],
) -> None:
    """Register nested element field models for a result type."""
    key = (str(software), str(analysis_type))
    if key in _RESULT_ELEMENT_MODEL_REGISTRY:
        existing = _RESULT_ELEMENT_MODEL_REGISTRY[key]
        raise ValueError(
            f"Nested field models already registered for software={software!r}, "
            f"analysis_type={analysis_type!r}. Existing={list(existing.keys())}"
        )
    _RESULT_ELEMENT_MODEL_REGISTRY[key] = field_models.copy()


def get_result_element_models(
    software: str | AnalysisSoftware,
    analysis_type: str | AnalysisType,
) -> dict[str, ModelClass | TypeAdapter] | None:
    """Return nested element field models for a result type."""
    key = (str(software), str(analysis_type))
    return _RESULT_ELEMENT_MODEL_REGISTRY.get(key)


def _hydrate_raw_value(model_cls: ModelClass | TypeAdapter, raw_value: Any) -> Any:
    if isinstance(model_cls, TypeAdapter):
        return model_cls.validate_python(raw_value)
    if issubclass(model_cls, BaseModel):
        return model_cls.model_validate(raw_value)
    raise TypeError(f"Unsupported nested element model type: {type(model_cls).__name__}")


def _hydrate_nested_fields(
    result_obj: BaseModel, field_models: dict[str, ModelClass | TypeAdapter]
) -> BaseModel:
    updates: dict[str, Any] = {}

    for field_name, model_cls in field_models.items():
        if not hasattr(result_obj, field_name):
            continue

        raw_value = getattr(result_obj, field_name)
        if raw_value is None:
            continue

        if isinstance(raw_value, list):
            if isinstance(model_cls, TypeAdapter):
                updates[field_name] = model_cls.validate_python(raw_value)
            else:
                updates[field_name] = [_hydrate_raw_value(model_cls, item) for item in raw_value]
        else:
            updates[field_name] = _hydrate_raw_value(model_cls, raw_value)

    return result_obj.model_copy(update=updates)


def hydrate_result(*, software: str, analysis_type: str, result: dict) -> Any:
    """Hydrate json data into a typed result object or raw data if unknown."""
    if not isinstance(result, dict | list | int | str | float | bool | None):
        raise ValueError("Expected result to be a JSON-serializable dict, list, primitive or None")

    model_cls = get_result_model(
        software=software,
        analysis_type=analysis_type,
    )
    if model_cls is None:
        return result

    if isinstance(model_cls, TypeAdapter):
        return model_cls.validate_python(result)

    elif issubclass(model_cls, BaseModel):
        result_obj = model_cls.model_validate(result)
        field_models = get_result_element_models(
            software=software,
            analysis_type=analysis_type,
        )
        if field_models:
            return _hydrate_nested_fields(result_obj, field_models)
        return result_obj

    raise TypeError(f"Unsupported model class type for hydration: {type(model_cls).__name__}")
