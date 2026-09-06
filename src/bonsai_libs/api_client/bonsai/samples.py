"""Sample-related API methods for Bonsai."""
from typing import Any, BinaryIO
import logging
import mimetypes
from http import HTTPStatus

from bonsai_libs.api_client.core.base import BaseClient
from bonsai_libs.api_client.core.exceptions import ClientError, NotModifiedError, UnauthorizedError

from .models import (
    ApiGetSamplesDetailsInput,
    CreateSampleResponse,
    GenomicResourceInput,
    PipelineRunInput,
    SampleBasketObject,
    SampleInfoInput,
    SubmittedJob,
    UploadAnalysisResultInput,
    UploadAnalysisResultResponse,
    UploadResultMeta,
    VariantCurationRecord,
    OpHeaders,
)

LOG = logging.getLogger(__name__)


class SamplesMixin(BaseClient):
    """Sample domain API functions."""

    def create_sample(
        self, sample_info: SampleInfoInput, *, headers: OpHeaders = None
    ) -> CreateSampleResponse:
        """Create a new sample in Bonsai."""

        payload = sample_info.model_dump(mode="json")

        try:
            resp = self.request_json(
                "POST",
                "samples/",
                json=payload,
                headers=headers,
                expected_status=(HTTPStatus.CREATED,),
            )
        except ClientError as exc:
            LOG.error(
                "Something went wrong creating the sample; %s",
                exc,
                extra={"payload": payload},
            )
            raise

        return CreateSampleResponse.model_validate(resp.data)

    def add_samples_to_group(
        self, group_id: str, *, sample_ids: list[str], headers: OpHeaders = None
    ):
        """Add sample to group."""

        url = f"groups/{group_id}/samples"
        params = {"s": sample_ids}

        try:
            resp = self.put(
                url,
                params=params,
                headers=headers,
                expected_status=(HTTPStatus.OK,),
            )
        except ClientError as exc:
            LOG.error(
                "Something went wrong creating the sample; %s",
                exc,
                extra={"params": params},
            )
            raise

        return resp.data

    def add_reference_genome_to_sample(
        self,
        sample_id: str,
        *,
        reference_genome_id: str,
        headers: OpHeaders = None,
    ) -> dict[str, Any]:
        """Associate a reference genome with a sample.

        Returns information of the reference genome."""
        try:
            resp = self.request_json(
                "PUT",
                f"samples/{sample_id}/reference-genome",
                headers=headers,
                json={"reference_genome_id": reference_genome_id},
                expected_status=(HTTPStatus.OK, HTTPStatus.NOT_MODIFIED),
            )
        except UnauthorizedError:
            LOG.error("Unauthorised when adding a reference genome for sample=%s", sample_id)
            raise
        except NotModifiedError:
            LOG.warning(
                "Sample %s already associated with genome id=%s",
                sample_id,
                reference_genome_id,
            )
            raise
        except ClientError:
            LOG.error(
                "Something went wrong when associating reference genome id=%s to sample=%s",
                reference_genome_id,
                sample_id,
            )
            raise
        return resp.data

    def add_annotation_track_to_sample(
        self,
        sample_id: str,
        *,
        track: GenomicResourceInput,
        force: bool = False,
        headers: OpHeaders = None,
    ) -> dict[str, Any]:
        """Add genomic resource to sample.

        Raises ConflictError (409) if the sample already has resources for
        this pipeline run and force=False.
        """
        payload = track.model_dump(exclude_none=True)
        try:
            resp = self.request_json(
                "POST",
                f"samples/{sample_id}/resources",
                headers=headers,
                json=payload,
                params={"force": force},
            )
        except UnauthorizedError:
            LOG.error("Unauthorised when adding a reference genome for sample=%s", sample_id)
            raise
        except ClientError:
            LOG.error(
                "Something went wrong when adding a genomic resource to sample; id=%s",
                sample_id,
            )
            raise
        return resp.data

    def upload_sourmash_signature(
        self, sample_id: str, *, signature_file: BinaryIO, filename: str = "signature.json", headers: OpHeaders = None
    ) -> str:
        """Upload sourmash signature to sample"""
        try:
            resp = self.request_multipart(
                f"samples/{sample_id}/signature",
                headers=headers,
                files={"signature": (filename, signature_file)},
                expected_status=(HTTPStatus.OK, HTTPStatus.CREATED),
            )
        except UnauthorizedError:
            LOG.error("Unauthorised when uploading sourmash signature for sample=%s", sample_id)
            raise
        except ClientError:
            LOG.error(
                "Something went wrong when uploading a sourmash signature for sample=%s",
                sample_id,
            )
            raise
        return resp.data

    def upload_ska_index(
        self, sample_id: str, *, index_path: str, force: bool = False, headers: OpHeaders = None
    ) -> str:
        """Upload ska index to sample"""
        try:
            resp = self.request_json(
                "POST",
                f"samples/{sample_id}/ska_index",
                json={"index": index_path, "force": force},
                headers=headers,
            )
        except UnauthorizedError:
            LOG.error("Unauthorised when uploading ska index for sample=%s", sample_id)
            raise
        except ClientError:
            LOG.error("Something went wrong when uploading ska index for sample=%s", sample_id)
            raise
        return resp.data

    def add_pipeline_run(
        self, sample_id: str, *, pipeline_run: PipelineRunInput, headers: OpHeaders = None
    ) -> str:
        """Add a pipeline run ID to a sample."""
        payload = pipeline_run.model_dump(mode="json")
        try:
            resp = self.request_json(
                "POST",
                f"samples/{sample_id}/pipeline-runs",
                json=payload,
                headers=headers,
                expected_status=(HTTPStatus.OK, HTTPStatus.CREATED),
            )
        except UnauthorizedError:
            LOG.error("Unauthorised when creating a pipeline run for sample=%s", sample_id)
            raise
        except ClientError as exc:
            LOG.error(
                "Something went wrong when adding a pipeline run to sample=%s",
                sample_id,
                extra={"exception": exc, "payload": payload},
            )
            raise
        return resp.data  # return inserted pipeline run ID

    def upload_analysis_result(
        self, result: UploadAnalysisResultInput, *, headers: OpHeaders = None, force: bool = False
    ) -> UploadAnalysisResultResponse:
        """Upload a analysis results to a existing sample."""

        data = result.model_dump(exclude={"file"})
        data["force"] = force

        mime = mimetypes.guess_type(result.file.name)[0] or "application/octet-stream"

        with result.file.open("rb") as fh:
            files = {"file": (result.file.name, fh, mime)}

            try:
                resp = self.request_multipart(
                    "analysis/",
                    data=data,
                    files=files,
                    headers=headers,
                    expected_status=(HTTPStatus.CREATED,),
                )
            except UnauthorizedError as exc:
                LOG.error("Failed authenticating user=%s", result.sample_id, exc_info=exc)
                raise

            request_id = resp.headers.get("x-request-id") or resp.headers.get("X-Request-Id")
            meta = UploadResultMeta(status=resp.status, request_id=request_id)

            body = resp.data or {}
            return UploadAnalysisResultResponse(
                sample_id=result.sample_id,
                pipeline_run_id=result.pipeline_run_id,
                analysis_id=body.get("analysis_id"),
                software=result.software,
                software_version=result.software_version,
                envelopes=body.get("envelopes", {}),
                meta=meta,
            )

    def get_igv_config(self, sample_id: str, *, analysis_id: str | None = None, variant_id: str | None = None, headers: OpHeaders = None) -> dict[str, Any]:
        """Get a IGV configuration for a sample.

        Optional center the view on a variant by providing a analysis_id and variant_id
        """
        try:
            resp = self.request_json(
                "GET",
                f"samples/{sample_id}/igv-config",
                json={"analysis_id": analysis_id, "variant_id": variant_id},
                headers=headers,
            )
        except UnauthorizedError as exc:
            LOG.error("Failed authenticating user", exc_info=exc)
            raise
        return resp.data

    def add_samples_to_basket(
        self, samples: list[SampleBasketObject], *, headers: OpHeaders = None
    ) -> dict[str, Any]:
        """Add samples to user basket."""
        serialized = [s.model_dump() for s in samples]
        resp = self.request_json(
            "PUT",
            "users/basket",
            json=serialized,
            headers=headers,
            expected_status=(HTTPStatus.OK,),
        )
        return resp.data or {}

    def remove_samples_from_basket(
        self, sample_ids: list[str], *, headers: OpHeaders = None
    ) -> dict[str, Any]:
        """Remove samples from user basket."""
        resp = self.request_json(
            "DELETE",
            "users/basket",
            json=sample_ids,
            headers=headers,
            expected_status=(HTTPStatus.OK, HTTPStatus.NO_CONTENT),
        )
        return resp.data or {}

    def get_sample_summaries(
        self,
        *,
        group_id: str | None = None,
        sample_ids: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
        headers: OpHeaders = None,
    ) -> dict[str, Any]:
        """Get multiple sample summaries."""
        if sample_ids is not None and len(sample_ids) == 0:
            raise ValueError("sample_ids list cannot be empty")

        data = ApiGetSamplesDetailsInput(
            limit=limit, offset=offset, sid=sample_ids, group_id=group_id
        )
        resp = self.request_json(
            "POST",
            "samples/summary",
            json=data.model_dump(mode="json"),
            headers=headers,
            expected_status=(HTTPStatus.OK,),
        )
        return resp.data or {}

    def get_valid_summary_columns(self, *, headers: OpHeaders = None) -> dict[str, Any]:
        """Get valid columns for sample summaries."""
        resp = self.request_json(
            "GET",
            "samples/summary/manifest",
            headers=headers,
            expected_status=(HTTPStatus.OK,),
        )
        return resp.data or {}

    def delete_samples(self, sample_ids: list[str], *, headers: OpHeaders = None) -> dict[str, Any]:
        """Delete samples."""
        resp = self.request_json(
            "DELETE",
            "samples/",
            json=sample_ids,
            headers=headers,
            expected_status=(HTTPStatus.OK, HTTPStatus.NO_CONTENT),
        )
        return resp.data or {}

    def get_sample_by_id(
        self, sample_id: str, *, headers: OpHeaders = None
    ) -> dict[str, Any]:
        """Get a sample by ID."""
        resp = self.request_json(
            "GET",
            f"samples/{sample_id}",
            headers=headers,
            expected_status=(HTTPStatus.OK,),
        )
        return resp.data or {}

    def get_sample_by_external_id(
        self, external_sample_id: str, *, headers: OpHeaders = None
    ) -> dict[str, Any]:
        """Get a sample by the external id assigned by the calling system.

        Raises NotFoundError (404) if no sample has this external_sample_id.
        """
        resp = self.request_json(
            "GET",
            f"samples/external/{external_sample_id}",
            headers=headers,
            expected_status=(HTTPStatus.OK,),
        )
        return resp.data or {}

    def post_comment_to_sample(
        self, sample_id: str, comment: str, username: str, *, headers: OpHeaders = None
    ) -> dict[str, Any]:
        """Add a comment to a sample."""
        payload = {"comment": comment, "username": username}
        resp = self.request_json(
            "POST",
            f"samples/{sample_id}/comment",
            json=payload,
            headers=headers,
            expected_status=(HTTPStatus.OK, HTTPStatus.CREATED),
        )
        return resp.data or {}

    def remove_comment_from_sample(
        self, sample_id: str, comment_id: str, *, headers: OpHeaders = None
    ) -> dict[str, Any]:
        """Remove a comment from a sample."""
        resp = self.request_json(
            "DELETE",
            f"samples/{sample_id}/comment/{comment_id}",
            headers=headers,
            expected_status=(HTTPStatus.OK, HTTPStatus.NO_CONTENT),
        )
        return resp.data or {}

    def update_sample_qc_classification(
        self,
        sample_id: str,
        status: str,
        *,
        action: str | None = None,
        comment: str | None = None,
        headers: OpHeaders = None,
    ) -> dict[str, Any]:
        """Update QC classification for a sample."""
        payload = {"status": status, "action": action, "comment": comment}
        resp = self.request_json(
            "PUT",
            f"samples/{sample_id}/qc_status",
            json=payload,
            headers=headers,
            expected_status=(HTTPStatus.OK,),
        )
        return resp.data or {}

    def update_variant_info(
        self,
        sample_id: str,
        variant_ids: str,
        status: dict[str, str | list[str] | None],
        *,
        headers: OpHeaders = None,
    ) -> dict[str, Any]:
        """Update variant annotation for a sample."""
        payload = {"variant_ids": variant_ids, **status}
        resp = self.request_json(
            "PUT",
            f"samples/{sample_id}/resistance/variants",
            json=payload,
            headers=headers,
            expected_status=(HTTPStatus.OK,),
        )
        return resp.data or {}

    def create_curation(
        self,
        analysis_id: str,
        analysis_type: str,
        *,
        record: VariantCurationRecord,
        headers: OpHeaders = None,
    ) -> dict[str, Any]:
        """Create or update a variant curation."""
        payload = {"analysis_type": analysis_type, "curation": record.model_dump(mode="json")}
        resp = self.request_json(
            "POST",
            f"analysis/{analysis_id}/curations",
            json=payload,
            headers=headers,
            expected_status=(HTTPStatus.OK, HTTPStatus.CREATED),
        )
        return resp.data or {}

    def cluster_samples(
        self,
        sample_ids: list[str],
        *,
        method: str = "single",
        typing_method: str = "cgmlst",
        distance: str = "jaccard",
        headers: OpHeaders = None,
    ) -> SubmittedJob:
        """Cluster samples using specified typing method."""
        payload = {
            "sample_ids": sample_ids,
            "method": method,
            "distance": distance,
        }
        resp = self.request_json(
            "POST",
            f"cluster/{typing_method}/",
            json=payload,
            headers=headers,
            expected_status=(HTTPStatus.OK, HTTPStatus.ACCEPTED),
        )
        return SubmittedJob.model_validate(resp.data or {})

    def find_samples_similar_to_reference(
        self,
        sample_id: str,
        *,
        similarity: float = 0.5,
        limit: int | None = None,
        headers: OpHeaders = None,
    ) -> SubmittedJob:
        """Find samples similar to a reference sample."""
        payload = {"similarity": similarity, "limit": limit, "cluster": False}
        resp = self.request_json(
            "POST",
            f"samples/{sample_id}/similar",
            json=payload,
            headers=headers,
            expected_status=(HTTPStatus.OK, HTTPStatus.ACCEPTED),
        )
        return SubmittedJob.model_validate(resp.data or {})

    def find_and_cluster_similar_samples(
        self,
        sample_id: str,
        *,
        similarity: float = 0.5,
        limit: int | None = None,
        typing_method: str | None = None,
        cluster_method: str | None = None,
        headers: OpHeaders = None,
    ) -> SubmittedJob:
        """Find and cluster samples similar to a reference sample."""
        payload = {
            "sample_id": sample_id,
            "similarity": similarity,
            "limit": limit,
            "cluster": True,
            "cluster_method": cluster_method,
            "typing_method": typing_method,
        }
        resp = self.request_json(
            "POST",
            f"samples/{sample_id}/similar",
            json=payload,
            headers=headers,
            expected_status=(HTTPStatus.OK, HTTPStatus.ACCEPTED),
        )
        return SubmittedJob.model_validate(resp.data or {})

    def cgmlst_cluster_samples(self, *, headers: OpHeaders = None) -> dict[str, Any]:
        """Cluster samples using cgmlst."""
        resp = self.request_json(
            "POST",
            "cluster/cgmlst",
            headers=headers,
            expected_status=(HTTPStatus.OK, HTTPStatus.ACCEPTED),
        )
        return resp.data or {}

    def get_lims_export_response(
        self, sample_id: str, *, fmt: str = "tsv", headers: OpHeaders = None
    ) -> bytes:
        """Get LIMS export for a sample."""
        resp = self.get(
            f"export/{sample_id}/lims",
            params={"fmt": fmt},
            headers=headers,
            expected_status=(HTTPStatus.OK,),
        )
        return resp.content
