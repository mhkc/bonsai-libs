"""API input and response models."""
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from pydantic import BaseModel, Field

from bonsai_libs.types.common import Model, IgnoreExtraModelMixin


class Visibility(StrEnum):
    """Determines the visibilty of a record."""

    PRIVATE = "private"
    ORG = "organization"
    PUBLIC = "public"


class SequencingPlatforms(StrEnum):
    """Supported sequencing platforms."""

    ILLUMUNA = "illumina"
    IONTORRENT = "ion torrent"
    ONT = "oxford nanopore technologies"
    BGI = "bgi"
    PACBIO = "Pacific Biosciences"


class SequencingInfo(Model, IgnoreExtraModelMixin):
    """Information on the sample was sequenced."""

    sequencing_run_id: str
    platform: SequencingPlatforms
    instrument: str | None = None
    method: dict[str, str] = Field(default_factory=dict)
    sequenced_at: datetime | None = None


class GenericMetadataEntry(Model):
    """Container of basic metadata information"""

    fieldname: str
    value: str | int | float
    category: str
    type: Literal["string", "integer", "float"]


class DatetimeMetadataEntry(Model):
    """Container of basic metadata information"""

    fieldname: str
    value: datetime
    category: str
    type: Literal["datetime"] = "datetime"


class InputTableMetadata(Model):
    """Metadata table info recieved by API."""

    fieldname: str
    value: str
    category: str = "general"
    type: Literal["table"] = "table"


InputMetaEntry = Annotated[
    DatetimeMetadataEntry
    | InputTableMetadata
    | GenericMetadataEntry,
    Field(discriminator='type')
]

class InputSampleInfo(Model, IgnoreExtraModelMixin):  # pylint: disable=too-few-public-methods
    """Defines output structure of group info used for creation."""

    sample_id: str | None = None
    sample_name: str
    lims_id: str | None = None

    groups: list[str] = Field(default_factory=list, description="Group ids")

    sequencing: SequencingInfo | None = None
    metadata: list[InputMetaEntry] = Field(default_factory=list)

    # preparation for role based access controll
    owners: list[str] = Field(default_factory=list, description="Owner identifiers (user:<id>)")
    owner_organizations: list[str] = Field(default_factory=list, description="Organization ids (org:<id>)")
    access_groups: list[str] = Field(default_factory=list, description="Optional access groups")
    visibility: Visibility = Visibility.PUBLIC


class CreateSampleResponse(BaseModel):
    """Expected response data when creating a sample."""

    inserted_id: str
    internal_sample_id: str
    external_sample_id: str
