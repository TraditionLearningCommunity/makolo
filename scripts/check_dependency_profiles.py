from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def lines(name: str) -> list[str]:
    return [
        line.strip()
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


base = lines("requirements.txt")
agents = lines("requirements-agents.txt")

for forbidden in ("crawlee", "playwright", "browserforge", "tldextract"):
    if any(forbidden in line.lower() for line in base):
        raise SystemExit(
            f"{forbidden} must not be installed by the Web/server requirements.txt profile"
        )

if "-r requirements.txt" not in agents:
    raise SystemExit("requirements-agents.txt must extend requirements.txt")
if "tldextract==5.3.2" not in agents:
    raise SystemExit("requirements-agents.txt must pin tldextract for Prospecteur domain scope")
if "crawlee[playwright]==1.10.1" not in agents:
    raise SystemExit("requirements-agents.txt must pin the tested Crawlee Playwright extra")

print("runtime dependency profiles: ok")
