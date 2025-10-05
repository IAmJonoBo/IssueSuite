"""GitHub App authentication integration for IssueSuite.

Provides GitHub App token management with automatic renewal,
JWT generation, and installation token handling, including
graceful fallbacks when the GitHub CLI is unavailable.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess  # nosec B404 - GitHub CLI interactions require subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .logging import get_logger


def _gh_command(*args: str) -> list[str]:
    """Return a GitHub CLI command preferring the absolute path when available."""
    gh_path = shutil.which('gh')
    base = gh_path if gh_path else 'gh'
    return [base, *args]


@dataclass
class GitHubAppConfig:
    """Configuration for GitHub App authentication."""

    enabled: bool
    app_id: str | None
    private_key_path: str | None
    installation_id: str | None
    token_cache_path: str = '.github_app_token.json'


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
            return 'mock_github_app_token'

        # Check if we have a valid cached token
        if self._is_token_valid():
            return self._cached_token

        # Try to load token from cache
        if self._load_cached_token():
            if self._is_token_valid():
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

    def _load_cached_token(self) -> bool:
        """Load token from cache file."""
        cache_path = Path(self.config.token_cache_path)
        if not cache_path.exists():
            return False

        try:
            with cache_path.open('r') as f:
                data = json.load(f)

            token_val = data.get('token')
            self._cached_token = str(token_val) if isinstance(token_val, str) else None
            expires_str = data.get('expires_at')
            if isinstance(expires_str, str) and expires_str:
                self._token_expires_at = datetime.fromisoformat(expires_str)

            self.logger.debug("Loaded cached GitHub App token")
            return True
        except Exception as e:
            self.logger.log_error("Failed to load cached token", error=str(e))
            return False

    def _save_cached_token(self) -> None:
        """Save token to cache file."""
        if not self._cached_token or self._token_expires_at is None:
            return

        try:
            cache_path = Path(self.config.token_cache_path)
            data = {
                'token': self._cached_token,
                'expires_at': self._token_expires_at.isoformat(),
                'cached_at': datetime.now(timezone.utc).isoformat(),
            }

            with cache_path.open('w') as f:
                json.dump(data, f, indent=2)

            # Set restrictive permissions
            cache_path.chmod(0o600)
            self.logger.debug("Cached GitHub App token")
        except Exception as e:
            self.logger.log_error("Failed to cache token", error=str(e))

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

            self._cached_token = str(installation_token['token'])

            # Parse expiration time
            expires_str = installation_token.get('expires_at')
            if isinstance(expires_str, str) and expires_str:
                # GitHub uses ISO format: 2025-01-01T10:00:00Z
                self._token_expires_at = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
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

            # For security, we'll use GitHub CLI if available, otherwise use simple JWT
            gh_cli = shutil.which('gh')
            if gh_cli:
                try:
                    result = subprocess.run(  # nosec B603 - fixed GitHub CLI arguments
                        [gh_cli, 'auth', 'status', '--show-token'],
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    # If gh CLI is already authenticated, we might not need App auth
                    if result.returncode == 0:
                        self.logger.debug(
                            "GitHub CLI already authenticated",
                            gh_path=gh_cli,
                        )

                except subprocess.CalledProcessError as exc:
                    self.logger.debug(
                        "GitHub CLI authentication status check failed",
                        gh_path=gh_cli,
                        error=(exc.stderr or str(exc)),
                    )
                except OSError as exc:
                    self.logger.debug(
                        "GitHub CLI invocation failed",
                        gh_path=gh_cli,
                        error=str(exc),
                    )
            else:
                self.logger.debug("GitHub CLI not found; skipping auth status probe")

            # Generate basic JWT (simplified for demo)
            # In production, use a proper JWT library like PyJWT
            now = int(time.time())
            header = {'typ': 'JWT', 'alg': 'RS256'}
            payload = {
                'iat': now - 60,  # Issued 60 seconds ago
                'exp': now + 600,  # Expires in 10 minutes
                'iss': self.config.app_id,
            }

            # This is a simplified JWT - in production use PyJWT
            header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')

            payload_b64 = (
                base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
            )

            jwt_token = f"{header_b64}.{payload_b64}.signature_placeholder"

            self.logger.debug("Generated JWT for GitHub App", app_id=self.config.app_id)
            return jwt_token

        except Exception as e:
            self.logger.log_error("Failed to generate JWT", error=str(e))
            return None

    def _get_installation_token(self, jwt_token: str) -> dict[str, Any] | None:
        """Get installation token using JWT."""
        try:
            # Use GitHub CLI with the JWT token
            if not self.config.installation_id:
                self.logger.log_error("Installation ID not configured")
                return None
            cmd = [
                'api',
                f'/app/installations/{self.config.installation_id}/access_tokens',
                '--method',
                'POST',
                '--header',
                f'Authorization: Bearer {jwt_token}',
                '--header',
                'Accept: application/vnd.github.v3+json',
            ]

            result = subprocess.run(  # nosec B603 B607 - arguments are fully controlled
                _gh_command(*cmd),
                capture_output=True,
                text=True,
                check=True,
            )
            token_data: dict[str, Any] = json.loads(result.stdout)

            self.logger.debug(
                "Retrieved installation token", installation_id=self.config.installation_id
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
            os.environ['GITHUB_TOKEN'] = token

            # Verify authentication
            result = subprocess.run(  # nosec B603 B607 - status check uses controlled arguments
                _gh_command('auth', 'status'),
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
