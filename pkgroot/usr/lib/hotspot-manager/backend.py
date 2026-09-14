#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
#   HOTSPOT MANAGER — Backend (runs entirely as root)
#   Saimum | Debian
#
#   No HTTP, no localhost — called directly by the Qt GUI or by
#   cli.py (used from cron for scheduled on/off/idle checks).
# ─────────────────────────────────────────────────────────────
import os
import re
import json
import time
import signal
import pwd
import subprocess
import threading

# ── PATHS ────────────────────────────────────────────────────
BASE_DIR            = "/etc/hotspot-manager"
NETWORKS_FILE       = f"{BASE_DIR}/networks.json"
SETTINGS_FILE       = f"{BASE_DIR}/settings.json"
WHITELIST_FILE      = f"{BASE_DIR}/whitelist.conf"
BLACKLIST_FILE      = f"{BASE_DIR}/blacklist.conf"

HOSTAPD_DIR         = "/etc/hostapd"
HOSTAPD_LAUNCHER    = f"{BASE_DIR}/hostapd-run.sh"
SYSTEMD_HOSTAPD     = "/etc/systemd/system/hotspot-manager-hostapd.service"

DNSMASQ_DIR         = "/etc/dnsmasq.d"
DNSMASQ_MAIN_CONF   = "/etc/dnsmasq.conf"
LEASES_FILE         = "/var/lib/misc/dnsmasq.leases"

STARTUP_SCRIPT      = "/usr/local/bin/hotspot-manager-startup.sh"
SYSTEMD_STARTUP     = "/etc/systemd/system/hotspot-manager-startup.service"
SLEEP_HOOK          = "/etc/systemd/system-sleep/hotspot-manager-resume.sh"

RUN_DIR             = "/run/hotspot-manager"
SLEEP_INHIBIT_PID   = f"{RUN_DIR}/sleep-inhibit.pid"

SUDOERS_FILE        = "/etc/sudoers.d/hotspot-manager"
MAIN_PY             = "/usr/lib/hotspot-manager/main.py"
CLI_PY              = "/usr/lib/hotspot-manager/cli.py"

# ── LOG BUFFER (in-process, shown in the Activity Log panel) ──
LOG_BUF  = []
LOG_LOCK = threading.Lock()


def add_log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with LOG_LOCK:
        LOG_BUF.append(line)
        if len(LOG_BUF) > 200:
            LOG_BUF.pop(0)
    print(line, flush=True)


def get_log(n=60):
    with LOG_LOCK:
        return list(LOG_BUF[-n:])


# ── LOW LEVEL HELPERS (already root — no sudo prefix needed) ──
def run_cmd(cmd, inp=None):
    try:
        r = subprocess.run(list(cmd), input=inp, capture_output=True,
                            text=True, timeout=60)
        if r.returncode != 0 and r.stderr and r.stderr.strip():
            add_log(f"⚠ {r.stderr.strip()[:150]}")
        return r
    except subprocess.TimeoutExpired:
        add_log(f"Timeout: {cmd[0]}")
        return None
    except Exception as e:
        add_log(f"Error: {e}")
        return None


def run_q(cmd):
    """Quiet run — used for polling/status checks, no log spam."""
    try:
        return subprocess.run(list(cmd), capture_output=True, text=True, timeout=10)
    except Exception:
        return None


def write_file(path, content):
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return True
    except Exception as e:
        add_log(f"Write error {path}: {e}")
        return False


def read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""


def get_real_user():
    """Resolve the actual desktop user even though we run as root
    (launched via sudo -n or pkexec)."""
    u = os.environ.get("SUDO_USER")
    if u and u != "root":
        return u
    uid = os.environ.get("PKEXEC_UID")
    if uid:
        try:
            return pwd.getpwuid(int(uid)).pw_name
        except Exception:
            pass
    try:
        return os.getlogin()
    except Exception:
        return ""


# ── SETTINGS ─────────────────────────────────────────────────
def default_settings():
    return {
        "password_off": False,
        "whitelist_enabled": False,
        "block_sleep": False,
        "dark_mode": True,
    }


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return default_settings()
    try:
        data = json.loads(read_file(SETTINGS_FILE) or "{}")
        merged = default_settings()
        merged.update(data)
        return merged
    except Exception:
        return default_settings()


def save_settings(s):
    write_file(SETTINGS_FILE, json.dumps(s, indent=2))


# ── NETWORK PROFILES (one per adapter) ──────────────────────
def get_networks():
    if not os.path.exists(NETWORKS_FILE):
        return []
    try:
        return json.loads(read_file(NETWORKS_FILE) or "[]")
    except Exception:
        return []


def save_networks(nets):
    write_file(NETWORKS_FILE, json.dumps(nets, indent=2))


def next_free_subnet(existing_nets):
    used = {n.get("hotspot_ip") for n in existing_nets if n.get("hotspot_ip")}
    for i in range(50, 90):
        candidate = f"192.168.{i}.1"
        if candidate not in used:
            return candidate
    raise RuntimeError("No free subnet available (too many networks)")


# ── ADAPTER DETECTION ────────────────────────────────────────
def get_adapter_bands(phy):
    r = run_q(["iw", "phy", phy, "info"])
    text = r.stdout if r and r.stdout else ""
    bands = []
    if re.search(r"Band 1:", text):
        bands.append("2.4")
    if re.search(r"Band 2:", text):
        bands.append("5")
    return bands or ["2.4"]


def list_adapters():
    """Return all wireless interfaces on the system with detected bands."""
    r = run_q(["iw", "dev"])
    adapters = []
    if not r or not r.stdout:
        return adapters
    cur_phy = None
    for raw in r.stdout.split("\n"):
        line = raw.strip()
        if line.startswith("phy#"):
            cur_phy = "phy" + line.split("#", 1)[1].split()[0].strip()
        elif line.startswith("Interface"):
            parts = line.split()
            if len(parts) >= 2:
                iface = parts[1]
                bands = get_adapter_bands(cur_phy) if cur_phy else ["2.4"]
                adapters.append({"iface": iface, "phy": cur_phy or "", "bands": bands})
    return adapters


def get_available_adapters_for_create():
    used = {n["iface"] for n in get_networks()}
    return [a for a in list_adapters() if a["iface"] not in used]


def get_default_iface():
    """Detect the current internet-facing (egress) interface."""
    r = run_q(["ip", "route", "show", "default"])
    if r and r.stdout:
        parts = r.stdout.split()
        if "dev" in parts:
            try:
                return parts[parts.index("dev") + 1]
            except IndexError:
                pass
    return None


# ── HOSTAPD / DNSMASQ CONFIG WRITERS ─────────────────────────
def _band_settings(band):
    if band == "5":
        return "a", "36"
    return "g", "6"


def write_hostapd_conf(net):
    hw_mode, channel = _band_settings(net.get("band", "2.4"))
    hidden = "1" if net.get("hidden") else "0"
    settings = load_settings()
    acl_block = ""
    if settings.get("whitelist_enabled"):
        acl_block = f"\nmacaddr_acl=1\naccept_mac_file={WHITELIST_FILE}"
    elif os.path.exists(BLACKLIST_FILE) and os.path.getsize(BLACKLIST_FILE) > 0:
        acl_block = f"\nmacaddr_acl=0\ndeny_mac_file={BLACKLIST_FILE}"
    content = (
        f"interface={net['iface']}\ndriver=nl80211\n"
        f"ctrl_interface=/var/run/hostapd\nctrl_interface_group=0\n"
        f"utf8_ssid=1\nssid={net['ssid']}\nhw_mode={hw_mode}\nchannel={channel}\n"
        f"wpa=2\nwpa_passphrase={net['password']}\nwpa_key_mgmt=WPA-PSK\n"
        f"rsn_pairwise=CCMP\nignore_broadcast_ssid={hidden}{acl_block}\n"
    )
    path = f"{HOSTAPD_DIR}/hotspot-manager-{net['iface']}.conf"
    write_file(path, content)
    return path


def write_dnsmasq_conf(net):
    ip = net["hotspot_ip"]
    base = ".".join(ip.split(".")[:3])
    dhcp_range = f"{base}.2,{base}.20,255.255.255.0,24h"
    content = f"interface={net['iface']}\nbind-dynamic\ndhcp-range={dhcp_range}\n"
    path = f"{DNSMASQ_DIR}/hotspot-manager-{net['iface']}.conf"
    write_file(path, content)
    return path


def ensure_dnsmasq_confdir_included():
    content = read_file(DNSMASQ_MAIN_CONF)
    if "conf-dir=/etc/dnsmasq.d" not in content:
        run_cmd(["bash", "-c",
                  f"echo 'conf-dir=/etc/dnsmasq.d/,*.conf' >> {DNSMASQ_MAIN_CONF}"])


def regen_hostapd_launcher():
    nets = get_networks()
    conf_files = [f"{HOSTAPD_DIR}/hotspot-manager-{n['iface']}.conf" for n in nets]
    if not conf_files:
        return False
    script = "#!/bin/bash\nexec /usr/sbin/hostapd " + " ".join(conf_files) + "\n"
    write_file(HOSTAPD_LAUNCHER, script)
    run_cmd(["chmod", "+x", HOSTAPD_LAUNCHER])
    return True


def install_systemd_hostapd_unit():
    unit = (
        "[Unit]\n"
        "Description=Hotspot Manager - hostapd (multi-interface)\n"
        "After=network.target NetworkManager.service\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={HOSTAPD_LAUNCHER}\n"
        "Restart=on-failure\n"
        "RestartSec=2\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
    write_file(SYSTEMD_HOSTAPD, unit)
    run_cmd(["systemctl", "daemon-reload"])


def is_hotspot_active():
    r = run_q(["systemctl", "is-active", "--quiet", "hotspot-manager-hostapd.service"])
    return bool(r and r.returncode == 0)


def is_permanent_enabled():
    r = run_q(["systemctl", "is-enabled", "--quiet", "hotspot-manager-startup.service"])
    return bool(r and r.returncode == 0)


def get_uptime():
    r = run_q(["systemctl", "show", "hotspot-manager-hostapd.service",
               "--property=ActiveEnterTimestamp"])
    if r and "=" in (r.stdout or ""):
        ts = r.stdout.strip().split("=", 1)[-1].strip()
        if ts:
            try:
                r2 = run_q(["date", "-d", ts, "+%s"])
                if r2 and r2.stdout.strip():
                    diff = int(time.time()) - int(r2.stdout.strip())
                    if diff < 0:
                        diff = 0
                    return f"{diff // 3600}h {(diff % 3600) // 60:02d}m"
            except Exception:
                pass
    return "--"


# ── NETWORK CRUD ─────────────────────────────────────────────
def create_network(iface, ssid, password, band, hidden):
    if not iface:
        return {"error": "Please select a Wi-Fi adapter"}
    if not ssid:
        return {"error": "SSID cannot be empty"}
    if len(password) < 8:
        return {"error": "Password must be at least 8 characters"}
    nets = get_networks()
    if any(n["iface"] == iface for n in nets):
        return {"error": f"{iface}  already has a network. Edit or delete it first."}
    ip = next_free_subnet(nets)
    net = {
        "iface": iface, "ssid": ssid, "password": password,
        "band": band, "hidden": bool(hidden), "hotspot_ip": ip,
    }
    nets.append(net)
    save_networks(nets)
    write_hostapd_conf(net)
    write_dnsmasq_conf(net)
    add_log(f"✓ Network '{ssid}' created on {iface} ({ip}/24)")
    return {"ok": True}


def update_network(iface, ssid, password, band, hidden):
    if not ssid:
        return {"error": "SSID cannot be empty"}
    if len(password) < 8:
        return {"error": "Password must be at least 8 characters"}
    nets = get_networks()
    for n in nets:
        if n["iface"] == iface:
            n.update({"ssid": ssid, "password": password, "band": band, "hidden": bool(hidden)})
            save_networks(nets)
            write_hostapd_conf(n)
            write_dnsmasq_conf(n)
            if is_hotspot_active():
                regen_hostapd_launcher()
                run_cmd(["systemctl", "restart", "hotspot-manager-hostapd.service"])
                run_cmd(["systemctl", "restart", "dnsmasq"])
                add_log(f"✓ {iface} updated and applied immediately")
            else:
                add_log(f"✓ {iface} updated — press Start Hotspot to apply")
            return {"ok": True}
    return {"error": "Network not found"}


def delete_network(iface):
    nets = get_networks()
    target = next((n for n in nets if n["iface"] == iface), None)
    if not target:
        return {"error": "Network not found"}
    add_log(f"Deleting network on {iface}...")
    run_cmd(["ip", "addr", "del", f"{target['hotspot_ip']}/24", "dev", iface])
    run_cmd(["nmcli", "device", "set", iface, "managed", "yes"])
    run_cmd(["rm", "-f", f"{HOSTAPD_DIR}/hotspot-manager-{iface}.conf"])
    run_cmd(["rm", "-f", f"{DNSMASQ_DIR}/hotspot-manager-{iface}.conf"])
    nets = [n for n in nets if n["iface"] != iface]
    save_networks(nets)
    if nets:
        regen_hostapd_launcher()
        if is_hotspot_active():
            run_cmd(["systemctl", "restart", "hotspot-manager-hostapd.service"])
            run_cmd(["systemctl", "restart", "dnsmasq"])
    else:
        run_cmd(["systemctl", "stop", "hotspot-manager-hostapd.service"])
    add_log(f"✓ Network on {iface} deleted")
    return {"ok": True}


# ── START / STOP ──────────────────────────────────────────────
def start_hotspot():
    add_log("Starting hotspot...")
    nets = get_networks()
    if not nets:
        add_log("⚠ No networks configured. Create one first.")
        return {"error": "No networks configured"}

    ensure_dnsmasq_confdir_included()
    for net in nets:
        write_hostapd_conf(net)
        write_dnsmasq_conf(net)
        run_cmd(["nmcli", "device", "set", net["iface"], "managed", "no"])
        run_cmd(["ip", "link", "set", net["iface"], "up"])
        run_cmd(["ip", "addr", "add", f"{net['hotspot_ip']}/24", "dev", net["iface"]])

    run_cmd(["sysctl", "-w", "net.ipv4.ip_forward=1"])
    egress = get_default_iface()
    if egress:
        run_cmd(["iptables", "-t", "nat", "-D", "POSTROUTING", "-o", egress, "-j", "MASQUERADE"])
        run_cmd(["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", egress, "-j", "MASQUERADE"])
    else:
        add_log("⚠ Could not detect the internet interface — internet sharing may not work")

    regen_hostapd_launcher()
    run_cmd(["systemctl", "daemon-reload"])
    run_cmd(["systemctl", "restart", "hotspot-manager-hostapd.service"])
    run_cmd(["systemctl", "restart", "dnsmasq"])
    time.sleep(1.5)

    ok_ifaces = []
    for net in nets:
        r2 = run_q(["ip", "addr", "show", net["iface"]])
        if r2 and r2.stdout and net["hotspot_ip"] in r2.stdout:
            ok_ifaces.append(net["iface"])

    if ok_ifaces:
        add_log(f"✓ Hotspot started on: {', '.join(ok_ifaces)}")
        settings = load_settings()
        if settings.get("block_sleep"):
            enable_sleep_block()
    else:
        add_log("✗ Failed to start. Check: journalctl -u hotspot-manager-hostapd -n 30")
    return {"ok": True, "started": ok_ifaces}


def stop_hotspot():
    add_log("Stopping hotspot...")
    run_cmd(["systemctl", "stop", "hotspot-manager-hostapd.service"])
    run_cmd(["systemctl", "stop", "dnsmasq"])
    run_cmd(["pkill", "-f", "hostapd .*hotspot-manager-"])
    run_cmd(["pkill", "-f", "hostapd-run.sh"])
    for net in get_networks():
        run_cmd(["ip", "addr", "del", f"{net['hotspot_ip']}/24", "dev", net["iface"]])
        run_cmd(["nmcli", "device", "set", net["iface"], "managed", "yes"])
    run_cmd(["iptables", "-t", "nat", "-F", "POSTROUTING"])
    disable_sleep_block()
    add_log("✓ Hotspot stopped and related processes killed")
    return {"ok": True}


# ── STATUS / DEVICES ──────────────────────────────────────────
def get_status():
    nets = get_networks()
    active = is_hotspot_active()
    per_net = []
    total_clients = 0
    for n in nets:
        clients = 0
        ip_ok = False
        if active:
            r = run_q(["ip", "addr", "show", n["iface"]])
            ip_ok = bool(r and r.stdout and n["hotspot_ip"] in r.stdout)
            r2 = run_q(["iw", "dev", n["iface"], "station", "dump"])
            if r2 and r2.stdout:
                clients = len([l for l in r2.stdout.split("\n")
                               if l.strip().startswith("Station")])
        total_clients += clients
        per_net.append({
            "iface": n["iface"], "ssid": n["ssid"], "password": n["password"],
            "band": n["band"], "hidden": n["hidden"],
            "ip": n["hotspot_ip"] if ip_ok else "N/A",
            "active": ip_ok, "clients": clients,
        })
    settings = load_settings()
    return {
        "active": active, "networks": per_net, "total_clients": total_clients,
        "count": len(nets), "uptime": get_uptime() if active else "--",
        "permanent": is_permanent_enabled(),
        "sleep_block": is_sleep_block_active(),
        "password_off": settings.get("password_off", False),
        "whitelist_enabled": settings.get("whitelist_enabled", False),
        "block_sleep": settings.get("block_sleep", False),
        "dark_mode": settings.get("dark_mode", True),
    }


_PREV_STATS = {}


def get_client_info(mac):
    mac_l = mac.lower()
    ip_, hostname, dev_type = "N/A", "unknown", ""
    leases = read_file(LEASES_FILE)
    for line in leases.split("\n"):
        parts = line.strip().split()
        if len(parts) >= 4 and parts[1].lower() == mac_l:
            ip_ = parts[2]
            hostname = parts[3] if parts[3] != "*" else "unknown"
            break
    hn = hostname.lower()
    if "android" in hn: dev_type = "Android"
    elif "iphone" in hn: dev_type = "iPhone"
    elif "ipad" in hn: dev_type = "iPad"
    elif any(x in hn for x in ("windows", "win")): dev_type = "Windows PC"
    elif any(x in hn for x in ("mac", "apple")): dev_type = "Mac"
    elif "linux" in hn: dev_type = "Linux"
    return ip_, hostname, dev_type


def get_devices():
    global _PREV_STATS
    devices = []
    wl = read_file(WHITELIST_FILE).lower() if os.path.exists(WHITELIST_FILE) else ""
    bl = read_file(BLACKLIST_FILE).lower() if os.path.exists(BLACKLIST_FILE) else ""
    now = time.time()
    new_prev = {}
    for n in get_networks():
        r = run_q(["iw", "dev", n["iface"], "station", "dump"])
        if not r or not r.stdout or not r.stdout.strip():
            continue
        cur = None
        raw_devices = []
        for line in r.stdout.split("\n"):
            line = line.strip()
            if line.startswith("Station"):
                if cur:
                    raw_devices.append(cur)
                mac = line.split()[1]
                ip_, hostname, dtype = get_client_info(mac)
                cur = {"mac": mac, "iface": n["iface"], "ssid": n["ssid"],
                       "ip": ip_, "hostname": hostname, "dev_type": dtype,
                       "signal": "", "tx_b": 0, "rx_b": 0}
            elif "signal:" in line and cur:
                cur["signal"] = line.split("signal:")[-1].strip().split()[0] + " dBm"
            elif "tx bytes:" in line and cur:
                try: cur["tx_b"] = int(line.split()[-1])
                except Exception: pass
            elif "rx bytes:" in line and cur:
                try: cur["rx_b"] = int(line.split()[-1])
                except Exception: pass
        if cur:
            raw_devices.append(cur)
        for d in raw_devices:
            ps = _PREV_STATS.get(d["mac"], {})
            tx_speed = rx_speed = 0.0
            if ps:
                dt = now - ps.get("t", now)
                if dt > 0:
                    tx_speed = max(0, (d["tx_b"] - ps.get("tx", d["tx_b"])) / dt / 1024)
                    rx_speed = max(0, (d["rx_b"] - ps.get("rx", d["rx_b"])) / dt / 1024)
            new_prev[d["mac"]] = {"tx": d["tx_b"], "rx": d["rx_b"], "t": now}
            devices.append({
                "mac": d["mac"], "iface": d["iface"], "ssid": d["ssid"],
                "ip": d["ip"], "hostname": d["hostname"], "dev_type": d["dev_type"],
                "signal": d["signal"],
                "tx_speed": round(tx_speed, 1), "rx_speed": round(rx_speed, 1),
                "tx_mb": round(d["tx_b"] / 1048576, 2), "rx_mb": round(d["rx_b"] / 1048576, 2),
                "in_whitelist": d["mac"].lower() in wl,
                "in_blacklist": d["mac"].lower() in bl,
            })
    _PREV_STATS = new_prev
    return devices


def kick_ban(mac, iface):
    add_log(f"Kicking {mac} ({iface})...")
    r = run_cmd(["hostapd_cli", "-p", "/var/run/hostapd", "-i", iface, "deauthenticate", mac])
    if not r or r.returncode != 0:
        run_cmd(["iw", "dev", iface, "station", "del", mac])
    if not os.path.exists(BLACKLIST_FILE):
        write_file(BLACKLIST_FILE, "")
    existing = read_file(BLACKLIST_FILE).lower()
    if mac.lower() not in existing:
        with open(BLACKLIST_FILE, "a") as f:
            f.write(mac + "\n")
    for n in get_networks():
        write_hostapd_conf(n)
    if is_hotspot_active():
        run_cmd(["systemctl", "restart", "hotspot-manager-hostapd.service"])
    add_log(f"✓ {mac} kicked + banned")
    return {"ok": True}


def get_whitelist():
    return [l.strip() for l in read_file(WHITELIST_FILE).split("\n") if l.strip()]


def get_blacklist():
    return [l.strip() for l in read_file(BLACKLIST_FILE).split("\n") if l.strip()]


def enable_whitelist():
    if not os.path.exists(WHITELIST_FILE):
        write_file(WHITELIST_FILE, "")
    added = []
    existing = read_file(WHITELIST_FILE).lower()
    for n in get_networks():
        r = run_q(["iw", "dev", n["iface"], "station", "dump"])
        if r and r.stdout:
            for line in r.stdout.split("\n"):
                if line.strip().startswith("Station"):
                    mac = line.strip().split()[1]
                    if mac.lower() not in existing:
                        with open(WHITELIST_FILE, "a") as f:
                            f.write(mac + "\n")
                        existing += mac.lower() + "\n"
                        added.append(mac)
    s = load_settings(); s["whitelist_enabled"] = True; save_settings(s)
    for n in get_networks():
        write_hostapd_conf(n)
    if is_hotspot_active():
        run_cmd(["systemctl", "restart", "hotspot-manager-hostapd.service"])
    add_log(f"✓ Whitelist enabled. {len(added)} device(s) auto-added.")
    return {"ok": True}


def disable_whitelist():
    s = load_settings(); s["whitelist_enabled"] = False; save_settings(s)
    for n in get_networks():
        write_hostapd_conf(n)
    if is_hotspot_active():
        run_cmd(["systemctl", "restart", "hotspot-manager-hostapd.service"])
    add_log("✓ Whitelist disabled — network is now OPEN")
    return {"ok": True}


def add_to_whitelist(mac):
    if not os.path.exists(WHITELIST_FILE):
        write_file(WHITELIST_FILE, "")
    existing = read_file(WHITELIST_FILE).lower()
    if mac.lower() not in existing:
        with open(WHITELIST_FILE, "a") as f:
            f.write(mac + "\n")
        for n in get_networks():
            write_hostapd_conf(n)
        if is_hotspot_active():
            run_cmd(["systemctl", "restart", "hotspot-manager-hostapd.service"])
        add_log(f"✓ {mac} added to whitelist")
    else:
        add_log(f"~ {mac} is already in the whitelist")
    return {"ok": True}


def remove_from_whitelist(mac):
    run_cmd(["sed", "-i", f"/^{re.escape(mac)}$/Id", WHITELIST_FILE])
    for n in get_networks():
        write_hostapd_conf(n)
    if is_hotspot_active():
        run_cmd(["systemctl", "restart", "hotspot-manager-hostapd.service"])
    add_log(f"✓ {mac} removed from whitelist")
    return {"ok": True}


def unban(mac):
    run_cmd(["sed", "-i", f"/^{re.escape(mac)}$/Id", BLACKLIST_FILE])
    for n in get_networks():
        write_hostapd_conf(n)
    if is_hotspot_active():
        run_cmd(["systemctl", "restart", "hotspot-manager-hostapd.service"])
    add_log(f"✓ {mac} unbanned")
    return {"ok": True}


# ── SLEEP BLOCK ────────────────────────────────────────────────
def enable_sleep_block():
    if not is_hotspot_active():
        add_log("✗ Hotspot is not active — cannot enable sleep block")
        return
    os.makedirs(RUN_DIR, exist_ok=True)
    if os.path.exists(SLEEP_INHIBIT_PID):
        try:
            pid = int(read_file(SLEEP_INHIBIT_PID).strip())
            os.kill(pid, 0)
            return
        except Exception:
            try: os.remove(SLEEP_INHIBIT_PID)
            except Exception: pass
    r = run_q(["which", "systemd-inhibit"])
    if not r or r.returncode != 0:
        add_log("✗ systemd-inhibit not found")
        return
    proc = subprocess.Popen(
        ["systemd-inhibit", "--what=sleep:idle", "--who=Hotspot Manager",
         "--why=Hotspot is active", "sleep", "infinity"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    write_file(SLEEP_INHIBIT_PID, str(proc.pid))
    add_log(f"✓ Sleep block enabled (PID {proc.pid})")


def disable_sleep_block():
    if os.path.exists(SLEEP_INHIBIT_PID):
        try:
            pid = int(read_file(SLEEP_INHIBIT_PID).strip())
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.2)
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        except Exception:
            pass
        try: os.remove(SLEEP_INHIBIT_PID)
        except Exception: pass
    add_log("✓ Sleep block disabled")


def is_sleep_block_active():
    if not os.path.exists(SLEEP_INHIBIT_PID):
        return False
    try:
        pid = int(read_file(SLEEP_INHIBIT_PID).strip())
        os.kill(pid, 0)
        return True
    except Exception:
        try: os.remove(SLEEP_INHIBIT_PID)
        except Exception: pass
        return False


def toggle_sleep_block():
    s = load_settings()
    if is_sleep_block_active():
        disable_sleep_block()
        s["block_sleep"] = False
        save_settings(s)
        return {"status": "off", "msg": "Sleep block disabled"}
    enable_sleep_block()
    s["block_sleep"] = True
    save_settings(s)
    return {"status": "on", "msg": "Sleep block enabled"}


# ── PERMANENT (boot persistence) ────────────────────────────
def build_startup_script():
    lines = ["#!/bin/bash", "sleep 5"]
    for n in get_networks():
        lines += [
            f"nmcli device set {n['iface']} managed no 2>/dev/null",
            f"ip link set {n['iface']} up",
            f"ip addr add {n['hotspot_ip']}/24 dev {n['iface']} 2>/dev/null",
        ]
    lines.append("sysctl -w net.ipv4.ip_forward=1 > /dev/null")
    egress = get_default_iface() or "eth0"
    lines += [
        f"iptables -t nat -D POSTROUTING -o {egress} -j MASQUERADE 2>/dev/null",
        f"iptables -t nat -A POSTROUTING -o {egress} -j MASQUERADE",
        "systemctl restart hotspot-manager-hostapd.service",
        "systemctl restart dnsmasq",
    ]
    return "\n".join(lines) + "\n"


def make_permanent():
    add_log("Enabling permanent mode...")
    if not get_networks():
        add_log("⚠ No networks — create one first")
        return {"error": "No networks"}
    write_file(STARTUP_SCRIPT, build_startup_script())
    run_cmd(["chmod", "+x", STARTUP_SCRIPT])
    svc = (
        "[Unit]\nDescription=Hotspot Manager Startup\n"
        "After=network.target NetworkManager.service hotspot-manager-hostapd.service\n"
        "Wants=network.target\n\n[Service]\nType=oneshot\n"
        f"ExecStart={STARTUP_SCRIPT}\nRemainAfterExit=yes\nTimeoutStartSec=30\n\n"
        "[Install]\nWantedBy=multi-user.target\n"
    )
    write_file(SYSTEMD_STARTUP, svc)
    run_cmd(["mkdir", "-p", "/etc/systemd/system-sleep"])
    resume_hook = ('#!/bin/bash\ncase "$1" in\n'
                   f'    post) sleep 5 && {STARTUP_SCRIPT} & ;;\nesac\n')
    write_file(SLEEP_HOOK, resume_hook)
    run_cmd(["chmod", "+x", SLEEP_HOOK])
    run_cmd(["systemctl", "daemon-reload"])
    run_cmd(["systemctl", "enable", "hotspot-manager-startup.service"])
    run_cmd(["systemctl", "enable", "hotspot-manager-hostapd.service"])
    run_cmd(["systemctl", "enable", "dnsmasq"])
    r = run_q(["grep", "-q", "net.ipv4.ip_forward=1", "/etc/sysctl.conf"])
    if not r or r.returncode != 0:
        run_cmd(["bash", "-c", "echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf"])
    r = run_q(["which", "netfilter-persistent"])
    if not r or r.returncode != 0:
        run_cmd(["apt-get", "install", "-y", "iptables-persistent"])
    run_cmd(["netfilter-persistent", "save"])
    add_log("✓ Hotspot will auto-start on every boot")
    return {"ok": True}


def reset_permanent():
    add_log("Disabling permanent mode...")
    run_cmd(["systemctl", "disable", "hotspot-manager-startup.service"])
    run_cmd(["rm", "-f", SYSTEMD_STARTUP, STARTUP_SCRIPT, SLEEP_HOOK])
    run_cmd(["systemctl", "daemon-reload"])
    add_log("✓ Permanent mode disabled")
    return {"ok": True}


# ── SCHEDULE (cron based — works even if the app is closed) ───
def get_schedule():
    r = run_q(["crontab", "-l"])
    s = {"on_h": None, "on_m": None, "off_h": None, "off_m": None, "idle_mins": None}
    if not r or not r.stdout:
        return s
    for line in r.stdout.split("\n"):
        if "# hotspot-on" in line and not line.startswith("#"):
            p = line.strip().split()
            if len(p) >= 2:
                try: s["on_m"], s["on_h"] = int(p[0]), int(p[1])
                except Exception: pass
        elif "# hotspot-off" in line and not line.startswith("#"):
            p = line.strip().split()
            if len(p) >= 2:
                try: s["off_m"], s["off_h"] = int(p[0]), int(p[1])
                except Exception: pass
        elif "# hotspot-idle" in line and not line.startswith("#"):
            m = re.search(r"\*/(\d+)", line)
            if m:
                s["idle_mins"] = int(m.group(1))
    return s


def _cron_update(tag, new_line=None):
    r = run_q(["crontab", "-l"])
    existing = r.stdout if r and r.stdout else ""
    lines = [l for l in existing.split("\n") if l.strip() and f"# {tag}" not in l]
    if new_line:
        lines.append(new_line)
    new_cron = "\n".join(lines) + "\n"
    subprocess.run(["crontab", "-"], input=new_cron, text=True, capture_output=True)


def set_schedule_on(h, m):
    cmd = f"/usr/bin/python3 {CLI_PY} start"
    _cron_update("hotspot-on", f"{m} {h} * * * {cmd} # hotspot-on")
    add_log(f"✓ Auto ON set to {h:02d}:{m:02d}")
    return {"ok": True}


def set_schedule_off(h, m):
    cmd = f"/usr/bin/python3 {CLI_PY} stop"
    _cron_update("hotspot-off", f"{m} {h} * * * {cmd} # hotspot-off")
    add_log(f"✓ Auto OFF set to {h:02d}:{m:02d}")
    return {"ok": True}


def set_idle_timeout(mins):
    cmd = f"/usr/bin/python3 {CLI_PY} idle-check"
    _cron_update("hotspot-idle", f"*/{mins} * * * * {cmd} # hotspot-idle ({mins} min)")
    add_log(f"✓ Idle timeout set to {mins} min")
    return {"ok": True}


def clear_schedule(what):
    tags = {"on": ["hotspot-on"], "off": ["hotspot-off"], "idle": ["hotspot-idle"],
            "all": ["hotspot-on", "hotspot-off", "hotspot-idle"]}
    for tag in tags.get(what, []):
        _cron_update(tag)
    add_log(f"✓ Schedule cleared: {what}")
    return {"ok": True}


def idle_check():
    """Invoked from cron. Stops the hotspot if no clients are connected."""
    if not is_hotspot_active():
        return
    status = get_status()
    if status["total_clients"] == 0:
        add_log("Idle timeout: no devices connected — stopping hotspot")
        stop_hotspot()


# ── QR CODE ────────────────────────────────────────────────────
def get_qr(iface):
    r = run_q(["which", "qrencode"])
    if not r or r.returncode != 0:
        return {"error": "qrencode is not installed. Run Setup > Install & Configure first."}
    net = next((n for n in get_networks() if n["iface"] == iface), None)
    if not net:
        return {"error": "Network not found"}
    hidden_flag = ";H:true" if net["hidden"] else ""
    wifi_str = f"WIFI:S:{net['ssid']};T:WPA;P:{net['password']}{hidden_flag};;"
    r2 = subprocess.run(["qrencode", "-t", "SVG", "-o", "-", wifi_str],
                         capture_output=True, text=True)
    if r2.returncode == 0:
        return {"svg": r2.stdout, "ssid": net["ssid"], "band": net["band"],
                "hidden": net["hidden"]}
    return {"error": "Failed to generate QR code"}


# ── SETUP: INSTALL / DELETE ALL / APP PASSWORD ────────────────
def install_configure():
    add_log("[1/5] Updating package list...")
    run_cmd(["apt-get", "update", "-qq"])
    add_log("[2/5] Installing hostapd, dnsmasq, iptables, qrencode...")
    run_cmd(["apt-get", "install", "-y", "hostapd", "dnsmasq", "iptables", "qrencode"])
    add_log("[3/5] Disabling the default hostapd service (we use our own)...")
    run_cmd(["systemctl", "unmask", "hostapd"])
    run_cmd(["systemctl", "stop", "hostapd"])
    run_cmd(["systemctl", "disable", "hostapd"])
    add_log("[4/5] Writing base configuration...")
    os.makedirs(BASE_DIR, exist_ok=True)
    for f in (WHITELIST_FILE, BLACKLIST_FILE):
        if not os.path.exists(f):
            write_file(f, "")
    ensure_dnsmasq_confdir_included()
    install_systemd_hostapd_unit()
    if not os.path.exists(NETWORKS_FILE):
        save_networks([])
    if not os.path.exists(SETTINGS_FILE):
        save_settings(default_settings())
    add_log("[5/5] ✓ Setup complete.")
    return {"ok": True}


def delete_all_setup():
    add_log("Deleting all setup — please wait...")
    stop_hotspot()
    run_cmd(["systemctl", "disable", "hotspot-manager-startup.service"])
    run_cmd(["systemctl", "disable", "hotspot-manager-hostapd.service"])
    disable_sleep_block()
    for f in [SYSTEMD_STARTUP, STARTUP_SCRIPT, SLEEP_HOOK, SYSTEMD_HOSTAPD, HOSTAPD_LAUNCHER]:
        run_cmd(["rm", "-f", f])
    run_cmd(["systemctl", "daemon-reload"])
    for n in get_networks():
        run_cmd(["rm", "-f", f"{HOSTAPD_DIR}/hotspot-manager-{n['iface']}.conf"])
        run_cmd(["rm", "-f", f"{DNSMASQ_DIR}/hotspot-manager-{n['iface']}.conf"])
    run_cmd(["rm", "-f", NETWORKS_FILE, WHITELIST_FILE, BLACKLIST_FILE])
    run_cmd(["rm", "-f", SUDOERS_FILE])
    run_cmd(["sed", "-i", "/net.ipv4.ip_forward=1/d", "/etc/sysctl.conf"])
    r = run_q(["which", "netfilter-persistent"])
    if r and r.returncode == 0:
        run_cmd(["netfilter-persistent", "flush"])
    clear_schedule("all")
    add_log("[*] Removing packages (hostapd, dnsmasq, qrencode)...")
    run_cmd(["apt-get", "remove", "-y", "--purge", "hostapd", "dnsmasq", "qrencode"])
    run_cmd(["apt-get", "autoremove", "-y"])
    save_settings(default_settings())
    save_networks([])
    add_log("✓ All setup deleted. Run Install & Configure again to start over.")
    return {"ok": True}


def _sudoers_content(real_user):
    return (
        f'Defaults:{real_user} env_keep += "DISPLAY XAUTHORITY QT_QPA_PLATFORM '
        f'WAYLAND_DISPLAY XDG_RUNTIME_DIR HOME"\n'
        f'{real_user} ALL=(root) NOPASSWD: /usr/bin/python3 {MAIN_PY}\n'
    )


def _write_password_off_sudoers(real_user):
    """Writes (or re-writes) the NOPASSWD rule, validating it first.
    Returns True on success. Bootstraps the `sudo` package itself if it's
    missing, since the app is already root at this point and can do that
    without needing sudo to exist yet."""
    if not run_q(["which", "sudo"]) or run_q(["which", "sudo"]).returncode != 0:
        add_log("sudo package not found — installing it first...")
        run_cmd(["apt-get", "update", "-qq"])
        run_cmd(["apt-get", "install", "-y", "sudo"])
    if not run_q(["which", "visudo"]) or run_q(["which", "visudo"]).returncode != 0:
        add_log("✗ visudo not available even after installing sudo — aborting")
        return False

    content = _sudoers_content(real_user)
    tmp_path = f"{SUDOERS_FILE}.tmp"
    write_file(tmp_path, content)
    run_cmd(["chmod", "440", tmp_path])
    check = run_q(["visudo", "-cf", tmp_path])
    if not check or check.returncode != 0:
        err = check.stderr.strip() if check and check.stderr else "unknown error"
        add_log(f"✗ Invalid sudoers rule, not applied: {err}")
        run_cmd(["rm", "-f", tmp_path])
        return False
    run_cmd(["mv", tmp_path, SUDOERS_FILE])
    run_cmd(["chmod", "440", SUDOERS_FILE])
    return True


def ensure_password_off_sudoers():
    """Self-healing check, run at every app startup. If the setting says
    'no password needed' but the sudoers rule is missing/stale/broken
    (e.g. left over from an older app version, or deleted by hand), fix it
    on the spot — we're already root at this point regardless of how this
    particular launch got here, so this never requires an extra prompt."""
    s = load_settings()
    if not s.get("password_off"):
        return
    real_user = get_real_user()
    if not real_user:
        return
    expected = _sudoers_content(real_user)
    current = read_file(SUDOERS_FILE) if os.path.exists(SUDOERS_FILE) else ""
    if current != expected:
        add_log("Refreshing no-password sudoers rule...")
        _write_password_off_sudoers(real_user)


def toggle_app_password():
    s = load_settings()
    s["password_off"] = not s.get("password_off", False)
    if s["password_off"]:
        real_user = get_real_user()
        if not real_user:
            add_log("✗ Could not detect the username")
            return {"error": "Could not detect the username"}
        if not _write_password_off_sudoers(real_user):
            add_log("✗ Could not enable no-password mode — left unchanged")
            return {"error": "Failed to enable no-password mode (see Activity Log)"}
        add_log("✓ App Password OFF — will now launch without a password")
    else:
        run_cmd(["rm", "-f", SUDOERS_FILE])
        add_log("✓ App Password ON — will now require a password to launch")
    save_settings(s)
    return {"status": "off" if s["password_off"] else "on"}


def set_dark_mode(is_dark):
    s = load_settings()
    s["dark_mode"] = bool(is_dark)
    save_settings(s)
    return {"ok": True}
