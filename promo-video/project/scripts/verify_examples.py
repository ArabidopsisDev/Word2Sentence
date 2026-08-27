#!/usr/bin/env python3
"""Run language-neutral example verification commands without invoking a shell."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


PLACEHOLDER = re.compile(r"\[\s*(?:REPLACE|TODO)[^\]]*\]|__REPLACE__|TBD|待替换|待填写", re.IGNORECASE)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    spec_path = (args.spec or root / "project" / "examples" / "verification.json").resolve()
    report_path = (args.report or root / "project" / "docs" / "EXAMPLE_QA.json").resolve()
    errors: list[dict] = []
    results: list[dict] = []
    if not spec_path.is_file():
        errors.append({"kind": "spec-missing", "message": "example verification spec is missing", "path": str(spec_path)})
        spec: dict = {}
    else:
        raw = spec_path.read_text(encoding="utf-8-sig")
        if PLACEHOLDER.search(raw):
            errors.append({"kind": "placeholder", "message": "example verification spec contains placeholders", "path": str(spec_path)})
        spec = json.loads(raw)

    runs = spec.get("runs", []) if isinstance(spec, dict) else []
    exceptions = spec.get("documented_exceptions", []) if isinstance(spec, dict) else []
    if not isinstance(runs, list) or not isinstance(exceptions, list) or (not runs and not exceptions):
        errors.append({"kind": "empty", "message": "verification needs at least one executable run or documented preview exception"})
        runs = runs if isinstance(runs, list) else []
        exceptions = exceptions if isinstance(exceptions, list) else []

    for offset, item in enumerate(runs, 1):
        if not isinstance(item, dict):
            errors.append({"kind": "run-type", "message": "run entry must be an object", "run": offset})
            continue
        run_id = str(item.get("id", f"run-{offset}"))
        proof_ids = item.get("proof_ids")
        source_files = item.get("source_files")
        if not isinstance(proof_ids, list) or not proof_ids or not all(isinstance(value, str) and value for value in proof_ids):
            errors.append({"kind": "proof-links", "message": "run must list the proof ids it verifies", "run": run_id})
            proof_ids = []
        if not isinstance(source_files, list) or not source_files:
            errors.append({"kind": "source-links", "message": "run must list source files used by the visible proofs", "run": run_id})
            source_files = []
        source_hashes: dict[str, str] = {}
        examples_root = (root / "project" / "examples").resolve()
        for source_value in source_files:
            source = Path(str(source_value))
            source = source if source.is_absolute() else root / source
            source = source.resolve()
            if examples_root != source and examples_root not in source.parents:
                errors.append({"kind": "source-scope", "message": "verified source must stay under project/examples", "run": run_id, "path": str(source)})
            elif not source.is_file():
                errors.append({"kind": "source-missing", "message": "verified source file is missing", "run": run_id, "path": str(source)})
            else:
                source_hashes[str(source.relative_to(root)).replace("\\", "/")] = digest(source)
        command = item.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(value, str) and value for value in command):
            errors.append({"kind": "command", "message": "command must be a non-empty argument list", "run": run_id})
            continue
        cwd_value = str(item.get("cwd", "."))
        cwd = Path(cwd_value)
        cwd = cwd if cwd.is_absolute() else root / cwd
        if not cwd.is_dir():
            errors.append({"kind": "cwd", "message": "verification working directory is missing", "run": run_id, "path": str(cwd)})
            continue
        timeout = float(item.get("timeout_seconds", 120))
        expected_exit = int(item.get("expected_exit", 0))
        environment = os.environ.copy()
        for key, value in dict(item.get("env", {})).items():
            environment[str(key)] = str(value)
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=False,
                check=False,
            )
            passed = completed.returncode == expected_exit
            missing_stdout = [value for value in item.get("stdout_contains", []) if str(value) not in completed.stdout]
            missing_stderr = [value for value in item.get("stderr_contains", []) if str(value) not in completed.stderr]
            passed = passed and not missing_stdout and not missing_stderr and "�" not in completed.stdout + completed.stderr
            result = {
                "id": run_id,
                "command": command,
                "cwd": str(cwd),
                "expected_exit": expected_exit,
                "actual_exit": completed.returncode,
                "missing_stdout": missing_stdout,
                "missing_stderr": missing_stderr,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "status": "pass" if passed else "fail",
                "proof_ids": proof_ids,
                "source_sha256": source_hashes,
            }
            results.append(result)
            if not passed:
                errors.append({"kind": "run-failed", "message": "example verification did not match expectations", "run": run_id})
        except subprocess.TimeoutExpired:
            errors.append({"kind": "timeout", "message": "example verification timed out", "run": run_id, "seconds": timeout})

    verified_exceptions: list[dict] = []
    for offset, item in enumerate(exceptions, 1):
        if not isinstance(item, dict):
            errors.append({"kind": "exception-type", "message": "documented exception must be an object", "entry": offset})
            continue
        exception_id = str(item.get("id", f"exception-{offset}"))
        if item.get("kind") != "preview-only":
            errors.append({"kind": "exception-kind", "message": "only preview-only examples may skip execution", "entry": exception_id})
        for key in ("reason", "required_environment", "official_source"):
            value = str(item.get(key, "")).strip()
            if len(value) < 8 or PLACEHOLDER.search(value):
                errors.append({"kind": "exception-field", "message": "preview exception needs concrete evidence", "entry": exception_id, "field": key})
        if item.get("official_source") and not str(item["official_source"]).startswith("http"):
            errors.append({"kind": "exception-source", "message": "preview exception source must be an official URL", "entry": exception_id})
        proof_ids = item.get("proof_ids")
        source_files = item.get("source_files")
        if not isinstance(proof_ids, list) or not proof_ids:
            errors.append({"kind": "proof-links", "message": "preview exception must list proof ids", "entry": exception_id})
            proof_ids = []
        if not isinstance(source_files, list) or not source_files:
            errors.append({"kind": "source-links", "message": "preview exception must list source files", "entry": exception_id})
            source_files = []
        source_hashes: dict[str, str] = {}
        examples_root = (root / "project" / "examples").resolve()
        for source_value in source_files:
            source = Path(str(source_value))
            source = source if source.is_absolute() else root / source
            source = source.resolve()
            if examples_root != source and examples_root not in source.parents:
                errors.append({"kind": "source-scope", "message": "preview source must stay under project/examples", "entry": exception_id, "path": str(source)})
            elif not source.is_file():
                errors.append({"kind": "source-missing", "message": "preview source file is missing", "entry": exception_id, "path": str(source)})
            else:
                source_hashes[str(source.relative_to(root)).replace("\\", "/")] = digest(source)
        verified_exceptions.append({**item, "proof_ids": proof_ids, "source_sha256": source_hashes})

    report = {
        "spec": str(spec_path),
        "spec_sha256": digest(spec_path) if spec_path.is_file() else None,
        "runs": results,
        "documented_exceptions": verified_exceptions,
        "errors": errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
