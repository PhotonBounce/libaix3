"""
admin.py — Admin backend blueprint for libaix knowledge management.

Provides:
  • Authenticated admin dashboard
  • File upload with auto-extraction (PDF/TXT/CSV/…) + file deletion after extraction
  • Text paste → knowledge extraction
  • Wikipedia crawler management (multi-topic, add/remove/toggle)
  • AI learning prompts ("Learn about <topic>")
  • Knowledge browser
  • One-click retrain
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from crawler import (
    crawl_single_topic,
    load_config,
    run_all_crawlers,
    save_config,
)
from file_processor import classify_domain, process_file, process_pasted_text
from knowledge_base import KNOWLEDGE, get_domains

# ── Config ────────────────────────────────────────────────────────────
UPLOAD_DIR = Path("data/uploads")
EXTRA_KNOWLEDGE_DIR = Path("data/extra_knowledge")
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".csv", ".log", ".conf",
    ".cfg", ".ini", ".json", ".xml", ".html",
}

# Credentials — override via env vars ADMIN_USER / ADMIN_PASS
_admin_user = os.environ.get("ADMIN_USER", "kakababa")
_admin_pass = os.environ.get("ADMIN_PASS", "Nepidaras25!!??")
ADMIN_CREDENTIALS = {
    "username": _admin_user,
    "password_hash": generate_password_hash(_admin_pass),
}
del _admin_pass  # scrub plaintext from process memory

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── Auth helper ───────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated


# ── Auth routes ───────────────────────────────────────────────────────

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if (
            username == ADMIN_CREDENTIALS["username"]
            and check_password_hash(ADMIN_CREDENTIALS["password_hash"], password)
        ):
            session["admin_logged_in"] = True
            session["admin_user"] = username
            return redirect(url_for("admin.dashboard"))
        flash("Invalid credentials", "error")
    return render_template("admin_login.html")


@admin_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


# ── Dashboard ─────────────────────────────────────────────────────────

@admin_bp.route("/")
@login_required
def dashboard():
    extra_count = _count_extra_knowledge()
    config = load_config()
    return render_template(
        "admin_dashboard.html",
        knowledge_count=len(KNOWLEDGE),
        extra_count=extra_count,
        total_count=len(KNOWLEDGE) + extra_count,
        domains=get_domains() + _get_extra_domains(),
        crawler_config=config,
    )


@admin_bp.route("/api/stats")
@login_required
def api_stats():
    extra_count = _count_extra_knowledge()
    config = load_config()
    return jsonify({
        "builtin_entries": len(KNOWLEDGE),
        "extra_entries": extra_count,
        "total_entries": len(KNOWLEDGE) + extra_count,
        "domains": get_domains() + _get_extra_domains(),
        "extra_files": _list_extra_files(),
        "crawler": {
            "topics": config.get("topics", []),
            "last_crawl": config.get("last_crawl"),
        },
    })


# ── File upload ───────────────────────────────────────────────────────

@admin_bp.route("/upload", methods=["POST"])
@login_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    domain_hint = request.form.get("domain", "")
    filename = secure_filename(file.filename)
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        return jsonify({
            "error": f"Unsupported format: {suffix}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        }), 400

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filepath = UPLOAD_DIR / filename
    file.save(filepath)

    try:
        entries, preview = process_file(filepath, domain_hint)
        if entries:
            save_path = _save_knowledge(entries, f"upload_{filename}")
            return jsonify({
                "status": "success",
                "file": filename,
                "entries_extracted": len(entries),
                "preview": preview,
                "samples": entries[:5],
                "saved_to": str(save_path),
                "message": f"Extracted {len(entries)} entries. File deleted.",
            })
        return jsonify({
            "status": "warning",
            "file": filename,
            "entries_extracted": 0,
            "preview": preview,
            "message": "No entries could be extracted from this file.",
        })
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        # ALWAYS delete the upload — space preservation
        if filepath.exists():
            filepath.unlink()


# ── Text paste ────────────────────────────────────────────────────────

@admin_bp.route("/paste", methods=["POST"])
@login_required
def paste_text():
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "No text provided"}), 400

    entries = process_pasted_text(data["text"], data.get("domain", ""))
    if entries:
        save_path = _save_knowledge(entries, "paste")
        return jsonify({
            "status": "success",
            "entries_extracted": len(entries),
            "samples": entries[:5],
            "saved_to": str(save_path),
        })
    return jsonify({
        "status": "warning",
        "entries_extracted": 0,
        "message": "No entries extracted. Try pasting structured content with definitions.",
    })


# ── Manual Q&A entry ─────────────────────────────────────────────────

@admin_bp.route("/add-entry", methods=["POST"])
@login_required
def add_entry():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    question = (data.get("question") or "").strip()
    answer = (data.get("answer") or "").strip()
    domain = (data.get("domain") or "").strip() or classify_domain(answer)
    if not question or not answer:
        return jsonify({"error": "Both question and answer are required"}), 400

    entries = [{"question": question, "answer": answer, "domain": domain}]
    save_path = _save_knowledge(entries, "manual")
    return jsonify({"status": "success", "entry": entries[0], "saved_to": str(save_path)})


# ── Crawler management ────────────────────────────────────────────────

@admin_bp.route("/crawler/topics")
@login_required
def get_crawler_topics():
    return jsonify(load_config().get("topics", []))


@admin_bp.route("/crawler/add-topic", methods=["POST"])
@login_required
def add_crawler_topic():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Topic name required"}), 400

    config = load_config()
    topics = config.get("topics", [])
    if any(t["name"].lower() == data["name"].lower() for t in topics):
        return jsonify({"error": "Topic already exists"}), 400

    topics.append({
        "name": data["name"],
        "keywords": [k.strip() for k in data.get("keywords", []) if k.strip()],
        "enabled": True,
        "max_articles": int(data.get("max_articles", 8)),
    })
    config["topics"] = topics
    save_config(config)
    return jsonify({"status": "success", "topics": topics})


@admin_bp.route("/crawler/remove-topic", methods=["POST"])
@login_required
def remove_crawler_topic():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Topic name required"}), 400
    config = load_config()
    config["topics"] = [t for t in config.get("topics", []) if t["name"] != data["name"]]
    save_config(config)
    return jsonify({"status": "success", "topics": config["topics"]})


@admin_bp.route("/crawler/toggle-topic", methods=["POST"])
@login_required
def toggle_crawler_topic():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Topic name required"}), 400
    config = load_config()
    for t in config.get("topics", []):
        if t["name"] == data["name"]:
            t["enabled"] = not t.get("enabled", True)
            break
    save_config(config)
    return jsonify({"status": "success", "topics": config["topics"]})


@admin_bp.route("/crawler/run", methods=["POST"])
@login_required
def run_crawler():
    results = run_all_crawlers()
    return jsonify(results)


@admin_bp.route("/crawler/run-topic", methods=["POST"])
@login_required
def run_single_crawler():
    data = request.get_json()
    if not data or not data.get("topic"):
        return jsonify({"error": "Topic required"}), 400
    return jsonify(crawl_single_topic(
        data["topic"],
        data.get("keywords", []),
        int(data.get("max_articles", 10)),
    ))


# ── AI learning prompts ──────────────────────────────────────────────

@admin_bp.route("/learn", methods=["POST"])
@login_required
def learn_prompt():
    """Parse an admin learning command and crawl for the topic."""
    data = request.get_json()
    if not data or not data.get("prompt"):
        return jsonify({"error": "Prompt required"}), 400

    topic = _parse_learning_prompt(data["prompt"])
    if not topic:
        return jsonify({
            "error": "Could not parse prompt. Try: 'Learn about <topic>'"
        }), 400

    keywords = [k.strip() for k in data.get("keywords", []) if k.strip()]
    result = crawl_single_topic(topic, keywords, max_articles=15)

    if result["status"] == "success":
        # Auto-add to crawler config for continuous learning
        config = load_config()
        topics = config.get("topics", [])
        if not any(t["name"].lower() == topic.lower() for t in topics):
            topics.append({
                "name": topic,
                "keywords": keywords,
                "enabled": True,
                "max_articles": 8,
            })
            config["topics"] = topics
            save_config(config)
        result["message"] = (
            f"Learned {result['entries']} facts about '{topic}'. "
            "Topic added to crawler for continuous learning."
        )
    return jsonify(result)


# ── Retrain ───────────────────────────────────────────────────────────

@admin_bp.route("/retrain", methods=["POST"])
@login_required
def retrain():
    try:
        from train_knowledge import train as _train
        model, bow, answer_map = _train(
            activation="tanh", optimizer="adam",
            lr=0.01, epochs=5000, hidden=256,
            augment=True, verbose=False,
        )
        return jsonify({
            "status": "success",
            "entries": len(answer_map),
            "vocab": bow.vocab_size,
            "message": f"Retrained on {len(answer_map)} answers, {bow.vocab_size} vocab words.",
        })
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500


# ── Knowledge browser ────────────────────────────────────────────────

@admin_bp.route("/knowledge")
@login_required
def browse_knowledge():
    domain_filter = request.args.get("domain", "")
    entries: list[dict] = []

    for q, a, d in KNOWLEDGE:
        if not domain_filter or d == domain_filter:
            entries.append({"question": q, "answer": a, "domain": d, "source": "builtin"})

    for fp in _iter_extra_files():
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            for e in data:
                if not domain_filter or e.get("domain") == domain_filter:
                    entries.append({
                        "question": e["question"],
                        "answer": e["answer"],
                        "domain": e.get("domain", "general"),
                        "source": f"extra:{fp.name}",
                    })
        except Exception:
            continue

    return jsonify({"entries": entries, "total": len(entries)})


# ── Helpers ───────────────────────────────────────────────────────────

def _save_knowledge(entries: list[dict], source: str) -> Path:
    EXTRA_KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w\-]", "_", source.lower())
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = EXTRA_KNOWLEDGE_DIR / f"{safe}_{ts}.json"
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _count_extra_knowledge() -> int:
    total = 0
    for fp in _iter_extra_files():
        try:
            total += len(json.loads(fp.read_text(encoding="utf-8")))
        except Exception:
            continue
    return total


def _list_extra_files() -> list[dict]:
    out: list[dict] = []
    for fp in _iter_extra_files():
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            out.append({
                "name": fp.name,
                "entries": len(data),
                "size_kb": round(fp.stat().st_size / 1024, 1),
            })
        except Exception:
            continue
    return out


def _iter_extra_files():
    if EXTRA_KNOWLEDGE_DIR.exists():
        yield from sorted(EXTRA_KNOWLEDGE_DIR.glob("*.json"))


def _get_extra_domains() -> list[str]:
    domains: set[str] = set()
    for fp in _iter_extra_files():
        try:
            for e in json.loads(fp.read_text(encoding="utf-8")):
                if "domain" in e:
                    domains.add(e["domain"])
        except Exception:
            continue
    return sorted(domains)


def _parse_learning_prompt(prompt: str) -> str:
    prompt = prompt.strip()
    prompt_lower = prompt.lower()
    prefixes = [
        "learn about", "research", "study", "find information about",
        "teach yourself about", "gather knowledge on", "crawl for",
        "learn", "fetch data about", "get information on", "find out about",
    ]
    for pfx in sorted(prefixes, key=len, reverse=True):
        if prompt_lower.startswith(pfx):
            topic = prompt[len(pfx):].strip()
            if topic:
                return topic
    return prompt if len(prompt) > 3 else ""
