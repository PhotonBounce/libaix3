#!/usr/bin/env python3
"""
train.py — Train a neural network on the XOR problem and display results.

Run:
    python train.py
"""

import numpy as np

from neural_network import NeuralNetwork


def main() -> None:
    # ----- XOR dataset -----
    x = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.float64)
    y = np.array([[0], [1], [1], [0]], dtype=np.float64)

    # ----- Build network: 2 inputs → 4 hidden → 1 output -----
    nn = NeuralNetwork(layer_sizes=[2, 4, 1], learning_rate=1.0, seed=42)

    print("=" * 50)
    print("  XOR Neural Network — Training")
    print("=" * 50)

    epochs = 10_000
    losses = nn.train(x, y, epochs=epochs, log_every=1_000)

    # ----- Evaluate -----
    print("\n" + "=" * 50)
    print("  Results after training")
    print("=" * 50)

    predictions = nn.predict(x)
    all_correct = True
    for inputs, target, pred in zip(x, y, predictions):
        rounded = int(round(float(pred[0])))
        correct = rounded == int(target[0])
        if not correct:
            all_correct = False
        mark = "✓" if correct else "✗"
        print(
            f"  Input: {inputs}  |  Target: {int(target[0])}  "
            f"|  Prediction: {pred[0]:.4f} → {rounded}  {mark}"
        )

    print()
    if all_correct:
        print("🎉  All XOR outputs learned correctly!")
    else:
        print("⚠️   Some outputs are incorrect — try more epochs or tweak hyperparameters.")

    print(f"\nFinal loss: {losses[-1]:.6f}")


if __name__ == "__main__":
    main()
