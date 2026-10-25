# plinth

Generate ready-to-push application and GitOps repositories from one config file.

plinth turns a short `plinth.yaml` into git repositories with working application code, a
[Dagger](https://dagger.io) CI pipeline, [Score](https://score.dev) workload specs, and an
[Argo CD](https://argo-cd.readthedocs.io) GitOps repository that deploys them. Start as a
modular monolith, a set of microservices or a hybrid of both, in one repo or one repo per app,
and grow later with `plinth add`.

## Install

```sh
uv tool install plinth-cli      # or: pipx install plinth-cli
plinth --version
```

The PyPI package is `plinth-cli`; the command is `plinth`. Requires Python 3.12+.

## Quick start

Answer a few questions:

```sh
plinth project
```

or write a config and generate from it:

```yaml
# plinth.yaml
project:
  name: atlas
  architecture: hybrid          # modular-monolith | microservices | hybrid
  layout: monorepo              # monorepo | split-repo
  gitProvider: github           # github | gitlab | generic
  gitBaseUrl: https://github.com/acme
  registry: ghcr.io/acme
applications:
  - {name: api, kind: modular-monolith}
  - {name: worker, kind: worker}
  - {name: notifier, kind: service, port: 8081}
environments: [dev, production]
```

```sh
plinth validate --config plinth.yaml
plinth generate --config plinth.yaml --output .
```

This writes `./atlas/` containing one folder per repository, each initialised with git, an
initial commit and an `origin` remote under `gitBaseUrl`. Create the empty repositories on your
git host and push.

More configs live in [`examples/`](examples/): every architecture with both layouts.

## What you get

**Application repositories** (one for a monorepo, one per app for split-repo):

- a small, dependency-free Python app per workload with a `/health` endpoint (services and the
  monolith) or a run loop (workers), plus tests; replace it with your own code
- a `Dockerfile` and a `score.yaml` describing how the workload runs
- a Dagger module (`.dagger/`) with `test`, `build` and `ship` functions that run identically on
  your laptop and in CI
- a CI file for your provider (`.github/workflows/ci.yaml` or `.gitlab-ci.yml`) that tests pull
  requests and ships `main`

**A GitOps repository:**

- an Argo CD app-of-apps (`bootstrap/root.yaml`) and one ApplicationSet per environment
- a Helm chart that deploys any workload straight from its `score.yaml`
- per-environment values, and `release.yaml` files written by CI on every ship
- `scripts/bootstrap-local.sh` to run everything on a local [k3d](https://k3d.io) cluster

The flow: push to `main` → CI tests, builds and pushes images tagged with the commit → CI writes
`environments/dev/<workload>/release.yaml` → Argo CD deploys it. Promote by copying a
`release.yaml` to another environment.

## Grow a project

Add a service or worker to a generated project:

```sh
cd atlas
plinth add service billing --port 8090
plinth add worker mailer
```

plinth creates the new workload's files (and a new repository for split-repo layouts) and
updates `plinth.yaml`. Adding to a modular monolith turns it into a hybrid. Existing files are
never overwritten; any that plinth would now generate differently are listed for you to review.

## Commands

| Command | What it does |
|---|---|
| `plinth project [--output DIR]` | interactive questions, then generate |
| `plinth validate --config FILE` | check a config and show the repositories it produces |
| `plinth generate --config FILE --output DIR [--dry-run]` | write the repositories |
| `plinth add {service,worker} NAME [--port N]` | add a workload to an existing project |

`--no-git` skips `git init` and the initial commit.

## Configuration

| Key | Notes |
|---|---|
| `project.name` | kebab-case, 2-30 chars; prefixes every repository name |
| `project.architecture` | `modular-monolith` (one monolith), `microservices` (services/workers only), `hybrid` (one monolith plus services/workers) |
| `project.layout` | `monorepo` (`<name>-app` holds every workload) or `split-repo` (`<name>-<app>` each) |
| `project.gitProvider` | picks the CI file; `generic` generates none |
| `project.gitBaseUrl` | `https://host/org` the repositories live under |
| `project.registry` | `host/path` images are pushed to |
| `applications[]` | `name`, `kind` (`modular-monolith`, `service`, `worker`), optional `port` for HTTP kinds |
| `environments` | must include `dev`, which CI releases to |

Defaults and pinned tool versions are in [`plinth/config.py`](plinth/config.py).

## When not to use plinth

- You only need a single repository from a template: [Copier](https://copier.readthedocs.io)
  or [Cookiecutter](https://cookiecutter.readthedocs.io) are simpler, and Copier can update
  projects later.
- You already run [Backstage](https://backstage.io): its software templates fit better there.
- You don't deploy to Kubernetes: the GitOps half won't help you.

plinth generates once. It does not keep generated repositories in sync with newer templates;
after generation the code is yours.

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Templates live in [`plinth/blueprints/`](plinth/blueprints/). Files ending in `.j2` are rendered
with Jinja; path segments starting with `dot-` are written with a leading `.`.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first; in short, open an
issue before large changes, and every contribution must be written by a human (no AI-generated
code or text).

## License

[MIT](LICENSE)
