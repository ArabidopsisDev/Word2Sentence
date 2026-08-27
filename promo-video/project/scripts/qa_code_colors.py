from __future__ import annotations

import hashlib
import json
from pathlib import Path

from project_digest import content_digest
from render_common import (
    BLUE,
    COMMENT,
    METHOD,
    NUMBER,
    STRING,
    TYPE,
    code_tokens,
    draw_code,
    make_context,
    semantic_spans,
)


ROOT = Path(__file__).resolve().parents[2]
COLORS = {
    "keyword": BLUE,
    "type": TYPE,
    "method": METHOD,
    "number": NUMBER,
    "string": STRING,
    "comment": COMMENT,
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def builtin_fixture(language: str) -> tuple[str, list[dict]]:
    if language in {"csharp", "cs"}:
        return (
            'public class Demo { string s = "text"; int n = 42; Run(); } // note',
            [
                {"token": "public", "kind": "keyword"},
                {"token": "Demo", "kind": "type"},
                {"token": '"text"', "kind": "string"},
                {"token": "42", "kind": "number"},
                {"token": "Run", "kind": "method"},
                {"token": "// note", "kind": "comment"},
            ],
        )
    if language in {"cpp", "c++"}:
        return (
            'auto value = std::string("Astra"); Run(42); // note',
            [
                {"token": "auto", "kind": "keyword"},
                {"token": "string", "kind": "type"},
                {"token": '"Astra"', "kind": "string"},
                {"token": "42", "kind": "number"},
                {"token": "Run", "kind": "method"},
                {"token": "// note", "kind": "comment"},
            ],
        )
    raise ValueError(f"no builtin fixture for {language}")


def main() -> int:
    config = json.loads((ROOT / "project" / "config.json").read_text(encoding="utf-8"))
    code_config = config.get("code", {})
    language = str(code_config.get("language", "csharp")).lower()
    lexer = str(code_config.get("lexer", "builtin"))
    errors: list[dict] = []
    if lexer == "builtin":
        try:
            text, checks = builtin_fixture(language)
            spans = None
            colored = code_tokens(text, language)
        except ValueError as exc:
            text, checks, spans, colored = "", [], None, []
            errors.append({"kind": "fixture-language", "message": str(exc)})
    elif lexer == "explicit-spans":
        fixture_path = ROOT / "project" / "content" / "code-color-fixture.json"
        if not fixture_path.is_file():
            text, checks, spans, colored = "", [], None, []
            errors.append({"kind": "fixture-missing", "message": "explicit-span lexer requires project/content/code-color-fixture.json"})
        else:
            fixture = json.loads(fixture_path.read_text(encoding="utf-8-sig"))
            text = str(fixture.get("text", ""))
            checks = list(fixture.get("checks", []))
            spans = list(fixture.get("spans", []))
            colored = semantic_spans(text, language, spans)
    else:
        text, checks, spans, colored = "", [], None, []
        errors.append({"kind": "lexer", "message": f"unsupported lexer mode: {lexer}"})

    results = []
    for check in checks:
        token = str(check.get("token", ""))
        kind = str(check.get("kind", ""))
        expected = COLORS.get(kind)
        actual = next((color for value, color in colored if value == token), None)
        passed = expected is not None and actual == expected
        results.append(
            {
                "token": token,
                "kind": kind,
                "expected_rgba": list(expected) if expected else None,
                "actual_rgba": list(actual) if actual else None,
                "status": "pass" if passed else "fail",
            }
        )
        if not passed:
            errors.append({"kind": "color-mismatch", "message": "semantic token color differs from the required palette", "token": token, "semantic_kind": kind})

    image_path = ROOT / "renders" / "code-color-fixture.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    if text:
        scene = {"start": 0.0}
        ctx = make_context(config, 0.0, scene)
        draw_code(ctx, text, (100, 180), size=40, spans=spans)
        ctx.image.convert("RGB").save(image_path)
    report = {
        "content_sha256": content_digest(ROOT),
        "language": language,
        "lexer": lexer,
        "palette": {name: list(color) for name, color in COLORS.items()},
        "checks": results,
        "fixture_image": str(image_path),
        "fixture_image_sha256": digest(image_path) if image_path.is_file() else None,
        "errors": errors,
        "warnings": [],
    }
    docs = ROOT / "project" / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "CODE_COLOR_QA.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 代码语义色 QA",
        "",
        f"- 内容 SHA-256：`{report['content_sha256']}`",
        f"- 语言 / lexer：{language} / {lexer}",
        f"- fixture PNG：`{image_path}`",
        f"- 错误：{len(errors)}",
        "",
        *(f"- `{item['token']}` / {item['kind']} / {item['actual_rgba']} / {item['status']}" for item in results),
    ]
    (docs / "CODE_COLOR_QA.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
