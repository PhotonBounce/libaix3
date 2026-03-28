"""
test_admin_chatbot.py — Tests for the admin chatbot intent classifier.

Covers:
  • classify_intent() — routing user messages to correct intent category
  • Edge cases — URLs, short phrases, questions, mixed signals
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from admin_chatbot import classify_intent  # noqa: E402


class TestClassifyIntentHelp:
    """Help intent detection."""

    def test_help_keyword(self):
        assert classify_intent("help") == "help"

    def test_question_mark(self):
        assert classify_intent("?") == "help"

    def test_commands_keyword(self):
        assert classify_intent("commands") == "help"

    def test_what_can_you_do(self):
        assert classify_intent("what can you do") == "help"


class TestClassifyIntentCrawl:
    """Crawl intent detection."""

    def test_crawl_keyword(self):
        assert classify_intent("crawl networking topics") == "crawl"

    def test_scrape_keyword(self):
        assert classify_intent("scrape the wiki page") == "crawl"

    def test_url_triggers_crawl(self):
        assert classify_intent("https://example.com/article") == "crawl"

    def test_fetch_keyword(self):
        assert classify_intent("fetch data from the internet") == "crawl"

    def test_visit_url(self):
        assert classify_intent("visit http://example.com") == "crawl"


class TestClassifyIntentLearn:
    """Learn intent detection."""

    def test_learn_about(self):
        assert classify_intent("learn about DNS") == "learn"

    def test_research(self):
        assert classify_intent("research TCP/IP") == "learn"

    def test_study(self):
        assert classify_intent("study networking") == "learn"

    def test_bare_topic(self):
        """Short phrases without question marks default to learn."""
        assert classify_intent("DNS records") == "learn"

    def test_short_phrase(self):
        assert classify_intent("WiFi security") == "learn"


class TestClassifyIntentStatus:
    """Status intent detection."""

    def test_status_keyword(self):
        assert classify_intent("status") == "status"

    def test_how_many(self):
        assert classify_intent("how many entries do we have?") == "status"

    def test_show_me(self):
        assert classify_intent("show me the stats") == "status"

    def test_accuracy_keyword(self):
        assert classify_intent("what is the accuracy?") == "status"

    def test_long_question_defaults_to_status(self):
        """Long messages ending in ? default to status."""
        assert classify_intent("I wonder what the current state of the knowledge base is?") == "status"


class TestClassifyIntentTune:
    """Tune intent detection."""

    def test_set_keyword(self):
        assert classify_intent("set learning rate to 0.01") == "tune"

    def test_enable_keyword(self):
        assert classify_intent("enable auto_optimize") == "tune"

    def test_disable_keyword(self):
        assert classify_intent("disable auto_optimize") == "tune"

    def test_toggle_keyword(self):
        assert classify_intent("toggle auto training") == "tune"

    def test_increase_keyword(self):
        assert classify_intent("increase the learning rate") == "tune"

    def test_configure_keyword(self):
        assert classify_intent("configure the scheduler") == "tune"

    def test_url_overrides_tune(self):
        """If a URL is present with a tune trigger, crawl wins."""
        result = classify_intent("set up crawling from https://example.com")
        assert result == "crawl"

    def test_disable_crawler_is_tune(self):
        """'disable crawler' should be tune, not crawl."""
        assert classify_intent("disable crawler") == "tune"


class TestClassifyIntentAction:
    """Action intent detection."""

    def test_retrain(self):
        assert classify_intent("retrain the model") == "action"

    def test_optimize(self):
        assert classify_intent("optimize the model") == "action"

    def test_growth_cycle(self):
        assert classify_intent("growth cycle") == "action"

    def test_run_growth(self):
        assert classify_intent("run growth") == "action"

    def test_stabilize(self):
        assert classify_intent("stabilize the model") == "action"

    def test_assess(self):
        assert classify_intent("assess model quality") == "action"


class TestClassifyIntentEdgeCases:
    """Edge cases and ambiguous inputs."""

    def test_empty_string(self):
        """Empty string should not crash."""
        result = classify_intent("")
        assert isinstance(result, str)

    def test_whitespace_only(self):
        result = classify_intent("   ")
        assert isinstance(result, str)

    def test_case_insensitive(self):
        assert classify_intent("HELP") == "help"
        assert classify_intent("Help") == "help"

    def test_mixed_case_crawl(self):
        assert classify_intent("Crawl the web") == "crawl"
