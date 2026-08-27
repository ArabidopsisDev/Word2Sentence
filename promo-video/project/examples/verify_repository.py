from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


EXAMPLES = Path(__file__).resolve().parent
REPOSITORY = EXAMPLES.parents[2]
PROOFS = json.loads((EXAMPLES / "feature-proofs.json").read_text(encoding="utf-8"))


def verify_sources() -> None:
    for relative, snippets in PROOFS.items():
        source = REPOSITORY / relative
        text = source.read_text(encoding="utf-8-sig")
        for snippet in snippets:
            if snippet not in text:
                raise RuntimeError(f"missing source proof in {relative}: {snippet}")
    print("WORD2SENTENCE_SOURCE_PROOFS_OK")


def run(command: list[str]) -> str:
    environment = os.environ.copy()
    environment["DOTNET_CLI_UI_LANGUAGE"] = "en-US"
    environment["DOTNET_NOLOGO"] = "1"
    completed = subprocess.run(
        command,
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        check=False,
    )
    output = completed.stdout + completed.stderr
    if completed.returncode:
        raise RuntimeError(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--algorithm", action="store_true")
    args = parser.parse_args()
    verify_sources()
    if args.build:
        output = run(["dotnet", "build", "Word2Sentence.slnx", "-c", "Release"])
        print(output)
        print("已成功生成")
    if args.algorithm:
        run(["dotnet", "build", "Word2Sentence.slnx", "-c", "Release"])
        output = run([
            "dotnet",
            "run",
            "--project",
            "Word2Sentence.AlgorithmChecks/Word2Sentence.AlgorithmChecks.csproj",
            "-c",
            "Release",
            "--no-build",
        ])
        print(output)


if __name__ == "__main__":
    main()
