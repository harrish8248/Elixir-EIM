"""Redis-Backed Session Management, CSRF Double-Submit Validation, and Cookie Utilities."""

import json
import secrets
import time
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Response
from pydantic import BaseModel, Field

from apps.api.app.platform.config import settings
from apps.api.app.platform.logging import logger

SESSION_COOKIE_NAME = "elixir_session"
CSRF_COOKIE_NAME = "elixir_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"

DEFAULT_IDLE_TIMEOUT_SECONDS = 1800  # 30 minutes
DEFAULT_ABSOLUTE_TIMEOUT_SECONDS = 43200  # 12 hours


class SessionData(BaseModel):
    """Encapsulates authenticated user session state stored in Redis."""

    session_id: str
    user_id: UUID
    tenant_id: UUID
    email: str
    username: str
    roles: list[str] = Field(default_factory=list)
    department: str | None = None
    clearance_level: int = 1
    acr: str | None = None
    amr: list[str] = Field(default_factory=list)
    csrf_token: str
    created_at: float
    last_active_at: float
    absolute_expiry: float
    idle_timeout: int = DEFAULT_IDLE_TIMEOUT_SECONDS
    id_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None


class SessionManager:
    """Manages server-side sessions with idle & absolute timeouts in Redis with resilient memory fallback."""

    def __init__(self, redis_url: str | None = None):
        self._redis_url = redis_url or settings.redis_url
        self._redis: aioredis.Redis | None = None
        self._memory_sessions: dict[str, SessionData] = {}

    async def get_redis(self) -> aioredis.Redis:
        import asyncio
        loop = asyncio.get_running_loop()
        if self._redis is None or getattr(self, "_loop", None) != loop:
            self._loop = loop
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                encoding="utf-8",
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
        return self._redis

    async def create_session(
        self,
        user_id: UUID,
        tenant_id: UUID,
        email: str,
        username: str,
        roles: list[str],
        department: str | None = None,
        clearance_level: int = 1,
        acr: str | None = None,
        amr: list[str] | None = None,
        id_token: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        idle_timeout: int = DEFAULT_IDLE_TIMEOUT_SECONDS,
        absolute_timeout: int = DEFAULT_ABSOLUTE_TIMEOUT_SECONDS,
    ) -> SessionData:
        """Create and persist a new session with cryptographically secure session and CSRF tokens."""
        now = time.time()
        session_id = secrets.token_urlsafe(48)
        csrf_token = secrets.token_urlsafe(32)

        session = SessionData(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            username=username,
            roles=roles,
            department=department,
            clearance_level=clearance_level,
            acr=acr,
            amr=amr or [],
            csrf_token=csrf_token,
            created_at=now,
            last_active_at=now,
            absolute_expiry=now + absolute_timeout,
            idle_timeout=idle_timeout,
            id_token=id_token,
            access_token=access_token,
            refresh_token=refresh_token,
        )

        # Cache session in memory for instant local retrieval
        self._memory_sessions[session_id] = session

        try:
            r = await self.get_redis()
            ttl = min(idle_timeout, absolute_timeout)
            key = f"elixir:session:{session_id}"
            await r.set(key, session.model_dump_json(), ex=ttl)

            # Track user's active sessions
            user_sessions_key = f"elixir:user_sessions:{user_id}"
            await r.sadd(user_sessions_key, session_id)
            await r.expire(user_sessions_key, absolute_timeout)
        except Exception as exc:
            logger.warning(f"Redis session write unavailable, caching in memory fallback: {exc}")

        return session

    async def get_session(self, session_id: str) -> SessionData | None:
        """
        Retrieve and touch an active session from Redis (or memory fallback).
        Enforces both idle and absolute expiration.
        """
        if not session_id:
            return None

        # Check in-memory cache first for instant retrieval
        session = self._memory_sessions.get(session_id)
        if not session:
            raw_data = None
            try:
                r = await self.get_redis()
                key = f"elixir:session:{session_id}"
                raw_data = await r.get(key)
            except Exception as exc:
                logger.debug(f"Redis get_session failed, reading from memory fallback: {exc}")

            if raw_data:
                try:
                    session = SessionData.model_validate_json(raw_data)
                    self._memory_sessions[session_id] = session
                except (ValueError, KeyError) as exc:
                    logger.error(f"Corrupt session data for {session_id}: {exc}")
                    return None

        if not session:
            return None

        now = time.time()

        # Enforce Absolute Timeout
        if now > session.absolute_expiry:
            logger.info(f"Session {session_id} exceeded absolute timeout.")
            await self.revoke_session(session_id)
            return None

        # Enforce Idle Timeout
        if now - session.last_active_at > session.idle_timeout:
            logger.info(f"Session {session_id} exceeded idle timeout.")
            await self.revoke_session(session_id)
            return None

        # Touch session and update TTL
        session.last_active_at = now
        remaining_absolute = max(1, int(session.absolute_expiry - now))
        new_ttl = min(session.idle_timeout, remaining_absolute)

        try:
            r = await self.get_redis()
            key = f"elixir:session:{session_id}"
            await r.set(key, session.model_dump_json(), ex=new_ttl)
        except Exception:
            pass
        return session

    async def revoke_session(self, session_id: str) -> bool:
        """Revoke a single session and clean up user session sets."""
        r = await self.get_redis()
        key = f"elixir:session:{session_id}"
        raw_data = await r.get(key)
        if raw_data:
            try:
                data = json.loads(raw_data)
                user_id = data.get("user_id")
                if user_id:
                    await r.srem(f"elixir:user_sessions:{user_id}", session_id)
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.debug(f"Non-critical cleanup warning for {session_id}: {exc}")

        deleted = await r.delete(key)
        return bool(deleted > 0)

    async def revoke_all_user_sessions(self, user_id: UUID) -> int:
        """Revoke all sessions belonging to a specific user (e.g. on role change or password reset)."""
        r = await self.get_redis()
        user_sessions_key = f"elixir:user_sessions:{user_id}"
        session_ids = await r.smembers(user_sessions_key)
        count = 0
        for sid in session_ids:
            if await self.revoke_session(str(sid)):
                count += 1
        await r.delete(user_sessions_key)
        return count

    @staticmethod
    def validate_csrf(session: SessionData, header_csrf_token: str | None) -> bool:
        """Verify CSRF token using constant-time string comparison."""
        if not header_csrf_token:
            return False
        return secrets.compare_digest(session.csrf_token, header_csrf_token)

    @staticmethod
    def attach_cookies(response: Response, session: SessionData) -> None:
        """
        Attach httpOnly session cookie and accessible CSRF cookie to the HTTP response.
        Enforces SameSite=Lax (or Strict) and Secure flags.
        """
        is_secure = settings.elixir_env != "development"

        # httpOnly session cookie - inaccessible to JavaScript
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session.session_id,
            httponly=True,
            secure=is_secure,
            samesite="lax",
            path="/",
            max_age=session.idle_timeout,
        )

        # CSRF token cookie - readable by JavaScript to attach in headers
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=session.csrf_token,
            httponly=False,
            secure=is_secure,
            samesite="lax",
            path="/",
            max_age=session.idle_timeout,
        )

    @staticmethod
    def clear_cookies(response: Response) -> None:
        """Clear session and CSRF cookies."""
        response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
        response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")


# Singleton instance
session_manager = SessionManager()
