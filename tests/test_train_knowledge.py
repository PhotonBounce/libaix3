"""Tests for train_knowledge.py — knowledge classifier training pipeline."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from train_knowledge import augment_questions, build_training_data, train


# Small knowledge subset for fast tests
MINI_KNOWLEDGE = [
    ("What is TCP?", "TCP is a connection-oriented transport protocol.", "networking"),
    ("What is UDP?", "UDP is a connectionless transport protocol.", "networking"),
    ("What is a firewall?", "A firewall filters network traffic.", "security"),
    ("What is DNS?", "DNS translates domain names to IP addresses.", "networking"),
    ("What is encryption?", "Encryption converts data into a coded format.", "security"),
]


class TestBuildTrainingData:
    def test_basic_output_shape(self):
        questions, labels, domains, answer_map = build_training_data(MINI_KNOWLEDGE)
        assert len(questions) == 5
        assert labels.shape == (5, 5)
        assert len(answer_map) == 5

    def test_labels_are_onehot(self):
        _, labels, _, _ = build_training_data(MINI_KNOWLEDGE)
        # Each row should have exactly one 1.0
        assert np.all(np.sum(labels, axis=1) == 1.0)

    def test_answer_map_contains_all_answers(self):
        _, _, _, answer_map = build_training_data(MINI_KNOWLEDGE)
        answers_in_map = set(answer_map.values())
        expected = {a for _, a, _ in MINI_KNOWLEDGE}
        assert expected == answers_in_map

    def test_domains_returned(self):
        _, _, domains, _ = build_training_data(MINI_KNOWLEDGE)
        assert isinstance(domains, list)
        assert len(domains) > 0


class TestAugmentQuestions:
    def test_augmentation_increases_count(self):
        augmented = augment_questions(MINI_KNOWLEDGE)
        assert len(augmented) > len(MINI_KNOWLEDGE)

    def test_original_entries_preserved(self):
        augmented = augment_questions(MINI_KNOWLEDGE)
        original_questions = {q for q, _, _ in MINI_KNOWLEDGE}
        augmented_questions = {q for q, _, _ in augmented}
        assert original_questions.issubset(augmented_questions)

    def test_augmented_have_same_answers(self):
        """Augmented variants should map to the same answer as the original."""
        augmented = augment_questions(MINI_KNOWLEDGE)
        # Build answer->domain lookup from originals
        orig_answers = {a for _, a, _ in MINI_KNOWLEDGE}
        for _, answer, _ in augmented:
            assert answer in orig_answers


class TestTrain:
    @pytest.fixture(autouse=True)
    def _isolate_train(self, tmp_path, monkeypatch):
        """Redirect model output to tmp_path and use MINI_KNOWLEDGE for speed."""
        import train_knowledge
        monkeypatch.setattr(train_knowledge, "MODEL_DIR", tmp_path)
        monkeypatch.setattr(train_knowledge, "MODEL_PATH", tmp_path / "knowledge.npz")
        monkeypatch.setattr(train_knowledge, "VECTORIZER_PATH", tmp_path / "vectorizer.json")
        monkeypatch.setattr(train_knowledge, "ANSWER_MAP_PATH", tmp_path / "answer_map.json")
        # Use small knowledge subset so training finishes quickly
        monkeypatch.setattr(train_knowledge, "KNOWLEDGE", MINI_KNOWLEDGE)
        # Use only built-in KNOWLEDGE (no extra knowledge files)
        monkeypatch.setattr(train_knowledge.Path("data/extra_knowledge"), "exists",
                            lambda: False) if False else None
        # Patch the extra_dir.exists() check inside train() to return False
        _real_path_exists = Path.exists
        def _fake_exists(self_):
            if "extra_knowledge" in str(self_):
                return False
            return _real_path_exists(self_)
        monkeypatch.setattr(Path, "exists", _fake_exists)
        self._tmp = tmp_path

    def test_train_returns_model_vectorizer_answermap(self):
        """Training should return a model, vectorizer, and answer map."""
        model, bow, answer_map = train(epochs=100, verbose=False, seed=42)
        from neural_network import NeuralNetwork
        from vectorizer import BagOfWords
        assert isinstance(model, NeuralNetwork)
        assert isinstance(bow, BagOfWords)
        assert isinstance(answer_map, dict)
        assert len(answer_map) > 0

    def test_train_saves_files(self):
        """Training should save model, vectorizer, and answer_map to disk."""
        train(epochs=100, verbose=False, seed=42)
        assert (self._tmp / "knowledge.npz").exists()
        assert (self._tmp / "vectorizer.json").exists()
        assert (self._tmp / "answer_map.json").exists()

    def test_saved_answer_map_is_valid_json(self):
        train(epochs=50, verbose=False, seed=42)
        am = json.loads((self._tmp / "answer_map.json").read_text(encoding="utf-8"))
        assert isinstance(am, dict)
        assert all(isinstance(v, str) for v in am.values())

    def test_train_with_early_stopping(self):
        """Early stopping param should work without error."""
        model, bow, am = train(
            epochs=500, verbose=False, seed=42,
            early_stopping=True, patience=100,
        )
        assert model is not None

    def test_train_with_dropout_and_clipping(self):
        model, _, _ = train(
            epochs=100, verbose=False, seed=42,
            dropout_rate=0.1, grad_clip=5.0,
        )
        assert model.dropout_rate == 0.1
        assert model.grad_clip == 5.0

    def test_train_no_augment(self):
        """Training without augmentation should still work."""
        model, bow, am = train(
            epochs=50, verbose=False, seed=42, augment=False,
        )
        assert model is not None
        assert bow.vocab_size > 0

    def test_train_with_val_split(self):
        """Training with val_split should produce a model and not crash."""
        model, bow, am = train(
            epochs=100, verbose=False, seed=42, val_split=0.2,
        )
        assert model is not None
        assert len(am) > 0

    def test_val_split_early_stopping(self):
        """Early stopping with val_split should monitor val loss."""
        model, bow, am = train(
            epochs=500, verbose=False, seed=42,
            val_split=0.2, early_stopping=True, patience=100,
        )
        assert model is not None
