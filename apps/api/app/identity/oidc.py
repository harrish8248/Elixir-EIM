"""OIDC Authentication, PKCE, and JWKS Rotation-Safe Token Validation."""

import base64
import hashlib
import secrets
import time
from typing import Any

import httpx
from jose import exceptions as jose_exceptions
from jose import jwt

from apps.api.app.platform.config import settings
from apps.api.app.platform.errors import AuthenticationError
from apps.api.app.platform.logging import logger


class OIDCService:
    """Provider-agnostic OpenID Connect Service with PKCE and cached JWKS verification."""

    def __init__(
        self,
        issuer_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str = "http://localhost:5173/auth/callback",
    ):
        self.issuer_url = (issuer_url or settings.oidc_issuer_url).rstrip("/")
        self.client_id = client_id or settings.oidc_client_id
        self.client_secret = client_secret or settings.oidc_client_secret
        self.redirect_uri = redirect_uri

        self._discovery_cache: dict[str, Any] | None = None
        self._discovery_fetched_at: float = 0
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_fetched_at: float = 0
        self._cache_ttl_seconds: int = 300  # 5 minutes TTL

    async def get_discovery_config(self, force_reload: bool = False) -> dict[str, Any]:
        """Fetch and cache OpenID Provider configuration from .well-known/openid-configuration."""
        now = time.time()
        if (
            not force_reload
            and self._discovery_cache
            and (now - self._discovery_fetched_at < self._cache_ttl_seconds)
        ):
            return self._discovery_cache

        discovery_url = f"{self.issuer_url}/.well-known/openid-configuration"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(discovery_url)
                res.raise_for_status()
                self._discovery_cache = res.json()
                self._discovery_fetched_at = now
                return self._discovery_cache
        except Exception as exc:
            logger.error(
                f"Failed to fetch OIDC discovery configuration from {discovery_url}: {exc}"
            )
            if self._discovery_cache:
                return self._discovery_cache
            raise AuthenticationError(
                f"OIDC discovery endpoint unavailable: {exc}", error_code="OIDC_DISCOVERY_FAILED"
            ) from exc

    async def get_jwks(self, force_reload: bool = False) -> dict[str, Any]:
        """Fetch and cache JWKS public certificates with dynamic rotation safety."""
        now = time.time()
        if (
            not force_reload
            and self._jwks_cache
            and (now - self._jwks_fetched_at < self._cache_ttl_seconds)
        ):
            return self._jwks_cache

        discovery = await self.get_discovery_config()
        jwks_uri = discovery.get("jwks_uri") or f"{self.issuer_url}/protocol/openid-connect/certs"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(jwks_uri)
                res.raise_for_status()
                self._jwks_cache = res.json()
                self._jwks_fetched_at = now
                return self._jwks_cache
        except Exception as exc:
            logger.error(f"Failed to fetch JWKS keys from {jwks_uri}: {exc}")
            if self._jwks_cache:
                return self._jwks_cache
            raise AuthenticationError(
                f"JWKS key endpoint unavailable: {exc}", error_code="JWKS_FETCH_FAILED"
            ) from exc

    @staticmethod
    def generate_pkce_pair() -> tuple[str, str]:
        """Generate a cryptographically secure PKCE code_verifier and code_challenge (S256)."""
        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return code_verifier, code_challenge

    async def create_authorization_url(
        self,
        state: str,
        nonce: str,
        code_challenge: str,
        scope: str = "openid email profile",
        acr_values: str | None = None,
    ) -> str:
        """Construct the Authorization Code URL with PKCE for Keycloak/OIDC provider."""
        discovery = await self.get_discovery_config()
        auth_endpoint = (
            discovery.get("authorization_endpoint")
            or f"{self.issuer_url}/protocol/openid-connect/auth"
        )

        params: dict[str, str] = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": scope,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if acr_values:
            params["acr_values"] = acr_values

        query_str = httpx.QueryParams(params)
        return f"{auth_endpoint}?{query_str}"

    async def exchange_code_for_tokens(self, code: str, code_verifier: str) -> dict[str, Any]:
        """Exchange authorization code and PKCE verifier for OIDC tokens at the token endpoint."""
        discovery = await self.get_discovery_config()
        token_endpoint = (
            discovery.get("token_endpoint") or f"{self.issuer_url}/protocol/openid-connect/token"
        )

        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(token_endpoint, data=data)
                if res.status_code != 200:
                    logger.warning(f"OIDC token exchange failed ({res.status_code}): {res.text}")
                    raise AuthenticationError(
                        f"Failed to exchange authorization code for tokens: {res.text}",
                        error_code="TOKEN_EXCHANGE_FAILED",
                    )
                return res.json()
        except AuthenticationError:
            raise
        except Exception as exc:
            logger.error(f"Error communicating with token endpoint {token_endpoint}: {exc}")
            raise AuthenticationError(
                f"Token endpoint unreachable: {exc}", error_code="TOKEN_ENDPOINT_ERROR"
            ) from exc

    async def validate_token(
        self,
        token: str,
        expected_nonce: str | None = None,
        expected_audience: str | None = None,
    ) -> dict[str, Any]:
        """
        Full cryptographic token validation:
        1. Decodes JWT header to extract key ID ('kid').
        2. Retrieves cached JWKS keys, reloading if 'kid' is unknown (rotation-safe).
        3. Cryptographically verifies RS256 signature against matching public key.
        4. Validates issuer, audience, expiration timestamp.
        5. Validates nonce claim against expected nonce if provided.
        """
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as exc:
            raise AuthenticationError(
                f"Malformed JWT token: {exc}", error_code="INVALID_TOKEN_FORMAT"
            ) from exc

        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg", "RS256")
        if alg not in ["RS256", "RS384", "RS512"]:
            raise AuthenticationError(
                f"Unsupported algorithm '{alg}'", error_code="UNSUPPORTED_ALGORITHM"
            )

        jwks = await self.get_jwks(force_reload=False)
        keys = jwks.get("keys", [])

        # Find key with matching kid
        matching_key = next((k for k in keys if k.get("kid") == kid), None)
        if not matching_key and kid:
            # Force refresh JWKS cache to support key rotation
            logger.info(f"Key ID '{kid}' not found in cached JWKS. Performing rotation refresh...")
            jwks = await self.get_jwks(force_reload=True)
            keys = jwks.get("keys", [])
            matching_key = next((k for k in keys if k.get("kid") == kid), None)

        target_audience = expected_audience or self.client_id

        decode_options = {
            "verify_signature": True,
            "verify_aud": bool(target_audience),
            "verify_iat": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iss": True,
            "verify_at_hash": False,
        }

        try:
            claims = jwt.decode(
                token,
                jwks,
                algorithms=[alg],
                audience=target_audience,
                issuer=self.issuer_url,
                options=decode_options,
            )
        except jose_exceptions.ExpiredSignatureError as exc:
            raise AuthenticationError("Token has expired", error_code="TOKEN_EXPIRED") from exc
        except jose_exceptions.JWTClaimsError as exc:
            raise AuthenticationError(
                f"Token claim validation failed: {exc}", error_code="INVALID_CLAIMS"
            ) from exc
        except jose_exceptions.JWTError as exc:
            raise AuthenticationError(
                f"Token cryptographic verification failed: {exc}", error_code="INVALID_SIGNATURE"
            ) from exc

        # Check nonce if required
        if expected_nonce and claims.get("nonce") != expected_nonce:
            raise AuthenticationError("Token nonce mismatch", error_code="INVALID_NONCE")

        return claims


# Singleton instance
oidc_service = OIDCService()
