# Contributing to MedAxis Platform

Thank you for taking the time to contribute.

## Getting Started

1. Fork the repository and clone your fork.
2. Copy the environment file and configure it:
   ```bash
   make env   # or: cp .env.example .env
   ```
3. Start all services:
   ```bash
   make up
   ```
4. Seed demo data:
   ```bash
   make seed
   ```

## Development Workflow

### Branching

| Branch type | Pattern | Example |
|---|---|---|
| Feature | `feat/<short-description>` | `feat/expiry-alerts` |
| Bug fix | `fix/<short-description>` | `fix/invoice-race-condition` |
| Chore / refactor | `chore/<short-description>` | `chore/update-deps` |

Always branch off `main` and target `main` in your PR.

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <short summary>

[optional body]
```

Examples:
```
feat(inventory): add FEFO deduction for controlled substances
fix(billing): resolve race condition on concurrent invoice confirm
chore(ci): pin ruff to 0.4.4
```

### Code Style

- Python code is linted with [ruff](https://github.com/astral-sh/ruff). Run `make lint` before pushing.
- Each service follows the same layered structure: `routes.py → service.py → models.py`.
- Do not add cross-service database queries. Services communicate only through HTTP APIs.
- All new endpoints must have a Pydantic schema (`schemas.py`) for request and response.

## Running Tests

```bash
make test          # all tests
make test-cov      # with HTML coverage report (htmlcov/index.html)
make lint          # ruff lint check
```

Tests use SQLite in-memory databases — no running Docker containers needed.

## Pull Request Checklist

- [ ] `make lint` passes with no errors
- [ ] `make test` passes with no failures
- [ ] New endpoints have Pydantic schemas and are covered by at least one test
- [ ] No secrets, `.env` files, or TLS certificates committed
- [ ] PR description explains *why* the change is needed

## Security

If you discover a security vulnerability, **do not open a public issue**. Instead, email the maintainers directly. See [SECURITY.md](SECURITY.md) if present, or use the GitHub private vulnerability reporting feature.

## Questions

Open a [GitHub Discussion](../../discussions) for questions or design proposals before writing code.
