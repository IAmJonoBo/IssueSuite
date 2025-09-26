#!/usr/bin/env python3
"""Development environment setup script for IssueSuite.

This script helps set up a complete development environment including:
- Virtual environment creation and activation
- Development dependencies installation
- Pre-commit hooks setup
- Development configuration
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and handle errors."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=check, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr and result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
    return result


def main():
    """Set up development environment."""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    print("🚀 Setting up IssueSuite development environment...")

    # Check if we're already in a virtual environment
    if not os.environ.get("VIRTUAL_ENV"):
        print("⚠️  Not in a virtual environment. Creating one...")

        # Create virtual environment
        venv_path = project_root / "venv"
        if not venv_path.exists():
            run_command([sys.executable, "-m", "venv", "venv"])
            print("✅ Virtual environment created at ./venv")

        # Detect activation script
        if sys.platform == "win32":
            activate_script = venv_path / "Scripts" / "activate.bat"
            print(f"🔧 Activate with: {activate_script}")
        else:
            activate_script = venv_path / "bin" / "activate"
            print(f"🔧 Activate with: source {activate_script}")

        print("Please activate the virtual environment and run this script again.")
        return 1

    print("✅ Virtual environment detected")

    # Upgrade pip
    print("📦 Upgrading pip...")
    run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

    # Install package in editable mode with dev dependencies
    print("📦 Installing IssueSuite in editable mode with dev dependencies...")
    run_command([sys.executable, "-m", "pip", "install", "-e", ".[dev,all]"])

    # Create development config if it doesn't exist
    dev_config = project_root / "issue_suite.config.yaml"
    if not dev_config.exists():
        print("📝 Creating development configuration...")
        sample_config = """version: 1
source:
  file: ISSUES.md
  id_pattern: "^[0-9]{3}$"
  milestone_required: true
  milestone_pattern: "^(Sprint 0:|M[0-9]+:)"
defaults:
  inject_labels: [meta:roadmap, managed:declarative]
  ensure_milestones: ["Sprint 0: Mobilize & Baseline"]
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
behavior:
  truncate_body_diff: 80
ai:
  schema_export_file: issue_export.schema.json
  schema_summary_file: issue_change_summary.schema.json
  schema_version: 1
"""
        dev_config.write_text(sample_config)
        print("✅ Created issue_suite.config.yaml")

    # Run tests to verify setup
    print("🧪 Running tests to verify setup...")
    result = run_command([sys.executable, "-m", "pytest", "tests/", "-v"], check=False)
    if result.returncode == 0:
        print("✅ All tests passed!")
    else:
        print("⚠️  Some tests failed. Development environment is set up but tests need attention.")

    # Check if issuesuite command works
    print("🔍 Verifying CLI installation...")
    result = run_command(["issuesuite", "--help"], check=False)
    if result.returncode == 0:
        print("✅ CLI command working!")
    else:
        print("❌ CLI command failed. Check installation.")
        return 1

    print("\n🎉 Development environment setup complete!")
    print("\nQuick start commands:")
    print("  issuesuite validate --config issue_suite.config.yaml")
    print("  issuesuite schema --stdout")
    print("  pytest tests/ -v")
    print("  ruff check src/")
    print("  mypy src/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
