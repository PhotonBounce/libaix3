# Contributing Guide

Thank you for your interest in contributing to OpsBrief!

---

## How to Set Up the Development Environment

### Prerequisites

- Python 3.11+
- Node.js 20.x (for mobile builds)
- Docker and Docker Compose (optional, for full stack)
- Git

### Backend Setup

```bash
cd D:/opsbrief/backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copy and edit environment variables
cp .env.example .env
# Edit .env with your OPENAI_API_KEY, GITHUB_TOKEN, etc.

# Run the development server
python run.py
```

The API will be available at `http://localhost:8000` with interactive docs at `/docs`.

### Frontend Setup

The frontend is a single-file PWA. No build step is required.

```bash
cd D:/opsbrief/frontend
# Open index.html directly in your browser
# Or serve via a local server:
python -m http.server 8080
```

### Mobile Setup

```bash
cd D:/opsbrief/mobile
npm install
npm run build-www
npx cap sync android
npx cap open android
```

### Docker (Full Stack)

```bash
cd D:/opsbrief
cp .env.example .env
# Edit .env with your secrets
docker-compose up -d --build
```

---

## Code Style

- **Python:** Follow PEP 8. Use `black` for formatting and `isort` for imports.
- **JavaScript:** Use standard ES6+ syntax. No semicolons required. Prefer `const` and `let` over `var`.
- **Naming:** Use `snake_case` for Python functions and variables, `PascalCase` for classes, and `camelCase` for JavaScript.
- **Comments:** Explain *why*, not *what*. Keep docstrings on all public functions.
- **Type hints:** Use Python type hints on all function signatures.

```bash
# Format Python code
black opsbrief/
isort opsbrief/
```

---

## Testing

Run the test suite before submitting a pull request:

```bash
cd D:/opsbrief/backend
pytest
```

All tests must pass. If you add a new feature, include tests that cover it. If you fix a bug, add a regression test.

---

## Pull Request Process

1. **Fork the repository** and create your branch from `main`.
2. **Make your changes.** Ensure the code follows the style guide and all tests pass.
3. **Update documentation** if your change affects user-facing behavior.
4. **Submit a pull request** with a clear description of the problem and the solution.
5. **Reference any related issues** using the GitHub issue number (e.g., `Fixes #123`).
6. A maintainer will review your PR and provide feedback. Please be responsive to review comments.

---

## Commit Message Format

We use conventional commit messages to keep the history clean and enable automated changelogs:

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

### Types

- `feat` — A new feature
- `fix` — A bug fix
- `docs` — Documentation only changes
- `style` — Formatting, missing semicolons, etc.; no code change
- `refactor` — Code change that neither fixes a bug nor adds a feature
- `perf` — A code change that improves performance
- `test` — Adding or correcting tests
- `chore` — Changes to build process, dependencies, etc.

### Examples

```
feat(chat): add streaming response support

fix(api): handle missing OPENAI_API_KEY gracefully

docs(readme): add Docker deployment instructions

test(auth): add regression test for JWT expiration
```

---

## Questions?

If you have questions about contributing, open a discussion or email us at contact@photon-bounce.com.
