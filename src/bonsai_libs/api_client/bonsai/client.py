"""API interface to the Bonsai API."""

import logging
from http import HTTPStatus
import mimetypes

LOG = logging.getLogger(__name__)

from bonsai_libs.api_client.core.base import BaseClient, merge_headers
from bonsai_libs.api_client.core.auth import BearerTokenAuth
from bonsai_libs.api_client.core.exceptions import ClientError, UnauthorizedError

from .models import CreateSampleResponse, InputAnalysisResult, InputSampleInfo, OpHeaders

class BonsaiApiClient(BaseClient):
    """High-level interface to the Bonsai API."""

    
    # ----------------------------
    # Authentication
    # ----------------------------
    def authenticate_user(self, username: str, password: str, *, headers: OpHeaders = None) -> bool:
        """Authenticate using username/password and configure bearer token.
        
        Returns True if login was successful.
        """
        final_headers = merge_headers(
            headers or {},
            {"Content-Type": "application/x-www-form-urlencoded"}
        )
        try:
            resp = self.post(
                "token", body={"username": username, "password": password},
                headers=final_headers,
                expected_status=(HTTPStatus.OK,)
            )
        except UnauthorizedError:
            LOG.error("Invalid login credentials for user=%s", username)
            return False
        except ClientError as exc:
            LOG.error("Failed authenticating user=%s", username, exc_info=exc)
            raise
        
        token_type = resp.get("token_type", "").lower()
        access_token = resp.get("access_token")

        if token_type == "bearer" and access_token:
            self.auth = BearerTokenAuth(token=access_token)
            return True
        
        LOG.error("Unexpected token response: %s", resp)
        return False
        
    
    # ----------------------------
    # Samples
    # ----------------------------

    def create_sample(self, sample_info: InputSampleInfo, *, headers: OpHeaders = None) -> CreateSampleResponse:
        """Create a new sample in Bonsai."""

        payload = sample_info.model_dump()
        final_headers = merge_headers(
            headers or {},
            {"Content-Type": "application/x-www-form-urlencoded"}
        )
        try:
            resp = self.post("samples/", json=payload, headers=final_headers, expected_status=(HTTPStatus.OK,))
        except ClientError as exc:
            LOG.error(
                "Something went wrong creating the sample; %s",
                exc,
                extra={"payload": payload},
            )
        
        return CreateSampleResponse.model_validate(resp)

    def add_samples_to_group(self, group_id: str, *, sample_ids: list[str], headers: OpHeaders = None):
        """Add sample to group."""

        url = f"groups/{group_id}/samples"
        params = {"s": sample_ids}
        final_headers = merge_headers(
            headers or {},
            {"Content-Type": "application/x-www-form-urlencoded"}
        )
        try:
            resp = self.put(url, expected_status=(HTTPStatus.OK,), params=params, headers=final_headers)
        except ClientError as exc:
            LOG.error(
                "Something went wrong creating the sample; %s",
                exc,
                extra={"params": params},
            )
        return resp

    def upload_sourmash_signature(self, sample_id: str, *, signature, headers: OpHeaders = None) -> str:
        """Upload sourmash signature to sample"""

        final_headers = merge_headers(
            headers or {},
            {"Content-Type": "application/x-www-form-urlencoded"}
        )
        try:
            resp = self.post(
                f"samples/{sample_id}/signature", 
                headers=final_headers,
                files={"signature": signature}
            )
        except ClientError as exc:
            LOG.error(
                "Something went wrong when uploading a sourmash signature; %s",
                exc,
            )
        # return jobid
        return resp

    def upload_ska_index(self, sample_id: str, *, index_path: str, headers: OpHeaders = None) -> str:
        """Upload sourmash signature to sample"""
        params = {"index": index_path}
        headers = headers or {}
        final_headers = merge_headers(
            headers or {},
            {"Content-Type": "application/x-www-form-urlencoded"}
        )
        try:
            resp = self.post(
                f"samples/{sample_id}/signature", params=params, headers=final_headers
            )
        except ClientError as exc:
            LOG.error(
                "Something went wrong when uploading a sourmash signature; %s",
                exc, extra={"params": params},
            )
        return resp
    
    def upload_analysis_result(self, result: InputAnalysisResult, *, headers: OpHeaders = None, force: bool = False):
        """Upload a analysis results to a existing sample."""

        final_headers = merge_headers(
            headers or {},
            {"Content-Type": "application/x-www-form-urlencoded"}
        )

        # build the data
        data = {
            "sample_id": result.sample_id,
            "software": result.software,
            "software_version": result.software_version,
        }
        if result.pipeline_run_id:
            data["pipeline_run_id"] = result.pipeline_run_id
        
        # Guess mime type
        mime = mimetypes.guess_type(result.file.name)[0] or "application/octet-stream"

        with result.file.open("rb") as fh:
            files = {"file": (result.file.name, fh, mime)}

            try:
                resp = self.post(
                    "analysis/", data=data, files=files, headers=final_headers,
                    expected_status=(HTTPStatus.OK,)
                )
            except ClientError as exc:
                LOG.error("Failed authenticating user=%s", result.sample_id, exc_info=exc)
                raise
