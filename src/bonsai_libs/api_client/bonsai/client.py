"""API interface to the Bonsai API."""

from typing import BinaryIO
import logging
import mimetypes
from http import HTTPStatus

LOG = logging.getLogger(__name__)

from bonsai_libs.api_client.core.auth import BearerTokenAuth
from bonsai_libs.api_client.core.base import BaseClient, merge_headers
from bonsai_libs.api_client.core.exceptions import ClientError, UnauthorizedError

from .models import (
    CreateGroupInput,
    CreateSampleResponse,
    CreateUserInput,
    GroupResponse,
    OpHeaders,
    PipelineRunInput,
    SampleInfoInput,
    UploadAnalysisResultInput,
    UploadAnalysisResultResponse,
    UploadResultMeta,
    UserResponse,
)


class BonsaiApiClient(BaseClient):
    """High-level interface to the Bonsai API."""

    # ----------------------------
    # Authentication
    # ----------------------------
    def authenticate_user(self, username: str, password: str, *, headers: OpHeaders = None) -> bool:
        """Authenticate using username/password and configure bearer token.

        Returns True if login was successful.
        """
        try:
            resp = self.request_form(
                "POST",
                "token",
                data={"username": username, "password": password},
                headers=headers,
                expected_status=(HTTPStatus.OK,),
            )
        except UnauthorizedError:
            LOG.error("Invalid login credentials for user=%s", username)
            return False
        except ClientError as exc:
            LOG.error(
                "Something went wrong when authenticating user %s; %s",
                username,
                exc,
            )
            raise

        data = resp.data or {}
        token_type = str(data.get("token_type", "")).lower()
        access_token = data.get("access_token")

        if token_type == "bearer" and access_token:
            self.auth = BearerTokenAuth(token=access_token)
            return True

        LOG.error("Unexpected token response: %s", resp)
        return False

    # ----------------------------
    # Users
    # ----------------------------

    def create_user(self, user: CreateUserInput, *, headers: OpHeaders = None) -> UserResponse:
        resp = self.request_json(
            "POST",
            "users/",
            json=user.model_dump(mode="json"),
            headers=headers,
            expected_status=(HTTPStatus.CREATED,),
        )
        return UserResponse.model_validate(resp.data)

    def get_user(self, username: str, *, headers: OpHeaders = None) -> UserResponse:
        """Query the API for a user with username."""
        resp = self.request_json(
            "GET",
            f"users/{username}",
            headers=headers,
            expected_status=(HTTPStatus.OK,),
        )
        return UserResponse.model_validate(resp.data)

    # ----------------------------
    # Groups
    # ----------------------------

    def create_group(self, group: CreateGroupInput, *, headers: OpHeaders = None) -> GroupResponse:
        """Create a group in Bonsai."""

        payload = group.model_dump(mode="json")
        resp = self.request_json(
            "POST", "groups/", json=payload, headers=headers, expected_status=(HTTPStatus.CREATED,)
        )

        return GroupResponse.model_validate(resp.data)

    def get_group(self, group_id: str, *, headers: OpHeaders = None) -> GroupResponse:
        """Query the API for a group using group id."""
        resp = self.request_json(
            "GET",
            f"groups/{group_id}",
            headers=headers,
            expected_status=(HTTPStatus.OK,),
        )
        return GroupResponse.model_validate(resp.data)

    # ----------------------------
    # Samples
    # ----------------------------

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
        self, sample_id: str, *, index_path: str, headers: OpHeaders = None
    ) -> str:
        """Upload sourmash signature to sample"""
        try:
            resp = self.request_form(
                "POST",
                f"samples/{sample_id}/ska_index",
                data={"index": index_path},
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
