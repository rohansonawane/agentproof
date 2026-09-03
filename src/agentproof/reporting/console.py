from __future__ import annotations

from rich.console import Console
from rich.table import Table

from agentproof.core.result import SuiteResult


def render_suite_result(result: SuiteResult, *, console: Console | None = None) -> None:
    output = console or Console()
    output.print("[bold]AgentProof[/bold]")
    output.print(
        f"{result.total_count} runs, {result.passed_count} passed, {result.failed_count} failed",
    )
    table = Table(show_header=True, header_style="bold")
    table.add_column("Run")
    table.add_column("Status")
    table.add_column("Severity")
    table.add_column("Failure")
    for item in result.results:
        failure_text = item.error_message or ", ".join(item.violated_invariants)
        table.add_row(item.name, item.status, item.severity, failure_text)
    output.print(table)
    for item in result.failures:
        output.print(f"\n[bold red]{item.status}[/bold red] {item.name}")
        if item.invariant_failures:
            for failure in item.invariant_failures:
                output.print(f"Invariant violated: {failure.name}")
                output.print(failure.message)
        if item.effects:
            output.print(f"Committed effects: {len(item.effects)}")
        if item.artifact_path:
            output.print(f"Reproduce: agentproof replay {item.artifact_path}")
        output.print(f"Seed: {item.seed}")
