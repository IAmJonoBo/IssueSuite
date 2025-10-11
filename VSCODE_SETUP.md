# VS Code & GitHub Copilot Setup Guide

This guide will help you set up IssueSuite for optimal integration with VS Code, GitHub Copilot, and online development environments.

## Quick Setup

1. Create a local virtual environment and install dev extras:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev,all]'
```

1. Setup authentication and optional VS Code integration files:

```bash
issuesuite setup --create-env --check-auth --vscode
```

> ℹ️  Re-run with `--force` (`issuesuite setup --vscode --force`) to refresh the shipped
> VS Code templates if you've customised or drifted from the defaults. JSON files are
> normalised automatically, so whitespace-only edits won't trigger drift warnings.

1. Open VS Code in your project directory:

```bash
code .
```

## Authentication Setup

IssueSuite supports multiple authentication methods optimized for different environments:

### Option 1: Environment Variables

Create a `.env` file in your project root:

```bash
issuesuite setup --create-env
```

Edit the `.env` file:

```env
# GitHub Personal Access Token
GITHUB_TOKEN=your_github_token_here

# Optional: GitHub App Configuration (for enhanced rate limits)
GITHUB_APP_ID=12345
GITHUB_APP_PRIVATE_KEY=path/to/private-key.pem
GITHUB_APP_INSTALLATION_ID=67890
```

After populating the file, run `issuesuite setup --check-auth` to confirm the credentials are detected.

### Option 2: VS Code/GitHub Codespaces secrets

In VS Code or GitHub Codespaces, the `GITHUB_TOKEN` is often automatically available. IssueSuite will detect and use it automatically.

### Option 3: GitHub CLI (local)

```bash
gh auth login
```

IssueSuite will automatically use your GitHub CLI authentication.

## VS Code Integration Features

The VS Code integration provides:

### 1. **Tasks** (Ctrl+Shift+P → "Tasks: Run Task")

- **IssueSuite: Validate** — Check configuration and specs before running heavier operations
- **IssueSuite: Dry-run Sync** — Test your changes safely with preflight checks and save both `issues_summary.json` and `issues_plan.json`
- **IssueSuite: Full Sync** — Apply changes to GitHub with preflight checks and emit fresh summary/plan artifacts
- **IssueSuite: Summary** — Quick roadmap overview
- **IssueSuite: Export** — Generate JSON exports
- **IssueSuite: Schema Bundle** — Persist export, summary, and AI context schemas (feeds IntelliSense)
- **IssueSuite: Projects Status** — Produce JSON + Markdown status artifacts from `Next_Steps.md`
- **IssueSuite: Security Audit (Offline)** — Run the dependency audit with offline-safe defaults and pip-audit fallbacks
- **IssueSuite: Agent Apply (dry-run)** — Apply `agent_updates.json` to `ISSUES.md` and run a dry-run sync (writes `issues_summary.json`)
- **IssueSuite: Agent Apply (apply)** — Apply `agent_updates.json` and perform a real sync to GitHub (writes `issues_summary.json`)
- **IssueSuite: Guided Setup** — Re-run the interactive checklist to confirm your workspace health
- You can also run the `agent-apply` command from the integrated terminal to apply Copilot/agent updates to `ISSUES.md` and optionally sync.

The plan JSON path is configurable via `output.plan_json` in `issue_suite.config.yaml`; the default task writes to `${workspaceFolder}/issues_plan.json`.

### 2. Debugging

- Use the built-in tasks and structured output; add print/log statements as needed.

### 3. IntelliSense & Validation

- YAML schema validation for `issue_suite.config.yaml` via `.vscode/issue_suite.config.schema.json`
- JSON schema validation for exports, summaries, and AI context once you run the Schema Bundle task
- Markdown syntax highlighting for `ISSUES.md`

## Copilot tips

- Use the provided VS Code tasks (Validate, Dry-run Sync, Full Sync, Export, Summary, Generate Schemas).
- For post-implementation updates, have Copilot produce a small JSON and run `issuesuite agent-apply --updates-json updates.json` to mark items complete and append summaries. A starter example is provided at `agent_updates.json`.
- Keep `ISSUES.md` in the canonical slug + YAML format (see README).

## Environment Detection

IssueSuite automatically detects your environment:

- **GitHub Codespaces**: Auto-configures authentication
- **VS Code Local**: Uses GitHub CLI or environment variables
- **CI/CD**: Uses `GITHUB_TOKEN` environment variable
- **Development**: Supports `.env` files and manual configuration

Check your environment:

```bash
issuesuite setup --check-auth
```

## Configuration for Online Usage

### Sample Configuration

```yaml
version: 1
source:
  file: ISSUES.md
  id_pattern: "^[a-z0-9][a-z0-9-_]*$"
  milestone_required: false

github:
  project:
    enable: true
    number: $PROJECT_NUMBER # Resolves from environment
    field_mappings:
      labels: "Status"
      milestone: "Priority"
  app:
    enabled: false

defaults:
  inject_labels: [meta:roadmap, managed:declarative]

behavior:
  truncate_body_diff: 80
```

## Workflows

### Daily Development Workflow

1. Edit `ISSUES.md` with your roadmap
1. Press `Ctrl+Shift+P` → "Tasks: Run Task" → "IssueSuite: Dry-run Sync"
1. Review changes in VS Code terminal
1. Run "IssueSuite: Full Sync" to apply changes

### GitHub Copilot Assistance

- Ask Copilot to help write issue descriptions.
- Use Copilot to generate milestone patterns.
- Let Copilot suggest configuration improvements.

### Performance Monitoring

- Review `performance_report.json` after sync operations
- Use benchmarking data to optimize large roadmaps
- Monitor memory and CPU usage for batch operations

## Troubleshooting

### Authentication Issues

```bash
issuesuite setup --check-auth
```

### VS Code Tasks Not Working

1. Ensure IssueSuite is installed: `pip install -e .[dev,all]`
1. Reload VS Code window: `Ctrl+Shift+P` → "Developer: Reload Window"
1. Check Python interpreter: `Ctrl+Shift+P` → "Python: Select Interpreter"

### Environment Variables Not Loading

1. Check `.env` file exists and has correct format
1. Ensure `python-dotenv` is installed: `pip install python-dotenv`
1. Verify environment configuration in `issue_suite.config.yaml`

## Advanced Configuration

### Multiple Environments

Use different `.env` files for different environments:

```yaml
# issue_suite.config.yaml
environment:
  enabled: true
  load_dotenv: true
  dotenv_path: ".env.production" # or .env.development
```

### Custom VS Code Settings

Add to `.vscode/settings.json`:

```json
{
  "issuesuite.autoSync": true,
  "issuesuite.showPerformanceMetrics": true,
  "terminal.integrated.env.linux": {
    "ISSUESUITE_DEBUG": "1"
  }
}
```

### GitHub Copilot Chat Integration

Use these prompts with GitHub Copilot Chat:

- "Help me optimize this ISSUES.md structure"
- "Suggest better milestone patterns for agile development"
- "Review my IssueSuite configuration for best practices"

## Best Practices

1. **Use descriptive issue titles** - Helps Copilot understand context
2. **Enable structured logging** - Better debugging and monitoring
3. **Use environment variables** - Secure and flexible configuration
4. **Enable performance benchmarking** - Monitor and optimize operations
5. **Leverage VS Code tasks** - Streamline your workflow
6. **Regular authentication checks** - Prevent sync failures

For more advanced configuration options, see the main [README.md](README.md).
