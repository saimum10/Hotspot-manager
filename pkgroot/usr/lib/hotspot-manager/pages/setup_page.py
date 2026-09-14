from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QMessageBox,
)
from PyQt5.QtCore import QThreadPool

import backend
from worker import Worker
from widgets import Card, SectionTitle, Hint, Badge, make_button, ToggleSwitch


class SetupPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.pool = QThreadPool.globalInstance()

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

        self.v.addWidget(SectionTitle("Setup"))

        # Install & configure
        install_card = Card()
        install_card.addWidget(SectionTitle("Install & Configure"))
        install_card.addWidget(Hint(
            "Installs and configures hostapd, dnsmasq, iptables and qrencode. "
            "You only need to run this once — progress is shown in the Activity Log."))
        self.install_btn = make_button("Install & Configure", "primary")
        self.install_btn.clicked.connect(self.on_install)
        install_card.addWidget(self.install_btn)
        self.v.addWidget(install_card)

        # Delete all setup
        delete_card = Card()
        delete_card.addWidget(SectionTitle("Delete All Setup"))
        delete_card.addWidget(Hint(
            "Stops the hotspot and completely removes all networks, config, packages "
            "(hostapd, dnsmasq, qrencode) and schedules. This cannot be undone."))
        self.delete_btn = make_button("Delete All Setup", "danger")
        self.delete_btn.clicked.connect(self.on_delete_all)
        delete_card.addWidget(self.delete_btn)
        self.v.addWidget(delete_card)

        # App password
        pw_card = Card()
        pw_row = QHBoxLayout()
        pw_row.addWidget(SectionTitle("App Password"))
        pw_row.addStretch()
        self.pw_badge = Badge("ON", "ok")
        pw_row.addWidget(self.pw_badge)
        pw_card.addLayout(pw_row)
        pw_card.addWidget(Hint(
            "ON (default): the app asks for your system password every time it opens. "
            "OFF: the app opens instantly with no password prompt (a restricted "
            "no-password rule is set up just for this app)."))
        pw_toggle_row = QHBoxLayout()
        pw_toggle_row.addWidget(QLabel("Require password on launch"))
        pw_toggle_row.addStretch()
        self.pw_toggle = ToggleSwitch()
        self.pw_toggle.stateChanged.connect(self.on_toggle_password)
        pw_toggle_row.addWidget(self.pw_toggle)
        pw_card.addLayout(pw_toggle_row)
        self.v.addWidget(pw_card)

        # Appearance
        app_card = Card()
        app_row = QHBoxLayout()
        app_row.addWidget(SectionTitle("Appearance"))
        app_row.addStretch()
        app_card.addLayout(app_row)
        dark_row = QHBoxLayout()
        dark_row.addWidget(QLabel("Dark Mode"))
        dark_row.addStretch()
        self.dark_toggle = ToggleSwitch()
        self.dark_toggle.stateChanged.connect(self.on_toggle_dark)
        dark_row.addWidget(self.dark_toggle)
        app_card.addLayout(dark_row)
        self.v.addWidget(app_card)

        # Branding footer
        footer = QLabel("Hotspot Manager  •  Saimum  •  Debian")
        footer.setStyleSheet("color: #8A8D96; font-size: 11px; padding-top: 8px;")
        self.v.addWidget(footer)

        self.v.addStretch()
        self.refresh()

    def refresh(self):
        w = Worker(backend.get_status)
        w.signals.finished.connect(self._apply)
        self.pool.start(w)

    def _apply(self, status):
        password_off = status["password_off"]
        password_required = not password_off
        self.pw_badge.set_variant("ok" if password_required else "off",
                                   "ON" if password_required else "OFF")
        self.pw_toggle.blockSignals(True)
        self.pw_toggle.setChecked(password_required)
        self.pw_toggle.blockSignals(False)

        self.dark_toggle.blockSignals(True)
        self.dark_toggle.setChecked(status["dark_mode"])
        self.dark_toggle.blockSignals(False)

    def on_install(self):
        self.install_btn.setEnabled(False)
        self.install_btn.setText("Working... (see Activity Log)")
        w = Worker(backend.install_configure)
        w.signals.finished.connect(self._after_install)
        self.pool.start(w)

    def _after_install(self, result):
        self.install_btn.setEnabled(True)
        self.install_btn.setText("Install & Configure")
        if result and result.get("error"):
            self.mw.toast.show_message(result["error"], "error")
        else:
            self.mw.toast.show_message("✓ Install & Configure complete", "success")

    def on_delete_all(self):
        reply = QMessageBox.warning(
            self, "Delete All Setup",
            "Are you sure? This will remove all networks, config and packages. "
            "This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.delete_btn.setEnabled(False)
        self.delete_btn.setText("Working... (see Activity Log)")
        w = Worker(backend.delete_all_setup)
        w.signals.finished.connect(self._after_delete_all)
        self.pool.start(w)

    def _after_delete_all(self, result):
        self.delete_btn.setEnabled(True)
        self.delete_btn.setText("Delete All Setup")
        self.mw.toast.show_message("✓ All setup deleted", "success")
        self.mw.refresh_current_page_data()

    def on_toggle_password(self, state):
        # Toggle checked == "password required". backend.toggle_app_password()
        # simply flips the stored password_off flag each call, so clicking
        # the switch always moves the backend state to match what's shown.
        w = Worker(backend.toggle_app_password)
        w.signals.finished.connect(self._after_toggle_password)
        w.signals.error.connect(self._on_toggle_error)
        self.pool.start(w)

    def _on_toggle_error(self, err):
        self.mw.toast.show_message(f"Failed to change App Password setting: {err}", "error")
        self.refresh()

    def _after_toggle_password(self, result):
        if result and result.get("error"):
            self.mw.toast.show_message(result["error"], "error")
        self.refresh()

    def on_toggle_dark(self, state):
        is_dark = self.dark_toggle.isChecked()
        backend.set_dark_mode(is_dark)
        self.mw.apply_theme(is_dark)
