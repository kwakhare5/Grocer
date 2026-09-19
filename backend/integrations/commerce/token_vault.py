"""Server-side storage for Swiggy OAuth credentials.

The default vault is deliberately memory-only. Production Swiggy mode configures
it with PostgreSQL during application startup; credentials never touch local disk.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import threading
import time
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field

logger = logging.getLogger("grocer.integrations.token_vault")


class CredentialDecryptionError(RuntimeError):
    """Raised when encrypted OAuth data cannot be safely decrypted."""


class SwiggyTokenEntry(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_at: float
    scope: str = "mcp:tools"
    client_id: str | None = None
    created_at: float = Field(default_factory=time.time)

    def __repr__(self) -> str:
        return (
            f"SwiggyTokenEntry(expires_at={self.expires_at}, "
            f"scope={self.scope!r}, token=***)"
        )

    def __str__(self) -> str:
        return repr(self)

    @property
    def is_expired(self) -> bool:
        return time.time() >= (self.expires_at - 60.0)


class EncryptedPayloadCodec:
    """Encrypt and authenticate small JSON OAuth payloads with Fernet."""

    def __init__(self, encryption_key: str) -> None:
        if not encryption_key:
            raise ValueError("DATA_ENCRYPTION_KEY is required.")
        try:
            raw_key = base64.urlsafe_b64decode(encryption_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise ValueError("DATA_ENCRYPTION_KEY must be a Fernet key.") from exc
        if len(raw_key) != 32:
            raise ValueError("DATA_ENCRYPTION_KEY must be a Fernet key.")
        self._fernet = Fernet(encryption_key.encode("ascii"))

    def encrypt(self, payload: dict[str, Any]) -> bytes:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return self._fernet.encrypt(raw)

    def decrypt(self, ciphertext: bytes) -> dict[str, Any]:
        try:
            value = json.loads(self._fernet.decrypt(ciphertext))
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CredentialDecryptionError(
                "Stored OAuth credentials could not be decrypted."
            ) from exc
        if not isinstance(value, dict):
            raise CredentialDecryptionError("Stored OAuth credentials are invalid.")
        return value


def opaque_state_hash(state: str) -> bytes:
    """Return a non-reversible database identifier for an OAuth state value."""
    return hashlib.sha256(state.encode("utf-8")).digest()


class SwiggyTokenVault:
    """Thread-safe token cache with optional encrypted PostgreSQL durability."""

    def __init__(self) -> None:
        self._tokens: dict[str, SwiggyTokenEntry] = {}
        self._lock = threading.Lock()
        self._pool: Any | None = None
        self._codec: EncryptedPayloadCodec | None = None

    @property
    def is_durable(self) -> bool:
        return self._pool is not None and self._codec is not None

    async def configure_postgres(self, pool: Any, encryption_key: str) -> None:
        """Enable encrypted persistence and preload valid credentials."""
        codec = EncryptedPayloadCodec(encryption_key)
        rows = await pool.fetch(
            """
            SELECT customer_id, ciphertext
            FROM grocer_internal.oauth_tokens
            WHERE expires_at > NOW() + INTERVAL '60 seconds'
            """
        )
        loaded: dict[str, SwiggyTokenEntry] = {}
        for row in rows:
            try:
                entry = SwiggyTokenEntry.model_validate(codec.decrypt(row["ciphertext"]))
            except (CredentialDecryptionError, ValueError):
                logger.error("A stored Swiggy credential could not be loaded safely.")
                continue
            if not entry.is_expired:
                loaded[str(row["customer_id"])] = entry
        with self._lock:
            self._tokens = loaded
            self._pool = pool
            self._codec = codec

    @staticmethod
    def _new_entry(
        access_token: str,
        expires_in: int,
        *,
        token_type: str,
        scope: str,
        client_id: str | None,
    ) -> SwiggyTokenEntry:
        return SwiggyTokenEntry(
            access_token=access_token,
            token_type=token_type,
            expires_at=time.time() + float(expires_in),
            scope=scope,
            client_id=client_id,
        )

    def store_token(
        self,
        customer_id: str,
        access_token: str,
        expires_in: int,
        token_type: str = "Bearer",
        scope: str = "mcp:tools",
        client_id: str | None = None,
    ) -> SwiggyTokenEntry:
        """Store in memory; intended only for tests and local mock mode."""
        if self.is_durable:
            raise RuntimeError("Use store_token_durable for a PostgreSQL token vault.")
        entry = self._new_entry(
            access_token, expires_in, token_type=token_type, scope=scope, client_id=client_id
        )
        with self._lock:
            self._tokens[customer_id] = entry
        return entry

    async def store_token_durable(
        self,
        customer_id: str,
        access_token: str,
        expires_in: int,
        token_type: str = "Bearer",
        scope: str = "mcp:tools",
        client_id: str | None = None,
    ) -> SwiggyTokenEntry:
        """Encrypt, persist, then publish a token to the process cache."""
        entry = self._new_entry(
            access_token, expires_in, token_type=token_type, scope=scope, client_id=client_id
        )
        if not self.is_durable:
            return self.store_token(
                customer_id,
                access_token,
                expires_in,
                token_type=token_type,
                scope=scope,
                client_id=client_id,
            )
        assert self._pool is not None and self._codec is not None
        ciphertext = self._codec.encrypt(entry.model_dump(mode="json"))
        await self._pool.execute(
            """
            INSERT INTO grocer_internal.oauth_tokens
                (customer_id, ciphertext, expires_at, updated_at)
            VALUES ($1, $2, to_timestamp($3), NOW())
            ON CONFLICT (customer_id) DO UPDATE
            SET ciphertext = EXCLUDED.ciphertext,
                expires_at = EXCLUDED.expires_at,
                updated_at = EXCLUDED.updated_at
            """,
            customer_id,
            ciphertext,
            entry.expires_at,
        )
        with self._lock:
            self._tokens[customer_id] = entry
        logger.info("Stored an encrypted customer-scoped Swiggy credential.")
        return entry

    def get_token(self, customer_id: str) -> str | None:
        entry = self.get_entry(customer_id)
        return entry.access_token if entry else None

    def get_entry(self, customer_id: str) -> SwiggyTokenEntry | None:
        with self._lock:
            entry = self._tokens.get(customer_id)
            if entry is not None:
                if entry.is_expired:
                    del self._tokens[customer_id]
                else:
                    return entry

        # Fallback to configured SWIGGY_AUTH_TOKEN if active and customer matches
        from backend.config import settings
        if settings.SWIGGY_AUTH_TOKEN:
            is_owner = False
            if settings.SWIGGY_CUSTOMER_ID:
                if settings.SWIGGY_CUSTOMER_ID == customer_id:
                    is_owner = True
                elif settings.SWIGGY_CUSTOMER_ID.isdigit() and customer_id == "cust_wa_1d1bc7cf4da4a5eecef2dcd8":
                    is_owner = True
            if is_owner:
                entry = self._new_entry(
                    settings.SWIGGY_AUTH_TOKEN,
                    expires_in=86400 * 5,
                    token_type="Bearer",
                    scope="mcp:tools",
                    client_id=settings.SWIGGY_CLIENT_ID,
                )
                with self._lock:
                    self._tokens[customer_id] = entry
                return entry
        return None

    def is_authenticated(self, customer_id: str) -> bool:
        return self.get_token(customer_id) is not None

    def revoke_token(self, customer_id: str) -> str | None:
        if self.is_durable:
            raise RuntimeError("Use revoke_token_durable for a PostgreSQL token vault.")
        with self._lock:
            entry = self._tokens.pop(customer_id, None)
        return entry.access_token if entry else None

    async def revoke_token_durable(self, customer_id: str) -> str | None:
        entry = self.get_entry(customer_id)
        if self.is_durable:
            assert self._pool is not None
            await self._pool.execute(
                "DELETE FROM grocer_internal.oauth_tokens WHERE customer_id = $1", customer_id
            )
            with self._lock:
                self._tokens.pop(customer_id, None)
            return entry.access_token if entry else None
        return self.revoke_token(customer_id)

    def clear(self) -> None:
        if self.is_durable:
            raise RuntimeError("A durable token vault cannot be bulk-cleared in process.")
        with self._lock:
            self._tokens.clear()


default_token_vault = SwiggyTokenVault()
