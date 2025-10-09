from __future__ import annotations

import base64
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from issuesuite.github_auth import (
    GitHubAppConfig,
    GitHubAppTokenManager,
    create_github_app_manager,
    is_github_app_configured,
    setup_github_app_auth,
)


def test_github_app_config() -> None:
    """Test GitHubAppConfig initialization."""
    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/path/to/key.pem",
        installation_id="67890",
    )

    assert config.enabled is True
    assert config.app_id == "12345"
    assert config.private_key_path == "/path/to/key.pem"
    assert config.installation_id == "67890"
    assert config.token_cache_path == ".github_app_token.json"


def test_github_app_token_manager_disabled() -> None:
    """Test GitHubAppTokenManager when disabled."""
    config = GitHubAppConfig(
        enabled=False, app_id=None, private_key_path=None, installation_id=None
    )
    manager = GitHubAppTokenManager(config)

    assert manager.is_enabled() is False
    assert manager.get_token() is None


def test_github_app_token_manager_mock_mode() -> None:
    """Test GitHubAppTokenManager in mock mode."""
    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/path/to/key.pem",
        installation_id="67890",
    )
    manager = GitHubAppTokenManager(config, mock=True)

    assert manager.is_enabled() is True
    assert manager.get_token() == "mock_github_app_token"


def test_github_app_token_manager_missing_config() -> None:
    """Test GitHubAppTokenManager with missing configuration."""
    # Missing app_id
    config = GitHubAppConfig(
        enabled=True,
        app_id=None,
        private_key_path="/path/to/key.pem",
        installation_id="67890",
    )
    manager = GitHubAppTokenManager(config)
    assert manager.is_enabled() is False

    # Missing private_key_path
    config = GitHubAppConfig(
        enabled=True, app_id="12345", private_key_path=None, installation_id="67890"
    )
    manager = GitHubAppTokenManager(config)
    assert manager.is_enabled() is False

    # Missing installation_id
    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/path/to/key.pem",
        installation_id=None,
    )
    manager = GitHubAppTokenManager(config)
    assert manager.is_enabled() is False


@patch("issuesuite.github_auth.keyring", None)
def test_token_caching(tmp_path: Path) -> None:
    """Test token caching functionality."""
    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/path/to/key.pem",
        installation_id="67890",
        token_cache_path=str(tmp_path / "test_token.json"),
    )
    manager = GitHubAppTokenManager(config)

    # Set up a test token
    test_token = "test_token_12345"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    manager._cached_token = test_token
    manager._token_expires_at = expires_at

    # Save to cache
    manager._save_cached_token()

    # Verify cache file exists
    cache_path = Path(config.token_cache_path)
    assert cache_path.exists()
    cache_data = json.loads(cache_path.read_text())
    assert "payload" in cache_data
    assert "token" not in cache_data
    payload = cache_data["payload"]
    decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
    decoded_data = json.loads(decoded)
    assert decoded_data["token"] == test_token

    # Create new manager and load from cache
    manager2 = GitHubAppTokenManager(config)
    success = manager2._load_cached_token()

    assert success is True
    assert manager2._cached_token == test_token
    assert manager2._token_expires_at is not None


def test_token_caching_with_keyring(tmp_path: Path) -> None:
    """Token caching prefers system keyring when available."""
    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/path/to/key.pem",
        installation_id="67890",
        token_cache_path=str(tmp_path / "test_token.json"),
    )
    manager = GitHubAppTokenManager(config)
    manager._cached_token = "secure_token"
    manager._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    stored_payload: dict[str, str] = {}

    def capture_set_password(service: str, key: str, value: str) -> None:
        stored_payload["value"] = value

    mock_keyring = MagicMock()
    mock_keyring.set_password.side_effect = capture_set_password
    mock_keyring.get_password.side_effect = lambda service, key: stored_payload.get("value")

    with (
        patch("issuesuite.github_auth.keyring", mock_keyring),
        patch("issuesuite.github_auth.KeyringErrorType", Exception),
    ):
        manager._save_cached_token()
        payload_value = stored_payload.get("value")
        assert payload_value is not None

        manager._cached_token = None
        manager._token_expires_at = None

        assert manager._load_cached_token() is True
        assert manager._cached_token == "secure_token"
        assert manager._token_expires_at is not None


@patch("issuesuite.github_auth.keyring", None)
def test_load_cached_token_legacy_format(tmp_path: Path) -> None:
    """Legacy plaintext cache files still load successfully."""
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    cache_payload = {
        "token": "legacy-token",
        "expires_at": expires_at.isoformat(),
    }
    cache_path = tmp_path / "legacy.json"
    cache_path.write_text(json.dumps(cache_payload))

    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/path/to/key.pem",
        installation_id="67890",
        token_cache_path=str(cache_path),
    )
    manager = GitHubAppTokenManager(config)

    assert manager._load_cached_token() is True
    assert manager._cached_token == "legacy-token"
    assert manager._token_expires_at is not None


def test_token_expiry_check() -> None:
    """Test token expiry validation."""
    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/path/to/key.pem",
        installation_id="67890",
    )
    manager = GitHubAppTokenManager(config)

    # No token
    assert manager._is_token_valid() is False

    # Valid token
    manager._cached_token = "valid_token"
    manager._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    assert manager._is_token_valid() is True

    # Expired token
    manager._token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    assert manager._is_token_valid() is False

    # Token expiring soon (within 5 minute buffer)
    manager._token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=2)
    assert manager._is_token_valid() is False


def test_jwt_generation_with_missing_key() -> None:
    """Test JWT generation with missing private key file."""
    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/nonexistent/key.pem",
        installation_id="67890",
    )
    manager = GitHubAppTokenManager(config)

    jwt_token = manager._generate_jwt()
    assert jwt_token is None


def test_jwt_generation_with_key_file(tmp_path: Path) -> None:
    """Test JWT generation with existing private key file."""
    # Create a dummy private key file
    key_path = tmp_path / "test_key.pem"
    key_path.write_text("-----BEGIN PRIVATE KEY-----\ntest_key_content\n-----END PRIVATE KEY-----")

    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path=str(key_path),
        installation_id="67890",
    )
    manager = GitHubAppTokenManager(config)

    jwt_token = manager._generate_jwt()

    # Should generate a JWT (simplified version)
    assert jwt_token is not None
    assert isinstance(jwt_token, str)
    assert "." in jwt_token  # JWT format has dots
    assert jwt_token.endswith("signature_placeholder")


def test_jwt_generation_without_pyjwt(tmp_path: Path) -> None:
    """Fallback JWT is generated when PyJWT is unavailable."""
    key_path = tmp_path / "test_key.pem"
    key_path.write_text("-----BEGIN PRIVATE KEY-----\ntest_key_content\n-----END PRIVATE KEY-----")

    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path=str(key_path),
        installation_id="67890",
    )
    manager = GitHubAppTokenManager(config)

    with patch("issuesuite.github_auth.jwt", None):
        token = manager._generate_jwt()

    assert token is not None
    assert token.endswith("signature_placeholder")


def test_jwt_generation_with_pyjwt_bytes(tmp_path: Path) -> None:
    """PyJWT integration decodes byte responses to string."""
    key_path = tmp_path / "test_key.pem"
    key_path.write_text("-----BEGIN PRIVATE KEY-----\ntest_key_content\n-----END PRIVATE KEY-----")

    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path=str(key_path),
        installation_id="67890",
    )
    manager = GitHubAppTokenManager(config)

    class DummyJWT:
        @staticmethod
        def encode(*_: object, **__: object) -> bytes:
            return b"signed-token"

    with patch("issuesuite.github_auth.jwt", DummyJWT):
        token = manager._generate_jwt()

    assert token == "signed-token"


@patch("subprocess.run")
def test_installation_token_success(mock_run: MagicMock) -> None:
    """Test successful installation token retrieval."""
    # Mock successful API response
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(
        {"token": "ghs_installation_token_12345", "expires_at": "2025-01-01T10:00:00Z"}
    )
    mock_run.return_value = mock_result

    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/path/to/key.pem",
        installation_id="67890",
    )
    manager = GitHubAppTokenManager(config)

    jwt_token = "test.jwt.token"
    token_data = manager._get_installation_token(jwt_token)

    assert token_data is not None
    assert token_data["token"] == "ghs_installation_token_12345"
    assert token_data["expires_at"] == "2025-01-01T10:00:00Z"

    # Verify the correct API call was made
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert os.path.basename(args[0]) == "gh"
    assert "api" in args
    assert "/app/installations/67890/access_tokens" in args


@patch("subprocess.run")
def test_installation_token_failure(mock_run: MagicMock) -> None:
    """Test installation token retrieval failure."""
    # Mock failed API response
    mock_run.side_effect = subprocess.CalledProcessError(1, "gh", stderr="Authentication failed")

    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/path/to/key.pem",
        installation_id="67890",
    )
    manager = GitHubAppTokenManager(config)

    jwt_token = "test.jwt.token"
    token_data = manager._get_installation_token(jwt_token)

    assert token_data is None


@patch("subprocess.run")
def test_configure_github_cli_success(mock_run: MagicMock) -> None:
    """Test successful GitHub CLI configuration."""
    # Mock successful gh auth status
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Logged in to github.com as app"
    mock_run.return_value = mock_result

    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/path/to/key.pem",
        installation_id="67890",
    )
    manager = GitHubAppTokenManager(config, mock=False)
    manager._cached_token = "test_token"
    manager._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    success = manager.configure_github_cli()
    assert success is True

    # Verify environment variable was set
    assert os.environ.get("GITHUB_TOKEN") == "test_token"


def test_configure_github_cli_mock() -> None:
    """Test GitHub CLI configuration in mock mode."""
    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/path/to/key.pem",
        installation_id="67890",
    )
    manager = GitHubAppTokenManager(config, mock=True)

    success = manager.configure_github_cli()
    assert success is True  # Should always succeed in mock mode


def test_cleanup_cached_token(tmp_path: Path) -> None:
    """Test cleanup of cached token file."""
    cache_path = tmp_path / "test_token.json"
    cache_path.write_text('{"token": "test"}')

    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/path/to/key.pem",
        installation_id="67890",
        token_cache_path=str(cache_path),
    )
    manager = GitHubAppTokenManager(config)

    assert cache_path.exists()
    mock_keyring = MagicMock()
    with (
        patch("issuesuite.github_auth.keyring", mock_keyring),
        patch("issuesuite.github_auth.KeyringErrorType", Exception),
    ):
        manager.cleanup_cached_token()
    assert not cache_path.exists()
    mock_keyring.delete_password.assert_called_once_with(
        "issuesuite.github_app", f"{config.app_id}:{config.installation_id}"
    )


def test_factory_function() -> None:
    """Test factory function for creating GitHubAppTokenManager."""
    config = GitHubAppConfig(
        enabled=True,
        app_id="12345",
        private_key_path="/path/to/key.pem",
        installation_id="67890",
    )

    manager = create_github_app_manager(config, mock=True)
    assert isinstance(manager, GitHubAppTokenManager)
    assert manager.config == config
    assert manager.mock is True


def test_setup_github_app_auth_success() -> None:
    """Test convenience function for setting up GitHub App auth."""
    with patch.object(GitHubAppTokenManager, "configure_github_cli", return_value=True):
        manager = setup_github_app_auth(
            app_id="12345",
            private_key_path="/path/to/key.pem",
            installation_id="67890",
            mock=True,
        )

        assert isinstance(manager, GitHubAppTokenManager)
        assert manager.config.app_id == "12345"


def test_setup_github_app_auth_failure() -> None:
    """Test convenience function failure."""
    with patch.object(GitHubAppTokenManager, "configure_github_cli", return_value=False):
        try:
            setup_github_app_auth(
                app_id="12345",
                private_key_path="/path/to/key.pem",
                installation_id="67890",
                mock=True,
            )
            raise AssertionError("Should have raised RuntimeError")
        except RuntimeError as e:
            assert "Failed to configure GitHub App authentication" in str(e)


def test_is_github_app_configured(tmp_path: Path) -> None:
    """Test utility function to check if GitHub App is configured."""
    # Not enabled
    config = GitHubAppConfig(
        enabled=False, app_id="123", private_key_path="/key", installation_id="456"
    )
    assert is_github_app_configured(config) is False

    # Missing app_id
    config = GitHubAppConfig(
        enabled=True, app_id=None, private_key_path="/key", installation_id="456"
    )
    assert is_github_app_configured(config) is False

    # Missing private key file
    config = GitHubAppConfig(
        enabled=True,
        app_id="123",
        private_key_path="/nonexistent",
        installation_id="456",
    )
    assert is_github_app_configured(config) is False

    # Properly configured
    key_path = tmp_path / "key.pem"
    key_path.write_text("test key")
    config = GitHubAppConfig(
        enabled=True,
        app_id="123",
        private_key_path=str(key_path),
        installation_id="456",
    )
    assert is_github_app_configured(config) is True
