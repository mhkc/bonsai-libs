"""Tests for parser and result-model registry behavior."""

import pytest
from packaging.version import Version
from typing import Any
from pydantic import BaseModel

from bonsai_libs.parse.exceptions import InvalidDataFormat, UnsupportedVersionError
from bonsai_libs.parse.core.registry import (
    VersionRange,
    _normalize_version,
    register_parser,
    register_result_model,
    register_result_element_models,
    _PARSER_REGISTRY,
    _RESULT_MODEL_REGISTRY,
    get_parser,
    get_result_model,
    hydrate_result,
)

# ---------------------------------------------------------------------------
# Dummy Classes
# ---------------------------------------------------------------------------


class DummyParser:
    pass


class DummyParser2:
    pass


class DummyModel:
    pass


# ---------------------------------------------------------------------------
# Version Normalization
# ---------------------------------------------------------------------------


def test_normalize_version_happy_path():
    """Version normalization accepts strings and Version objects."""
    cases = ["1.0.0", "1.0", "1", Version("2.3.4")]

    for value in cases:
        result = _normalize_version(value)
        assert isinstance(result, Version)


def test_normalize_version_invalid_inputs():
    """Invalid or inappropriate version formats raise clear exceptions."""
    with pytest.raises(InvalidDataFormat):
        _normalize_version("invalid")

    with pytest.raises(TypeError):
        _normalize_version(lambda: None)


# ---------------------------------------------------------------------------
# Parser Registration — Version Range Safety
# ---------------------------------------------------------------------------


def assert_registers(software, min_v, max_v, cls):
    """Helper to register and retrieve stored version ranges."""
    register_parser(software, min_v, max_v)(cls)
    return _PARSER_REGISTRY[software]


def test_register_single_range():
    """Registering one parser stores one version range."""
    ranges = assert_registers("tool", "1.0.0", "2.0.0", DummyParser)

    assert len(ranges) == 1
    vr = ranges[0]
    assert isinstance(vr, VersionRange)
    assert vr.entry is DummyParser
    assert vr.min_version == Version("1.0.0")
    assert vr.max_version == Version("2.0.0")


def test_non_overlapping_ranges_allowed():
    """Two non-overlapping ranges should register without error."""
    assert_registers("tool", "1.0.0", "2.0.0", DummyParser)
    assert_registers("tool", "2.1.0", "3.0.0", DummyParser2)

    ranges = sorted(_PARSER_REGISTRY["tool"], key=lambda r: r.min_version)
    assert [r.entry for r in ranges] == [DummyParser, DummyParser2]


@pytest.mark.parametrize(
    "existing, new",
    [
        (("1.0.0", "3.0.0"), ("2.0.0", "4.0.0")),  # partial overlap
        (("1.0.0", "5.0.0"), ("2.0.0", "3.0.0")),  # containment
        (("1.0.0", "2.0.0"), ("1.0.0", "2.0.0")),  # exact match
        (("1.0.0", "2.0.0"), ("2.0.0", "3.0.0")),  # touching edge (inclusive overlap)
    ],
)
def test_overlapping_ranges_rejected(existing, new):
    """All forms of overlap should raise ValueError."""
    (e_min, e_max), (n_min, n_max) = existing, new

    assert_registers("tool", e_min, e_max, DummyParser)

    with pytest.raises(ValueError):
        assert_registers("tool", n_min, n_max, DummyParser2)


def test_mixed_version_types_still_overlap():
    """Mixing Version objects and strings still applies overlap rules."""
    assert_registers("tool", Version("1.0.0"), Version("2.0.0"), DummyParser)

    with pytest.raises(ValueError):
        assert_registers("tool", "1.5.0", "2.5.0", DummyParser2)


# ---------------------------------------------------------------------------
# Parser Retrieval
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["1.0.0", "1.2.0", "1.5.0"])
def test_get_supported_parser(version):
    """get_parser returns the expected parser for supported versions."""
    assert_registers("tool", "1.0.0", "1.5.0", DummyParser)

    parser = get_parser("tool", version=version)
    assert parser == DummyParser


@pytest.mark.parametrize("version", ["0.9.0", "1.5.1"])
def test_get_unsupported_parser(version):
    """Unsupported versions should raise UnsupportedVersionError."""
    assert_registers("tool", "1.0.0", "1.5.0", DummyParser)

    with pytest.raises(UnsupportedVersionError):
        get_parser("tool", version=version)


# ---------------------------------------------------------------------------
# Result Model Registration
# ---------------------------------------------------------------------------


def test_register_result_model():
    """Result models register correctly under (software, analysis)."""
    register_result_model("soft", "analysis")(DummyModel)
    assert ("soft", "analysis") in _RESULT_MODEL_REGISTRY


def test_reregister_result_model_throws_error():
    """Re-registering a model for the same (software, analysis) should raise."""
    register_result_model("soft", "analysis")(DummyModel)

    with pytest.raises(ValueError):
        register_result_model("soft", "analysis")(DummyModel)


@pytest.mark.parametrize(
    "key, exists",
    [
        (("soft", "analysis"), True),
        (("soft", "missing"), False),
    ],
)
def test_get_result_model(key, exists):
    """get_result_model returns model only when registered."""
    register_result_model("soft", "analysis")(DummyModel)
    result = get_result_model(*key)

    assert (result == DummyModel) == exists


class DummyElementTypeResult(BaseModel):
    genes: list[Any] = []
    variants: list[Any] = []


class DummyGene(BaseModel):
    name: str


class DummyVariant(BaseModel):
    pos: int


def test_register_result_element_models_and_hydrate_nested_fields():
    register_result_model("soft", "analysis")(DummyElementTypeResult)
    register_result_element_models(
        "soft",
        "analysis",
        field_models={"genes": DummyGene, "variants": DummyVariant},
    )

    raw = {"genes": [{"name": "g1"}], "variants": [{"pos": 42}]}
    hydrated = hydrate_result(software="soft", analysis_type="analysis", result=raw)

    assert isinstance(hydrated, DummyElementTypeResult)
    assert isinstance(hydrated.genes[0], DummyGene)
    assert isinstance(hydrated.variants[0], DummyVariant)
