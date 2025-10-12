# Contributing to Prometh Cortex

Thank you for your interest in contributing to Prometh Cortex! This document provides guidelines for contributing to the project.

## Getting Started

### Prerequisites
- Python 3.9 or higher
- Git for version control
- Basic knowledge of Python, RAG systems, and vector databases
- Familiarity with LlamaIndex and FastAPI (helpful but not required)

### Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/ivannagy/prometh-cortex.git
   cd prometh-cortex
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   # or
   .venv\Scripts\activate  # On Windows
   ```

3. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

5. **Set up configuration**
   ```bash
   cp config.toml.sample config.toml
   # Edit config.toml with your test datalake paths
   ```

6. **Build test index**
   ```bash
   pcortex build --force
   ```

## How to Contribute

### Reporting Issues

- Use GitHub Issues to report bugs or request features
- Check existing issues before creating a new one
- Provide clear descriptions with steps to reproduce
- Include relevant command outputs and error messages

### Submitting Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow existing code structure and patterns
   - Write clean, documented Python code
   - Add type hints to functions and methods
   - Follow PEP 8 style guidelines

3. **Test your changes**
   ```bash
   # Run unit tests
   pytest tests/unit/

   # Run integration tests
   pytest tests/integration/

   # Run all tests with coverage
   pytest --cov=src/prometh_cortex

   # Test CLI commands manually
   pcortex build --force
   pcortex query "test search"
   ```

4. **Check code quality**
   ```bash
   # Format code
   black src/ tests/
   isort src/ tests/

   # Lint code
   flake8 src/ tests/

   # Type check
   mypy src/
   ```

5. **Update documentation**
   - Update [README.md](README.md) for new features
   - Add entries to [CHANGELOG.md](CHANGELOG.md)
   - Update [CLAUDE.md](CLAUDE.md) if architecture changes
   - Add docstrings to new functions/classes

6. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: Brief description of your changes"
   ```

   Use conventional commit format:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation
   - `test:` for tests
   - `refactor:` for refactoring
   - `perf:` for performance improvements

7. **Push and create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```
   - Open a Pull Request on GitHub
   - Provide a clear description of changes
   - Reference any related issues
   - Include test results if applicable

## Development Guidelines

### Project Structure

```
src/prometh_cortex/
├── cli/                    # CLI commands and entry point
│   ├── commands/          # Individual command implementations
│   └── main.py            # Main CLI entry point
├── config/                # Configuration management
├── indexer/               # RAG indexing and querying logic
├── mcp/                   # MCP protocol server
├── parser/                # Markdown and YAML parsing
├── server/                # HTTP REST API server
└── utils/                 # Utility functions
```

### Coding Style

- **Python Style**: Follow PEP 8 conventions
- **Type Hints**: Use type annotations for all function signatures
- **Docstrings**: Use Google-style docstrings for modules, classes, and functions
- **Error Handling**: Use specific exception types and provide helpful error messages
- **Logging**: Use the logging module (not print statements)
- **Imports**: Use absolute imports, organize with isort

Example:
```python
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

def process_documents(paths: List[str], max_results: Optional[int] = None) -> List[str]:
    """Process documents from given paths.

    Args:
        paths: List of file paths to process
        max_results: Maximum number of results to return

    Returns:
        List of processed document IDs

    Raises:
        ValueError: If paths is empty
        FileNotFoundError: If a path doesn't exist
    """
    if not paths:
        raise ValueError("Paths list cannot be empty")
    # Implementation
```

### Testing Guidelines

- **Unit Tests**: Test individual functions and classes in isolation
- **Integration Tests**: Test components working together
- **Coverage**: Aim for >80% code coverage
- **Test Structure**: Use AAA pattern (Arrange, Act, Assert)
- **Fixtures**: Use pytest fixtures for common test data
- **Mocking**: Mock external dependencies (file system, network, etc.)

Example test structure:
```python
import pytest
from prometh_cortex.parser import YAMLParser

def test_yaml_parser_with_valid_frontmatter():
    # Arrange
    content = "---\ntitle: Test\n---\nContent"
    parser = YAMLParser()

    # Act
    result = parser.parse(content)

    # Assert
    assert result.metadata["title"] == "Test"
    assert result.content == "Content"
```

### Adding New Features

When adding new features:

1. **CLI Commands**: Add to `src/prometh_cortex/cli/commands/`
2. **Configuration**: Update `src/prometh_cortex/config/settings.py`
3. **Tests**: Add tests in `tests/unit/` or `tests/integration/`
4. **Documentation**: Update README.md with usage examples
5. **Type Safety**: Run `mypy` to ensure type correctness

## Pull Request Process

1. **Update documentation** - Ensure README.md and CHANGELOG.md reflect your changes
2. **Maintain quality** - Follow coding style and testing guidelines
3. **Clear description** - Explain what changes were made and why
4. **Review feedback** - Be responsive to review comments
5. **Backward compatibility** - Ensure existing functionality remains intact

## Areas for Contribution

We welcome contributions in these areas:

### Core Features
- New vector store backends (e.g., Pinecone, Weaviate)
- Enhanced YAML frontmatter schema support
- Improved incremental indexing algorithms
- Additional query filters and search capabilities
- Performance optimizations for large datalakes

### Integrations
- Additional MCP tools and capabilities
- New HTTP API endpoints
- Integration guides for other platforms
- VSCode extension development
- Browser extension development

### Documentation
- Improved README.md sections
- Additional usage examples and tutorials
- Architecture diagrams and flow charts
- Video walkthroughs
- API reference documentation

### Testing & Quality
- Increase test coverage
- Add performance benchmarks
- Integration tests for vector stores
- Load testing for HTTP server
- Cross-platform compatibility testing

### Developer Experience
- Better error messages and debugging
- Development containers (Docker)
- GitHub Actions CI/CD pipeline
- Pre-commit hooks and linting
- CLI command auto-completion

## Release Notes

When contributing features or behavior changes:

1. Update `CHANGELOG.md` with your changes
2. Follow the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format
3. Place changes in the `[Unreleased]` section
4. Use categories: Added, Changed, Deprecated, Removed, Fixed, Security

## Questions?

- Open a [GitHub Issue](https://github.com/ivannagy/prometh-cortex/issues) for general questions
- Check existing documentation in [README.md](README.md) and [CLAUDE.md](CLAUDE.md)
- Review [SECURITY.md](SECURITY.md) for security-related questions
- Join [GitHub Discussions](https://github.com/ivannagy/prometh-cortex/discussions) for community support

## Code of Conduct

This project adheres to the Contributor Covenant Code of Conduct. By participating, you are expected to uphold this code. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details.

## License

By contributing to Prometh Cortex, you agree that your contributions will be licensed under the Apache License 2.0.

## Recognition

Contributors will be recognized in:
- Project README.md contributors section
- Release notes for significant contributions
- GitHub contributor graphs

---

Thank you for helping make Prometh Cortex better!
