"""Install the project-owned experiment and learning skills."""
from pathlib import Path
import shutil
import time

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("rx-dev-failure-analysis", "rx-dev-experiment-design", "rx-dev-evaluation-review",
         "rx-dev-learning-analysis", "rx-dev-learning-design", "rx-dev-learning-review")


def main():
    destinations = [Path.home()/".codex/skills", Path.home()/".hermes/profiles/rx-dev/skills/robotics"]
    for destination in destinations:
        for name in NAMES:
            source = ROOT/"skills"/name/"SKILL.md"
            target = destination/name/"SKILL.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != source.read_bytes():
                shutil.copy2(target, target.with_name(f"SKILL.md.before-{time.time_ns()}"))
            shutil.copy2(source, target)
    print(f"Installed {len(NAMES)} rx-dev skills into Codex and the rx-dev Hermes profile; other skills unchanged")


if __name__ == "__main__":
    main()
