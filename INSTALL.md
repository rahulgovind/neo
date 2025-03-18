# Neo Installation Guide

This document provides instructions for setting up a clean, isolated environment for the Neo application.

## Prerequisites

- Python 3.8 or newer
- pip (Python package installer)
- virtualenv or venv (recommended)

## Option 1: Installation with virtualenv (Recommended)

### 1. Create a virtual environment

```bash
# Install virtualenv if you don't have it
pip install virtualenv

# Create a new virtual environment
virtualenv neo_env

# Activate the virtual environment
# On Windows:
neo_env\Scripts\activate
# On Unix or MacOS:
source neo_env/bin/activate
```

### 2. Install Neo

```bash
# Install the package in development mode
pip install -e .

# For development, install dev dependencies as well
pip install -e ".[dev]"
```

## Option 2: Installation with venv (Python 3.8+)

### 1. Create a virtual environment

```bash
# Create a new virtual environment
python -m venv neo_env

# Activate the virtual environment
# On Windows:
neo_env\Scripts\activate
# On Unix or MacOS:
source neo_env/bin/activate
```

### 2. Install Neo

```bash
# Install the package in development mode
pip install -e .

# For development, install dev dependencies as well
pip install -e ".[dev]"
```

## Option 3: Installation with conda

### 1. Create a conda environment

```bash
# Create a new conda environment
conda create -n neo_env python=3.10

# Activate the conda environment
conda activate neo_env
```

### 2. Install Neo

```bash
# Install the package in development mode
pip install -e .

# For development, install dev dependencies as well
pip install -e ".[dev]"
```

## Configuration

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit the `.env` file and set your API credentials:

```
API_KEY=your_actual_api_key
API_URL=your_api_url_if_needed
```

## Verifying the Installation

You can verify that Neo was installed correctly by running:

```bash
# Check that the neo command is available
neo --version

# Run the tests (without E2E tests)
pytest -xvs tests/

# Run the tests with coverage report
pytest --cov=src tests/
```

## Running End-to-End Tests

To run end-to-end tests that interact with the actual LLM API:

1. Ensure your `.env` file has a valid `API_KEY`
2. Set `RUN_E2E_TESTS=1` in your `.env` file
3. Run the tests:

```bash
pytest -xvs tests/test_model.py::TestModelE2E
```

## Troubleshooting

### Import errors

If you encounter import errors, ensure your virtual environment is activated and that the package is installed in development mode with `-e`.

### API errors

- Verify that your API credentials in the `.env` file are correct
- Check that the required environment variables are loaded (you might need to restart your terminal or IDE after creating the `.env` file)

### Dependency conflicts

If you encounter dependency conflicts, consider creating a fresh virtual environment and reinstalling the package.

```bash
deactivate  # Exit current virtual environment
rm -rf neo_env  # Remove the environment
# Then follow the installation steps again
```