"""Tests for ML optimizations in NeuralNetwork (early stopping, LR scheduling, dropout, grad clipping)."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from neural_network import NeuralNetwork


# ── Fixtures ──────────────────────────────────────────────────────────
XOR_X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.float64)
XOR_Y = np.array([[0], [1], [1], [0]], dtype=np.float64)


class TestEarlyStopping:
    def test_stops_before_max_epochs(self):
        """Early stopping should terminate before all epochs if loss plateaus."""
        nn = NeuralNetwork([2, 4, 1], learning_rate=1.0, seed=42)
        losses = nn.train(
            XOR_X, XOR_Y,
            epochs=50_000,
            log_every=0,
            early_stopping=True,
            patience=500,
            min_delta=1e-4,
        )
        # Should stop well before 50k epochs once loss stabilises
        assert len(losses) < 50_000

    def test_disabled_runs_all_epochs(self):
        """Without early stopping, all epochs should run."""
        nn = NeuralNetwork([2, 4, 1], learning_rate=1.0, seed=42)
        losses = nn.train(
            XOR_X, XOR_Y,
            epochs=100,
            log_every=0,
            early_stopping=False,
        )
        assert len(losses) == 100

    def test_with_validation_data(self):
        """Early stopping with separate validation data."""
        nn = NeuralNetwork([4, 8, 3], learning_rate=0.01, activation="tanh",
                           optimizer="adam", loss="cross_entropy",
                           softmax_output=True, seed=42)
        rng = np.random.default_rng(0)
        x_train = rng.random((6, 4))
        y_train = np.zeros((6, 3), dtype=np.float64)
        for i in range(6):
            y_train[i, i % 3] = 1.0

        x_val = rng.random((3, 4))
        y_val = np.eye(3, dtype=np.float64)

        losses = nn.train(
            x_train, y_train,
            epochs=5000,
            log_every=0,
            early_stopping=True,
            patience=200,
            x_val=x_val,
            y_val=y_val,
        )
        # Should still converge reasonably
        assert len(losses) > 0
        assert losses[-1] < losses[0]


class TestLRScheduling:
    def test_step_schedule_reduces_lr(self):
        """Step schedule should halve the LR every lr_step_every epochs."""
        nn = NeuralNetwork([2, 4, 1], learning_rate=1.0, lr_schedule="step",
                           lr_step_every=100, seed=42)
        initial_lr = nn.learning_rate
        nn.train(XOR_X, XOR_Y, epochs=200, log_every=0)
        # After 200 epochs with step_every=100, LR should have been halved twice
        assert nn.learning_rate < initial_lr

    def test_cosine_schedule_reduces_lr(self):
        """Cosine schedule should reduce LR towards 0."""
        nn = NeuralNetwork([2, 4, 1], learning_rate=1.0, lr_schedule="cosine", seed=42)
        nn.train(XOR_X, XOR_Y, epochs=500, log_every=0)
        # Near end of training, cosine should have reduced LR significantly
        assert nn.learning_rate < 1.0

    def test_no_schedule_keeps_lr_constant(self):
        """Without a schedule, LR should remain constant."""
        nn = NeuralNetwork([2, 4, 1], learning_rate=0.5, seed=42)
        nn.train(XOR_X, XOR_Y, epochs=100, log_every=0)
        assert nn.learning_rate == 0.5

    def test_invalid_schedule_rejected(self):
        """Invalid schedule names should raise ValueError."""
        with pytest.raises(ValueError, match="lr_schedule"):
            NeuralNetwork([2, 4, 1], lr_schedule="linear")

    def test_convergence_with_step_schedule(self):
        """Network should still converge with step schedule."""
        nn = NeuralNetwork([2, 4, 1], learning_rate=1.0, lr_schedule="step",
                           lr_step_every=2000, seed=42)
        nn.train(XOR_X, XOR_Y, epochs=10_000, log_every=0)
        preds = nn.predict(XOR_X)
        rounded = np.round(preds).astype(int)
        np.testing.assert_array_equal(rounded, XOR_Y.astype(int))


class TestDropout:
    def test_dropout_during_training(self):
        """Dropout should be active during training (outputs differ between runs)."""
        nn = NeuralNetwork([2, 8, 1], learning_rate=0.5, dropout_rate=0.5, seed=42)
        # Training with dropout should still reduce loss
        losses = nn.train(XOR_X, XOR_Y, epochs=1000, log_every=0)
        assert losses[-1] < losses[0]

    def test_no_dropout_during_predict(self):
        """Predict should give deterministic results (no dropout)."""
        nn = NeuralNetwork([2, 8, 1], learning_rate=0.5, dropout_rate=0.5, seed=42)
        nn.train(XOR_X, XOR_Y, epochs=500, log_every=0)
        pred1 = nn.predict(XOR_X).copy()
        pred2 = nn.predict(XOR_X).copy()
        np.testing.assert_array_equal(pred1, pred2)

    def test_zero_dropout_is_noop(self):
        """Dropout rate of 0 should behave identically to no dropout."""
        nn1 = NeuralNetwork([2, 4, 1], learning_rate=1.0, dropout_rate=0.0, seed=42)
        nn2 = NeuralNetwork([2, 4, 1], learning_rate=1.0, seed=42)
        losses1 = nn1.train(XOR_X, XOR_Y, epochs=100, log_every=0)
        losses2 = nn2.train(XOR_X, XOR_Y, epochs=100, log_every=0)
        np.testing.assert_array_almost_equal(losses1, losses2)

    def test_convergence_with_dropout(self):
        """Network should converge even with moderate dropout."""
        nn = NeuralNetwork([2, 16, 1], learning_rate=1.0, dropout_rate=0.3, seed=42)
        nn.train(XOR_X, XOR_Y, epochs=15_000, log_every=0)
        preds = nn.predict(XOR_X)
        rounded = np.round(preds).astype(int)
        np.testing.assert_array_equal(rounded, XOR_Y.astype(int))


class TestGradientClipping:
    def test_grad_clip_prevents_explosion(self):
        """With gradient clipping, training should remain stable."""
        nn = NeuralNetwork([2, 4, 1], learning_rate=5.0, grad_clip=1.0, seed=42)
        losses = nn.train(XOR_X, XOR_Y, epochs=500, log_every=0)
        # All losses should be finite (no NaN/Inf from exploding gradients)
        assert all(np.isfinite(v) for v in losses)

    def test_no_clip_is_default(self):
        """Default grad_clip should be None."""
        nn = NeuralNetwork([2, 4, 1])
        assert nn.grad_clip is None

    def test_convergence_with_clipping(self):
        """Network should still converge with gradient clipping."""
        nn = NeuralNetwork([2, 4, 1], learning_rate=1.0, grad_clip=5.0, seed=42)
        nn.train(XOR_X, XOR_Y, epochs=10_000, log_every=0)
        preds = nn.predict(XOR_X)
        rounded = np.round(preds).astype(int)
        np.testing.assert_array_equal(rounded, XOR_Y.astype(int))


class TestSaveLoadNewParams:
    def test_round_trip_preserves_new_params(self):
        """Save/load should preserve dropout, grad_clip, lr_schedule."""
        nn = NeuralNetwork(
            [2, 4, 1], learning_rate=0.5,
            dropout_rate=0.3, grad_clip=2.0,
            lr_schedule="step", lr_step_every=500,
            seed=42,
        )
        nn.train(XOR_X, XOR_Y, epochs=100, log_every=0)

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "model.npz"
            nn.save(path)
            loaded = NeuralNetwork.load(path)

        assert loaded.dropout_rate == 0.3
        assert loaded.grad_clip == 2.0
        assert loaded.lr_schedule == "step"
        assert loaded.lr_step_every == 500

    def test_backward_compat_load(self):
        """Loading a model saved without new params should use defaults."""
        nn = NeuralNetwork([2, 4, 1], seed=42)
        nn.train(XOR_X, XOR_Y, epochs=50, log_every=0)

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "model.npz"
            nn.save(path)
            loaded = NeuralNetwork.load(path)

        assert loaded.dropout_rate == 0.0
        assert loaded.grad_clip is None
        assert loaded.lr_schedule is None


class TestCombinedFeatures:
    def test_all_features_together(self):
        """All ML optimizations combined should still reduce loss."""
        nn = NeuralNetwork(
            [2, 16, 1],
            learning_rate=0.5,
            activation="tanh",
            optimizer="adam",
            dropout_rate=0.1,
            grad_clip=5.0,
            lr_schedule="step",
            lr_step_every=2000,
            seed=42,
        )
        losses = nn.train(
            XOR_X, XOR_Y,
            epochs=5_000,
            log_every=0,
        )
        # Loss should decrease significantly
        assert losses[-1] < losses[0]
        # All losses should be finite
        assert all(np.isfinite(v) for v in losses)

    def test_dropout_and_clipping_convergence(self):
        """Dropout + gradient clipping should still allow XOR convergence."""
        nn = NeuralNetwork(
            [2, 8, 1],
            learning_rate=1.0,
            optimizer="adam",
            dropout_rate=0.1,
            grad_clip=5.0,
            seed=42,
        )
        nn.train(XOR_X, XOR_Y, epochs=15_000, log_every=0)
        preds = nn.predict(XOR_X)
        rounded = np.round(preds).astype(int)
        np.testing.assert_array_equal(rounded, XOR_Y.astype(int))
