from pathlib import Path

path = Path("tests/test_current_docs_consistency.py")
text = path.read_text(encoding="utf-8")
old = '    r"(?P<path>"\n'
new = '    r"(?<![A-Za-z0-9_./-])(?P<path>"\n'
if old not in text:
    raise SystemExit("expected repo-path regex anchor not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
