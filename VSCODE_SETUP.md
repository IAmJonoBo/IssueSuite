# VS Code & GitHub Copilot Setup Guide

This guide will help you set up IssueSuite for optimal integration with VS Code, GitHub Copilot, and online development environments.

## Quick Setup

1. **Install IssueSuite with VS Code extensions:**
   ```bash
   pip install issuesuite[vscode]
   ```

2. **Setup authentication and VS Code integration:**
   ```bash
   issuesuite setup --create-env --check-auth --vscode
   ```

3. **Open VS Code in your project directory:**
   ```bash
   code .
   ```

## Authentication Setup

IssueSuite supports multiple authentication methods optimized for different environments:

### Option 1: Environment Variables (Recommended for Online/Cloud)

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

### Option 2: VS Code Secrets (GitHub Codespaces/Online)

In VS Code or GitHub Codespaces, the `GITHUB_TOKEN` is often automatically available. IssueSuite will detect and use it automatically.

### Option 3: GitHub CLI (Local Development)

```bash
gh auth login
```

IssueSuite will automatically use your GitHub CLI authentication.

## VS Code Integration Features

The VS Code integration provides:

### 1. **Tasks** (Ctrl+Shift+P → "Tasks: Run Task")
- **IssueSuite: Dry-run Sync** - Test your changes safely
- **IssueSuite: Full Sync** - Apply changes to GitHub
- **IssueSuite: Export** - Generate JSON exports
- **IssueSuite: Summary** - Quick roadmap overview
- **IssueSuite: Validate** - Check configuration and issues

### 2. **Debug Configurations** (F5)
- Debug sync operations with breakpoints
- Step through issue processing logic
- Inspect configuration and authentication

### 3. **IntelliSense & Validation**
- YAML schema validation for `issue_suite.config.yaml`
- JSON schema validation for exports and summaries
- Markdown syntax highlighting for `ISSUES.md`

## GitHub Copilot Optimization

IssueSuite is optimized for GitHub Copilot workflows:

### 1. **Structured Logging**
Enable JSON logging for better Copilot understanding:
```yaml
# issue_suite.config.yaml
logging:
  json_enabled: true
  level: INFO
```

### 2. **Performance Benchmarking**
Enable performance monitoring to identify optimization opportunities:
```yaml
# issue_suite.config.yaml
performance:
  benchmarking: true
```

### 3. **Copilot-Friendly Configuration**
Use clear, descriptive field mappings that Copilot can understand:
```yaml
# issue_suite.config.yaml
github:
  project:
    enable: true
    number: 123
    field_mappings:
      labels: "Status"          # Maps issue labels to Status field
      milestone: "Priority"     # Maps milestone to Priority field
```

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

### Sample Configuration for VS Code/Copilot
```yaml
version: 1
source:
  file: ISSUES.md
  id_pattern: "^[0-9]{3}$"
  milestone_required: true

github:
  project:
    enable: true
    number: $PROJECT_NUMBER  # Resolves from environment
    field_mappings:
      labels: "Status"
      milestone: "Priority"
  app:
    enabled: true
    app_id: $GITHUB_APP_ID
    private_key_path: $GITHUB_APP_PRIVATE_KEY
    installation_id: $GITHUB_APP_INSTALLATION_ID

defaults:
  inject_labels: [meta:roadmap, managed:declarative]

logging:
  json_enabled: true
  level: INFO

performance:
  benchmarking: true

concurrency:
  enabled: true
  max_workers: 4

environment:
  enabled: true
  load_dotenv: true
```

## Workflows

### Daily Development Workflow
1. Edit `ISSUES.md` with your roadmap
2. Press `Ctrl+Shift+P` → "Tasks: Run Task" → "IssueSuite: Dry-run Sync"
3. Review changes in VS Code terminal
4. Run "IssueSuite: Full Sync" to apply changes

### GitHub Copilot Assistance
- Ask Copilot to help write issue descriptions
- Use Copilot to generate milestone patterns
- Let Copilot suggest configuration improvements

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
1. Ensure IssueSuite is installed: `pip install issuesuite[vscode]`
2. Reload VS Code window: `Ctrl+Shift+P` → "Developer: Reload Window"
3. Check Python interpreter: `Ctrl+Shift+P` → "Python: Select Interpreter"

### Environment Variables Not Loading
1. Check `.env` file exists and has correct format
2. Ensure `python-dotenv` is installed: `pip install python-dotenv`
3. Verify environment configuration in `issue_suite.config.yaml`

## Advanced Configuration

### Multiple Environments
Use different `.env` files for different environments:
```yaml
# issue_suite.config.yaml
environment:
  enabled: true
  load_dotenv: true
  dotenv_path: ".env.production"  # or .env.development
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