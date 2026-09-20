# Hotspot Manager GUI

A native Qt desktop app for managing a WiFi hotspot on Debian — no browser,
no terminal, no localhost server involved.

**Supported OS:** Debian (and Debian-based distros with `apt`/`dpkg`).

## Build

```bash
chmod +x build_deb.sh
./build_deb.sh
```

The script checks for `dpkg-dev` and `fakeroot` and installs them if missing
(may prompt for your `sudo` password — only needed at build time). Output:
`hotspot-manager-gui_<version>_all.deb`.

## Install

```bash
sudo apt install ./hotspot-manager-gui_<version>_all.deb
```

`hostapd`, `dnsmasq`, `iptables`, and `qrencode` are **not** installed at
this step — they're installed/configured on demand from inside the app.

## Setup (first run)

1. Launch **"Hotspot Manager"** from the Application Menu. It runs as root
   (via `pkexec`/`sudo`), so it will prompt for a password on first launch —
   unless the in-app "Password OFF" toggle (Setup page) is enabled.
2. Go to **Setup → Install & Configure** to install the required packages
   (`hostapd`, `dnsmasq`, `iptables`, `qrencode`) and generate the needed
   config files/folders.
3. Go to **Network → Create Network +** to set up your first WiFi network
   (adapter and band are auto-detected).

## Use

- **Network** page: create/edit/delete saved network profiles. Only one
  network is active at a time — press **Activate** on a profile to select it.
- **Dashboard**: simple ON/OFF toggles for the hotspot itself, sleep-block,
  and auto-start on boot.
- **Devices**: view connected clients; whitelist/blacklist them.
- **Schedule**: auto ON/OFF and idle-timeout, run via root's crontab — works
  even while the app itself is closed.
- **QR code**: share the network credentials by scanning.
- Closing the app ("Exit App") only quits the GUI — the hotspot keeps running
  if it was on.

## Uninstall

```bash
sudo apt purge hotspot-manager-gui
```

This stops the hotspot and automatically removes all app config, saved
networks, and schedules (equivalent to the app's own "Delete All Setup"),
plus `hostapd`/`dnsmasq`/`qrencode` if they were installed by the app.
