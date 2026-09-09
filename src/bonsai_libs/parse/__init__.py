"""Parse output of softwares in pipeline."""

from importlib import import_module
from pathlib import Path
from .core.registry import (
    get_parser,
    registered_softwares,
    registered_version_ranges,
    run_parser,
    hydrate_result,
)

# auto-import all modules under parse/parsers to ensure that all parsers are registered
PARSER_DIR = "parsers"
_pkg_dir = Path(__file__).parent.joinpath(PARSER_DIR)
for file in _pkg_dir.glob("*.py"):
    if file.name not in ("__init__.py", "utils.py"):
        import_module(f"{__name__}.{PARSER_DIR}.{file.stem}")

__all__ = [
    "get_parser",
    "registered_softwares",
    "registered_version_ranges",
    "run_parser",
    "hydrate_result",
]
