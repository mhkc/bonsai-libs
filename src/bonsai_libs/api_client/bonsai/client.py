"""API interface to the Bonsai API."""

import logging
from http import HTTPStatus

LOG = logging.getLogger(__name__)

from bonsai_libs.api_client.core.base import BaseClient
from bonsai_libs.api_client.core.auth import BearerTokenAuth
from bonsai_libs.api_client.core.exceptions import ClientError, UnauthorizedError

from .models import CreateSampleResponse, InputSampleInfo

class BonsaiApiClient(BaseClient):
    """High-level interface to the Bonsai API."""

    
    # ----------------------------
    # Authentication
    # ----------------------------
    def authenticate_user(self, username: str, password: str) -> bool:
        """Authenticate using username/password and configure bearer token.
        
        Returns True if login was successful.
        """
        try:
            resp = self.post(
                "token", body={"username": username, "password": password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                expected_status=(HTTPStatus.OK,)
            )
        except UnauthorizedError:
            LOG.error("Invalid login credentials for user=%s", username)
            return False
        except ClientError as exc:
            LOG.error("Failed authenticating user=%s", username, exc)
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
    def create_sample(self, sample_info: InputSampleInfo) -> CreateSampleResponse:
        """Create a new sample in Bonsai."""

        payload = sample_info
        try:
            resp = self.post("samples/", json=payload, expected_status=(HTTPStatus.OK,))
        except ClientError as exc:
            LOG.error(
                "Something went wrong creating the sample; %s",
                exc,
                extra={"payload": payload},
            )
        
        return CreateSampleResponse.model_validate(resp)
