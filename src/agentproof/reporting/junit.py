from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from agentproof.core.result import SuiteResult


def write_junit_report(result: SuiteResult, path: str | Path) -> None:
    testsuite = ET.Element(
        "testsuite",
        {
            "name": "agentproof",
            "tests": str(result.total_count),
            "failures": str(
                len(
                    [
                        item
                        for item in result.results
                        if item.status in {"INVARIANT_FAILURE", "BASELINE_FAILURE"}
                    ]
                )
            ),
            "errors": str(
                len(
                    [
                        item
                        for item in result.results
                        if item.status
                        in {"AGENT_ERROR", "TEST_ERROR", "ADAPTER_ERROR", "UNSUPPORTED"}
                    ]
                )
            ),
            "skipped": str(len([item for item in result.results if item.status == "SKIPPED"])),
        },
    )
    for item in result.results:
        testcase = ET.SubElement(
            testsuite,
            "testcase",
            {
                "classname": f"agentproof.{item.scenario}",
                "name": item.name,
            },
        )
        message = item.error_message or ",".join(item.violated_invariants)
        body = _trace_body(item)
        if item.status in {"INVARIANT_FAILURE", "BASELINE_FAILURE"}:
            failure = ET.SubElement(testcase, "failure", {"message": message or item.status})
            failure.text = body
        elif item.status in {"AGENT_ERROR", "TEST_ERROR", "ADAPTER_ERROR", "UNSUPPORTED"}:
            error = ET.SubElement(testcase, "error", {"message": message or item.status})
            error.text = body
        elif item.status == "SKIPPED":
            ET.SubElement(testcase, "skipped", {"message": message or "skipped"})
    tree = ET.ElementTree(testsuite)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _trace_body(item: object) -> str:
    trace = getattr(item, "trace", [])
    lines = []
    for event in trace:
        lines.append(f"{event.seq} {event.kind} {event.name} {event.data}")
    return "\n".join(lines)
