# Changelog

All notable changes to IssueSuite are documented here. A legacy section for the previous
"StratMaster" project follows after the `--- Legacy (StratMaster) ---` marker.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_No unreleased changes yet._

## [0.1.5] - 2025-09-26

### Added
- 0.1.1: Optional preflight auto-create flags (`ensure_labels_enabled`, `ensure_milestones_enabled`), parser equivalence & project stub tests.
- 0.1.2: Debug logging via `ISSUESUITE_DEBUG=1` environment variable.
- 0.1.3: Native argparse CLI (`issuesuite`), JSON schema exports, initial CLI tests, packaging workflows.
- 0.1.4: Mock mode (`ISSUES_SUITE_MOCK=1`) skipping all GitHub CLI calls while printing `MOCK` actions.

### Fixed
- Snapshot-based VS Code secret detection to avoid false positives.
- Module-level `load_dotenv` shim for reliable patching in tests.
- Gated GitHub CLI calls during preflight when label/milestone ensures are disabled (prevents unnecessary subprocess usage in dry-run scenarios).

### Internal
- Modernized type hints in env auth module & minor sync gating adjustments.
- Refactored `sync` method to helper functions (maintains behavior, lowers complexity).

--- Legacy (StratMaster) ---

### Enhanced (Legacy)

- **Analytics Router** with new HEART and product forecasting endpoints
- **Strategy Generation** with industry-specific template selection
- **Template Management** with metadata, KPIs, and validation
- **Documentation Architecture** with comprehensive quality gates
- **Link Checking Automation** with broken link detection
- **Accessibility Validation** with WCAG 2.2 AA compliance checking

### Technical Improvements

- Feature flags for gradual rollout: `ENABLE_PREDICTIVE_ANALYTICS`, `ENABLE_EVENT_STREAMING`, `ENABLE_INDUSTRY_TEMPLATES`
- Backward compatibility maintained through fallback implementations
- Comprehensive error handling and graceful degradation
- Performance optimizations with caching and async processing
- Enhanced observability with event-driven metrics collection

### Added

- Multi-agent debate system with specialized AI agents
- Comprehensive security model with zero-trust architecture
- Infrastructure setup guides for local and production deployment
- Operations playbook for day-to-day system management
- FAQ covering common questions and troubleshooting
- Complete YAML configuration reference documentation
- Quality gate validation with automated testing
- Evidence grading using GRADE framework

### Changed

- Restructured documentation using Diátaxis framework
- Enhanced API documentation with OpenAPI 3.1 integration
- Improved configuration management with hierarchical YAML files
- Updated security practices to enterprise standards

### Fixed

- Documentation links and cross-references
- Configuration validation and error handling
- API endpoint consistency and error responses

## [0.1.0] - 2024-01-15

### Added

- Initial release of StratMaster platform
- FastAPI-based REST API with comprehensive endpoints
- Multi-database architecture (PostgreSQL, Qdrant, OpenSearch, NebulaGraph)
- MCP (Model Context Protocol) microservices architecture
- Temporal workflow orchestration for complex multi-agent processes  
- Comprehensive observability with Prometheus, Grafana, and OpenTelemetry
- Multi-tenant isolation with row-level security
- Authentication and authorization system with JWT and OAuth2
- Container-first deployment with Docker and Kubernetes
- Helm charts for production deployment
- CI/CD pipelines with GitHub Actions

### Documentation

- Complete API reference with interactive Swagger UI and ReDoc
- Developer quick start guide and tutorials  
- How-to guides for development setup, deployment, and troubleshooting
- Architecture overview and system design documentation
- Security model and compliance framework
- Configuration reference for all system components

### Infrastructure

- Local development environment with Docker Compose
- Kubernetes manifests for production deployment
- ArgoCD GitOps configuration
- Monitoring and alerting stack with Prometheus and Grafana
- Centralized logging with structured JSON logs
- Backup and disaster recovery procedures

### Security

- End-to-end encryption with TLS 1.3
- Data encryption at rest with AES-256-GCM
- Comprehensive audit logging
- Network policies and security hardening
- Vulnerability scanning in CI/CD pipeline
- OWASP security best practices implementation

### Quality Assurance

- Comprehensive test suite with unit, integration, and e2e tests
- Code quality tools: Ruff, mypy, bandit, pre-commit hooks
- Documentation validation with markdownlint, cspell, Vale, lychee
- Performance benchmarking and quality gates
- Automated dependency updates with Renovate

### Performance

- Horizontal pod autoscaling based on CPU and memory
- Connection pooling and query optimization
- Multi-level caching (Redis, application, CDN)
- Vector search optimization with Qdrant
- Database read replicas for improved performance

## [0.0.1] - 2023-12-01

### Added

- Initial project structure and repository setup
- Basic FastAPI application scaffold
- Docker development environment
- Initial documentation framework
- GitHub Actions CI/CD pipeline setup
- Basic security scanning and code quality tools

---

## Release Notes

### Version 0.1.0 Release Notes

**Release Date**: January 15, 2024

**What's New**:

🚀 **Multi-Agent Debate System**: Revolutionary AI collaboration where specialized agents (Research, Analysis, Critic, Evidence, Synthesis) work together to produce high-quality, evidence-based strategic insights through structured argumentation.

🏗️ **Enterprise-Ready Architecture**: Built on microservices architecture using Model Context Protocol (MCP) for optimal scalability and maintainability. Supports horizontal scaling from single-node development to multi-region production deployments.

🔒 **Zero-Trust Security**: Comprehensive security model with end-to-end encryption, multi-factor authentication, audit logging, and compliance framework supporting GDPR, SOC 2, and ISO 27001.

📊 **Advanced Analytics**: Real-time performance monitoring, quality gates validation, and comprehensive observability stack with Prometheus, Grafana, and OpenTelemetry integration.

🌐 **Multi-Tenant SaaS Ready**: Native multi-tenancy with strict data isolation, custom domains, and tenant-specific configurations for enterprise deployments.

**Technical Highlights**:

- **Performance**: Sub-second API response times with 99.9% uptime SLA
- **Scalability**: Handles 10,000+ concurrent users with auto-scaling
- **Quality**: 90%+ test coverage with automated quality gates
- **Security**: Zero critical vulnerabilities with automated scanning
- **Documentation**: 100% API coverage with interactive documentation

**Breaking Changes**: None (initial release)

**Migration Guide**: Not applicable (initial release)

**Known Issues**:

- Vector search performance may degrade with very large document collections (>1M documents)
- Real-time notifications require WebSocket connection, fallback to polling available
- Some AI providers may have rate limits that affect high-volume usage

**Deprecations**: None

**Coming in v0.2.0**:

- Real-time collaboration features
- Advanced visualization capabilities  
- Enhanced mobile support
- Additional AI provider integrations
- Performance optimizations for large-scale deployments

---

## Contributing to the Changelog

When contributing changes, please follow these guidelines:

1. **Add entries to [Unreleased]** section during development
2. **Use standard categories**: Added, Changed, Deprecated, Removed, Fixed, Security
3. **Write clear, descriptive entries** that explain the impact to users
4. **Link to relevant issues/PRs** where appropriate
5. **Move items to versioned section** when releasing

### Entry Format

```markdown
### Added
- New feature description with impact explanation [#123](link-to-issue)

### Changed  
- Changed feature description explaining what and why [#456](link-to-pr)

### Fixed
- Bug fix description with impact [#789](link-to-issue)
```

### Version Numbering

StratMaster follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions  
- **PATCH** version for backwards-compatible bug fixes

Examples:

- `0.1.0 → 0.1.1`: Bug fixes only
- `0.1.1 → 0.2.0`: New features, backwards compatible
- `0.2.0 → 1.0.0`: Breaking API changes or major milestone

---

For detailed technical changes, see:

- [GitHub Releases](https://github.com/IAmJonoBo/StratMaster/releases)
- [Commit History](https://github.com/IAmJonoBo/StratMaster/commits/main)
- [Pull Requests](https://github.com/IAmJonoBo/StratMaster/pulls?q=is%3Apr+is%3Aclosed)
