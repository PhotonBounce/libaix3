# Security Policy

## Supported Versions

The following versions of OpsBrief are currently supported with security updates:

| Version | Supported | Status |
|---------|-----------|--------|
| 1.0.x | ✅ Yes | Active support — latest stable |
| < 1.0.0 | ❌ No | Pre-release, no support |

We provide security patches for the latest stable release. Users should always run the most recent version.

---

## Reporting Vulnerabilities

If you discover a security vulnerability in OpsBrief, please report it responsibly.

**Email:** security@photon-bounce.com

**What to include:**
- A clear description of the vulnerability
- Steps to reproduce
- Potential impact and severity assessment
- Any suggested fixes or patches (optional but appreciated)

We aim to acknowledge receipt within 48 hours and provide a preliminary assessment within 7 days.

Please do not disclose the vulnerability publicly until we have had a reasonable opportunity to address it.

---

## Disclosure Policy

We follow a coordinated disclosure policy:

1. **Acknowledgment:** We acknowledge receipt of the report within 48 hours.
2. **Investigation:** We investigate and validate the vulnerability within 14 days.
3. **Remediation:** We develop and test a fix. For critical vulnerabilities, we aim to release a patch within 30 days.
4. **Public Disclosure:** We will publicly disclose the vulnerability after a fix is released, or after 90 days from the initial report, whichever comes first. We will credit the reporter (unless they wish to remain anonymous).

---

## Known Vulnerabilities

| CVE | Description | Status | Fixed In |
|-----|-------------|--------|----------|
| CVE-2024-33663 | PyJWT (dependency of FastAPI) — improper key type validation | ✅ Fixed | v1.0.0 |

No other known vulnerabilities at this time.

---

## Security Measures

OpsBrief implements the following security controls:

| Measure | Implementation |
|---------|----------------|
| **Transport Security** | HTTPS / TLS 1.3 for all client-server communication |
| **Password Storage** | bcrypt hashing with per-user salt |
| **Authentication** | JWT access tokens (short-lived) |
| **Content Security** | Content Security Policy (CSP) headers |
| **Injection Protection** | SQLAlchemy ORM prevents SQL injection; HTML escaping prevents XSS |
| **Rate Limiting** | API-level rate limiting on chat and registration endpoints |
| **CORS Restrictions** | Strict origin allowlist for cross-origin requests |
| **API Keys** | Third-party API keys stored server-side only; never exposed to client |

---

## Security Best Practices for Users

- Use a strong, unique password for your OpsBrief account.
- Do not share your API keys or credentials.
- Enable HTTPS only in production and verify your SSL certificate.
- Keep your self-hosted instance updated to the latest version.
- Report any suspicious activity or security concerns immediately.
