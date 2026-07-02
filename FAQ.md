# Frequently Asked Questions

## What is OpsBrief?

OpsBrief is an IT Professional Intelligence Agent that delivers daily, AI-curated security briefings personalized to your technology stack. It aggregates vulnerability data from NVD, GitHub Security Advisories, and Cisco PSIRT, then scores and summarizes the most relevant threats for you every morning.

## How does it work?

1. You select your tech stack during onboarding (e.g., Python, Docker, Cisco IOS).
2. Every 6 hours, OpsBrief fetches the latest security advisories from multiple sources.
3. Once daily, it scores each advisory against your stack and uses AI to generate a personalized briefing.
4. You can ask follow-up questions in the AI chat, save critical items, and install the app as a PWA on your phone.

## Is it free?

Yes. The current version is completely free to use. A Pro tier with unlimited chats, saved items, and team features is planned for a future release.

## What data sources does OpsBrief use?

OpsBrief aggregates intelligence from:

- **NVD** (National Vulnerability Database) — Official CVE feed
- **GitHub Security Advisories** — Repository-level security alerts
- **Cisco PSIRT** — Cisco product security incident response

## Is my data safe?

Yes. We take security seriously:

- All data is encrypted in transit (HTTPS/TLS 1.3).
- Passwords are hashed with bcrypt.
- Authentication uses JWT tokens.
- Chat messages are shared with OpenAI only for AI processing; OpenAI does not use them for model training via our API integration.
- We do not sell your data or use it for advertising.

## Can I self-host?

Absolutely. OpsBrief is designed for self-hosting:

- Docker Compose file included (`docker-compose.yml`)
- SQLite default for quick development (no PostgreSQL setup needed)
- All environment variables documented in `.env.example`
- No external dependencies beyond an OpenAI API key

## How can I contribute?

We welcome contributions! Please see [`CONTRIBUTING.md`](CONTRIBUTING.md) for:

- Setting up your development environment
- Code style guidelines
- Running tests
- Submitting pull requests

## How do I report bugs or request features?

- **Email:** contact@photon-bounce.com
- **Security issues:** See [`SECURITY.md`](SECURITY.md) for our vulnerability disclosure policy
- **GitHub Issues:** If the project is open-sourced on GitHub, open an issue there

We aim to respond to all bug reports within 48 hours.
