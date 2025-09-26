"""Environment-based authentication for IssueSuite.

Provides support for environment variables, .env files, and VS Code secrets
for enhanced online usage and GitHub Copilot integration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .logging import get_logger

try:  # optional dependency; tests patch this symbol
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    from os import PathLike
    from typing import IO

    def load_dotenv(
        dotenv_path: str | PathLike[str] | None = None,
        stream: IO[str] | None = None,
        verbose: bool = False,
        override: bool = False,
        interpolate: bool = True,
        encoding: str | None = None,
    ) -> bool:
        raise ImportError("python-dotenv not installed")


@dataclass
class EnvAuthConfig:
    """Configuration for environment-based authentication."""

    load_dotenv: bool = True
    dotenv_path: str | None = None
    github_token_var: str = "GITHUB_TOKEN"
    github_app_id_var: str = "GITHUB_APP_ID"
    github_app_private_key_var: str = "GITHUB_APP_PRIVATE_KEY"
    github_app_installation_id_var: str = "GITHUB_APP_INSTALLATION_ID"
    vscode_secrets_enabled: bool = True


class EnvironmentAuthManager:
    """Manages authentication through environment variables and .env files."""

    def __init__(self, config: EnvAuthConfig):
        self.config = config
        self.logger = get_logger()
        self._dotenv_loaded = False
        # Snapshot VS Code vars present at construction so we can ignore pre-existing editor plumbing
        self._initial_vscode_vars = {
            k: os.getenv(k)
            for k in ('VSCODE_GIT_ASKPASS_MAIN', 'VSCODE_GIT_IPC_HANDLE', 'GITHUB_TOKEN')
            if os.getenv(k)
        }

        if config.load_dotenv:
            self._load_dotenv()

    def _load_dotenv(self) -> None:
        """Load .env file if available."""
        try:
            dotenv_path = self.config.dotenv_path or '.env'
            env_file = Path(dotenv_path)
            if env_file.exists():
                load_dotenv(str(env_file))
                self._dotenv_loaded = True
                self.logger.debug(f"Loaded environment variables from {env_file}")
            else:
                for location in ['.env', '.env.local', '.venv/.env']:
                    env_path = Path(location)
                    if env_path.exists():
                        load_dotenv(str(env_path))
                        self._dotenv_loaded = True
                        self.logger.debug(f"Loaded environment variables from {env_path}")
                        break
        except Exception as e:  # pragma: no cover - defensive
            self.logger.debug(f"Failed to load .env file: {e}")

    def get_github_token(self) -> str | None:
        """Get GitHub token from environment variables."""
        token = os.getenv(self.config.github_token_var)
        if token:
            self.logger.debug("Found GitHub token in environment variables")
            return token

        # Try alternative environment variable names
        alternatives = ["GH_TOKEN", "GITHUB_ACCESS_TOKEN", "GH_ACCESS_TOKEN", "GITHUB_PAT"]

        for alt_var in alternatives:
            token = os.getenv(alt_var)
            if token:
                self.logger.debug(f"Found GitHub token in {alt_var}")
                return token

        return None

    def get_github_app_config(self) -> dict[str, str | None]:
        """Get GitHub App configuration from environment variables."""
        return {
            'app_id': os.getenv(self.config.github_app_id_var),
            'private_key': os.getenv(self.config.github_app_private_key_var),
            'installation_id': os.getenv(self.config.github_app_installation_id_var),
        }

    def configure_github_cli(self) -> bool:
        """Configure GitHub CLI with available authentication."""
        token = self.get_github_token()
        if token:
            os.environ['GITHUB_TOKEN'] = token
            self.logger.log_operation("github_cli_configured_from_env")
            return True

        self.logger.debug("No GitHub token found in environment")
        return False

    def get_vscode_secrets(self) -> dict[str, Any]:
        """Get secrets from VS Code environment (if available).

        Returns only variables that appear after manager construction so pre-existing
        editor plumbing env vars don't count as newly discovered secrets.
        """
        if not self.config.vscode_secrets_enabled:
            return {}
        vscode_secrets: dict[str, Any] = {}
        vscode_env_vars = [
            'VSCODE_GIT_ASKPASS_MAIN',
            'VSCODE_GIT_IPC_HANDLE',
            'GITHUB_TOKEN',
        ]
        for var in vscode_env_vars:
            value = os.getenv(var)
            if value and (
                var not in self._initial_vscode_vars or self._initial_vscode_vars[var] != value
            ):
                vscode_secrets[var.lower()] = value
        if vscode_secrets:
            self.logger.debug("Found VS Code environment secrets")
        return vscode_secrets

    def is_online_environment(self) -> bool:
        """Detect if running in an online environment (VS Code, Codespaces, etc.)."""
        online_indicators = [
            'CODESPACES',  # GitHub Codespaces
            'VSCODE_IPC_HOOK',  # VS Code
            'VSCODE_PID',  # VS Code
            'GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN',  # Codespaces
            'CI',  # CI/CD environments
            'GITHUB_ACTIONS',  # GitHub Actions
        ]

        for indicator in online_indicators:
            if os.getenv(indicator):
                self.logger.debug(f"Detected online environment: {indicator}")
                return True

        return False

    def get_authentication_recommendations(self) -> list[str]:
        """Get authentication setup recommendations based on environment."""
        recommendations: list[str] = []

        if not self.get_github_token():
            if self.is_online_environment():
                recommendations.extend(
                    [
                        "Set GITHUB_TOKEN environment variable",
                        "Or create .env file with GITHUB_TOKEN=your_token",
                        "For VS Code: Use GitHub authentication extension",
                        "For Codespaces: Token should be automatically available",
                    ]
                )
            else:
                recommendations.extend(
                    [
                        "Install GitHub CLI and run 'gh auth login'",
                        "Or set GITHUB_TOKEN environment variable",
                        "Or create .env file with GITHUB_TOKEN=your_token",
                    ]
                )

        app_config = self.get_github_app_config()
        if not all(app_config.values()) and any(app_config.values()):
            recommendations.append(
                "Incomplete GitHub App configuration - set GITHUB_APP_ID, "
                "GITHUB_APP_PRIVATE_KEY, and GITHUB_APP_INSTALLATION_ID"
            )

        return recommendations

    def create_sample_env_file(self, path: str = '.env') -> None:
        """Create a sample .env file with authentication variables."""
        sample_content = """# IssueSuite Environment Configuration

# GitHub Personal Access Token (classic or fine-grained)
GITHUB_TOKEN=your_github_token_here

# Optional: GitHub App Configuration (for enhanced rate limits)
# GITHUB_APP_ID=12345
# GITHUB_APP_PRIVATE_KEY=path/to/private-key.pem
# GITHUB_APP_INSTALLATION_ID=67890

# Optional: Debug mode
# ISSUESUITE_DEBUG=1

# Optional: Mock mode (for testing without GitHub API calls)
# ISSUES_SUITE_MOCK=1
"""

        env_path = Path(path)
        if not env_path.exists():
            env_path.write_text(sample_content)
            self.logger.log_operation("sample_env_created", file_path=str(env_path))
        else:
            self.logger.debug(f"Environment file already exists: {env_path}")


def create_env_auth_manager(config: EnvAuthConfig | None = None) -> EnvironmentAuthManager:
    """Factory function to create environment authentication manager."""
    if config is None:
        config = EnvAuthConfig()
    return EnvironmentAuthManager(config)


def setup_authentication_from_env() -> dict[str, Any]:
    """Convenience function to setup authentication from environment."""
    auth_manager = create_env_auth_manager()

    result: dict[str, Any] = {
        'github_token': auth_manager.get_github_token(),
        'github_app': auth_manager.get_github_app_config(),
        'vscode_secrets': auth_manager.get_vscode_secrets(),
        'is_online': auth_manager.is_online_environment(),
        'recommendations': auth_manager.get_authentication_recommendations(),
    }

    # Configure GitHub CLI if token is available
    if result['github_token']:
        auth_manager.configure_github_cli()

    return result
