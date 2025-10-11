import os

from issuesuite.cli import main

CONFIG = """
version: 1
source:
  file: ISSUES.md
github: {}
defaults:
  inject_labels: []
  ensure_milestones: []
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
output: {}
behavior: {}
ai: {}
logging:
  json_enabled: false
  level: INFO
"""


def test_cli_setup_help(tmp_path, capsys):
    """Test setup command help."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(CONFIG)

    # Change to temp directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = main(["setup", "--config", str(cfg_path)])
        assert result == 0

        captured = capsys.readouterr()
        assert "[setup] Use --help to see available setup options" in captured.out
        assert "--create-env" in captured.out
        assert "--check-auth" in captured.out
        assert "--vscode" in captured.out
    finally:
        os.chdir(original_cwd)


def test_cli_setup_create_env(tmp_path, capsys):
    """Test setup command with --create-env."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(CONFIG)

    # Change to temp directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = main(["setup", "--create-env", "--config", str(cfg_path)])
        assert result == 0

        # Check that .env file was created
        env_file = tmp_path / ".env"
        assert env_file.exists()

        content = env_file.read_text()
        assert "GITHUB_TOKEN=" in content
        assert "IssueSuite Environment Configuration" in content

        captured = capsys.readouterr()
        assert "[setup] Created sample .env file" in captured.out
    finally:
        os.chdir(original_cwd)


def test_cli_setup_check_auth_no_token(tmp_path, capsys, monkeypatch):
    """Test setup command with --check-auth when no token exists."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(CONFIG)

    # Clear any existing tokens
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    # Change to temp directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = main(["setup", "--check-auth", "--config", str(cfg_path)])
        assert result == 0

        captured = capsys.readouterr()
        assert "[setup] Environment: Local" in captured.out
        assert "[setup] GitHub Token: ✗ Not found" in captured.out
        assert "[setup] Recommendations:" in captured.out
    finally:
        os.chdir(original_cwd)


def test_cli_setup_check_auth_with_token(tmp_path, capsys, monkeypatch):
    """Test setup command with --check-auth when token exists."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(CONFIG)

    # Set up environment with token
    monkeypatch.setenv("GITHUB_TOKEN", "test_token_123")

    # Change to temp directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = main(["setup", "--check-auth", "--config", str(cfg_path)])
        assert result == 0

        captured = capsys.readouterr()
        assert "[setup] GitHub Token: ✓ Found" in captured.out
    finally:
        os.chdir(original_cwd)


def test_cli_setup_check_auth_online_environment(tmp_path, capsys, monkeypatch):
    """Test setup command in online environment."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(CONFIG)

    # Simulate VS Code environment
    monkeypatch.setenv("VSCODE_PID", "12345")
    monkeypatch.setenv("GITHUB_TOKEN", "vscode_token")

    # Change to temp directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = main(["setup", "--check-auth", "--config", str(cfg_path)])
        assert result == 0

        captured = capsys.readouterr()
        assert "[setup] Environment: Online" in captured.out
        assert "[setup] GitHub Token: ✓ Found" in captured.out
    finally:
        os.chdir(original_cwd)


def test_cli_setup_vscode(tmp_path, capsys):
    """Test setup command with --vscode."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(CONFIG)

    # Change to temp directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = main(["setup", "--vscode", "--config", str(cfg_path)])
        assert result == 0

        captured = capsys.readouterr()
        assert "[setup] VS Code integration includes:" in captured.out
        assert "Tasks for common IssueSuite operations" in captured.out
        assert "Expanded debug configurations" in captured.out
    finally:
        os.chdir(original_cwd)


def test_cli_setup_vscode_with_existing_dir(tmp_path, capsys):
    """Test setup command with --vscode when .vscode directory exists."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(CONFIG)

    # Create .vscode directory
    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()

    # Change to temp directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = main(["setup", "--vscode", "--config", str(cfg_path)])
        assert result == 0

        captured = capsys.readouterr()
        assert "[setup] VS Code integration files already exist" in captured.out
    finally:
        os.chdir(original_cwd)


def test_cli_setup_github_app_config(tmp_path, capsys, monkeypatch):
    """Test setup command with GitHub App configuration."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(CONFIG)

    # Set up partial GitHub App config
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    # Missing other required vars

    # Change to temp directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = main(["setup", "--check-auth", "--config", str(cfg_path)])
        assert result == 0

        captured = capsys.readouterr()
        assert "[setup] GitHub App: ✗ Not configured" in captured.out
        assert "Incomplete GitHub App configuration" in captured.out
    finally:
        os.chdir(original_cwd)


def test_cli_setup_complete_github_app_config(tmp_path, capsys, monkeypatch):
    """Test setup command with complete GitHub App configuration."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(CONFIG)

    # Set up complete GitHub App config
    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "/path/to/key.pem")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "67890")

    # Change to temp directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = main(["setup", "--check-auth", "--config", str(cfg_path)])
        assert result == 0

        captured = capsys.readouterr()
        assert "[setup] GitHub App: ✓ Configured" in captured.out
    finally:
        os.chdir(original_cwd)


def test_cli_setup_multiple_options(tmp_path, capsys, monkeypatch):
    """Test setup command with multiple options."""
    cfg_path = tmp_path / "issue_suite.config.yaml"
    cfg_path.write_text(CONFIG)

    monkeypatch.setenv("GITHUB_TOKEN", "test_token")

    # Change to temp directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = main(
            [
                "setup",
                "--create-env",
                "--check-auth",
                "--vscode",
                "--config",
                str(cfg_path),
            ]
        )
        assert result == 0

        captured = capsys.readouterr()

        # Should have output from all three options
        assert "[setup] Created sample .env file" in captured.out
        assert "[setup] GitHub Token: ✓ Found" in captured.out
        assert "[setup] VS Code integration includes:" in captured.out

        # Should have created .env file
        env_file = tmp_path / ".env"
        assert env_file.exists()
    finally:
        os.chdir(original_cwd)
