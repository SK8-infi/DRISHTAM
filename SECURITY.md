# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅        |

## Reporting a Vulnerability

If you discover a security vulnerability in DRISHTAM, please report it
responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities.
2. Email: **shivansh.katiyar1712@gmail.com**
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will acknowledge receipt within **48 hours** and provide a fix or
mitigation plan within **7 days**.

## Security Measures

### API Security
- **CORS**: Restricted to explicit allowed origins (no wildcard)
- **Rate Limiting**: 120 requests/minute per IP (configurable)
- **Security Headers**: CSP, HSTS, X-Frame-Options, X-Content-Type-Options,
  X-XSS-Protection, Referrer-Policy, Permissions-Policy
- **Request Tracing**: X-Request-ID on every response
- **Input Validation**: Pydantic models with field-level bounds on all endpoints
- **ReDoS Prevention**: User input escaped before regex operations
- **Body Size Limit**: 10 MB max request body
- **Error Handling**: Stack traces suppressed in production
- **Docs Disabled**: OpenAPI/Swagger/Redoc disabled in production

### Infrastructure
- **Docker**: Non-root user, read-only filesystem, no-new-privileges
- **Dependencies**: All versions pinned exactly (`==`) for reproducible builds
- **Secrets**: No hardcoded secrets; all via environment variables
- **`.dockerignore`**: Prevents `.env`, `.git`, data files from entering images
- **GitHub Push Protection**: Enabled, blocks commits containing secrets

### Frontend
- **CSP**: Script, style, image, and connect sources restricted
- **HSTS**: Enforced with preload
- **X-Frame-Options**: DENY (prevents clickjacking)
- **No `dangerouslySetInnerHTML`**: No XSS vectors in React components

### Data Privacy
- Violation data is **pre-anonymized** (anonymized CSV filenames in config)
- No PII (names, addresses, license plates) stored or served
- Device IDs are only used for aggregate counts, never exposed via API
- Geographic coordinates are public road locations, not personal addresses
