.PHONY: fixup lint format test ci docs-serve docs-build


install-deps:
	@echo "Installing dependencies..."
	@uv sync --all-packages --no-dev


install-dev-deps:
	@echo "Installing development dependencies..."
	@uv sync --all-packages --group dev


fixup:
	@echo "Fixing up..."
	@uv run --group dev ruff check . --fix
	@uv run --group dev ruff format .

typecheck:
	@echo "Typechecking"
	@uv run --group dev pyright .


lint:
	@echo "Linting with Ruff..."
	@uv run --group dev ruff check .

format:
	@echo "Formatting with Ruff..."
	@uv run --group dev ruff format .

test:
	@echo "Running tests..."
	@uv run --group dev pytest .

ci: lint format typecheck test

docs-serve:
	@echo "Serving docs..."
	@uv run --group dev mkdocs serve

docs-build:
	@echo "Building docs..."
	@uv run --group dev mkdocs build --strict

publish:
	@echo "Building the package..."
	@uv build --package assertive-mock-api-server
	@echo "Publishing to PyPI..."
	@uv publish --token $$PYPI_TOKEN
