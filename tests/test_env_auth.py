import os
from unittest.mock import patch

from issuesuite.env_auth import (
    EnvAuthConfig,
    EnvironmentAuthManager,
    create_env_auth_manager,
    setup_authentication_from_env,
)


def test_env_auth_config():
    """Test EnvAuthConfig initialization."""
    config = EnvAuthConfig(
        load_dotenv=True,
        dotenv_path=".env.test",
        github_token_var="CUSTOM_GITHUB_TOKEN",
    )

    assert config.load_dotenv is True
    assert config.dotenv_path == ".env.test"
    assert config.github_token_var == "CUSTOM_GITHUB_TOKEN"


def test_env_auth_config_defaults():
    """Test EnvAuthConfig with defaults."""
    config = EnvAuthConfig()

    assert config.load_dotenv is True
    assert config.dotenv_path is None
    assert config.github_token_var == "GITHUB_TOKEN"
    assert config.vscode_secrets_enabled is True


def test_environment_auth_manager_no_token(monkeypatch):
    """Test EnvironmentAuthManager when no token is available."""
    # Clear any existing tokens
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    config = EnvAuthConfig(load_dotenv=False)
    manager = EnvironmentAuthManager(config)

    assert manager.get_github_token() is None
    assert not manager.configure_github_cli()


def test_environment_auth_manager_with_token(monkeypatch):
    """Test EnvironmentAuthManager with GitHub token."""
    monkeypatch.setenv("GITHUB_TOKEN", "test_token_123")

    config = EnvAuthConfig(load_dotenv=False)
    manager = EnvironmentAuthManager(config)

    assert manager.get_github_token() == "test_token_123"
    assert manager.configure_github_cli()
    assert os.environ["GITHUB_TOKEN"] == "test_token_123"


def test_environment_auth_manager_alternative_tokens(monkeypatch):
    """Test EnvironmentAuthManager with alternative token names."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "alt_token_456")

    config = EnvAuthConfig(load_dotenv=False)
    manager = EnvironmentAuthManager(config)

    assert manager.get_github_token() == "alt_token_456"


def test_github_app_config_retrieval(monkeypatch):
    """Test GitHub App configuration retrieval."""
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "/path/to/key.pem")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "67890")

    config = EnvAuthConfig(load_dotenv=False)
    manager = EnvironmentAuthManager(config)

    app_config = manager.get_github_app_config()
    assert app_config["app_id"] == "12345"
    assert app_config["private_key"] == "/path/to/key.pem"
    assert app_config["installation_id"] == "67890"


def test_online_environment_detection(monkeypatch):
    """Test detection of online environments."""
    config = EnvAuthConfig(load_dotenv=False)
    manager = EnvironmentAuthManager(config)

    # No online indicators
    assert not manager.is_online_environment()

    # With VS Code indicator
    monkeypatch.setenv("VSCODE_PID", "12345")
    assert manager.is_online_environment()

    # With Codespaces indicator
    monkeypatch.delenv("VSCODE_PID")
    monkeypatch.setenv("CODESPACES", "true")
    assert manager.is_online_environment()


def test_vscode_secrets_detection(monkeypatch):
    """Test VS Code secrets detection."""
    config = EnvAuthConfig(load_dotenv=False)
    manager = EnvironmentAuthManager(config)

    # No VS Code environment
    secrets = manager.get_vscode_secrets()
    assert len(secrets) == 0

    # With VS Code environment variables
    monkeypatch.setenv("VSCODE_GIT_ASKPASS_MAIN", "/path/to/askpass")
    monkeypatch.setenv("GITHUB_TOKEN", "vscode_token")

    secrets = manager.get_vscode_secrets()
    assert "vscode_git_askpass_main" in secrets
    assert "github_token" in secrets


def test_vscode_secrets_snapshot_ignored_until_changed(monkeypatch):
    """Initial VS Code env vars present at construction should not appear until changed."""
    # Set variables BEFORE manager construction (baseline)
    monkeypatch.setenv("VSCODE_GIT_ASKPASS_MAIN", "/original/askpass")
    monkeypatch.setenv("GITHUB_TOKEN", "initial_token")
    config = EnvAuthConfig(load_dotenv=False)
    manager = EnvironmentAuthManager(config)
    # Should ignore baseline
    assert manager.get_vscode_secrets() == {}
    # Change one variable and add a new one
    monkeypatch.setenv("GITHUB_TOKEN", "rotated_token")
    monkeypatch.setenv("VSCODE_GIT_IPC_HANDLE", "/tmp/ipc.sock")
    secrets = manager.get_vscode_secrets()
    # rotated token and newly added ipc handle should appear
    assert "github_token" in secrets and secrets["github_token"] == "rotated_token"
    assert "vscode_git_ipc_handle" in secrets


def test_authentication_recommendations_no_token():
    """Test authentication recommendations when no token is found."""
    config = EnvAuthConfig(load_dotenv=False)
    manager = EnvironmentAuthManager(config)

    recommendations = manager.get_authentication_recommendations()
    assert any("GITHUB_TOKEN" in rec for rec in recommendations)


def test_authentication_recommendations_incomplete_app(monkeypatch):
    """Test recommendations with incomplete GitHub App config."""
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    # Missing other app config

    config = EnvAuthConfig(load_dotenv=False)
    manager = EnvironmentAuthManager(config)

    recommendations = manager.get_authentication_recommendations()
    assert any("Incomplete GitHub App" in rec for rec in recommendations)


def test_create_sample_env_file(tmp_path):
    """Test creation of sample .env file."""
    config = EnvAuthConfig(load_dotenv=False)
    manager = EnvironmentAuthManager(config)

    env_file = tmp_path / ".env"
    manager.create_sample_env_file(str(env_file))

    assert env_file.exists()
    content = env_file.read_text()
    assert "GITHUB_TOKEN=" in content
    assert "GITHUB_APP_ID=" in content
    assert "IssueSuite Environment Configuration" in content


def test_create_sample_env_file_existing(tmp_path):
    """Test that existing .env file is not overwritten."""
    config = EnvAuthConfig(load_dotenv=False)
    manager = EnvironmentAuthManager(config)

    env_file = tmp_path / ".env"
    env_file.write_text("EXISTING_CONTENT=true")

    manager.create_sample_env_file(str(env_file))

    # Should not overwrite existing file
    content = env_file.read_text()
    assert content == "EXISTING_CONTENT=true"


@patch("issuesuite.env_auth.load_dotenv")
def test_dotenv_loading_with_file(mock_load_dotenv, tmp_path):
    """Test .env file loading when file exists."""
    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_TOKEN=test_token")

    config = EnvAuthConfig(load_dotenv=True, dotenv_path=str(env_file))

    # Change to temp directory so the file is found
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        EnvironmentAuthManager(config)
        mock_load_dotenv.assert_called_once()
    finally:
        os.chdir(original_cwd)


def test_dotenv_loading_without_package():
    """Test graceful handling when python-dotenv is not available."""
    config = EnvAuthConfig(load_dotenv=True)

    with patch("issuesuite.env_auth.load_dotenv", side_effect=ImportError):
        manager = EnvironmentAuthManager(config)
        assert not manager._dotenv_loaded


def test_factory_function():
    """Test factory function for creating EnvironmentAuthManager."""
    manager = create_env_auth_manager()
    assert isinstance(manager, EnvironmentAuthManager)

    config = EnvAuthConfig(load_dotenv=False)
    manager = create_env_auth_manager(config)
    assert manager.config == config


def test_setup_authentication_from_env(monkeypatch):
    """Test convenience function for authentication setup."""
    monkeypatch.setenv("GITHUB_TOKEN", "test_token")
    monkeypatch.setenv("VSCODE_PID", "12345")

    result = setup_authentication_from_env()

    assert result["github_token"] == "test_token"
    assert result["is_online"] is True
    assert isinstance(result["github_app"], dict)
    assert isinstance(result["vscode_secrets"], dict)
    assert isinstance(result["recommendations"], list)


def test_vscode_secrets_disabled():
    """Test VS Code secrets when disabled."""
    config = EnvAuthConfig(vscode_secrets_enabled=False)
    manager = EnvironmentAuthManager(config)

    secrets = manager.get_vscode_secrets()
    assert len(secrets) == 0


def test_custom_token_variable(monkeypatch):
    """Test using custom GitHub token environment variable."""
    monkeypatch.setenv("CUSTOM_TOKEN", "custom_value")

    config = EnvAuthConfig(load_dotenv=False, github_token_var="CUSTOM_TOKEN")
    manager = EnvironmentAuthManager(config)

    assert manager.get_github_token() == "custom_value"


def test_custom_app_variables(monkeypatch):
    """Test using custom GitHub App environment variables."""
    monkeypatch.setenv("CUSTOM_APP_ID", "999")
    monkeypatch.setenv("CUSTOM_APP_KEY_PATH", "/custom/key")
    monkeypatch.setenv("CUSTOM_INSTALLATION_ID", "888")

    config = EnvAuthConfig(
        load_dotenv=False,
        github_app_id_var="CUSTOM_APP_ID",
        github_app_private_key_var="CUSTOM_APP_KEY_PATH",  # pragma: allowlist secret - placeholder env var name
        github_app_installation_id_var="CUSTOM_INSTALLATION_ID",
    )
    manager = EnvironmentAuthManager(config)

    app_config = manager.get_github_app_config()
    assert app_config["app_id"] == "999"
    assert app_config["private_key"] == "/custom/key"
    assert app_config["installation_id"] == "888"
