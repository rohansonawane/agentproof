from __future__ import annotations

import importlib.util
import sys
from contextlib import suppress
from pathlib import Path
from types import ModuleType

import click
from rich.console import Console

from agentproof.api import AgentTest
from agentproof.core.faults import MutationSpec, Severity
from agentproof.mutations import MUTATION_TYPES, mutation_from_spec
from agentproof.replay.player import replay_artifact_sync
from agentproof.reporting.console import render_suite_result
from agentproof.reporting.json_report import write_json_report
from agentproof.reporting.junit import write_junit_report


@click.group()
def main() -> None:
    """AgentProof command line interface."""


@main.command()
@click.option("--force", is_flag=True, help="Overwrite existing scaffold files.")
def init(force: bool) -> None:
    files = {
        "agentproof.toml": '[agentproof]\nseed = 42\nrepetitions = 1\nfail_on = "high"\n',
        "tests/agentproof/.gitkeep": "",
    }
    for raw_path, content in files.items():
        path = Path(raw_path)
        if path.exists() and not force:
            raise click.ClickException(f"{path} already exists; use --force to overwrite")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    Path(".agentproof").mkdir(mode=0o700, exist_ok=True)
    click.echo("Initialized AgentProof files.")


@main.command(name="mutations")
def list_mutations() -> None:
    for name, cls in sorted(MUTATION_TYPES.items()):
        stability = "stable" if cls.stable else "experimental"
        click.echo(f"{name}\t{stability}\t{cls.description}")


@main.command()
@click.argument("path", required=False, default=".")
@click.option("--scenario", "scenario_name", default=None, help="Run only one scenario.")
@click.option(
    "--mutation",
    "mutation_value",
    default=None,
    help="Run only one mutation, optionally type:target.",
)
@click.option("--seed", default=42, type=int, show_default=True)
@click.option(
    "--fail-on",
    type=click.Choice(["low", "medium", "high", "critical"]),
    default="high",
    show_default=True,
)
@click.option("--json", "json_path", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--junit", "junit_path", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--no-color", is_flag=True)
def run(
    path: str,
    scenario_name: str | None,
    mutation_value: str | None,
    seed: int,
    fail_on: Severity,
    json_path: Path | None,
    junit_path: Path | None,
    no_color: bool,
) -> None:
    suites = _load_suites(Path(path))
    if not suites:
        raise click.ClickException(f"no AgentTest suites found under {path}")
    mutation_override = [_parse_mutation(mutation_value)] if mutation_value else None
    aggregate = None
    exit_code = 0
    for source_path, suite_name, suite in suites:
        result = suite.run_sync(
            scenario=scenario_name,
            mutations=mutation_override,
            mutation_name=None,
            seed=seed,
            source_path=str(source_path),
            suite_name=suite_name,
        )
        aggregate = result
        render_suite_result(result, console=Console(no_color=no_color))
        exit_code = max(exit_code, result.exit_code(fail_on))
    if aggregate is not None and json_path is not None:
        write_json_report(aggregate, json_path)
    if aggregate is not None and junit_path is not None:
        write_junit_report(aggregate, junit_path)
    raise SystemExit(exit_code)


@main.command()
@click.argument("artifact", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--fail-on",
    type=click.Choice(["low", "medium", "high", "critical"]),
    default="high",
    show_default=True,
)
def replay(artifact: Path, fail_on: Severity) -> None:
    result = replay_artifact_sync(artifact)
    render_suite_result(result)
    raise SystemExit(result.exit_code(fail_on))


@main.command()
def doctor() -> None:
    click.echo(f"Python: {sys.version.split()[0]}")
    for module in ("agents", "langchain", "langgraph"):
        try:
            imported = __import__(module)
        except Exception as exc:
            click.echo(f"{module}: unavailable ({exc})")
        else:
            version = getattr(imported, "__version__", "installed")
            click.echo(f"{module}: {version}")
    Path(".agentproof").mkdir(mode=0o700, exist_ok=True)
    click.echo(".agentproof: writable")


def _parse_mutation(value: str) -> object:
    mutation_type, _, target = value.partition(":")
    severity: Severity = (
        "high" if mutation_type in {"timeout_after_commit", "duplicate_user_request"} else "medium"
    )
    spec = MutationSpec(type=mutation_type, target=target or None, severity=severity)
    return mutation_from_spec(spec)


def _load_suites(path: Path) -> list[tuple[Path, str, AgentTest]]:
    source_files = [path] if path.is_file() else sorted(path.rglob("*.py"))
    suites: list[tuple[Path, str, AgentTest]] = []
    for source in source_files:
        if any(part.startswith(".") for part in source.parts):
            continue
        module = _load_module(source)
        for name, value in vars(module).items():
            if isinstance(value, AgentTest):
                suites.append((source, name, value))
    return suites


def _load_module(path: Path) -> ModuleType:
    module_name = f"agentproof_cli_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise click.ClickException(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        with suppress(ValueError):
            sys.path.remove(str(path.parent))
    return module


if __name__ == "__main__":
    main()
