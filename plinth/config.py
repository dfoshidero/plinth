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

# wizard defaults; the placeholder must be replaced before a config validates
PLACEHOLDER = "YOUR_"
DEFAULT_REGISTRY = "ghcr.io/YOUR_ACCOUNT"
DEFAULT_GIT_BASE_URL = {
    "github": "https://github.com/YOUR_ACCOUNT",
    "gitlab": "https://gitlab.com/YOUR_GROUP",
    "generic": "https://git.example.com/YOUR_GROUP",
}

# user name paired with a token for HTTPS git pushes from CI
GIT_TOKEN_USER = {"github": "x-access-token", "gitlab": "oauth2", "generic": "git"}

# registries whose CI login is built in (no registry secrets needed)
BUILTIN_REGISTRY = {"github": "ghcr.io", "gitlab": "registry.gitlab.com"}

# cluster secrets that scripts/bootstrap-local.sh creates when credentials are given
IMAGE_PULL_SECRET = "registry-credentials"
REPO_CREDS_SECRET = "plinth-repo-creds"

# branch in every generated repo holding plinth's untouched output; `plinth update` merges it
TEMPLATE_BRANCH = "plinth"
RELEASE_PUSH_ATTEMPTS = 5

# pinned tool versions
PYTHON_VERSION = "3.14"
PYTHON_IMAGE = f"python:{PYTHON_VERSION}-slim"
DOCKER_IMAGE = "docker:29"
CHECKOUT_ACTION = "actions/checkout@v7"
SETUP_PYTHON_ACTION = "actions/setup-python@v7"
ARGO_CD_CHART_VERSION = "10.11.1"  # ships Argo CD 3.5.6
