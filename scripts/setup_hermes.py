"""Provision only rx-dev; preserve the shared gateway's other routes and keys.

Run with the installed Hermes venv (PyYAML), outside the workspace sandbox.
Secrets stay in the user's Hermes profile, never in this repository.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home() / ".hermes"
PROFILE = HOME / "profiles" / "rx-dev"


def env_values(path):
    values = {}
    for line in path.read_text().splitlines() if path.exists() else []:
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


def update_env(path, updates):
    remaining = dict(updates)
    lines = []
    for line in path.read_text().splitlines() if path.exists() else []:
        key = line.split("=", 1)[0].strip() if "=" in line else None
        if key in updates:
            if key in remaining:
                lines.append(f"{key}={remaining.pop(key)}")
        else:
            lines.append(line)
    lines.extend(f"{key}={value}" for key, value in remaining.items())
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o600)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway-env", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8679)
    parser.add_argument("--source-profile", default="default")
    parser.add_argument("--start", action="store_true")
    args = parser.parse_args()
    if not args.gateway_env.is_file():
        raise SystemExit("Shared gateway .env does not exist")
    if not PROFILE.exists():
        subprocess.run(["hermes", "profile", "create", "rx-dev",
                        "--no-skills", "--no-alias", "--description",
                        "rx-dev robotics experiment analyst, designer and evidence reviewer"], check=True)
    stamp = str(time.time_ns())
    config_path = PROFILE / "config.yaml"
    config = yaml.safe_load(config_path.read_text()) or {}
    source = HOME if args.source_profile == "default" else HOME / "profiles" / args.source_profile
    source_config = yaml.safe_load((source / "config.yaml").read_text()) or {}
    if not source_config.get("model"):
        raise SystemExit("Source Hermes profile has no model configuration")
    config["model"] = source_config["model"]
    provider = config["model"].get("provider")
    if provider in source_config.get("providers", {}):
        config.setdefault("providers", {})[provider] = source_config["providers"][provider]
    if config_path.exists():
        shutil.copy2(config_path, PROFILE / f"config.yaml.before-rx-dev-{stamp}")
    # A scoped experimental service, not a second Telegram/Discord dispatcher.
    config["platforms"] = {"api_server": {"enabled": True, "extra": {
        "host": "127.0.0.1", "port": args.port, "model_name": "rx-dev", "cors_origins": ""}}}
    config.setdefault("platform_toolsets", {})["api_server"] = []
    config.setdefault("terminal", {})["cwd"] = str(ROOT)
    config["max_turns"] = 4
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    config_path.chmod(0o600)
    current = env_values(PROFILE / ".env")
    api_key = current.get("API_SERVER_KEY") or secrets.token_hex(32)
    client_key = current.get("RX_DEV_GATEWAY_KEY") or secrets.token_hex(32)
    update_env(PROFILE / ".env", {
        "API_SERVER_ENABLED": "true", "API_SERVER_HOST": "127.0.0.1",
        "API_SERVER_PORT": str(args.port), "API_SERVER_MODEL_NAME": "rx-dev",
        "API_SERVER_KEY": api_key, "RX_DEV_GATEWAY_KEY": client_key,
        "RX_DEV_GATEWAY_BASE_URL": "http://127.0.0.1:8700",
    })
    (PROFILE / "SOUL.md").write_text((ROOT / "backend" / "rx_dev_soul.md").read_text())
    gateway = env_values(args.gateway_env)
    upstreams = json.loads(gateway.get("HERMES_UPSTREAMS", "{}"))
    aliases = json.loads(gateway.get("GATEWAY_MODEL_ALIASES", "{}"))
    keys = [k.strip() for k in gateway.get("GATEWAY_CLIENT_KEYS", "").split(",") if k.strip()]
    if client_key not in keys:
        keys.append(client_key)
    upstreams["rx-dev"] = {"base_url": f"http://127.0.0.1:{args.port}", "api_key": api_key}
    aliases["rx-dev"] = "rx-dev/rx-dev"
    backup = args.gateway_env.with_name(f".env.before-rx-dev-{stamp}")
    shutil.copy2(args.gateway_env, backup)
    backup.chmod(0o600)
    update_env(args.gateway_env, {
        "HERMES_UPSTREAMS": json.dumps(upstreams, separators=(",", ":")),
        "GATEWAY_MODEL_ALIASES": json.dumps(aliases, separators=(",", ":")),
        "GATEWAY_CLIENT_KEYS": ",".join(keys),
    })
    if args.start:
        # This machine currently uses a per-profile fleet. Only install this profile;
        # never migrate/restart the unrelated host Hermes gateway.
        subprocess.run(["hermes", "-p", "rx-dev", "gateway", "install", "--force", "--start-now"], check=True)
        if os.uname().sysname == "Darwin":
            subprocess.run(["launchctl", "kickstart", "-k",
                            f"gui/{os.getuid()}/dev.businessweb.hermes-gateway"], check=True)
    print(f"rx-dev registered: gateway :8700 → profile :{args.port}; secrets not printed")


if __name__ == "__main__":
    main()
