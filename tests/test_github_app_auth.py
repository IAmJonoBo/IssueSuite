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

KEY_HEADER = "-----BEGIN " "PRIVATE KEY-----"
KEY_FOOTER = "-----END " "PRIVATE KEY-----"


def test_github_app_config():
    """Test GitHubAppConfig initialization."""
    config = GitHubAppConfig(
        enabled=True, app_id='12345', private_key_path='/path/to/key.pem', installation_id='67890'
    )

    assert config.enabled is True
    assert config.app_id == '12345'
    assert config.private_key_path == '/path/to/key.pem'
    assert config.installation_id == '67890'
    assert config.token_cache_path == '.github_app_token.json'


def test_github_app_token_manager_disabled():
    """Test GitHubAppTokenManager when disabled."""
    config = GitHubAppConfig(
        enabled=False, app_id=None, private_key_path=None, installation_id=None
    )
    manager = GitHubAppTokenManager(config)

    assert manager.is_enabled() is False
    assert manager.get_token() is None


def test_github_app_token_manager_mock_mode():
    """Test GitHubAppTokenManager in mock mode."""
    config = GitHubAppConfig(
        enabled=True, app_id='12345', private_key_path='/path/to/key.pem', installation_id='67890'
    )
    manager = GitHubAppTokenManager(config, mock=True)

    assert manager.is_enabled() is True
    assert manager.get_token() == 'mock_github_app_token'


def test_github_app_token_manager_missing_config():
    """Test GitHubAppTokenManager with missing configuration."""
    # Missing app_id
    config = GitHubAppConfig(
        enabled=True, app_id=None, private_key_path='/path/to/key.pem', installation_id='67890'
    )
    manager = GitHubAppTokenManager(config)
    assert manager.is_enabled() is False

    # Missing private_key_path
    config = GitHubAppConfig(
        enabled=True, app_id='12345', private_key_path=None, installation_id='67890'
    )
    manager = GitHubAppTokenManager(config)
    assert manager.is_enabled() is False

    # Missing installation_id
    config = GitHubAppConfig(
        enabled=True, app_id='12345', private_key_path='/path/to/key.pem', installation_id=None
    )
    manager = GitHubAppTokenManager(config)
    assert manager.is_enabled() is False


def test_token_caching(tmp_path):
    """Test token caching functionality."""
    config = GitHubAppConfig(
        enabled=True,
        app_id='12345',
        private_key_path='/path/to/key.pem',
        installation_id='67890',
        token_cache_path=str(tmp_path / 'test_token.json'),
    )
    manager = GitHubAppTokenManager(config)

    # Set up a test token
    test_token = 'test_token_12345'
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    manager._cached_token = test_token
    manager._token_expires_at = expires_at

    # Save to cache
    manager._save_cached_token()

    # Verify cache file exists
    cache_path = Path(config.token_cache_path)
    assert cache_path.exists()

    # Create new manager and load from cache
    manager2 = GitHubAppTokenManager(config)
    success = manager2._load_cached_token()

    assert success is True
    assert manager2._cached_token == test_token
    assert manager2._token_expires_at is not None


def test_token_expiry_check():
    """Test token expiry validation."""
    config = GitHubAppConfig(
        enabled=True, app_id='12345', private_key_path='/path/to/key.pem', installation_id='67890'
    )
    manager = GitHubAppTokenManager(config)

    # No token
    assert manager._is_token_valid() is False

    # Valid token
    manager._cached_token = 'valid_token'
    manager._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    assert manager._is_token_valid() is True

    # Expired token
    manager._token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    assert manager._is_token_valid() is False

    # Token expiring soon (within 5 minute buffer)
    manager._token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=2)
    assert manager._is_token_valid() is False


def test_jwt_generation_with_missing_key():
    """Test JWT generation with missing private key file."""
    config = GitHubAppConfig(
        enabled=True,
        app_id='12345',
        private_key_path='/nonexistent/key.pem',
        installation_id='67890',
    )
    manager = GitHubAppTokenManager(config)

    jwt_token = manager._generate_jwt()
    assert jwt_token is None


def test_jwt_generation_with_key_file(tmp_path):
    """Test JWT generation with existing private key file."""
    # Create a dummy private key file
    key_path = tmp_path / 'test_key.pem'
    key_path.write_text(f"{KEY_HEADER}\ntest_key_content\n{KEY_FOOTER}")

    config = GitHubAppConfig(
        enabled=True, app_id='12345', private_key_path=str(key_path), installation_id='67890'
    )
    manager = GitHubAppTokenManager(config)

    jwt_token = manager._generate_jwt()

    # Should generate a JWT (simplified version)
    assert jwt_token is not None
    assert isinstance(jwt_token, str)
    assert '.' in jwt_token  # JWT format has dots


@patch('issuesuite.github_auth.shutil.which', return_value=None)
@patch('issuesuite.github_auth.subprocess.run')
def test_jwt_generation_without_gh_cli(mock_run, mock_which, tmp_path):
    """Ensure JWT generation skips GitHub CLI when it is unavailable."""
    key_path = tmp_path / 'test_key.pem'
    key_path.write_text(f"{KEY_HEADER}\nfake\n{KEY_FOOTER}")

    config = GitHubAppConfig(
        enabled=True, app_id='12345', private_key_path=str(key_path), installation_id='67890'
    )
    manager = GitHubAppTokenManager(config)

    jwt_token = manager._generate_jwt()

    assert jwt_token is not None
    mock_which.assert_called_once_with('gh')
    mock_run.assert_not_called()


@patch('subprocess.run')
def test_installation_token_success(mock_run):
    """Test successful installation token retrieval."""
    # Mock successful API response
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(
        {'token': 'ghs_installation_token_12345', 'expires_at': '2025-01-01T10:00:00Z'}
    )
    mock_run.return_value = mock_result

    config = GitHubAppConfig(
        enabled=True, app_id='12345', private_key_path='/path/to/key.pem', installation_id='67890'
    )
    manager = GitHubAppTokenManager(config)

    jwt_token = 'test.jwt.token'
    token_data = manager._get_installation_token(jwt_token)

    assert token_data is not None
    assert token_data['token'] == 'ghs_installation_token_12345'
    assert token_data['expires_at'] == '2025-01-01T10:00:00Z'

    # Verify the correct API call was made
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert 'gh' in args
    assert 'api' in args
    assert '/app/installations/67890/access_tokens' in args


@patch('subprocess.run')
def test_installation_token_failure(mock_run):
    """Test installation token retrieval failure."""
    # Mock failed API response
    mock_run.side_effect = subprocess.CalledProcessError(1, 'gh', stderr='Authentication failed')

    config = GitHubAppConfig(
        enabled=True, app_id='12345', private_key_path='/path/to/key.pem', installation_id='67890'
    )
    manager = GitHubAppTokenManager(config)

    jwt_token = 'test.jwt.token'
    token_data = manager._get_installation_token(jwt_token)

    assert token_data is None


@patch('subprocess.run')
def test_configure_github_cli_success(mock_run):
    """Test successful GitHub CLI configuration."""
    # Mock successful gh auth status
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = 'Logged in to github.com as app'
    mock_run.return_value = mock_result

    config = GitHubAppConfig(
        enabled=True, app_id='12345', private_key_path='/path/to/key.pem', installation_id='67890'
    )
    manager = GitHubAppTokenManager(config, mock=False)
    manager._cached_token = 'test_token'
    manager._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    success = manager.configure_github_cli()
    assert success is True

    # Verify environment variable was set
    assert os.environ.get('GITHUB_TOKEN') == 'test_token'


def test_configure_github_cli_mock():
    """Test GitHub CLI configuration in mock mode."""
    config = GitHubAppConfig(
        enabled=True, app_id='12345', private_key_path='/path/to/key.pem', installation_id='67890'
    )
    manager = GitHubAppTokenManager(config, mock=True)

    success = manager.configure_github_cli()
    assert success is True  # Should always succeed in mock mode


def test_cleanup_cached_token(tmp_path):
    """Test cleanup of cached token file."""
    cache_path = tmp_path / 'test_token.json'
    cache_path.write_text('{"token": "test"}')

    config = GitHubAppConfig(
        enabled=True,
        app_id='12345',
        private_key_path='/path/to/key.pem',
        installation_id='67890',
        token_cache_path=str(cache_path),
    )
    manager = GitHubAppTokenManager(config)

    assert cache_path.exists()
    manager.cleanup_cached_token()
    assert not cache_path.exists()


def test_factory_function():
    """Test factory function for creating GitHubAppTokenManager."""
    config = GitHubAppConfig(
        enabled=True, app_id='12345', private_key_path='/path/to/key.pem', installation_id='67890'
    )

    manager = create_github_app_manager(config, mock=True)
    assert isinstance(manager, GitHubAppTokenManager)
    assert manager.config == config
    assert manager.mock is True


def test_setup_github_app_auth_success():
    """Test convenience function for setting up GitHub App auth."""
    with patch.object(GitHubAppTokenManager, 'configure_github_cli', return_value=True):
        manager = setup_github_app_auth(
            app_id='12345', private_key_path='/path/to/key.pem', installation_id='67890', mock=True
        )

        assert isinstance(manager, GitHubAppTokenManager)
        assert manager.config.app_id == '12345'


def test_setup_github_app_auth_failure():
    """Test convenience function failure."""
    with patch.object(GitHubAppTokenManager, 'configure_github_cli', return_value=False):
        try:
            setup_github_app_auth(
                app_id='12345',
                private_key_path='/path/to/key.pem',
                installation_id='67890',
                mock=True,
            )
            raise AssertionError("Should have raised RuntimeError")
        except RuntimeError as e:
            assert "Failed to configure GitHub App authentication" in str(e)


def test_is_github_app_configured(tmp_path):
    """Test utility function to check if GitHub App is configured."""
    # Not enabled
    config = GitHubAppConfig(
        enabled=False, app_id='123', private_key_path='/key', installation_id='456'
    )
    assert is_github_app_configured(config) is False

    # Missing app_id
    config = GitHubAppConfig(
        enabled=True, app_id=None, private_key_path='/key', installation_id='456'
    )
    assert is_github_app_configured(config) is False

    # Missing private key file
    config = GitHubAppConfig(
        enabled=True, app_id='123', private_key_path='/nonexistent', installation_id='456'
    )
    assert is_github_app_configured(config) is False

    # Properly configured
    key_path = tmp_path / 'key.pem'
    key_path.write_text('test key')
    config = GitHubAppConfig(
        enabled=True, app_id='123', private_key_path=str(key_path), installation_id='456'
    )
    assert is_github_app_configured(config) is True
