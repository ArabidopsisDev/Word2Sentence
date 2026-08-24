# Security policy

## Sensitive data

Word2Sentence stores learner content locally and sends individual exercises to the configured OpenRouter model. Reports must not include:

- `OR_KEY` values;
- real `wordbook.json` files;
- private learner sentences or notes;
- full HTTP authorization headers.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting feature when it is available for the repository. If private reporting is unavailable, contact the maintainer privately before opening a public issue.

Include affected versions, reproduction steps, impact, and the smallest non-sensitive example possible.
