from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QCheckBox,
)
from PyQt5.QtCore import Qt, QThreadPool

import backend
from worker import Worker
from widgets import Card, SectionTitle, Hint, Badge, make_button, ToggleSwitch


class DeviceRow(Card):
    def __init__(self, dev, on_kick, on_whitelist, parent=None):
        super().__init__(parent)
        top = QHBoxLayout()
        name = dev["hostname"] if dev["hostname"] != "unknown" else dev["mac"]
        title = QLabel(f"📱  {name}")
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        top.addWidget(title)
        if dev["dev_type"]:
            top.addWidget(Badge(dev["dev_type"], "info"))
        top.addWidget(Badge(dev["ssid"], "off"))
        if dev["in_whitelist"]:
            top.addWidget(Badge("Whitelisted", "ok"))
        if dev["in_blacklist"]:
            top.addWidget(Badge("Blacklisted", "danger"))
        top.addStretch()
        self.addLayout(top)

        info = QHBoxLayout()
        info.addWidget(QLabel(f"MAC: {dev['mac']}"))
        info.addWidget(QLabel(f"IP: {dev['ip']}"))
        if dev["signal"]:
            info.addWidget(QLabel(f"Signal: {dev['signal']}"))
        info.addStretch()
        self.addLayout(info)

        speed = QHBoxLayout()
        speed.addWidget(QLabel(f"↓ {dev['rx_speed']} KB/s   ↑ {dev['tx_speed']} KB/s"))
        speed.addWidget(QLabel(f"   Total: {dev['rx_mb']} MB / {dev['tx_mb']} MB"))
        speed.addStretch()
        wl_btn = make_button("+ Whitelist")
        wl_btn.clicked.connect(lambda: on_whitelist(dev["mac"]))
        kick_btn = make_button("Kick + Ban", "danger")
        kick_btn.clicked.connect(lambda: on_kick(dev["mac"], dev["iface"]))
        speed.addWidget(wl_btn)
        speed.addWidget(kick_btn)
        self.addLayout(speed)


class MacListRow(QHBoxLayout):
    def __init__(self, mac, on_remove):
        super().__init__()
        self.addWidget(QLabel(mac))
        self.addStretch()
        btn = make_button("Remove")
        btn.clicked.connect(lambda: on_remove(mac))
        self.addWidget(btn)


class DevicesPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.pool = QThreadPool.globalInstance()
        self._busy = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        self.v = QVBoxLayout(content)
        self.v.setContentsMargins(24, 20, 24, 20)
        self.v.setSpacing(16)

        header = QHBoxLayout()
        header.addWidget(SectionTitle("Connected Devices"))
        header.addStretch()
        self.auto_refresh_chk = QCheckBox("Auto-refresh")
        self.auto_refresh_chk.setChecked(True)
        header.addWidget(self.auto_refresh_chk)
        self.v.addLayout(header)

        self.devices_container = QVBoxLayout()
        self.devices_container.setSpacing(10)
        self.v.addLayout(self.devices_container)
        self.empty_hint = Hint("No devices connected. (Nothing shows here while the hotspot is off.)")
        self.v.addWidget(self.empty_hint)

        # Whitelist card
        wl_card = Card()
        wl_head = QHBoxLayout()
        wl_head.addWidget(SectionTitle("Whitelist (Trusted Devices)"))
        wl_head.addStretch()
        self.wl_toggle = ToggleSwitch()
        self.wl_toggle.stateChanged.connect(self.on_toggle_whitelist)
        wl_head.addWidget(QLabel("Enabled"))
        wl_head.addWidget(self.wl_toggle)
        wl_card.addLayout(wl_head)
        wl_card.addWidget(Hint("When enabled, only devices in the whitelist will be able to connect."))
        self.wl_list_container = QVBoxLayout()
        wl_card.addLayout(self.wl_list_container)
        self.v.addWidget(wl_card)

        # Blacklist card
        bl_card = Card()
        bl_card.addWidget(SectionTitle("Blacklist (Banned Devices)"))
        self.bl_list_container = QVBoxLayout()
        bl_card.addLayout(self.bl_list_container)
        self.v.addWidget(bl_card)

        self.v.addStretch()
        self.refresh()

    def refresh(self):
        if self._busy or not self.auto_refresh_chk.isChecked():
            return
        self._busy = True

        def fetch():
            return {
                "devices": backend.get_devices(),
                "whitelist_enabled": backend.load_settings().get("whitelist_enabled", False),
                "whitelist": backend.get_whitelist(),
                "blacklist": backend.get_blacklist(),
            }

        w = Worker(fetch)
        w.signals.finished.connect(self._apply)
        w.signals.error.connect(lambda e: setattr(self, "_busy", False))
        self.pool.start(w)

    def _apply(self, data):
        self._busy = False

        while self.devices_container.count():
            item = self.devices_container.takeAt(0)
            wgt = item.widget()
            if wgt:
                wgt.deleteLater()
        devices = data["devices"]
        self.empty_hint.setVisible(len(devices) == 0)
        for d in devices:
            self.devices_container.addWidget(DeviceRow(d, self.on_kick, self.on_whitelist))

        self.wl_toggle.blockSignals(True)
        self.wl_toggle.setChecked(data["whitelist_enabled"])
        self.wl_toggle.blockSignals(False)

        while self.wl_list_container.count():
            item = self.wl_list_container.takeAt(0)
            lay = item.layout()
            if lay:
                while lay.count():
                    sub = lay.takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
        for mac in data["whitelist"]:
            self.wl_list_container.addLayout(MacListRow(mac, self.on_remove_whitelist))

        while self.bl_list_container.count():
            item = self.bl_list_container.takeAt(0)
            lay = item.layout()
            if lay:
                while lay.count():
                    sub = lay.takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
        for mac in data["blacklist"]:
            self.bl_list_container.addLayout(MacListRow(mac, self.on_unban))

    def on_kick(self, mac, iface):
        w = Worker(backend.kick_ban, mac, iface)
        w.signals.finished.connect(lambda r: (self.mw.toast.show_message(
            f"✓ {mac} kicked + banned", "success"), self.refresh()))
        self.pool.start(w)

    def on_whitelist(self, mac):
        w = Worker(backend.add_to_whitelist, mac)
        w.signals.finished.connect(lambda r: (self.mw.toast.show_message(
            "✓ Added to whitelist", "success"), self.refresh()))
        self.pool.start(w)

    def on_remove_whitelist(self, mac):
        w = Worker(backend.remove_from_whitelist, mac)
        w.signals.finished.connect(lambda r: self.refresh())
        self.pool.start(w)

    def on_unban(self, mac):
        w = Worker(backend.unban, mac)
        w.signals.finished.connect(lambda r: self.refresh())
        self.pool.start(w)

    def on_toggle_whitelist(self, state):
        fn = backend.enable_whitelist if self.wl_toggle.isChecked() else backend.disable_whitelist
        w = Worker(fn)
        w.signals.finished.connect(lambda r: self.refresh())
        self.pool.start(w)
