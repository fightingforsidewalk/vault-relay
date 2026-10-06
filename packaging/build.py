"""Build the vault-relay plugin from this folder.

    python3 packaging/build.py [OUT_DIR]

Writes OUT_DIR/vault-relay.plugin (default: the current folder): a zip holding the
plugin manifest, the skill and the tool at the path the skill expects
(skills/vault-relay/scripts/relay.py). Standard library only.
"""
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = {
    ".claude-plugin/plugin.json": ROOT / "packaging" / "plugin.json",
    "skills/vault-relay/SKILL.md": ROOT / "SKILL.md",
    "skills/vault-relay/scripts/relay.py": ROOT / "relay.py",
    "README.md": ROOT / "README.md",
    "LICENSE": ROOT / "LICENSE",
}


def problems(root: Path = ROOT) -> list:
    """What claude.ai's plugin upload would refuse, checked before packing."""
    found = []
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    parts = text.split("---", 2)
    head = parts[1] if text.startswith("---") and len(parts) == 3 else ""
    desc = [l for l in head.splitlines() if l.startswith("description:")]
    if not desc:
        found.append("SKILL.md has no description in its frontmatter")
    else:
        d = desc[0][len("description:"):].strip()
        if "<" in d or ">" in d:
            found.append("SKILL.md description contains < or >, which the upload reads as an XML tag")
        if len(d) > 1024:
            found.append(f"SKILL.md description is {len(d)} characters; the limit is 1024")
    manifest = json.loads((root / "packaging" / "plugin.json").read_text(encoding="utf-8"))
    for key in ("name", "version", "description"):
        if not manifest.get(key):
            found.append(f"plugin.json has no {key}")
    return found


def main() -> int:
    bad = problems()
    if bad:
        for p in bad:
            print(f"refusing to build: {p}", file=sys.stderr)
        return 1
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    if not folder.is_dir():
        print(f"{folder} isn't a folder", file=sys.stderr)
        return 1
    out = folder / "vault-relay.plugin"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, src in FILES.items():
            z.write(src, name)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
