# Motorola / Android Hidden & Diagnostic Commands — Safe Reference

## Dialer / Hidden Test Codes

| Code | Description |
| ---- | ----------- |
| `*#06#` | Show IMEI / MEID / EID. |
| `*##4636##*` | Android testing menu: phone info, battery, Wi-Fi, usage stats. |
| `*##225##` | Calendar sync info (device dependent). |
| `*##426##` | Google Play Services diagnostics (FCM). |
| `*##232338##` | Wi-Fi MAC address display. |
| `*##232331##` | Bluetooth test. |
| `*##1472365##` | GPS test (device dependent). |
| `*##2663##` | Touchscreen firmware/test panel. |
| `*##0842##` | Vibration and backlight test. |
| `*##0*##` | LCD/color bars. |
| `*##197328640##` | Engineering mode (Qualcomm variants). |
| `*##7764726` + Call | Motorola programming menu (carrier/OEM may restrict). |
| `*##7262626##` | Field test (varies by OEM). |

> **Note:** Availability varies by firmware, region, and carrier configuration. Treat all menus as read-only unless you are following OEM documentation.

## ADB Essentials (Read-Only)

Enable Developer Options and USB debugging on the device before running these commands.

```bash
adb devices
adb bugreport > bugreport.zip
adb logcat -d > logcat.txt
adb shell dumpsys telephony.registry > telephony.txt
adb shell dumpsys ims > ims.txt
adb shell dumpsys connectivity > connectivity.txt
adb shell getprop ro.product.model
adb shell getprop gsm.operator.numeric
adb shell content query --uri content://telephony/carriers/current
adb shell am broadcast -a android.telephony.action.CARRIER_CONFIG_CHANGED
```

## Fastboot Inspection & Safe Flashes

```bash
fastboot devices
fastboot getvar all
fastboot oem get_unlock_data
fastboot oem device-info
fastboot flash boot boot.img
fastboot flashing unlock
fastboot flashing lock
```

> **Warning:** Only flash signed/authorized images with owner consent. Unlocking typically wipes user data.

## Helpful Play Store Apps (No Root Required)

- **Network Cell Info Lite**, **LTE Discovery**, **Signal Spy** — RF metrics and band information
- **Device Info HW** — Hardware and sensor inventory
- **Termux** — Local shell scripting environment

## Safety & Publishing Notes

- Flag destructive commands (factory reset, flash/erase) prominently
- Mention that OEM/carrier firmware may restrict outputs
- Encourage operators to capture an `adb bugreport` and screenshots before changing device state
