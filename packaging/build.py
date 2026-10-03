"""Build the vault-relay plugin from this folder.

    python3 packaging/build.py [OUT_DIR]

Writes OUT_DIR/vault-relay.plugin (default: the current folder): a zip holding the
plugin manifest, the skill and the tool at the path the skill expects
(skills/vault-relay/scripts/relay.py). Standard library only.
"""
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


def main() -> int:
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
