# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-01

### Added

- Initial release of OpsBrief
- Progressive Web App (PWA) support with offline capability and install prompt
- Multi-source intelligence aggregation: NVD, GitHub Security Advisories, and Cisco PSIRT
- AI-powered daily security briefings personalized to your technology stack
- Conversational AI chat assistant for threat analysis and remediation guidance
- Admin dashboard with stats, intel feed, and user management
- Docker deployment with docker-compose for full stack (app, PostgreSQL, Redis, nginx, Celery)
- JWT authentication with bcrypt password hashing
- Rate limiting and security headers (CSP, X-Frame-Options, X-XSS-Protection)
- Redis caching with in-memory fallback
- Google Play store assets and submission documentation

### Changed

- N/A — Initial release

### Fixed

- N/A — Initial release

### Security

- Implemented XSS protection via HTML escaping on all AI chat output
- Added Content Security Policy (CSP) headers
- Added rate limiting on API endpoints
- Resolved CVE-2024-33663 dependency vulnerability in fastapi-cors
- Enforced HTTPS-only communication in production builds
- Admin API protected with separate API key authentication
