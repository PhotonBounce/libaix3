# libaix — Project Guidelines

## Architecture

- `neural_network.py` — Core `NeuralNetwork` class (forward/backward, activations, optimizers, softmax, cross-entropy, save/load)
- `vectorizer.py` — `BagOfWords` text vectorizer with TF-IDF (tokenize, fit, transform, save/load)
- `knowledge_base.py` — Curated Q&A knowledge entries across 22 domains (networking, programming, algorithms, databases, cloud, linux, devops, etc.)
- `reasoning_engine.py` — Deductive reasoning engine with 6 strategies (direct, deductive, causal, analogical, multi_hop, synthesis)
- `conversation_engine.py` — Conversation context tracking, follow-up detection, pronoun resolution
- `gamification.py` — Achievement system, XP/leveling, quiz mode, streak tracking
- `train.py` — CLI training script with argparse (multi-dataset, configurable hypers)
- `train_knowledge.py` — Knowledge classifier training pipeline (vectorize → train → save model)
- `app.py` — Flask web UI with AI chat (`/chat`), logic-gate playground (`/predict`, `/train`), game endpoints (`/game/*`)
- `templates/index.html` — Tabbed UI: AI Chat + Playground + Dashboard (pure JS, no frameworks)
- `ml_engine.py` — Self-growth, hyperparameter optimization, gap detection
- `boil_engine.py` — Knowledge distillation and conditioning
- `digest_engine.py` — Digest generation engine
- `models/` — Saved model files (knowledge.npz, vectorizer.json, answer_map.json)
- `tests/` — pytest suite (593+ tests across 21+ test files)

## Code Style

- Python 3.10+, type hints on public APIs
- NumPy only for math — no external ML frameworks
- Lint with `ruff check`, format with `ruff format`

## Build and Test

```bash
make install     # pip install -r requirements.txt
make test        # pytest tests/ -v
make run         # Train XOR end-to-end
make lint        # ruff check
make check       # lint + test
python train_knowledge.py  # Train AI knowledge model
python app.py    # Launch web UI on port 5000
```

## Conventions

- New features must include tests in `tests/`
- All datasets use the shared `INPUTS` array from `train.py`
- Web API endpoints return JSON; inputs are validated and clamped server-side
- Model config is stored as JSON inside `.npz` files (no pickle)
- Knowledge entries use (question, answer, domain) triples

## Crash Recovery Protocol (MANDATORY)

All agents (including subagents) MUST follow this protocol to survive crashes:

### 1. Session Memory Checkpointing
- At the START of any multi-step task, create/update `/memories/session/progress.md`
- After EACH completed subtask, immediately update the session progress file
- Format: `- [x] task description (file: path, lines: N)` for completed, `- [ ]` for pending

### 2. Subagent Work Logging
- Every subagent MUST write a summary of what it did to `/memories/session/progress.md` BEFORE returning
- Include: files created/modified, test counts, any errors encountered
- If a subagent creates a file, log the filename and line count

### 3. Resume Protocol
- On "RESUME WORK" or "PROCEED" or after a crash, FIRST read `/memories/session/progress.md`
- Compare session memory against actual file state (git status, file existence)
- Pick up from the last incomplete task — do NOT restart from scratch

### 4. Atomic Commits
- After completing a logical batch of work (e.g., "all new test files"), commit immediately
- Do not accumulate 8000+ lines of uncommitted changes — commit in chunks
- Commit message format: `[area] description (N tests, M files)`
