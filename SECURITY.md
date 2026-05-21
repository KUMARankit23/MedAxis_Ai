# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| main branch | Yes |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Use [GitHub's private vulnerability reporting](../../security/advisories/new) feature, or email the maintainers directly.

Please include:
- A description of the vulnerability and its potential impact
- The affected service(s) and version/commit
- Steps to reproduce
- Any suggested fix (optional)

We will acknowledge receipt within 48 hours and aim to release a patch within 7 days for critical issues.

## Security Design Notes

- All inter-service communication is internal to the Docker network — only nginx exposes ports 80/443
- JWT tokens are validated at both the API gateway and within each service
- SQL injection is prevented by SQLAlchemy ORM parameterized queries throughout
- The conversational AI agent only generates `SELECT` statements — write operations are blocked at parse time
- Redis (production) requires password authentication
- pgAdmin and Prometheus are bound to `127.0.0.1` only in production
- TLS certificates are excluded from version control via `.gitignore`
