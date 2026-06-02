# Contributing to NexusAgent

> Thank you for contributing! This guide covers everything you need to know.

---

## Getting Started

### Prerequisites

- **Python 3.10+** (3.12 recommended)
- **Git**
- A working GGUF model or cloud API keys for testing

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/nexus-agent/nexus-agent.git
cd nexus-agent

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\Activate.ps1  # Windows

# Install in editable mode with all extras
pip install -e ".[all]"

# Verify installation
nexus --version
nexus hardware
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/nexus_agent/memory/test_memory.py -v

# Run with coverage
python -m pytest tests/ --cov=src/nexus_agent --cov-report=html
```

---

## Project Structure

```
src/nexus_agent/       # All source code (installed as package)
tests/                 # Test suite
docs/                  # Documentation
config/                # Default YAML configuration
```

**Key rules:**
- All source code lives under `src/nexus_agent/`
- Tests mirror the source tree under `tests/nexus_agent/`
- No TypeScript, Go, or Rust (Python only unless approved)

---

## Code Style

We use `ruff` for linting and formatting. Configuration is in `pyproject.toml`.

```bash
# Check code
python -m ruff check src/

# Format code
python -m ruff format src/
```

**Style rules:**
- Line length: 100 characters
- Target Python: 3.10+
- Lint rules: `E, F, I, N, W, UP` (ruff)
- Type checking: `mypy src/nexus_agent/` (strict mode)
- **No bare `except Exception`** — always catch specific exceptions
- **No `shell=True`** in subprocess calls
- Docstrings for all public classes and functions

---

## Type Annotations

NexusAgent uses strict type checking with mypy. All new code must include type annotations.

```python
def process_files(paths: list[str], verbose: bool = False) -> dict[str, bool]:
    """Process a list of files.
    
    Args:
        paths: List of file paths to process.
        verbose: If True, print progress to stdout.
    
    Returns:
        Dict mapping file path to success boolean.
    """
    ...
```

---

## Adding a New LLM Provider

1. Create `src/nexus_agent/llm/providers/myprovider_provider.py`
2. Extend `LLMProvider` from `llm/base.py`
3. Implement `name`, `get_capabilities()`, and `chat_completion()`
4. Add tests in `tests/nexus_agent/llm/test_providers.py`
5. Register in `llm/providers/__init__.py` and `llm/providers/factory.py`
6. Update docs (`docs/API.md`, `docs/CONTEXT.md`)

Example skeleton:

```python
from nexus_agent.llm.base import LLMProvider, Message, Role, ToolDefinition

class MyProvider(LLMProvider):
    def __init__(self, config: dict[str, Any]):
        self._config = config
        self._api_key = config.get("api_key") or os.environ.get("MY_API_KEY")
    
    @property
    def name(self) -> str:
        return "myprovider"
    
    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tool_calling=True,
            supports_streaming=True,
            supports_vision=False,
        )
    
    def chat_completion(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        **kwargs
    ) -> LLMResponse:
        # Implementation
        ...
```

---

## Adding a New Tool

1. Create a class in `src/nexus_agent/tools/` extending `Tool`
2. Register in the appropriate tool list in `core/agent.py`
3. Add tests

```python
from nexus_agent.tools.base import Tool, ToolResult

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "Does something useful"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "arg1": {"type": "string", "description": "The input"}
            },
            "required": ["arg1"]
        }
    
    def execute(self, arg1: str, **kwargs) -> ToolResult:
        # Implementation
        return ToolResult(success=True, output="result")
```

---

## Writing Tests

- Place tests in `tests/nexus_agent/<module>/test_<component>.py`
- Use `unittest.TestCase` or `pytest` fixtures
- Mock external services (HTTP calls, file system, etc.)
- Aim for >80% coverage on new code

```python
import unittest
from unittest.mock import MagicMock, patch
from nexus_agent.tools.my_tool import MyTool

class TestMyTool(unittest.TestCase):
    def test_execute_success(self):
        tool = MyTool()
        result = tool.execute(arg1="hello")
        self.assertTrue(result.success)
```

---

## Documentation

- Update `docs/CONTEXT.md` when adding new modules or changing architecture
- Update `docs/MEMORY.md` with implementation decisions
- Public APIs should have docstrings

---

## Git Workflow

### Branch Naming

```
feature/add-ollama-provider
fix/memory-leak-in-context
refactor/agent-loop-split
docs/api-reference-update
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(memory): add FTS5 full-text search to long-term memory
fix(sandbox): prevent command injection via unquoted variables
refactor(agent): extract _execute_tool into standalone method
docs: update CONTEXT.md with Phase C completion status
test(providers): add Google Gemini provider tests
```

### Pull Request Checklist

- [ ] Tests pass (`python -m pytest tests/`)
- [ ] Lint clean (`ruff check src/`)
- [ ] Type check clean (`mypy src/nexus_agent/`)
- [ ] New public APIs have docstrings
- [ ] `docs/CONTEXT.md` updated for new modules
- [ ] No secrets or keys in diff

---

## Reporting Issues

- Search existing issues before creating new ones
- Include `nexus --version` output and relevant logs
- For bugs: OS, Python version, GPU model, model file used
- For feature requests: describe the problem you want solved, not just the solution

---

## Code of Conduct

Be respectful. We follow the [Python Community Code of Conduct](https://www.python.org/psf/codeofconduct/).