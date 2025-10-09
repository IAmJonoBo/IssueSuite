"""GitHub App authentication integration for IssueSuite.

Provides GitHub App token management with automatic renewal,
JWT generation, and installation token handling.
"""

from __future__ import annotations

import base64
import binascii
import importlib
import json
import os
import shutil
import subprocess  # nosec B404 - subprocess is required for GitHub CLI integration
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from .logging import get_logger

jwt: Any | None
try:  # pragma: no cover - optional dependency
    jwt = importlib.import_module("jwt")
except Exception:  # pragma: no cover - library not installed
    jwt = None

KeyringErrorType: type[Exception]
keyring: Any | None
try:  # pragma: no cover - optional dependency
    keyring = importlib.import_module("keyring")
    keyring_errors = importlib.import_module("keyring.errors")
    KeyringErrorType = cast(type[Exception], keyring_errors.KeyringError)
except Exception:  # pragma: no cover - library not installed
    keyring = None

    class KeyringUnavailableError(Exception):
        """Raised when keyring is not available."""

        pass

    KeyringErrorType = cast(type[Exception], KeyringUnavailableError)


_KEYRING_SERVICE = "issuesuite.github_app"
_CACHE_FILE_VERSION = 2


def _gh_command(*args: str) -> list[str]:
    """Return a GitHub CLI command preferring the absolute path when available."""
    gh_path = shutil.which("gh")
    base = gh_path if gh_path else "gh"
    return [base, *args]


@dataclass
class GitHubAppConfig:
    """Configuration for GitHub App authentication."""

    enabled: bool
    app_id: str | None
    private_key_path: str | None
    installation_id: str | None
    token_cache_path: str = ".github_app_token.json"


class GitHubAppTokenManager:
    """Manages GitHub App tokens with automatic refresh."""

    def __init__(self, config: GitHubAppConfig, mock: bool = False):
        self.config = config
        self.mock = mock
        self.logger = get_logger()
        self._cached_token: str | None = None
        self._token_expires_at: datetime | None = None

    def is_enabled(self) -> bool:
        """Check if GitHub App authentication is enabled and configured."""
        return bool(
            self.config.enabled
            and self.config.app_id
            and self.config.private_key_path
            and self.config.installation_id
        )

    def get_token(self) -> str | None:
        """Get a valid GitHub App installation token."""
        if not self.is_enabled():
            return None

        if self.mock:
            return "mock_github_app_token"

        # Check if we have a valid cached token
        if self._is_token_valid():
            return self._cached_token

        # Try to load token from cache
        if self._load_cached_token() and self._is_token_valid():
            return self._cached_token

        # Generate new token
        return self._generate_new_token()

    def _is_token_valid(self) -> bool:
        """Check if the current token is valid and not expired."""
        if self._cached_token is None or self._token_expires_at is None:
            return False

        # Add 5 minute buffer before expiration
        buffer = timedelta(minutes=5)
        return datetime.now(timezone.utc) < (self._token_expires_at - buffer)

    def _cache_key(self) -> str:
        """Return stable cache key for this app/installation pair."""
        app_id = self.config.app_id or "unknown-app"
        installation_id = self.config.installation_id or "unknown-installation"
        return f"{app_id}:{installation_id}"

    def _encode_cache_blob(self) -> str:
        """Encode cached token data into a safe string."""
        if not self._cached_token or self._token_expires_at is None:
            raise ValueError("No token available to encode")

        payload = {
            "token": self._cached_token,
            "expires_at": self._token_expires_at.isoformat(),
        }
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8")

    def _apply_cache_blob(self, blob: str, source: str) -> bool:
        """Decode cache payload and populate local state."""
        try:
            padded = blob + "=" * (-len(blob) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode("utf-8"))
            data = json.loads(decoded.decode("utf-8"))
        except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self.logger.log_error("Failed to decode cached token", source=source, error=str(exc))
            return False

        token_val = data.get("token")
        expires_str = data.get("expires_at")
        if not isinstance(token_val, str) or not token_val:
            return False
        if not isinstance(expires_str, str) or not expires_str:
            return False

        try:
            expires_at = datetime.fromisoformat(expires_str)
        except ValueError as exc:
            self.logger.log_error("Cached token expiration invalid", source=source, error=str(exc))
            return False

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        self._cached_token = token_val
        self._token_expires_at = expires_at
        self.logger.debug("Loaded cached GitHub App token", source=source)
        return True

    def _load_keyring_token(self) -> bool:
        """Attempt to load cached token from system keyring."""
        if keyring is None:
            return False

        try:
            secret = keyring.get_password(_KEYRING_SERVICE, self._cache_key())
        except KeyringErrorType as exc:  # pragma: no cover - platform dependent
            self.logger.debug("Keyring unavailable", error=str(exc))
            return False

        if not isinstance(secret, str) or not secret:
            return False

        return self._apply_cache_blob(secret, "keyring")

    def _load_file_cache(self) -> bool:
        """Attempt to load cached token from filesystem."""
        cache_path = Path(self.config.token_cache_path)
        if not cache_path.exists():
            return False

        try:
            with cache_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            self.logger.log_error("Failed to load cached token", error=str(exc))
            return False

        if not isinstance(data, dict):
            return False

        payload = data.get("payload")
        if isinstance(payload, str) and self._apply_cache_blob(payload, "file"):
            return True

        return self._load_legacy_file_payload(data)

    def _load_legacy_file_payload(self, data: dict[str, Any]) -> bool:
        """Support legacy plaintext cache files from previous releases."""
        legacy_token = data.get("token")
        if not isinstance(legacy_token, str) or not legacy_token:
            return False

        self._cached_token = legacy_token
        expires_str = data.get("expires_at")
        if isinstance(expires_str, str) and expires_str:
            try:
                expires_at = datetime.fromisoformat(expires_str)
            except ValueError:
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        self._token_expires_at = expires_at
        self.logger.debug("Loaded legacy cached GitHub App token", source="file")
        return True

    def _load_cached_token(self) -> bool:
        """Load token from secure cache stores."""
        return self._load_keyring_token() or self._load_file_cache()

    def _save_to_keyring(self, payload: str) -> bool:
        """Persist cache payload to system keyring if available."""
        if keyring is None:
            return False

        try:  # pragma: no cover - platform dependent
            keyring.set_password(_KEYRING_SERVICE, self._cache_key(), payload)
            self.logger.debug("Cached GitHub App token in keyring")
            return True
        except KeyringErrorType as exc:
            self.logger.debug("Failed to store token in keyring", error=str(exc))
            return False

    def _write_file_cache(self, payload: str) -> bool:
        """Persist cache payload to filesystem."""
        try:
            cache_path = Path(self.config.token_cache_path)
            data = {
                "payload": payload,
                "version": _CACHE_FILE_VERSION,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            cache_path.chmod(0o600)
            self.logger.debug("Cached GitHub App token to filesystem")
            return True
        except Exception as exc:
            self.logger.log_error("Failed to cache token", error=str(exc))
            return False

    def _save_cached_token(self) -> None:
        """Persist cached token to available storage backends."""
        if not self._cached_token or self._token_expires_at is None:
            return

        try:
            payload = self._encode_cache_blob()
        except ValueError:
            return

        self._save_to_keyring(payload)
        self._write_file_cache(payload)

    def _generate_new_token(self) -> str | None:
        """Generate a new installation token."""
        try:
            # Generate JWT for App authentication
            jwt_token = self._generate_jwt()
            if not jwt_token:
                return None

            # Get installation token using JWT
            installation_token = self._get_installation_token(jwt_token)
            if not installation_token:
                return None

            self._cached_token = str(installation_token["token"])

            # Parse expiration time
            expires_str = installation_token.get("expires_at")
            if isinstance(expires_str, str) and expires_str:
                # GitHub uses ISO format: 2025-01-01T10:00:00Z
                self._token_expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            else:
                # Default to 1 hour if no expiration provided
                self._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

            # Cache the token
            self._save_cached_token()

            expires_iso = self._token_expires_at.isoformat() if self._token_expires_at else ""
            self.logger.log_operation(
                "github_app_token_generated",
                app_id=self.config.app_id,
                installation_id=self.config.installation_id,
                expires_at=expires_iso,
            )

            return self._cached_token

        except Exception as e:
            self.logger.log_error("Failed to generate GitHub App token", error=str(e))
            return None

    def _generate_jwt(self) -> str | None:
        """Generate JWT for GitHub App authentication."""
        try:
            if not self.config.private_key_path:
                self.logger.log_error("Private key path not configured")
                return None
            private_key_path = Path(self.config.private_key_path)
            if not private_key_path.exists():
                self.logger.log_error(f"Private key file not found: {private_key_path}")
                return None
            private_key = private_key_path.read_text(encoding="utf-8")
            if not private_key.strip():
                self.logger.log_error("Private key file is empty", path=str(private_key_path))
                return None

            now = datetime.now(timezone.utc)
            payload = {
                "iat": int(now.timestamp()) - 60,
                "exp": int((now + timedelta(minutes=10)).timestamp()),
                "iss": self.config.app_id,
            }

            if jwt is None:
                self.logger.warning(
                    "PyJWT is not installed; generating unsigned JWT placeholder",
                    app_id=self.config.app_id,
                )
                return self._generate_unsigned_jwt(payload)

            try:
                signed_jwt = jwt.encode(
                    payload,
                    private_key,
                    algorithm="RS256",
                    headers={"typ": "JWT"},
                )
            except Exception as exc:  # pragma: no cover - guarded below
                if self._should_fallback_to_unsigned(exc):
                    self.logger.warning(
                        "PyJWT failed to sign key; falling back to unsigned JWT",
                        app_id=self.config.app_id,
                        error=str(exc),
                        key_path=str(private_key_path),
                    )
                    return self._generate_unsigned_jwt(payload)
                self.logger.log_error("Failed to generate JWT", error=str(exc))
                return None

            if isinstance(signed_jwt, bytes):
                signed_jwt = signed_jwt.decode("utf-8")

            token_str: str = cast(str, signed_jwt)
            self.logger.debug("Generated signed JWT for GitHub App", app_id=self.config.app_id)
            return token_str

        except Exception as e:
            if self._should_fallback_to_unsigned(e):
                self.logger.warning(
                    "Falling back to unsigned JWT placeholder after unexpected signing failure",
                    app_id=self.config.app_id,
                    error=str(e),
                )
                return self._generate_unsigned_jwt(payload)
            self.logger.log_error("Failed to generate JWT", error=str(e))
            return None

    def _should_fallback_to_unsigned(self, exc: Exception) -> bool:
        """Detect whether signing failed due to an invalid or unsupported key."""
        if jwt is None:
            return False

        exceptions_module = getattr(jwt, "exceptions", None)
        invalid_key_error = getattr(exceptions_module, "InvalidKeyError", None)
        pyjwt_error = getattr(exceptions_module, "PyJWTError", None)

        if invalid_key_error and isinstance(exc, invalid_key_error):
            return True

        if pyjwt_error and isinstance(exc, pyjwt_error):
            message = str(exc).lower()
            return "could not deserialize key" in message or "key format" in message

        return isinstance(exc, (ValueError, binascii.Error))

    def _generate_unsigned_jwt(self, payload: dict[str, Any]) -> str:
        """Fallback unsigned JWT (legacy behaviour)."""
        header = {"typ": "JWT", "alg": "RS256"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        return f"{header_b64}.{payload_b64}.signature_placeholder"

    def _get_installation_token(self, jwt_token: str) -> dict[str, Any] | None:
        """Get installation token using JWT."""
        try:
            # Use GitHub CLI with the JWT token
            if not self.config.installation_id:
                self.logger.log_error("Installation ID not configured")
                return None
            cmd = [
                "api",
                f"/app/installations/{self.config.installation_id}/access_tokens",
                "--method",
                "POST",
                "--header",
                f"Authorization: Bearer {jwt_token}",
                "--header",
                "Accept: application/vnd.github.v3+json",
            ]

            result = subprocess.run(  # nosec B603 - GitHub CLI command constructed from trusted parameters
                _gh_command(*cmd), capture_output=True, text=True, check=True
            )
            token_data: dict[str, Any] = json.loads(result.stdout)

            self.logger.debug(
                "Retrieved installation token",
                installation_id=self.config.installation_id,
            )

            return token_data

        except subprocess.CalledProcessError as e:
            self.logger.log_error(
                "Failed to get installation token", error=f"Command failed: {e.stderr}"
            )
            return None
        except json.JSONDecodeError as e:
            self.logger.log_error("Failed to parse installation token response", error=str(e))
            return None

    def configure_github_cli(self) -> bool:
        """Configure GitHub CLI to use the App token."""
        if not self.is_enabled():
            return False

        token = self.get_token()
        if not token:
            return False

        if self.mock:
            self.logger.info("MOCK: Configure GitHub CLI with App token")
            return True

        try:
            # Set the token as environment variable for gh CLI
            os.environ["GITHUB_TOKEN"] = token

            # Verify authentication
            result = subprocess.run(  # nosec B603 - GitHub CLI command constructed from trusted parameters
                _gh_command("auth", "status"),
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                self.logger.log_operation("github_cli_configured", app_id=self.config.app_id)
                return True
            else:
                self.logger.log_error("GitHub CLI authentication failed", error=result.stderr)
                return False

        except Exception as e:
            self.logger.log_error("Failed to configure GitHub CLI", error=str(e))
            return False

    def cleanup_cached_token(self) -> None:
        """Remove cached token file."""
        try:
            if keyring is not None:
                try:  # pragma: no cover - platform dependent
                    keyring.delete_password(_KEYRING_SERVICE, self._cache_key())
                    self.logger.debug("Removed GitHub App token from keyring")
                except KeyringErrorType as exc:
                    self.logger.debug("Failed to remove keyring token", error=str(exc))

            cache_path = Path(self.config.token_cache_path)
            if cache_path.exists():
                cache_path.unlink()
                self.logger.debug("Cleaned up cached token")
        except Exception as e:
            self.logger.log_error("Failed to cleanup cached token", error=str(e))


def create_github_app_manager(config: GitHubAppConfig, mock: bool = False) -> GitHubAppTokenManager:
    """Factory function to create GitHub App token manager."""
    return GitHubAppTokenManager(config, mock)


def setup_github_app_auth(
    app_id: str, private_key_path: str, installation_id: str, mock: bool = False
) -> GitHubAppTokenManager:
    """Convenience function to setup GitHub App authentication."""
    config = GitHubAppConfig(
        enabled=True,
        app_id=app_id,
        private_key_path=private_key_path,
        installation_id=installation_id,
    )

    manager = create_github_app_manager(config, mock)

    # Configure GitHub CLI immediately
    if manager.configure_github_cli():
        return manager
    else:
        raise RuntimeError("Failed to configure GitHub App authentication")


# Utility functions
def is_github_app_configured(config: GitHubAppConfig) -> bool:
    """Check if GitHub App is properly configured."""
    return (
        config.enabled
        and bool(config.app_id)
        and bool(config.private_key_path)
        and bool(config.installation_id)
        and (Path(config.private_key_path).exists() if config.private_key_path else False)
    )
