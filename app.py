#!/usr/bin/env python3
"""
app.py — Simple Flask web UI for the XOR neural network.

Run:
    python app.py
Then open http://localhost:5000 in your browser.
"""

import json

import numpy as np
from flask import Flask, render_template, request, jsonify

from neural_network import NeuralNetwork

app = Flask(__name__)

# Train once at startup
print("Training XOR neural network …")
nn = NeuralNetwork(layer_sizes=[2, 4, 1], learning_rate=1.0, seed=42)
X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.float64)
Y = np.array([[0], [1], [1], [0]], dtype=np.float64)
nn.train(X, Y, epochs=10_000, log_every=2_000)
print("Training complete!\n")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True)
    a = int(data.get("a", 0))
    b = int(data.get("b", 0))
    # Clamp to 0/1
    a = max(0, min(1, a))
    b = max(0, min(1, b))
    raw = float(nn.predict(np.array([[a, b]], dtype=np.float64))[0, 0])
    return jsonify({"a": a, "b": b, "raw": round(raw, 6), "result": int(round(raw))})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
