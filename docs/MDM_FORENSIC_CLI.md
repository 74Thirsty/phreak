# MDM Interactive CLI & Forensic Playbook

The Mobile Device Management (MDM) integration ships with a dedicated, Rich-based
command shell that lets you interrogate and remediate an `hmdm-server` instance
without plugging anything into the main PHREAK console. This document captures
_every_ moving piece—from environment preparation to exporting forensic evidence.

---

## 1. Environment Preparation

1. **Bootstrap dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install -e ./integrations[mdm]
   ```

   The editable install wires the `integrations` package into your virtualenv and
   ensures the `requests` dependency used by the REST client is present.

2. **Provide credentials via environment variables**

   | Variable        | Purpose                             | Example value                          |
   | --------------- | ----------------------------------- | -------------------------------------- |
   | `MDM_BASE_URL`  | Base URL of the `hmdm-server` API   | `https://mdm.internal.example/hmdm`    |
   | `MDM_API_KEY`   | Bearer token for the REST requests  | `super-secret-api-token`               |
   | `MDM_TIMEOUT`   | Optional request timeout in seconds | `15`                                   |

   ```bash
   export MDM_BASE_URL="https://mdm.internal.example/hmdm"
   export MDM_API_KEY="super-secret-api-token"
   export MDM_TIMEOUT="15"
   ```

3. **Smoke-test the package**

   ```bash
   PYTHONPATH=. python -c "import integrations.mdm; print(integrations.mdm.__file__)"
   ```

   You should see an absolute path print out. If the import fails, confirm the
   virtualenv is activated and the editable install finished successfully.

---

## 2. Launching the Interactive Shell

Run the CLI directly with Python:

```bash
PYTHONPATH=. python -m integrations.mdm.cli
```

The entrypoint renders a cyan banner reminding you that `Ctrl+C` exits at any
moment. Each loop paints an action matrix:

```
┏━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Option┃ Description                          ┃
┣━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ 1     ┃ List devices                         ┃
┃ 2     ┃ List policies                        ┃
┃ 3     ┃ Apply policy to device               ┃
┃ 4     ┃ Export forensic snapshot             ┃
┃ 5     ┃ Refresh audit (devices & policies)   ┃
┃ q     ┃ Quit                                 ┃
┗━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

Use the numeric accelerator or press `q` to bail. The prompt defaults to `5`
(a combined audit pass) so repeatedly pressing enter re-runs a full status sweep.

---

## 3. Action Catalogue

### 3.1 List devices (`1`)

* Fetches `/api/devices` and prints the enrollment roster in a Rich table.
* Empty fields (IMEI, policy, or last-seen) render as em-dashes so gaps stand
  out immediately.

### 3.2 List policies (`2`)

* Queries `/api/policies` and prints every policy with installed apps and
  restriction keys.
* Restrictions are alphabetised, letting you eyeball mismatched payloads fast.

### 3.3 Apply policy (`3`)

1. Prompts for the numeric device ID.
2. Prompts for the numeric policy ID.
3. Requests confirmation before firing the REST call.
4. Renders the raw JSON response in a bordered panel.

Any HTTP or transport error is wrapped inside a red alert panel that preserves
the exception text for copy/paste into tickets.

### 3.4 Export forensic snapshot (`4`)

* Pulls both device and policy inventories and serialises them into
  `mdm_forensics/mdm_snapshot_<timestamp>.json`.
* Timestamps are recorded in UTC using the integration's `utils.timestamp()`
  helper so they align with PHREAK's broader logging format.
* Ideal for attaching to incident reports, SOC escalations, or compliance
  handoffs.

### 3.5 Refresh audit (`5`)

* Runs the device and policy listings back-to-back and frames them with Rich
  rules (`──── Device Overview ────`).
* Designed for live-ops dashboards where you want a rolling view without
  re-selecting menu items.

---

## 4. Operational Tips

* **Timeout tuning** – Adjust `MDM_TIMEOUT` when dealing with slow links. The
  CLI surfaces request failures instantly, so you will know when the server
  refuses to answer.
* **Non-destructive exports** – The `mdm_forensics/` folder is created lazily
  in the current working directory. Clean it between runs if you only want the
  latest snapshot.
* **Keyboard interrupts** – Hitting `Ctrl+C` inside any action returns you to
  the main menu unless the request already completed. A second `Ctrl+C` exits
  gracefully with a yellow notification.
* **Integration wiring** – When you eventually plug this module into PHREAK
  proper, import `integrations.mdm.server.MDMService` or reuse the CLI's helper
  routines. No modifications to `phreak_v5` are required.

---

## 5. Troubleshooting Checklist

| Symptom                            | Investigation Steps                                                                 | Remedy                                                                 |
| ---------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `ModuleNotFoundError: requests`    | Run `pip install -e ./integrations[mdm]` inside your virtualenv.                   | Re-install dependencies; ensure the venv is active.                    |
| `401 Unauthorized` API responses   | Confirm `MDM_API_KEY` matches your server token and hasn't expired.                | Issue a fresh token from the hmdm-server console.                      |
| Empty tables despite enrollments   | Use `curl` against `/api/devices` to check if the backend is filtering results.    | Review server-side permissions; some tokens only see specific tenants. |
| Export file missing                | Verify you have write permissions in the working directory.                        | Run CLI from a writable location or set `PWD` accordingly.             |

---

## 6. Sample Session Transcript

```
$ PYTHONPATH=. python -m integrations.mdm.cli
╭────────────────────────────────────────────────────────╮
│ Mobile Device Management Interactive Shell             │
│                     Press Ctrl+C to exit at any time   │
╰────────────────────────────────────────────────────────╯
┏━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Option┃ Description                          ┃
┣━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ 1     ┃ List devices                         ┃
┃ 2     ┃ List policies                        ┃
┃ 3     ┃ Apply policy to device               ┃
┃ 4     ┃ Export forensic snapshot             ┃
┃ 5     ┃ Refresh audit (devices & policies)   ┃
┃ q     ┃ Quit                                 ┃
┗━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
Select an action [1,2,3,4,5,q] (default 5): 5
────────────────────────────── Device Overview ───────────────────────────────
┏━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ ID ┃ IMEI         ┃ Model             ┃ Policy ┃ Last Seen            ┃
┣━━━━╋━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━╋━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━┫
┃ 42 ┃ 357862104... ┃ Pixel 7 Pro       ┃ 9      ┃ 2024-04-28T01:32:14Z  ┃
┃ 43 ┃ 353112096... ┃ Galaxy S23 Ultra  ┃ —      ┃ —                    ┃
┗━━━━┻━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━┻━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━┛
────────────────────────────── Policy Overview ──────────────────────────────
┏━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ID ┃ Name         ┃ Apps                ┃ Restrictions                ┃
┣━━━━╋━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ 9  ┃ Stock Lock   ┃ dialer, files       ┃ allow_usb_debugging         ┃
┃ 10 ┃ Field Force  ┃ maps, drive, sheets ┃ enforce_wifi,enforce_vpn    ┃
┗━━━━┻━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

This transcript can be dropped into operational tickets to demonstrate the
exact state of the fleet at the time of triage.

---

The CLI is purpose-built for investigations: high-contrast tables, explicit
confirmation gates, and forensic exports on tap. Wire it into your runbooks and
hand it to responders who need answers _now_.
