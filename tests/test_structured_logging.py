import json

from issuesuite import IssueSuite, load_config
from issuesuite.logging import StructuredLogger, configure_logging

CONFIG_WITH_JSON_LOGGING = """
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
  json_enabled: true
  level: INFO
"""

CONFIG_WITHOUT_JSON_LOGGING = """
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
  level: DEBUG
"""

ISSUES = """## [slug: demo-issue]
```yaml
title: Demo Issue
labels: [test-label]
body: |
    Body text
```
"""


def test_structured_logger_json_format(capsys):
    """Test that structured logger produces JSON output when configured."""
    logger = StructuredLogger(name='test', json_logging=True, level='INFO')
    logger.log_operation('test_operation', param1='value1', param2=42)
    
    captured = capsys.readouterr()
    log_lines = [line for line in captured.out.strip().split('\n') if line]
    
    assert len(log_lines) == 1
    log_data = json.loads(log_lines[0])
    
    assert log_data['level'] == 'INFO'
    assert log_data['operation'] == 'test_operation'
    assert log_data['param1'] == 'value1'
    assert log_data['param2'] == 42
    assert 'timestamp' in log_data


def test_structured_logger_regular_format(capsys):
    """Test that structured logger produces regular text output when JSON disabled."""
    logger = StructuredLogger(name='test', json_logging=False, level='INFO')
    logger.log_operation('test_operation', param1='value1')
    
    captured = capsys.readouterr()
    assert 'Operation: test_operation' in captured.out
    assert 'test' in captured.out
    assert 'INFO' in captured.out


def test_structured_logger_issue_actions(capsys):
    """Test structured logging of issue actions."""
    logger = StructuredLogger(name='test', json_logging=True, level='INFO')
    logger.log_issue_action('create', 'EXT001', issue_number=123, dry_run=True)
    
    captured = capsys.readouterr()
    log_data = json.loads(captured.out.strip())
    
    assert log_data['operation'] == 'issue_create'
    assert log_data['external_id'] == 'EXT001'
    assert log_data['issue_number'] == 123
    assert log_data['dry_run'] is True


def test_structured_logger_performance_timing(capsys):
    """Test performance timing logging."""
    logger = StructuredLogger(name='test', json_logging=True, level='INFO')
    logger.log_performance('sync_operation', 1234.56, spec_count=10)
    
    captured = capsys.readouterr()
    log_data = json.loads(captured.out.strip())
    
    assert log_data['operation'] == 'sync_operation'
    assert log_data['duration_ms'] == 1234.56
    assert log_data['spec_count'] == 10


def test_timed_operation_context_manager(capsys):
    """Test timed operation context manager."""
    logger = StructuredLogger(name='test', json_logging=True, level='INFO')
    
    with logger.timed_operation('test_sync', dry_run=True):
        pass  # Simulate work
    
    captured = capsys.readouterr()
    log_lines = [line for line in captured.out.strip().split('\n') if line]
    
    # Should have start and performance log entries
    assert len(log_lines) >= 2
    
    start_log = json.loads(log_lines[0])
    assert start_log['operation'] == 'test_sync_start'
    assert start_log['dry_run'] is True
    
    perf_log = json.loads(log_lines[1])
    assert perf_log['operation'] == 'test_sync'
    assert 'duration_ms' in perf_log


def test_issue_suite_with_json_logging_enabled(monkeypatch, tmp_path, capsys):
    """Test IssueSuite with JSON logging enabled."""
    cfg_path = tmp_path / 'issue_suite.config.yaml'
    (tmp_path / 'ISSUES.md').write_text(ISSUES)
    cfg_path.write_text(CONFIG_WITH_JSON_LOGGING)
    
    # Set mock mode to avoid GitHub CLI calls
    monkeypatch.setenv('ISSUES_SUITE_MOCK', '1')
    
    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)
    
    # Run sync to generate structured logs
    suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)
    
    captured = capsys.readouterr()
    
    # Should contain JSON formatted logs
    json_log_lines = []
    for line in captured.out.split('\n'):
        if line.strip() and line.strip().startswith('{'):
            try:
                json_log_lines.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                pass
    
    # Should have at least some structured log entries
    assert len(json_log_lines) > 0
    
    # Check for expected operations in logs
    operations = [log.get('operation') for log in json_log_lines]
    assert 'sync_start' in operations or any('sync' in op for op in operations if op)


def test_issue_suite_with_json_logging_disabled(monkeypatch, tmp_path, capsys):
    """Test IssueSuite with JSON logging disabled."""
    cfg_path = tmp_path / 'issue_suite.config.yaml'
    (tmp_path / 'ISSUES.md').write_text(ISSUES)
    cfg_path.write_text(CONFIG_WITHOUT_JSON_LOGGING)
    
    # Set mock mode to avoid GitHub CLI calls
    monkeypatch.setenv('ISSUES_SUITE_MOCK', '1')
    
    cfg = load_config(cfg_path)
    suite = IssueSuite(cfg)
    
    # Run sync to generate logs
    suite.sync(dry_run=True, update=False, respect_status=False, preflight=False)
    
    captured = capsys.readouterr()
    
    # Should contain regular text logs, not JSON
    lines = captured.out.split('\n')
    json_lines = 0
    for line in lines:
        if line.strip() and line.strip().startswith('{'):
            try:
                json.loads(line.strip())
                json_lines += 1
            except json.JSONDecodeError:
                pass
    
    # Should have very few (or no) JSON lines since JSON logging is disabled
    assert json_lines < len([l for l in lines if 'issuesuite' in l])


def test_configure_logging():
    """Test global logging configuration."""
    logger1 = configure_logging(json_logging=True, level='DEBUG')
    logger2 = configure_logging(json_logging=False, level='INFO')
    
    # Second call should return different logger with new config
    assert logger1 != logger2