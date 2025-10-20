# Contributing to Trading System Engine

Thank you for contributing to the Trading System Engine! This document provides guidelines for development workflow, code standards, and pull request process.

---

## Table of Contents

- [Development Environment](#development-environment)
- [Workflow](#workflow)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Git Conventions](#git-conventions)

---

## Development Environment

### Prerequisites

- **Python**: 3.13+
- **Conda**: For environment management
- **PostgreSQL**: 15+ (for integration tests)
- **Redis**: 7+ (for service discovery and caching)
- **Git**: With git quality standards hooks installed

### Environment Setup

```bash
# Activate conda environment
conda activate py313_trading_ecosystem_dev

# Install dependencies
pip install -e .

# Install development dependencies
pip install -e ".[dev]"

# Install git hooks
./.claude/plugins/git_quality_standards/scripts/install-git-hooks-enhanced.sh -y -y -y
```

---

## Workflow

### 1. Branch Creation

**Always** create a feature branch from `main`:

```bash
# Update main
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/epic-TSE-0001-engine-your-feature

# OR for bug fixes
git checkout -b fix/epic-TSE-0001-engine-bug-description
```

**Branch Naming Convention**: `type/epic-XXX-9999-milestone-description`

**Valid types**:
- `feature/` - New functionality
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `test/` - Test additions/updates
- `docs/` - Documentation changes
- `chore/` - Maintenance tasks

### 2. Development

**Before committing**:
1. Run tests: `pytest tests/ -v`
2. Run linting: `ruff check src/ tests/`
3. Run type checking: `mypy src/`
4. Update TODO.md if working on milestone tasks

### 3. Committing Changes

**Pre-commit checklist** (enforced by hooks):
- [ ] On feature branch (NOT main/master)
- [ ] Branch name follows convention
- [ ] All tests pass
- [ ] Code is linted and formatted
- [ ] TODO.md updated (if applicable)

**Commit message format**:

```bash
git commit -m "type(epic-XXX-9999/milestone): short description

- Detailed change 1
- Detailed change 2
- Detailed change 3

Milestone: Milestone Name
Behavior: Specific behavior implemented
Task: Specific task from TODO.md"
```

### 4. Creating Pull Requests

**Option 1: Automated (Recommended)**

```bash
# 1. Create PR documentation
cat > docs/prs/feature-epic-TSE-0001-your-feature.md <<EOF
# feat(epic-TSE-0001/milestone): Your feature title

## Summary
What changed and why...
EOF

# 2. Use automated PR creation
./.claude/plugins/git_quality_standards/scripts/create-pr.sh
```

**Option 2: Manual**

```bash
# 1. Push branch
git push -u origin feature/epic-TSE-0001-your-feature

# 2. Create PR via GitHub or gh CLI
gh pr create --fill
```

---

## Code Standards

### Python Style

**Follow**:
- PEP 8 style guide
- Type hints for all functions
- Docstrings for public APIs
- Clean Architecture principles

**Tools**:
- **Formatter**: `ruff format`
- **Linter**: `ruff check`
- **Type Checker**: `mypy`

**Example**:

```python
from typing import Protocol

class OrderService(Protocol):
    """Service interface for order management."""

    async def place_order(self, order: Order) -> OrderResult:
        """Place a new order.

        Args:
            order: Order entity to place

        Returns:
            OrderResult with execution details

        Raises:
            ValidationError: If order validation fails
            ExecutionError: If order execution fails
        """
        ...
```

### Clean Architecture Rules

1. **Domain Layer**: NO external dependencies
   - Pure Python entities and interfaces
   - Business logic only
   - No database, HTTP, or framework imports

2. **Application Layer**: Depends on domain
   - Use cases and application services
   - Orchestrates domain logic
   - Depends only on domain interfaces

3. **Infrastructure Layer**: Depends on domain/application
   - Implements domain interfaces
   - PostgreSQL, Redis, HTTP implementations
   - Framework-specific code

4. **Dependency Direction**: Always inward
   ```
   Infrastructure → Application → Domain
   ✅ Allowed: Outer layers import inner layers
   ❌ Forbidden: Inner layers import outer layers
   ```

### File Organization

```
src/trading_system_engine/
├── domain/
│   ├── entities/          # Domain models
│   ├── ports/             # Repository/service interfaces
│   └── exceptions.py      # Domain exceptions
├── application/
│   └── services/          # Application services
├── infrastructure/
│   ├── repositories/      # PostgreSQL implementations
│   ├── adapters/          # Data adapters
│   └── observability/     # Metrics, logging
└── presentation/
    └── api/               # FastAPI routes
```

---

## Testing Requirements

### Coverage Requirements

- **Minimum**: 80% overall coverage
- **Domain Layer**: 100% coverage (critical business logic)
- **Application Layer**: 90% coverage
- **Infrastructure**: 85% coverage
- **Integration tests**: Required for all repository implementations

### Test Structure

```
tests/
├── unit/
│   ├── domain/          # Pure unit tests, no mocks needed
│   ├── application/     # Application service tests with mocks
│   └── infrastructure/  # Unit tests with mocks
└── integration/
    ├── repositories/    # Real PostgreSQL tests
    └── api/             # API integration tests
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests (requires PostgreSQL/Redis)
pytest tests/integration/ -v

# With coverage
pytest tests/ -v --cov=src/trading_system_engine --cov-report=term-missing

# Coverage threshold check
pytest tests/ --cov=src/trading_system_engine --cov-fail-under=80
```

### Test Naming Convention

```python
# Unit test
def test_should_place_order_when_valid_data():
    """Test that service places order with valid data."""
    # Arrange
    service = OrderService()
    order = Order(id="1", symbol="AAPL")

    # Act
    result = await service.place_order(order)

    # Assert
    assert result.status == OrderStatus.PLACED
```

---

## Pull Request Process

### 1. Pre-PR Checklist

- [ ] All tests pass: `pytest tests/ -v`
- [ ] Linting passes: `ruff check src/ tests/`
- [ ] Type checking passes: `mypy src/`
- [ ] Coverage maintained: `pytest tests/ --cov-fail-under=80`
- [ ] TODO.md updated
- [ ] PR documentation created in `docs/prs/`
- [ ] Branch up to date with main

### 2. PR Documentation Requirements

**File**: `docs/prs/{branch-name}.md`

**Required sections**:
- Summary (What, Why, Impact)
- Epic/Milestone Reference
- Quality Assurance (tests, coverage, manual testing)
- Security & Dependencies
- Deployment (env vars, migrations)
- Breaking Changes (if any)

**Template**: See `.github/pull_request_template.md`

### 3. PR Review Process

1. **Automated checks** (GitHub Actions):
   - Branch naming validation
   - PR documentation validation
   - Linting and type checking
   - Test suite execution
   - Coverage threshold

2. **Code review** (human):
   - Clean Architecture compliance
   - Test coverage adequacy
   - Code clarity and maintainability
   - Security considerations

3. **Approval and merge**:
   - Requires 1 approval (when team grows)
   - All checks must pass
   - Squash and merge (preserves clean history)

---

## Git Conventions

### Branch Protection

- ❌ **Never commit directly to `main`**
- ❌ **Never push to `main` without PR**
- ✅ **Always use feature branches**
- ✅ **Always create PR for review**

**Pre-push hook enforces**:
1. Not on protected branch (main/master)
2. Branch name follows convention
3. PR documentation exists
4. PR has required sections
5. TODO.md updated (when applicable)
6. Markdown files lint correctly
7. Repository structure validation passes

### Commit Messages

**Format**: `type(epic-XXX-9999/milestone): description`

**Good examples**:

```
feat(epic-TSE-0001/engine): add order placement service
fix(epic-TSE-0001/engine): resolve race condition in order matching
test(epic-TSE-0001/engine): add integration tests for order lifecycle
docs(epic-TSE-0001/engine): update README with gRPC examples
```

**Bad examples**:

```
❌ fix bug
❌ update code
❌ changes
❌ WIP
```

### PR Titles

**Format**: Same as commit messages

**Example**: `feat(epic-TSE-0001/engine): implement risk monitoring service`

---

## Quality Gates

### Automated Validation

**Pre-push** (local):
- Branch naming validation
- PR documentation exists
- TODO.md updated
- Markdown linting
- Repository structure validation

**GitHub Actions** (remote):
- PR title validation
- Linting (ruff)
- Type checking (mypy)
- Test suite execution
- Coverage threshold (80%)

### Manual Review

**Code reviewer checks**:
- [ ] Clean Architecture compliance
- [ ] Appropriate abstraction level
- [ ] Test coverage adequate
- [ ] Error handling robust
- [ ] Documentation clear
- [ ] No security vulnerabilities
- [ ] Performance implications considered

---

## Getting Help

### Resources

- **Project Plan**: See `../project-plan/CLAUDE.md`
- **TODO**: See `TODO.md` for current tasks
- **Plugin README**: See `.claude/plugins/git_quality_standards/README.md`
- **Architecture**: See `../project-plan/.claude/` for Clean Architecture patterns

### Common Issues

**Pre-push hook fails**:

```bash
# Reinstall hooks
./.claude/plugins/git_quality_standards/scripts/install-git-hooks-enhanced.sh -y -y -y
```

**Tests fail locally**:

```bash
# Ensure PostgreSQL/Redis running
docker-compose up -d postgres redis

# Ensure correct Python environment
conda activate py313_trading_ecosystem_dev
```

**Linting errors**:

```bash
# Auto-fix most issues
ruff check --fix src/ tests/
ruff format src/ tests/
```

---

## Project Context

This repository is part of the **Trading Ecosystem** multi-component project:
- Epic: TSE-0001 - Trading System Engine Foundation
- Project: Trading Ecosystem Simulation
- Architecture: Clean Architecture with microservices

**Related repositories**: See `../project-plan/REPOSITORIES.md`

---

**Thank you for contributing to the Trading System Engine!**

Questions? See project documentation in `../project-plan/` or check TODO.md for current priorities.
