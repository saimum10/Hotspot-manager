from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QComboBox,
)
from PyQt5.QtCore import Qt, QThreadPool, QByteArray

try:
    from PyQt5.QtSvg import QSvgWidget
    HAS_QTSVG = True
except Exception:
    QSvgWidget = None
    HAS_QTSVG = False

import backend
from worker import Worker
from widgets import Card, SectionTitle, Hint, Badge, make_button


class QrCodePage(QWidget):
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

        self.v.addWidget(SectionTitle("QR Code"))
        self.v.addWidget(Hint("Scan the QR code to connect to the Wi-Fi instantly."))

        card = Card()
        row = QHBoxLayout()
        self.net_combo = QComboBox()
        row.addWidget(QLabel("Network:"))
        row.addWidget(self.net_combo, 1)
        gen_btn = make_button("Generate QR", "primary")
        gen_btn.clicked.connect(self.on_generate)
        row.addWidget(gen_btn)
        card.addLayout(row)
        self.v.addWidget(card)

        self.qr_card = Card()
        self.qr_card.setMinimumHeight(320)
        if HAS_QTSVG:
            self.qr_svg = QSvgWidget()
            self.qr_svg.setFixedSize(260, 260)
        else:
            self.qr_svg = QLabel("QtSvg module not found —\nrun 'sudo apt install python3-pyqt5.qtsvg'")
            self.qr_svg.setFixedSize(260, 260)
            self.qr_svg.setAlignment(Qt.AlignCenter)
            self.qr_svg.setWordWrap(True)
        qr_wrap = QHBoxLayout()
        qr_wrap.addStretch()
        qr_wrap.addWidget(self.qr_svg)
        qr_wrap.addStretch()
        self.qr_card.addLayout(qr_wrap)
        self.info_lbl = QLabel("Select a network and press Generate QR")
        self.info_lbl.setAlignment(Qt.AlignCenter)
        self.qr_card.addWidget(self.info_lbl)
        self.v.addWidget(self.qr_card)
        self.v.addStretch()

        self.refresh_networks()

    def refresh(self):
        # Called only when this page becomes active (not on every poll tick),
        # so it never resets the user's current selection while they're here.
        self.refresh_networks()

    def refresh_networks(self):
        current_iface = self.net_combo.currentData()
        self.net_combo.blockSignals(True)
        self.net_combo.clear()
        for n in backend.get_networks():
            self.net_combo.addItem(f"{n['ssid']}  ({n['iface']})", n["iface"])
        if current_iface:
            idx = self.net_combo.findData(current_iface)
            if idx >= 0:
                self.net_combo.setCurrentIndex(idx)
        self.net_combo.blockSignals(False)

    def on_generate(self):
        iface = self.net_combo.currentData()
        if not iface:
            self.mw.toast.show_message("Create a network first", "error")
            return
        w = Worker(backend.get_qr, iface)
        w.signals.finished.connect(self._apply)
        self.pool.start(w)

    def _apply(self, result):
        if result.get("error"):
            self.mw.toast.show_message(result["error"], "error")
            self.info_lbl.setText(result["error"])
            return
        if HAS_QTSVG:
            self.qr_svg.load(QByteArray(result["svg"].encode("utf-8")))
        vis = "Hidden" if result["hidden"] else "Visible"
        self.info_lbl.setText(f"SSID: {result['ssid']}   •   Band: {result['band']} GHz   •   {vis}")
