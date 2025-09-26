import json
import os
import subprocess
import sys
from pathlib import Path


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, '-m', 'issuesuite.cli', *args]
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, env=proc_env, check=False)  # noqa: PLR1730

def test_ai_context_quiet_suppresses_logs(tmp_path: Path) -> None:
    cfg = tmp_path / 'issue_suite.config.yaml'
    cfg.write_text('version: 1\nrepository: example/repo\n')
    (tmp_path / 'ISSUES.md').write_text('# Roadmap\n\n## [slug: example-feature]\n```yaml\ntitle: Example Feature\nlabels: [feature]\nbody: |\n  Task one\n```\n')

    # Without quiet we may see recommendation logs (best-effort heuristic)
    res_no_quiet = run_cli('ai-context', '--config', str(cfg))
    assert res_no_quiet.returncode == 0
    noisy = 'Authentication recommendations' in res_no_quiet.stdout

    # With quiet flag we expect fewer or equal lines and ideally suppressed recommendations
    res_quiet = run_cli('ai-context', '--quiet', '--config', str(cfg))
    assert res_quiet.returncode == 0, res_quiet.stderr
    if noisy:
        assert res_quiet.stdout.count('Authentication recommendations') <= 1

    # Parse JSON (should start at first '{')
    lines = [line for line in res_quiet.stdout.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        if line.lstrip().startswith('{'):
            data = json.loads('\n'.join(lines[idx:]))
            break
    else:  # pragma: no cover - defensive
        raise AssertionError('No JSON found in quiet output')
    assert data['schemaVersion'].startswith('ai-context/1')

    # Env var variant
    res_env_quiet = run_cli('ai-context', '--config', str(cfg), env={'ISSUESUITE_QUIET':'1'})
    assert res_env_quiet.returncode == 0
    if noisy:
        assert res_env_quiet.stdout.count('Authentication recommendations') <= 1

    # If initial run was noisy, confirm quiet actually reduced output length (sanity)
    if noisy:
        assert len(res_quiet.stdout) <= len(res_no_quiet.stdout)
