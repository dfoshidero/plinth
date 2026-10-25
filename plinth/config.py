"""Defaults and pinned versions used across the schema, wizard and blueprints.

Change a value here and every generated file picks it up. Templates read this
module as `defaults`.
"""

from __future__ import annotations

CONFIG_FILENAME = "plinth.yaml"
REPO_METADATA_FILENAME = ".plinth.yaml"

# naming
NAME_MIN_LEN = 2
NAME_MAX_LEN = 30
RESERVED_APP_NAMES = frozenset(("app", "gitops"))

# applications
DEFAULT_PORT = 8000
SERVICE_PORT = 80
HEALTH_PATH = "/health"
WORKER_INTERVAL_SECONDS = 30
RESOURCES = {
    "requests": {"cpu": "250m", "memory": "256Mi"},
    "limits": {"cpu": "1", "memory": "512Mi"},
}

# environments
DEFAULT_ENVIRONMENTS = ("dev", "production")
RELEASE_ENVIRONMENT = "dev"  # CI releases here; other environments are promoted by hand
REPLICAS = {"dev": 1, "production": 2}
DEFAULT_REPLICAS = 1

# wizard defaults
DEFAULT_REGISTRY = "ghcr.io/YOUR_ACCOUNT"
DEFAULT_GIT_BASE_URL = {
    "github": "https://github.com/YOUR_ACCOUNT",
    "gitlab": "https://gitlab.com/YOUR_GROUP",
    "generic": "https://git.example.com/YOUR_GROUP",
}

# user name paired with a token for HTTPS git pushes from CI
GIT_TOKEN_USER = {"github": "x-access-token", "gitlab": "oauth2", "generic": "git"}

# pinned tool versions
PYTHON_IMAGE = "python:3.12-slim"
GIT_IMAGE = "alpine:3.22"
DOCKER_IMAGE = "docker:28"
DAGGER_VERSION = "0.21.11"
DAGGER_GITHUB_ACTION = "dagger/dagger-for-github@v8"
CHECKOUT_ACTION = "actions/checkout@v5"
ARGO_CD_CHART_VERSION = "10.10.5"  # ships Argo CD 3.5.6
