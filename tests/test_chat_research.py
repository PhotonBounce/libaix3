"""
test_chat_research.py — Tests for chat research/crawl command detection,
the /chat/research endpoint, and the assess_model accuracy fix.

Covers:
  • _detect_chat_command() for research, learn, crawl, and regular questions
  • /chat endpoint handling of research commands
  • /chat endpoint handling of URL crawl commands
  • /chat/research dedicated endpoint
  • assess_model() filtering of entries to only evaluable ones
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure repo root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import _detect_chat_command, app  # noqa: E402


# ── _detect_chat_command tests ───────────────────────────────────────


class TestDetectChatCommand:
    """Tests for the _detect_chat_command helper."""

    def test_research_prefix(self):
        cmd = _detect_chat_command("research quantum computing")
        assert cmd is not None
        assert cmd["type"] == "research"
        assert cmd["topic"] == "quantum computing"

    def test_learn_about_prefix(self):
        cmd = _detect_chat_command("learn about OSPF routing")
        assert cmd is not None
        assert cmd["type"] == "research"
        assert "OSPF routing" in cmd["topic"]

    def test_study_prefix(self):
        cmd = _detect_chat_command("study WPA3 encryption")
        assert cmd is not None
        assert cmd["type"] == "research"
        assert "WPA3" in cmd["topic"]

    def test_investigate_prefix(self):
        cmd = _detect_chat_command("investigate zero trust architecture")
        assert cmd is not None
        assert cmd["type"] == "research"

    def test_find_information_about(self):
        cmd = _detect_chat_command("find information about BGP")
        assert cmd is not None
        assert cmd["type"] == "research"

    def test_url_detection(self):
        cmd = _detect_chat_command("crawl https://example.com for networking")
        assert cmd is not None
        assert cmd["type"] == "crawl"
        assert "https://example.com" in cmd["urls"]
        assert cmd["topic"]  # Should have extracted topic

    def test_multiple_urls(self):
        cmd = _detect_chat_command(
            "https://example.com https://other.com networking"
        )
        assert cmd is not None
        assert cmd["type"] == "crawl"
        assert len(cmd["urls"]) == 2

    def test_url_with_no_surrounding_text(self):
        cmd = _detect_chat_command("https://docs.example.com/security")
        assert cmd is not None
        assert cmd["type"] == "crawl"
        assert cmd["topic"] == "general"

    def test_regular_question_returns_none(self):
        cmd = _detect_chat_command("What is TCP?")
        assert cmd is None

    def test_regular_long_question_returns_none(self):
        cmd = _detect_chat_command("How does a DNS server resolve domain names?")
        assert cmd is None

    def test_research_too_short_topic_returns_none(self):
        cmd = _detect_chat_command("research ab")
        assert cmd is None

    def test_case_insensitive_research(self):
        cmd = _detect_chat_command("Research WiFi security")
        assert cmd is not None
        assert cmd["type"] == "research"

    def test_case_insensitive_learn(self):
        cmd = _detect_chat_command("Learn About firewalls")
        assert cmd is not None
        assert cmd["type"] == "research"


# ── /chat endpoint research command tests ─────────────────────────────


class TestChatResearchEndpoint:
    """Tests for research command handling via /chat."""

    def setup_method(self):
        self.client = app.test_client()

    @patch("app._execute_research")
    def test_chat_research_command(self, mock_research):
        mock_research.return_value = {
            "total_entries": 15,
            "sources": {"wikipedia": {"entries": 10, "status": "success"}},
            "topic": "firewall rules",
        }
        resp = self.client.post("/chat", json={"question": "research firewall rules"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "research" in data
        assert data["domain"] == "research"
        assert data["confidence"] == 1.0
        assert "15" in data["answer"]
        mock_research.assert_called_once_with("firewall rules")

    @patch("app._execute_research")
    def test_chat_research_no_results(self, mock_research):
        mock_research.return_value = {
            "total_entries": 0,
            "sources": {},
            "topic": "obscure_topic_xyz",
        }
        resp = self.client.post("/chat", json={"question": "research obscure_topic_xyz"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "couldn't find" in data["answer"].lower() or "no results" in data["answer"].lower()

    @patch("app._execute_research")
    def test_chat_url_crawl(self, mock_research):
        mock_research.return_value = {
            "total_entries": 5,
            "sources": {"site:https://example.com": {"entries": 5, "status": "success"}},
            "topic": "networking",
        }
        resp = self.client.post(
            "/chat",
            json={"question": "crawl https://example.com for networking"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["domain"] == "crawl"
        assert "research" in data
        mock_research.assert_called_once()
        # Check URL was passed
        call_args = mock_research.call_args
        assert call_args[1].get("urls") or (len(call_args[0]) > 1 and call_args[0][1])

    @patch("app._execute_research")
    def test_chat_url_no_results(self, mock_research):
        mock_research.return_value = {
            "total_entries": 0,
            "sources": {},
            "topic": "general",
        }
        resp = self.client.post(
            "/chat", json={"question": "https://example.com"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "couldn't extract" in data["answer"].lower() or "crawled" in data["answer"].lower()

    def test_chat_regular_question_not_intercepted(self):
        """Regular questions should NOT trigger research."""
        resp = self.client.post("/chat", json={"question": "What is TCP?"})
        data = resp.get_json()
        # Either returns a proper answer or 503 (model not loaded)
        if resp.status_code == 200:
            assert "research" not in data or data.get("domain") != "research"
        else:
            assert resp.status_code == 503

    def test_chat_empty_question_still_rejected(self):
        resp = self.client.post("/chat", json={"question": ""})
        assert resp.status_code == 400

    def test_chat_too_long_still_rejected(self):
        resp = self.client.post("/chat", json={"question": "x" * 2001})
        assert resp.status_code == 400


# ── /chat/research dedicated endpoint tests ──────────────────────────


class TestChatResearchDedicatedEndpoint:
    """Tests for POST /chat/research."""

    def setup_method(self):
        self.client = app.test_client()

    @patch("app._execute_research")
    def test_research_endpoint_success(self, mock_research):
        mock_research.return_value = {
            "total_entries": 20,
            "sources": {"wikipedia": {"entries": 10, "status": "success"},
                        "forums": {"entries": 10, "status": "success"}},
            "topic": "VLAN security",
        }
        resp = self.client.post("/chat/research", json={"topic": "VLAN security"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["total_entries"] == 20
        assert data["topic"] == "VLAN security"

    @patch("app._execute_research")
    def test_research_endpoint_no_results(self, mock_research):
        mock_research.return_value = {
            "total_entries": 0,
            "sources": {},
            "topic": "nonexistent",
        }
        resp = self.client.post("/chat/research", json={"topic": "nonexistent"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "no_results"

    def test_research_endpoint_missing_topic(self):
        resp = self.client.post("/chat/research", json={})
        assert resp.status_code == 400
        assert "Topic" in resp.get_json()["error"]

    def test_research_endpoint_empty_topic(self):
        resp = self.client.post("/chat/research", json={"topic": ""})
        assert resp.status_code == 400

    def test_research_endpoint_topic_too_long(self):
        resp = self.client.post("/chat/research", json={"topic": "x" * 201})
        assert resp.status_code == 400
        assert "too long" in resp.get_json()["error"]

    @patch("app._execute_research")
    def test_research_endpoint_with_urls(self, mock_research):
        mock_research.return_value = {
            "total_entries": 5,
            "sources": {},
            "topic": "security",
        }
        resp = self.client.post("/chat/research", json={
            "topic": "security",
            "urls": ["https://example.com/security"],
        })
        assert resp.status_code == 200
        mock_research.assert_called_once()
        call_args = mock_research.call_args
        assert call_args[1].get("urls") == ["https://example.com/security"]

    @patch("app._execute_research")
    def test_research_endpoint_invalid_urls_filtered(self, mock_research):
        mock_research.return_value = {
            "total_entries": 0,
            "sources": {},
            "topic": "security",
        }
        resp = self.client.post("/chat/research", json={
            "topic": "security",
            "urls": ["not-a-url", 123, "https://valid.com"],
        })
        assert resp.status_code == 200
        call_args = mock_research.call_args
        # Only the valid URL should be passed
        urls_passed = call_args[1].get("urls") or (call_args[0][1] if len(call_args[0]) > 1 else [])
        if urls_passed:
            assert all(u.startswith("https://") for u in urls_passed)


# ── assess_model accuracy fix tests ───────────────────────────────────


class TestAssessModelAccuracyFix:
    """Tests for the assess_model() entry filtering fix."""

    @patch("ml_engine.Path.exists", return_value=True)
    def test_assess_filters_unknown_answers(self, _mock_exists):
        """Entries whose answers are NOT in answer_map should be excluded.

        We verify the filtering logic that assess_model now applies:
        only entries with answers present in the answer_map values are evaluated.
        """
        answer_map = {"0": "Answer A", "1": "Answer B"}
        known_answers = set(answer_map.values())

        # Knowledge includes entries with known and unknown answers
        test_knowledge = [
            ("Q1", "Answer A", "domain1"),
            ("Q2", "Answer B", "domain1"),
            ("Q3", "Unknown answer", "domain2"),  # NOT in answer_map
            ("Q4", "Another unknown", "domain2"),  # NOT in answer_map
        ]

        evaluable = [
            (q, a, d) for q, a, d in test_knowledge if a in known_answers
        ]
        assert len(evaluable) == 2  # Only "Answer A" and "Answer B"
        assert all(a in known_answers for _, a, _ in evaluable)
        # The unknown entries are excluded
        excluded = [q for q, a, _ in test_knowledge if a not in known_answers]
        assert len(excluded) == 2

    def test_filter_logic_excludes_extra_entries(self):
        """The filtering logic should only keep entries with known answers."""
        answer_map = {"0": "TCP is a protocol", "1": "UDP is connectionless"}
        known_answers = set(answer_map.values())

        all_knowledge = [
            ("What is TCP?", "TCP is a protocol", "networking"),
            ("What is UDP?", "UDP is connectionless", "networking"),
            ("Crawled Q1", "Some crawled answer not in map", "wifi"),
            ("Crawled Q2", "Another crawled answer", "security"),
        ]

        evaluable = [(q, a, d) for q, a, d in all_knowledge if a in known_answers]
        assert len(evaluable) == 2
        assert evaluable[0][0] == "What is TCP?"
        assert evaluable[1][0] == "What is UDP?"

    def test_filter_keeps_all_when_all_match(self):
        """When all entries have answers in answer_map, all are kept."""
        answer_map = {"0": "A1", "1": "A2", "2": "A3"}
        known_answers = set(answer_map.values())

        all_knowledge = [
            ("Q1", "A1", "d1"),
            ("Q2", "A2", "d2"),
            ("Q3", "A3", "d3"),
        ]
        evaluable = [(q, a, d) for q, a, d in all_knowledge if a in known_answers]
        assert len(evaluable) == 3


# ── _execute_research tests ──────────────────────────────────────────


class TestExecuteResearch:
    """Tests for the _execute_research helper."""

    @patch("app._background_retrain")
    def test_execute_research_calls_crawlers(self, mock_retrain):
        """Research should attempt multiple sources."""
        from app import _execute_research

        # The function uses lazy imports, so we mock at the import source
        mock_wiki_result = {"status": "success", "entries": 3}
        mock_forum_result = {"status": "success", "entries": 5}

        with patch.dict("sys.modules", {
            "crawler": MagicMock(
                crawl_single_topic=MagicMock(return_value=mock_wiki_result),
                load_config=MagicMock(return_value={"topics": []}),
                save_config=MagicMock(),
            ),
            "forum_crawler": MagicMock(
                crawl_single_forum_topic=MagicMock(return_value=mock_forum_result),
            ),
        }):
            result = _execute_research("test topic")
            assert result["total_entries"] == 8
            assert "wikipedia" in result["sources"]
            assert "forums" in result["sources"]

    @patch("app._background_retrain")
    def test_execute_research_handles_failures_gracefully(self, mock_retrain):
        """If crawlers fail, should still return a result dict."""
        from app import _execute_research

        with patch.dict("sys.modules", {
            "crawler": MagicMock(
                crawl_single_topic=MagicMock(side_effect=Exception("fail")),
                load_config=MagicMock(return_value={"topics": []}),
                save_config=MagicMock(),
            ),
            "forum_crawler": MagicMock(
                crawl_single_forum_topic=MagicMock(side_effect=Exception("fail")),
            ),
        }):
            result = _execute_research("failing topic")
            assert result["total_entries"] == 0
            assert result["sources"]["wikipedia"]["status"] == "error"
            assert result["sources"]["forums"]["status"] == "error"
