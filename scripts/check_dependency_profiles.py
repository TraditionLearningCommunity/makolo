from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def lines(name: str) -> list[str]:
    return [
        line.strip()
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


base = lines("requirements.txt")
prospector = lines("requirements-prospector.txt")
observer = lines("requirements-observer.txt")

for forbidden in ("crawlee", "playwright", "browserforge", "tldextract"):
    if any(forbidden in line.lower() for line in base):
        raise SystemExit(
            f"{forbidden} must not be installed by the Web/server requirements.txt profile"
        )

if "-r requirements.txt" not in prospector:
    raise SystemExit("requirements-prospector.txt must extend requirements.txt")
if "crawlee==1.10.1" not in prospector:
    raise SystemExit("requirements-prospector.txt must pin Crawlee without browser extras")
if any("playwright" in line.lower() for line in prospector):
    raise SystemExit("Prospector profile must not install Playwright")

if "-r requirements.txt" not in observer:
    raise SystemExit("requirements-observer.txt must extend requirements.txt")
if "crawlee[playwright]==1.10.1" not in observer:
    raise SystemExit("requirements-observer.txt must pin the tested Crawlee Playwright extra")

print("runtime dependency profiles: ok")
