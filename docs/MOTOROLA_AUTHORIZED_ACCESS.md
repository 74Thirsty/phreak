# Motorola Authorized Diagnostic Access

PHREAK can collect diagnostics and open an ADB terminal while a Motorola
device's screen is locked when the host was authorized before the device was
locked. Android does not provide an external command that silently authorizes a
new host or enables USB debugging on an unprovisioned locked production phone.

## Supported Fleet Design

1. Enroll company-owned Motorola devices as Android Enterprise fully managed
   devices during initial setup or after a factory reset.
2. Deploy Moto OEMConfig from managed Google Play through the organization's
   EMM, MDM, or UEM.
3. Permit developer settings through the enterprise policy when ADB service
   access is required.
4. Authorize dedicated PHREAK service-station host keys during provisioning.
5. Use Motorola Moto Remote Control for approved attended or unattended remote
   support workflows.
6. Keep diagnostic actions audited and restrict them to enrolled device serials.

## PHREAK Enrollment Wizard

Run `python -m phreak_v5`, choose **Motorola Enterprise**, then choose **Setup
enrollment wizard**. Paste the fully-managed enrollment token or QR payload
created by the organization's EMM. PHREAK writes the provisioning payload and
renders a scannable PNG when the optional `qrencode` command is installed.

On a new or factory-reset Motorola, tap the same place on the welcome screen six
times, connect to Wi-Fi, and scan the QR code. After Android Device Policy
finishes enrollment, let Moto OEMConfig and the assigned enterprise policy
install before running PHREAK's verification check.

## PHREAK Readiness Evidence

An authorized PHREAK diagnostic bundle includes:

- `device_policy.txt`: device-owner and policy state
- `developer_settings.txt`: developer-settings and ADB enablement state
- `motorola_enterprise_packages.txt`: installed Motorola enterprise components
- `screen_lock_state.txt`: confirms whether authorized diagnostics ran while
  the screen was locked
- `manifest.json`: selected transport and access limitations

For a retail Motorola device that was not enrolled and whose host was not
previously authorized, use Motorola's official support or repair workflow.
