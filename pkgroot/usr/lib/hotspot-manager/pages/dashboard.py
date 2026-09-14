from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QMessageBox,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, QThreadPool

import backend
from worker import Worker
from widgets import Card, StatCard, SectionTitle, Hint, Badge, make_button, hline


class NetworkRow(Card):
    def __init__(self, net, parent=None):
        super().__init__(parent)
        self.net = net
        self.password_hidden = True

        top = QHBoxLayout()
        title = QLabel(f"📶  {net['ssid']}")
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        top.addWidget(title)
        top.addStretch()
        top.addWidget(Badge(net["iface"], "info"))
        top.addWidget(Badge(f"{net['band']} GHz", "info"))
        top.addWidget(Badge("Hidden" if net["hidden"] else "Visible",
                             "warn" if net["hidden"] else "off"))
        top.addWidget(Badge("Active" if net["active"] else "Inactive",
                             "ok" if net["active"] else "off"))
        self.addLayout(top)

        row2 = QHBoxLayout()
        self.pw_label = QLabel("Password: ••••••••")
        row2.addWidget(self.pw_label)
        self.eye_btn = make_button("👁", "flat")
        self.eye_btn.setFixedWidth(34)
        self.eye_btn.clicked.connect(self.toggle_pw)
        row2.addWidget(self.eye_btn)
        row2.addStretch()
        row2.addWidget(QLabel(f"IP: {net['ip']}"))
        row2.addSpacing(16)
        row2.addWidget(QLabel(f"Clients: {net['clients']}"))
        self.addLayout(row2)

    def toggle_pw(self):
        self.password_hidden = not self.password_hidden
        if self.password_hidden:
            self.pw_label.setText("Password: ••••••••")
        else:
            self.pw_label.setText(f"Password: {self.net['password']}")


class DashboardPage(QWidget):
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

        self.v.addWidget(SectionTitle("Dashboard"))

        # stat row
        stat_row = QHBoxLayout()
        stat_row.setSpacing(12)
        self.stat_status = StatCard("STATUS", "OFF")
        self.stat_networks = StatCard("ACTIVE NETWORKS", "0/0")
        self.stat_clients = StatCard("TOTAL CLIENTS", "0")
        self.stat_uptime = StatCard("UPTIME", "--")
        for s in (self.stat_status, self.stat_networks, self.stat_clients, self.stat_uptime):
            stat_row.addWidget(s)
        self.v.addLayout(stat_row)

        # actions card
        action_card = Card()
        action_card.addWidget(SectionTitle("Controls"))
        btn_row = QHBoxLayout()
        self.start_btn = make_button("▶  Start Hotspot", "success")
        self.stop_btn = make_button("■  Stop Hotspot", "danger")
        self.start_btn.clicked.connect(self.on_start)
        self.stop_btn.clicked.connect(self.on_stop)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        action_card.addLayout(btn_row)

        btn_row2 = QHBoxLayout()
        self.perm_btn = make_button("Make Permanent")
        self.reset_perm_btn = make_button("Reset Permanent")
        self.perm_btn.clicked.connect(self.on_make_permanent)
        self.reset_perm_btn.clicked.connect(self.on_reset_permanent)
        btn_row2.addWidget(self.perm_btn)
        btn_row2.addWidget(self.reset_perm_btn)
        btn_row2.addStretch()
        self.perm_badge = Badge("Permanent: OFF", "off")
        self.sleep_badge = Badge("Sleep Block: OFF", "off")
        btn_row2.addWidget(self.perm_badge)
        btn_row2.addWidget(self.sleep_badge)
        action_card.addLayout(btn_row2)
        self.v.addWidget(action_card)

        # networks list
        self.v.addWidget(SectionTitle("Your Networks"))
        self.networks_container = QVBoxLayout()
        self.networks_container.setSpacing(10)
        self.v.addLayout(self.networks_container)

        self.empty_hint = Hint(
            "No networks created yet. Go to the Network page and press "
            "\"+ Create Network\" to set up a Wi-Fi hotspot network."
        )
        self.v.addWidget(self.empty_hint)
        self.v.addStretch()

        self.refresh()

    # ── data refresh ──────────────────────────────────────────
    def refresh(self):
        if self._busy:
            return
        self._busy = True
        w = Worker(backend.get_status)
        w.signals.finished.connect(self._apply_status)
        w.signals.error.connect(lambda e: setattr(self, "_busy", False))
        self.pool.start(w)

    def _apply_status(self, status):
        self._busy = False
        active = status["active"]
        self.stat_status.set_value("ON" if active else "OFF")
        self.stat_networks.set_value(
            f"{sum(1 for n in status['networks'] if n['active'])}/{status['count']}")
        self.stat_clients.set_value(status["total_clients"])
        self.stat_uptime.set_value(status["uptime"])

        self.perm_badge.set_variant("ok" if status["permanent"] else "off",
                                     f"Permanent: {'ON' if status['permanent'] else 'OFF'}")
        self.sleep_badge.set_variant("ok" if status["sleep_block"] else "off",
                                      f"Sleep Block: {'ON' if status['sleep_block'] else 'OFF'}")

        # rebuild network rows
        while self.networks_container.count():
            item = self.networks_container.takeAt(0)
            wgt = item.widget()
            if wgt:
                wgt.deleteLater()

        nets = status["networks"]
        self.empty_hint.setVisible(len(nets) == 0)
        for n in nets:
            self.networks_container.addWidget(NetworkRow(n))

    # ── actions ───────────────────────────────────────────────
    def on_start(self):
        self.start_btn.setEnabled(False)
        self.mw.toast.show_message("Starting hotspot...", "info")
        w = Worker(backend.start_hotspot)
        w.signals.finished.connect(self._after_start)
        self.pool.start(w)

    def _after_start(self, result):
        self.start_btn.setEnabled(True)
        if result and result.get("error"):
            self.mw.toast.show_message(result["error"], "error")
        else:
            self.mw.toast.show_message("✓ Hotspot started", "success")
        self.refresh()

    def on_stop(self):
        self.stop_btn.setEnabled(False)
        w = Worker(backend.stop_hotspot)
        w.signals.finished.connect(self._after_stop)
        self.pool.start(w)

    def _after_stop(self, result):
        self.stop_btn.setEnabled(True)
        self.mw.toast.show_message("✓ Hotspot stopped", "info")
        self.refresh()

    def on_make_permanent(self):
        w = Worker(backend.make_permanent)
        w.signals.finished.connect(lambda r: self._after_perm(r, True))
        self.pool.start(w)

    def on_reset_permanent(self):
        reply = QMessageBox.question(
            self, "Reset Permanent",
            "Turn off Permanent mode? It will no longer auto-start at boot.",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        w = Worker(backend.reset_permanent)
        w.signals.finished.connect(lambda r: self._after_perm(r, False))
        self.pool.start(w)

    def _after_perm(self, result, enabling):
        if result and result.get("error"):
            self.mw.toast.show_message(result["error"], "error")
        else:
            msg = "✓ Permanent mode enabled" if enabling else "✓ Permanent mode disabled"
            self.mw.toast.show_message(msg, "success")
        self.refresh()
