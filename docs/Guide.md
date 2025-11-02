# 🌟 PHREAK v5 Operator Quickstart

Welcome to your PHREAK v5 control tower! This guide is written to feel like a teammate sitting beside you, walking through the first launch with plenty of context and gentle guardrails. By the end you will have the control tower running, logging, and ready to accept demo commands.

---

## 1. Before you dive in

| What you need | Why it matters |
| --- | --- |
| **Python 3.10 or newer** | The control tower uses modern dataclasses, enums, and asyncio patterns. |
| **pip / virtualenv** | Keeps PHREAK's dependencies tidy and separate from the rest of your machine. |
| **Git** | To clone the repository. |
| **Optional: ADB/Fastboot** | Only required if you plan to talk to physical devices right away. |

PHREAK will create its working folders under `~/.phreak` the first time it boots. That includes the audit log, vault, firmware cache, backups, and plugin directories so everything is grouped in one predictable home base.【F:phreak_v5/config.py†L9-L44】

> **Heads-up on crypto**: If you install the `cryptography` package, the secret vault automatically upgrades to Fernet encryption. Otherwise it transparently falls back to the built-in XOR cipher—fine for demos, but not recommended for production secrets.【F:phreak_v5/core/vault.py†L13-L112】

---

## 2. Grab the code and set up your sandbox

```bash
# Clone and step into the repo
git clone https://github.com/your-org/phreak.git
cd phreak

# Create an isolated Python environment
python -m venv .venv
source .venv/bin/activate

# Install helpful dependencies
python -m pip install --upgrade pip
python -m pip install cryptography rich
```

Feel free to add any other tooling you like (linting, type checking, etc.) once you're comfortable.

---

## 3. Meet the control tower

The `PhreakControlTower` class wires together every subsystem—connections, policy checks, audit logging, telemetry, vault, firmware handling, backups, ML diagnostics, plugins, and the device graph.【F:phreak_v5/__init__.py†L53-L130】 A quick bootstrap call prepares the filesystem, spins up the audit log, and seeds the vault.【F:phreak_v5/__init__.py†L185-L194】

The snippet below launches the tower, registers a loopback demo device, loads any plugins it finds, and fires a sample command through the loopback connector:

```bash
python - <<'PY'
import asyncio
from phreak_v5 import PhreakControlTower
from phreak_v5.core.connection import LoopbackConnector
from phreak_v5.models import CommandRequest, Device

# Create the tower and prepare storage (audit log, vault, caches)
tower = PhreakControlTower()
tower.bootstrap()

# Register a friendly demo device routed through the loopback connector
demo_device = Device(device_id="demo-emu-01", connection_uri="loopback://demo")
tower.register_devices([demo_device])
tower.connection_matrix.bind_connector("demo-emu-01", LoopbackConnector())

# Optionally discover community plugins in ~/.phreak/plugins
tower.load_plugins()

async def main():
    request = CommandRequest(
        action="diagnostics.ping",
        device_ids=("demo-emu-01",),
        requested_by="quickstart",
    )
    await tower.dispatch(request)

asyncio.run(main())
print("🎉 Control tower is awake and responding!")
PY
```

Behind the scenes, the command router streams everything through the policy engine, connection matrix, and telemetry bus so the audit log captures the entire story.【F:phreak_v5/__init__.py†L172-L194】【F:phreak_v5/core/connection.py†L68-L146】

---

## 4. Check your new HQ

After the quickstart script runs, take a peek at the working directory under `~/.phreak`:

```bash
ls ~/.phreak
```

You should spot:

- `audit.log.jsonl` – append-only command history ready for compliance exports.
- `vault.json` – secret storage (encrypted if `cryptography` is installed).
- `firmware/` and `backups/` – staging areas for future operations.
- `plugins/` – drop-in folder for JSON manifest plugins.

These locations come straight from the default `ControlTowerConfig`, so if you ever need a different layout, override the config when instantiating the tower.【F:phreak_v5/config.py†L9-L59】

---

## 5. Next adventures

1. **Add real devices** – Swap the loopback connector for your actual transport layer and register devices with meaningful `connection_uri` values.【F:phreak_v5/core/connection.py†L78-L145】
2. **Tune policies** – Feed custom `PolicyRule` objects into the tower constructor to enforce lab-specific guardrails before commands fire.【F:phreak_v5/__init__.py†L56-L87】
3. **Schedule backups & ingest firmware** – Use `schedule_backup` and `ingest_firmware` to build a safety net before running risky operations.【F:phreak_v5/__init__.py†L185-L213】
4. **Build dashboards** – Tap into the telemetry bus to power status boards or alerts as your fleet grows.【F:phreak_v5/__init__.py†L62-L131】

Wherever you head next, the tower keeps emitting telemetry and logging every decision so you always have a trustworthy paper trail.

Happy launching, and welcome to PHREAK v5! 🚀
