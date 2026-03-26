# Oceanum PRAX CLI
*(Platform for Rapid Application Execution)*

Deploy and manage your projects on Oceanum.io PRAX platform. In the PRAX platform, you can deploy  applications in a serverless environment and run them in a secure and scalable way. The main components of the PRAX platform are:

- **Oceanum PRAX CLI**: A command-line interface to deploy and manage your projects on the PRAX platform (this repository).
- **Oceanum PRAX Dashboard**: A web-based interface to monitor and manage your deployed resources on the PRAX platform (coming soon).
- [Oceanum PRAX API](https://prax.oceanum.io/): A RESTful API to interact with the PRAX platform programmatically.

## Installation

```
pip install oceanum-prax
```

## Authentication

```
oceanum auth login
```

## Usage
```
oceanum prax --help
```

## Documentation

ReadTheDocs: [https://oceanum-prax-cli.readthedocs.io/](https://oceanum-prax-cli.readthedocs.io/en/)

## Development

### Setup

1. Clone the repository
2. Install development dependencies:
   ```bash
   pip install -e .[dev,test]
   ```
3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

### Code Quality

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

- **Lint code**: `ruff check src/`
- **Format code**: `ruff format src/`
- **Auto-fix issues**: `ruff check --fix src/`

Pre-commit hooks will automatically format code and check for issues before each commit.

### Testing

Run tests with parallel execution:
```bash
pytest -n auto
```

Run tests with coverage:
```bash
pytest --cov oceanum.cli.prax tests/ -n auto -v
```

### Configuration

- **Ruff**: Configured in `pyproject.toml` with 88-character line length
- **Pre-commit**: Configured in `.pre-commit-config.yaml`
- **Python versions**: 3.10, 3.11, 3.12, 3.13
