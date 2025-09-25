import os
from pathlib import Path
from issuesuite import IssueSuite, load_config


CONFIG_WITH_GITHUB_APP = """
version: 1
source:
  file: ISSUES.md
github:
  app:
    enabled: true
    app_id: "12345"
    private_key_path: "/path/to/private-key.pem"
    installation_id: "67890"
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

CONFIG_WITHOUT_GITHUB_APP = """
version: 1
source:
  file: ISSUES.md
github:
  app:
    enabled: false
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

ISSUES = """## 001 | Test Issue
labels: bug
---
Test issue body
"""


def test_sync_with_github_app_enabled(monkeypatch, tmp_path):
    """Test sync with GitHub App authentication enabled."""
    cfg_path = tmp_path / 'issue_suite.config.yaml'
    (tmp_path / 'ISSUES.md').write_text(ISSUES)
    cfg_path.write_text(CONFIG_WITH_GITHUB_APP)
    
    # Set mock mode to avoid actual GitHub authentication
    monkeypatch.setenv('ISSUES_SUITE_MOCK', '1')
    
    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)
    
    # Verify GitHub App config is loaded
    assert cfg.github_app_enabled is True
    assert cfg.github_app_id == "12345"
    assert cfg.github_app_private_key_path == "/path/to/private-key.pem"
    assert cfg.github_app_installation_id == "67890"
    
    # Verify GitHub App manager is configured
    assert suite._github_app_config.enabled is True
    assert suite._github_app_config.app_id == "12345"
    assert suite._github_app_manager is not None
    
    # Run sync - should work with GitHub App auth
    summary = suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)
    
    # Should complete successfully
    assert summary['totals']['specs'] == 1
    assert summary['totals']['created'] == 1


def test_sync_with_github_app_disabled(monkeypatch, tmp_path):
    """Test sync with GitHub App authentication disabled."""
    cfg_path = tmp_path / 'issue_suite.config.yaml'
    (tmp_path / 'ISSUES.md').write_text(ISSUES)
    cfg_path.write_text(CONFIG_WITHOUT_GITHUB_APP)
    
    # Set mock mode
    monkeypatch.setenv('ISSUES_SUITE_MOCK', '1')
    
    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)
    
    # Verify GitHub App is disabled
    assert cfg.github_app_enabled is False
    assert suite._github_app_config.enabled is False
    
    # Run sync - should still work without GitHub App auth
    summary = suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)
    
    # Should complete successfully
    assert summary['totals']['specs'] == 1
    assert summary['totals']['created'] == 1


def test_github_app_config_loading(tmp_path):
    """Test loading GitHub App configuration from config file."""
    cfg_path = tmp_path / 'issue_suite.config.yaml'
    cfg_path.write_text(CONFIG_WITH_GITHUB_APP)
    
    cfg = load_config(cfg_path)
    
    # Verify GitHub App settings are loaded correctly
    assert cfg.github_app_enabled is True
    assert cfg.github_app_id == "12345"
    assert cfg.github_app_private_key_path == "/path/to/private-key.pem"
    assert cfg.github_app_installation_id == "67890"


def test_github_app_config_defaults(tmp_path):
    """Test default GitHub App configuration when not specified."""
    config_without_app_section = """
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
"""
    
    cfg_path = tmp_path / 'issue_suite.config.yaml'
    cfg_path.write_text(config_without_app_section)
    
    cfg = load_config(cfg_path)
    
    # Verify default GitHub App settings
    assert cfg.github_app_enabled is False
    assert cfg.github_app_id is None
    assert cfg.github_app_private_key_path is None
    assert cfg.github_app_installation_id is None


def test_github_app_with_existing_private_key(monkeypatch, tmp_path):
    """Test GitHub App integration with an actual private key file."""
    # Create a dummy private key file
    key_path = tmp_path / 'test-key.pem'
    key_path.write_text("""-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...
-----END PRIVATE KEY-----""")
    
    config_with_real_key = f"""
version: 1
source:
  file: ISSUES.md
github:
  app:
    enabled: true
    app_id: "12345"
    private_key_path: "{key_path}"
    installation_id: "67890"
defaults:
  inject_labels: []
  ensure_milestones: []
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
output: {{}}
behavior: {{}}
ai: {{}}
logging:
  json_enabled: false
  level: INFO
"""
    
    cfg_path = tmp_path / 'issue_suite.config.yaml'
    (tmp_path / 'ISSUES.md').write_text(ISSUES)
    cfg_path.write_text(config_with_real_key)
    
    # Set mock mode
    monkeypatch.setenv('ISSUES_SUITE_MOCK', '1')
    
    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)
    
    # Verify the private key path is correctly loaded
    assert cfg.github_app_private_key_path == str(key_path)
    assert suite._github_app_config.private_key_path == str(key_path)
    
    # In mock mode, authentication should work
    summary = suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)
    assert summary['totals']['specs'] == 1


def test_github_app_error_handling(monkeypatch, tmp_path, capsys):
    """Test error handling when GitHub App setup fails."""
    # Config with invalid key path
    config_with_invalid_key = """
version: 1
source:
  file: ISSUES.md
github:
  app:
    enabled: true
    app_id: "12345"
    private_key_path: "/nonexistent/key.pem"
    installation_id: "67890"
defaults:
  inject_labels: []
  ensure_milestones: []
  ensure_labels_enabled: false
  ensure_milestones_enabled: false
output: {}
behavior: {}
ai: {}
logging:
  json_enabled: true
  level: INFO
"""
    
    cfg_path = tmp_path / 'issue_suite.config.yaml'
    (tmp_path / 'ISSUES.md').write_text(ISSUES)
    cfg_path.write_text(config_with_invalid_key)
    
    # Don't set mock mode to test real error handling
    
    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)
    
    # Should handle GitHub App setup errors gracefully
    # The sync should still work (falling back to regular auth)
    summary = suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)
    assert summary['totals']['specs'] == 1
    
    # Check for error logs
    captured = capsys.readouterr() 
    output = captured.out + captured.err
    # In mock mode OFF, may get authentication errors, but shouldn't crash