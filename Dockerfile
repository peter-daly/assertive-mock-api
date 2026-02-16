########
# BASE #
########
FROM python:3.12-slim AS base

# Use Bash Strict Mode
SHELL ["/bin/bash", "-euo", "pipefail", "-c"]

ENV \
    # Set work directory
    WORKDIR=/app \
    UV_PROJECT_ENVIRONMENT=/venv/app \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    # uv config
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

ENV \
    PYTHONPATH=${WORKDIR} \
    # Add venv to PATH
    PATH=${UV_PROJECT_ENVIRONMENT}/bin:${PATH}

WORKDIR ${WORKDIR}

RUN \
    # Create venv
    python -m venv ${UV_PROJECT_ENVIRONMENT}

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

FROM base AS dependency_builder
WORKDIR /builder

RUN \
    apt-get update \
    && apt-get install --no-install-recommends -y \
    # Install common dependencies
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN \
    --mount=type=bind,source=pyproject.toml,target=/builder/pyproject.toml \
    --mount=type=bind,source=server/pyproject.toml,target=/builder/server/pyproject.toml \
    --mount=type=bind,source=server/assertive_mock_api_server,target=/builder/server/assertive_mock_api_server \
    --mount=type=bind,source=client/pyproject.toml,target=/builder/client/pyproject.toml \
    --mount=type=bind,source=uv.lock,target=/builder/uv.lock \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package assertive-mock-api-server --no-editable

FROM base AS prod

# Copy Python packages and executables
COPY \
    --from=dependency_builder \
    ${UV_PROJECT_ENVIRONMENT} ${UV_PROJECT_ENVIRONMENT}


# Copy full application source
COPY ./pyproject.toml ./uv.lock ${WORKDIR}/
COPY ./server/pyproject.toml ${WORKDIR}/server/pyproject.toml
COPY ./client/pyproject.toml ${WORKDIR}/client/pyproject.toml
COPY ./server/assertive_mock_api_server ${WORKDIR}/server/assertive_mock_api_server

WORKDIR ${WORKDIR}

ENTRYPOINT [ "python", "-m", "assertive_mock_api_server" ]
