.PHONY: install run test clean

## Install dependencies
install:
	pip install -r requirements.txt

## Train the XOR neural network
run: install
	python train.py

## Run the test suite
test: install
	python -m pytest tests/ -v

## Remove cached files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
