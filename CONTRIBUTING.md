# Contributing to Word2Sentence

Thanks for helping improve Word2Sentence. Contributions can include bug reports, UX proposals, localization, documentation, tests, and code.

## Before you start

1. Search existing issues before opening a new one.
2. For substantial behavior, data-format, AI-prompt, or scheduler changes, open a design issue first.
3. Never commit API keys, learner data, generated `wordbook.json` files, or model responses containing private text.

## Development setup

Requirements:

- Windows 10/11;
- .NET 10 SDK;
- optional `OR_KEY` user environment variable for live AI tests.

```powershell
dotnet restore .\Word2Sentence.slnx
dotnet build .\Word2Sentence.slnx -c Release --no-restore
dotnet run --project .\Word2Sentence.AlgorithmChecks\Word2Sentence.AlgorithmChecks.csproj -c Release --no-build
```

Use `WORD2SENTENCE_DATA_DIR` when testing workflows that write data:

```powershell
$env:WORD2SENTENCE_DATA_DIR = "$PWD\work\local-profile"
dotnet run --project .\Word2Sentence\Word2Sentence.csproj
```

## Pull-request expectations

- Keep changes focused and preserve the existing Fluent desktop visual language.
- Add both English and Simplified Chinese strings for user-visible UI.
- Keep target-language logic Unicode-safe; do not reintroduce ASCII-only validation.
- Add or update checks for behavior changes.
- Build with zero warnings.
- Do not expose the usage card before sentence submission.
- Do not add learner self-rating controls.

## Scheduler changes

`ReviewScheduler.cs` is expected to conform to `py-fsrs 6.3.1` reference behavior. A scheduling pull request must include at least one of:

- upstream reference vectors;
- a documented FSRS version migration;
- time-split held-out evaluation with log loss, Brier score, and calibration results.

Hand-tuned interval thresholds or multipliers are not accepted without empirical validation.

## Commit style

Use short imperative subjects, for example:

```text
Add English localization resources
Fix target-evidence reconciliation
Document FSRS reference vectors
```

## Reporting security problems

Do not disclose secrets or private learner data in a public issue. Follow [SECURITY.md](SECURITY.md).
