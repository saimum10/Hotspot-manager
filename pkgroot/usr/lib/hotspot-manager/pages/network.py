from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QDialog,
    QLineEdit, QComboBox, QRadioButton, QButtonGroup, QMessageBox,
    QFormLayout,
)
from PyQt5.QtCore import Qt, QThreadPool

import backend
from worker import Worker
from widgets import Card, SectionTitle, Hint, Badge, make_button


class NetworkDialog(QDialog):
    def __init__(self, parent, mode="create", net=None):
        super().__init__(parent)
        self.mode = mode
        self.net = net or {}
        self.setWindowTitle("Create Network" if mode == "create" else f"Edit Network — {net['iface']}")
        self.setMinimumWidth(380)
        self.pool = QThreadPool.globalInstance()

        v = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        # Adapter
        if mode == "create":
            self.adapters = backend.get_available_adapters_for_create()
            self.adapter_combo = QComboBox()
            if self.adapters:
                for a in self.adapters:
                    self.adapter_combo.addItem(f"{a['iface']}  ({'/'.join(a['bands'])} GHz)", a)
            else:
                self.adapter_combo.addItem("No free adapter available", None)
                self.adapter_combo.setEnabled(False)
            self.adapter_combo.currentIndexChanged.connect(self.on_adapter_changed)
            form.addRow("Wi-Fi Adapter", self.adapter_combo)
        else:
            all_adapters = backend.list_adapters()
            self.fixed_bands = next(
                (a["bands"] for a in all_adapters if a["iface"] == net["iface"]), ["2.4", "5"])
            lbl = QLabel(net["iface"])
            lbl.setStyleSheet("font-weight: 700;")
            form.addRow("Wi-Fi Adapter", lbl)

        # SSID
        self.ssid_edit = QLineEdit(net.get("ssid", "") if net else "")
        self.ssid_edit.setPlaceholderText("Network name")
        form.addRow("Network Name", self.ssid_edit)

        # Password
        pw_row = QHBoxLayout()
        self.pw_edit = QLineEdit(net.get("password", "") if net else "")
        self.pw_edit.setPlaceholderText("At least 8 characters")
        self.pw_edit.setEchoMode(QLineEdit.Password)
        pw_row.addWidget(self.pw_edit)
        eye = make_button("👁", "flat")
        eye.setFixedWidth(34)
        eye.clicked.connect(self.toggle_pw)
        pw_row.addWidget(eye)
        form.addRow("Password", pw_row)

        # Band
        self.band_group = QButtonGroup(self)
        band_row = QHBoxLayout()
        self.band_24 = QRadioButton("2.4 GHz")
        self.band_5 = QRadioButton("5 GHz")
        self.band_group.addButton(self.band_24)
        self.band_group.addButton(self.band_5)
        band_row.addWidget(self.band_24)
        band_row.addWidget(self.band_5)
        form.addRow("Band", band_row)

        # Visibility
        self.vis_group = QButtonGroup(self)
        vis_row = QHBoxLayout()
        self.vis_visible = QRadioButton("Visible")
        self.vis_hidden = QRadioButton("Hidden")
        self.vis_group.addButton(self.vis_visible)
        self.vis_group.addButton(self.vis_hidden)
        vis_row.addWidget(self.vis_visible)
        vis_row.addWidget(self.vis_hidden)
        form.addRow("Visibility", vis_row)

        v.addLayout(form)

        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet("color: #E4685D; font-weight: 600;")
        self.error_lbl.setWordWrap(True)
        v.addWidget(self.error_lbl)

        btn_row = QHBoxLayout()
        cancel_btn = make_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self.save_btn = make_button("Save & Apply", "primary")
        self.save_btn.clicked.connect(self.on_save)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        v.addLayout(btn_row)

        # initial state
        if mode == "create":
            self.on_adapter_changed(0)
        else:
            self._apply_bands(self.fixed_bands)
            if net.get("band") == "5":
                self.band_5.setChecked(True)
            else:
                self.band_24.setChecked(True)
            if net.get("hidden"):
                self.vis_hidden.setChecked(True)
            else:
                self.vis_visible.setChecked(True)

    def _apply_bands(self, bands):
        self.band_24.setEnabled("2.4" in bands)
        self.band_5.setEnabled("5" in bands)
        if "2.4" in bands:
            self.band_24.setChecked(True)
        elif "5" in bands:
            self.band_5.setChecked(True)
        self.vis_visible.setChecked(True)

    def on_adapter_changed(self, idx):
        data = self.adapter_combo.currentData() if self.adapters else None
        bands = data["bands"] if data else ["2.4"]
        self._apply_bands(bands)

    def toggle_pw(self):
        if self.pw_edit.echoMode() == QLineEdit.Password:
            self.pw_edit.setEchoMode(QLineEdit.Normal)
        else:
            self.pw_edit.setEchoMode(QLineEdit.Password)

    def on_save(self):
        ssid = self.ssid_edit.text().strip()
        password = self.pw_edit.text()
        band = "5" if self.band_5.isChecked() else "2.4"
        hidden = self.vis_hidden.isChecked()

        if self.mode == "create":
            data = self.adapter_combo.currentData()
            if not data:
                self.error_lbl.setText("No free Wi-Fi adapter available")
                return
            iface = data["iface"]
            fn = backend.create_network
            args = (iface, ssid, password, band, hidden)
        else:
            iface = self.net["iface"]
            fn = backend.update_network
            args = (iface, ssid, password, band, hidden)

        self.save_btn.setEnabled(False)
        w = Worker(fn, *args)
        w.signals.finished.connect(self._after_save)
        self.pool.start(w)

    def _after_save(self, result):
        self.save_btn.setEnabled(True)
        if result and result.get("error"):
            self.error_lbl.setText(result["error"])
        else:
            self.accept()


class NetworkListRow(Card):
    def __init__(self, net, on_edit, on_delete, parent=None):
        super().__init__(parent)
        row = QHBoxLayout()
        title = QLabel(f"📶  {net['ssid']}")
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        row.addWidget(title)
        row.addWidget(Badge(net["iface"], "info"))
        row.addWidget(Badge(f"{net['band']} GHz", "info"))
        row.addWidget(Badge("Hidden" if net["hidden"] else "Visible",
                             "warn" if net["hidden"] else "off"))
        row.addStretch()
        edit_btn = make_button("Edit")
        del_btn = make_button("Delete", "danger")
        edit_btn.clicked.connect(lambda: on_edit(net))
        del_btn.clicked.connect(lambda: on_delete(net))
        row.addWidget(edit_btn)
        row.addWidget(del_btn)
        self.addLayout(row)


class NetworkPage(QWidget):
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

        header = QHBoxLayout()
        header.addWidget(SectionTitle("Networks"))
        header.addStretch()
        self.create_btn = make_button("+ Create Network", "primary")
        self.create_btn.clicked.connect(self.on_create)
        header.addWidget(self.create_btn)
        self.v.addLayout(header)

        self.v.addWidget(Hint(
            "Each network uses its own Wi-Fi adapter — only wireless adapters "
            "are listed here (wired/Ethernet ports like enp3s0 can't broadcast "
            "a hotspot). If you have more than one Wi-Fi adapter, multiple "
            "networks can run at the same time."))

        self.list_container = QVBoxLayout()
        self.list_container.setSpacing(10)
        self.v.addLayout(self.list_container)

        self.empty_hint = Hint("No networks created yet.")
        self.v.addWidget(self.empty_hint)
        self.v.addStretch()

        self.refresh()

    def refresh(self):
        while self.list_container.count():
            item = self.list_container.takeAt(0)
            wgt = item.widget()
            if wgt:
                wgt.deleteLater()
        nets = backend.get_networks()
        self.empty_hint.setVisible(len(nets) == 0)
        for n in nets:
            self.list_container.addWidget(NetworkListRow(n, self.on_edit, self.on_delete))

    def on_create(self):
        dlg = NetworkDialog(self, mode="create")
        if dlg.exec_() == QDialog.Accepted:
            self.mw.toast.show_message("✓ Network created", "success")
            self.refresh()
            self.mw.refresh_current_page_data()

    def on_edit(self, net):
        dlg = NetworkDialog(self, mode="edit", net=net)
        if dlg.exec_() == QDialog.Accepted:
            self.mw.toast.show_message("✓ Network updated", "success")
            self.refresh()
            self.mw.refresh_current_page_data()

    def on_delete(self, net):
        reply = QMessageBox.question(
            self, "Delete Network",
            f"Delete \"{net['ssid']}\" ({net['iface']})?",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        w = Worker(backend.delete_network, net["iface"])
        w.signals.finished.connect(lambda r: self._after_delete(r))
        self.pool.start(w)

    def _after_delete(self, result):
        if result and result.get("error"):
            self.mw.toast.show_message(result["error"], "error")
        else:
            self.mw.toast.show_message("✓ Network deleted", "success")
        self.refresh()
