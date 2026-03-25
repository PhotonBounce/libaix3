"""
neural_network.py — A minimal neural network built from scratch using only NumPy.

Implements:
  • Configurable multi-layer feed-forward network
  • Sigmoid activation with numerically-stable derivative
  • Xavier/Glorot weight initialisation
  • Stochastic-gradient-descent back-propagation
"""

import numpy as np


class NeuralNetwork:
    """A fully-connected feed-forward neural network.

    Parameters
    ----------
    layer_sizes : list[int]
        Number of neurons in each layer, e.g. ``[2, 4, 1]`` for a network
        with 2 inputs, one hidden layer of 4 neurons, and 1 output.
    learning_rate : float, optional
        Step size for gradient descent (default ``0.5``).
    seed : int | None, optional
        Random seed for reproducibility (default ``None``).
    """

    def __init__(
        self,
        layer_sizes: list[int],
        learning_rate: float = 0.5,
        seed: int | None = None,
    ) -> None:
        if len(layer_sizes) < 2:
            raise ValueError("Need at least an input and an output layer.")
        self.layer_sizes = layer_sizes
        self.learning_rate = learning_rate
        self._rng = np.random.default_rng(seed)

        # Xavier initialisation for weights; zeros for biases
        self.weights: list[np.ndarray] = []
        self.biases: list[np.ndarray] = []
        for i in range(len(layer_sizes) - 1):
            fan_in = layer_sizes[i]
            fan_out = layer_sizes[i + 1]
            limit = np.sqrt(6.0 / (fan_in + fan_out))
            w = self._rng.uniform(-limit, limit, size=(fan_in, fan_out))
            b = np.zeros((1, fan_out))
            self.weights.append(w)
            self.biases.append(b)

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------
    @staticmethod
    def _sigmoid(z: np.ndarray) -> np.ndarray:
        """Numerically-stable sigmoid."""
        return np.where(
            z >= 0,
            1.0 / (1.0 + np.exp(-z)),
            np.exp(z) / (1.0 + np.exp(z)),
        )

    @staticmethod
    def _sigmoid_derivative(a: np.ndarray) -> np.ndarray:
        """Derivative of sigmoid given the *activated* output ``a``."""
        return a * (1.0 - a)

    # ------------------------------------------------------------------
    # Forward pass
    # ------------------------------------------------------------------
    def forward(self, x: np.ndarray) -> np.ndarray:
        """Compute the network output for input ``x``.

        Also stores intermediate activations for use by :meth:`backward`.
        """
        self._activations: list[np.ndarray] = [x]
        a = x
        for w, b in zip(self.weights, self.biases):
            z = a @ w + b
            a = self._sigmoid(z)
            self._activations.append(a)
        return a

    # ------------------------------------------------------------------
    # Backward pass (back-propagation)
    # ------------------------------------------------------------------
    def backward(self, y: np.ndarray) -> float:
        """Run back-propagation and update weights.

        Parameters
        ----------
        y : np.ndarray
            Target values with the same shape as the network output.

        Returns
        -------
        float
            Mean-squared-error loss for this batch.
        """
        output = self._activations[-1]
        error = y - output  # (batch, output_dim)
        loss = float(np.mean(error ** 2))

        deltas: list[np.ndarray] = [None] * len(self.weights)  # type: ignore[list-item]

        # Output layer delta
        deltas[-1] = error * self._sigmoid_derivative(output)

        # Hidden layer deltas (propagate error backwards)
        for i in range(len(self.weights) - 2, -1, -1):
            error_hidden = deltas[i + 1] @ self.weights[i + 1].T
            deltas[i] = error_hidden * self._sigmoid_derivative(
                self._activations[i + 1]
            )

        # Update weights and biases
        for i in range(len(self.weights)):
            self.weights[i] += (
                self.learning_rate * (self._activations[i].T @ deltas[i])
            )
            self.biases[i] += self.learning_rate * np.sum(
                deltas[i], axis=0, keepdims=True
            )

        return loss

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def train(
        self,
        x: np.ndarray,
        y: np.ndarray,
        epochs: int = 10_000,
        log_every: int = 1_000,
    ) -> list[float]:
        """Train the network on the full dataset for *epochs* iterations.

        Parameters
        ----------
        x : np.ndarray
            Input data of shape ``(samples, features)``.
        y : np.ndarray
            Target data of shape ``(samples, outputs)``.
        epochs : int
            Number of training iterations.
        log_every : int
            Print loss every *log_every* epochs (0 to silence).

        Returns
        -------
        list[float]
            Loss recorded at each epoch.
        """
        losses: list[float] = []
        for epoch in range(1, epochs + 1):
            self.forward(x)
            loss = self.backward(y)
            losses.append(loss)
            if log_every and epoch % log_every == 0:
                print(f"Epoch {epoch:>6d}  |  Loss: {loss:.6f}")
        return losses

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Return the network output without storing gradients."""
        a = x
        for w, b in zip(self.weights, self.biases):
            z = a @ w + b
            a = self._sigmoid(z)
        return a
