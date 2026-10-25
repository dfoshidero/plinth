import pytest

from plinth import config as defaults
from plinth.model.loader import ConfigError, parse_config


def test_base_config_is_valid(config_dict):
    parse_config(config_dict)


def test_examples_are_valid(example):
    from plinth.model.loader import load_config

    load_config(example)


@pytest.mark.parametrize(
    ("architecture", "kinds", "valid"),
    [
        ("modular-monolith", ["modular-monolith"], True),
        ("modular-monolith", ["modular-monolith", "service"], False),
        ("modular-monolith", ["service"], False),
        ("microservices", ["service", "worker"], True),
        ("microservices", ["modular-monolith", "service"], False),
        ("hybrid", ["modular-monolith", "worker"], True),
        ("hybrid", ["modular-monolith"], False),
        ("hybrid", ["service", "worker"], False),
    ],
)
def test_architecture_rules(config_dict, architecture, kinds, valid):
    config_dict["project"]["architecture"] = architecture
    config_dict["applications"] = [{"name": f"app{i}", "kind": k} for i, k in enumerate(kinds)]
    if valid:
        parse_config(config_dict)
    else:
        with pytest.raises(ConfigError):
            parse_config(config_dict)


@pytest.mark.parametrize("name", ["Atlas", "1atlas", "at--las", "atlas-", "a", "x" * 31, "at_las"])
def test_bad_project_names_rejected(config_dict, name):
    config_dict["project"]["name"] = name
    with pytest.raises(ConfigError, match="project.name"):
        parse_config(config_dict)


@pytest.mark.parametrize("name", sorted(defaults.RESERVED_APP_NAMES))
def test_reserved_app_names_rejected(config_dict, name):
    config_dict["applications"][1]["name"] = name
    with pytest.raises(ConfigError, match="reserved"):
        parse_config(config_dict)


def test_duplicate_app_names_rejected(config_dict):
    config_dict["applications"][2]["name"] = "worker"
    with pytest.raises(ConfigError, match="duplicate"):
        parse_config(config_dict)


def test_worker_with_port_rejected(config_dict):
    config_dict["applications"][1]["port"] = 9000
    with pytest.raises(ConfigError, match="no HTTP port"):
        parse_config(config_dict)


def test_http_apps_get_default_port(config_dict):
    del config_dict["applications"][2]["port"]
    config = parse_config(config_dict)
    ports = {a.name: a.http_port for a in config.applications}
    assert ports["notifier"] == defaults.DEFAULT_PORT
    assert ports["api"] == defaults.DEFAULT_PORT
    assert ports["worker"] is None


@pytest.mark.parametrize("port", [0, 70000])
def test_out_of_range_port_rejected(config_dict, port):
    config_dict["applications"][2]["port"] = port
    with pytest.raises(ConfigError):
        parse_config(config_dict)


@pytest.mark.parametrize(
    "registry",
    [
        "https://ghcr.io/acme",
        "ghcr.io/acme/",
        "",
        "ghcr.io/YOUR_ACCOUNT",
        "ghcr.io/Acme",
        'ghcr.io/acme"x',
        "ghcr.io/ac me",
    ],
)
def test_bad_registry_rejected(config_dict, registry):
    config_dict["project"]["registry"] = registry
    with pytest.raises(ConfigError, match="registry"):
        parse_config(config_dict)


@pytest.mark.parametrize(
    "url",
    [
        "github.com/acme",
        "http://github.com/acme",
        "https://github.com/acme/",
        "https://github.com",
        "https://github.com/YOUR_ACCOUNT",
        'https://github.com/acme"x',
        "https://github.com/{{x}}",
    ],
)
def test_bad_git_base_url_rejected(config_dict, url):
    config_dict["project"]["gitBaseUrl"] = url
    with pytest.raises(ConfigError, match="gitBaseUrl"):
        parse_config(config_dict)


def test_release_environment_required(config_dict):
    config_dict["environments"] = [
        e for e in config_dict["environments"] if e != defaults.RELEASE_ENVIRONMENT
    ]
    with pytest.raises(ConfigError, match=defaults.RELEASE_ENVIRONMENT):
        parse_config(config_dict)


def test_duplicate_environments_rejected(config_dict):
    config_dict["environments"] = ["dev", "dev"]
    with pytest.raises(ConfigError, match="unique"):
        parse_config(config_dict)


def test_environments_default_when_omitted(config_dict):
    del config_dict["environments"]
    assert parse_config(config_dict).environments == list(defaults.DEFAULT_ENVIRONMENTS)


def test_unknown_keys_rejected(config_dict):
    config_dict["project"]["colour"] = "blue"
    with pytest.raises(ConfigError):
        parse_config(config_dict)


def test_non_mapping_rejected():
    with pytest.raises(ConfigError, match="mapping"):
        parse_config(["not", "a", "mapping"])


def test_error_message_names_the_field(config_dict):
    config_dict["project"]["name"] = "Bad"
    with pytest.raises(ConfigError) as exc:
        parse_config(config_dict, source="plinth.yaml")
    assert "plinth.yaml" in str(exc.value)
    assert "kebab-case (" in str(exc.value)


@pytest.mark.parametrize(
    "registry", ["ghcr.io/acme", "localhost:5000/team/app", "registry.gitlab.com/a-b/c_d"]
)
def test_good_registries_accepted(config_dict, registry):
    config_dict["project"]["registry"] = registry
    assert parse_config(config_dict).project.registry == registry
