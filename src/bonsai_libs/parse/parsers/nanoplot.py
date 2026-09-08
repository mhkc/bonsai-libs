"""Nanoplot parser."""

import re
from pathlib import Path
from typing import Any, Literal

from bonsai_libs.parse.io.utils import ensure_text_stream
from bonsai_libs.parse.core.base import SingleAnalysisParser, StreamOrPath
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.models.enums import AnalysisSoftware, AnalysisType
from bonsai_libs.parse.models.qc import NanoPlotQcCutoff, NanoPlotQcResult, NanoPlotSummary

from .utils import safe_float, safe_int, safe_percent

NANOPLOT = AnalysisSoftware.NANOPLOT
PERCENTAGE_PATTERN = re.compile(r"\(([0-9\.%]+)\)")

SUMMARY_KEY_MAP = {
    "Mean read length": "mean_read_length",
    "Mean read quality": "mean_read_quality",
    "Median read length": "median_read_length",
    "Median read quality": "median_read_quality",
    "Number of reads": "n_reads",
    "Read length N50": "read_length_n50",
    "STDEV read length": "stdev_read_length",
    "Total bases": "total_bases",
}

Mode = Literal["summary", "qc_cutoff", "top_quality", "top_longest"]


def _process_line(line: str, *, mode: Mode) -> tuple[str, str | float]:
    """Process row depending on the mode."""
    label = None
    value = None
    if mode == "summary":
        raw_label, raw_value = line.split(":", maxsplit=1)
        label = SUMMARY_KEY_MAP.get(raw_label.strip())
        value = safe_float(raw_value.strip())

    if mode == "qc_cutoff":
        raw_label, raw_value = line.split(":", maxsplit=1)
        label = raw_label.strip()
        # Get percentage "num (num%) x.xMb"
        m = PERCENTAGE_PATTERN.search(raw_value.strip())
        if m:
            value = safe_percent(m.group(1))

    if mode == "top_quality":
        raw_label, raw_value = line.split(":", maxsplit=1)
        label = raw_label.strip()
        value = safe_float(raw_value.strip().split(" ")[0])

    if mode == "top_longest":
        raw_label, raw_value = line.split(":", maxsplit=1)
        label = raw_label.strip()
        value = safe_int(raw_value.strip().split(" ")[0])

    return label, value


def _read_nanoplot(source: StreamOrPath, *, encoding: str = "utf-8") -> dict[str, Any]:
    """Read nanoplot file."""
    if isinstance(source, (str, Path)):
        with open(source, "r", encoding=encoding, newline="") as fp:
            return _read_nanoplot(fp, encoding=encoding)

    text_stream = ensure_text_stream(source, encoding=encoding)

    results: dict[Mode, Any] = {
        "summary": {},
        "qc_cutoff": {},
        "top_quality": {},
        "top_longest": {},
    }
    mode: Mode = None
    for raw in text_stream:
        line = raw.strip()
        if not line:
            continue

        # detect section header
        if line.lower().startswith("general "):
            mode = "summary"
            continue
        if line.lower().startswith("number, percentage"):
            mode = "qc_cutoff"
            continue
        if line.lower().startswith("top 5 highest mean"):
            mode = "top_quality"
            continue
        if line.lower().startswith("top 5 longest reads"):
            mode = "top_longest"
            continue

        # Parse based on mode
        label, value = _process_line(line, mode=mode)
        results[mode][label] = value
    return results


def _to_qc_result(data: dict[str, Any]) -> NanoPlotQcResult:
    """Convert raw nanoplot results to a NanoPlotQc object."""
    s = data["summary"]
    summary = NanoPlotSummary(
        mean_read_length=s["mean_read_length"],
        mean_read_quality=s["mean_read_quality"],
        median_read_length=s["median_read_length"],
        median_read_quality=s["median_read_quality"],
        n_reads=s["n_reads"],
        read_length_n50=s["read_length_n50"],
        stdev_read_length=s["stdev_read_length"],
        total_bases=s["total_bases"],
    )

    q = data["qc_cutoff"]
    qc_cutoff = NanoPlotQcCutoff(
        q10=q[">Q10"],
        q15=q[">Q15"],
        q20=q[">Q20"],
        q25=q[">Q25"],
        q30=q[">Q30"],
    )
    top_longest = sorted(list(data["top_longest"].values()), reverse=True)
    top_quality = sorted(list(data["top_quality"].values()), reverse=True)
    return NanoPlotQcResult(
        summary=summary,
        qc_cutoff=qc_cutoff,
        top_longest=top_longest,
        top_quality=top_quality,
    )


@register_parser(NANOPLOT)
class NanoplotParser(SingleAnalysisParser):
    """Nanoplot parser."""

    software = NANOPLOT
    parser_name = "NanoplotParser"
    parser_version = 1
    schema_version = 1

    analysis_type = AnalysisType.QC
    produces = {analysis_type}

    def _parse_one(
        self,
        source: StreamOrPath,
        **kwargs: Any,
    ) -> NanoPlotQcResult | None:
        """Parse nanoplot output and return NanoPlotQcResult."""

        raw_data = _read_nanoplot(source)
        return _to_qc_result(raw_data)
