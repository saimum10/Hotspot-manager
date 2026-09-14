from PyQt5.QtWidgets import (
    QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QPlainTextEdit, QButtonGroup, QApplication, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon

import backend
import theme
from widgets import Toast, make_button
from pages.dashboard import DashboardPage
from pages.network import NetworkPage
from pages.devices import DevicesPage
from pages.schedule import SchedulePage
from pages.qrcode_page import QrCodePage
from pages.setup_page import SetupPage

ICON_PATH = "/usr/share/icons/hicolor/scalable/apps/hotspot-manager.svg"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hotspot Manager — Saimum | Debian")
        self.resize(1080, 720)
        try:
            self.setWindowIcon(QIcon(ICON_PATH))
        except Exception:
            pass

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ─────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(14, 18, 14, 14)
        sb.setSpacing(4)

        brand_row = QHBoxLayout()
        brand_title = QLabel("📡 Hotspot Manager")
        brand_title.setObjectName("BrandTitle")
        brand_row.addWidget(brand_title)
        sb.addLayout(brand_row)
        brand_sub = QLabel("Saimum | Debian")
        brand_sub.setObjectName("BrandSubtitle")
        sb.addWidget(brand_sub)
        sb.addSpacing(10)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "🏠  Dashboard"),
            ("network", "📶  Network"),
            ("devices", "💻  Devices"),
            ("schedule", "⏰  Schedule"),
            ("qrcode", "🔳  QR Code"),
            ("setup", "⚙️  Setup"),
        ]
        for key, label in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self.switch_page(k))
            self.nav_group.addButton(btn)
            self.nav_buttons[key] = btn
            sb.addWidget(btn)

        sb.addStretch()

        log_label = QLabel("Activity Log")
        log_label.setObjectName("SectionTitle")
        log_label.setStyleSheet("font-size: 12px; padding-top: 6px;")
        sb.addWidget(log_label)
        self.log_panel = QPlainTextEdit()
        self.log_panel.setObjectName("LogPanel")
        self.log_panel.setReadOnly(True)
        self.log_panel.setFixedHeight(150)
        sb.addWidget(self.log_panel)

        exit_btn = make_button("⏻  Exit App")
        exit_btn.clicked.connect(self.on_exit)
        sb.addWidget(exit_btn)

        root.addWidget(sidebar)

        # ── Pages ───────────────────────────────────────────
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.pages = {
            "dashboard": DashboardPage(self),
            "network": NetworkPage(self),
            "devices": DevicesPage(self),
            "schedule": SchedulePage(self),
            "qrcode": QrCodePage(self),
            "setup": SetupPage(self),
        }
        self.page_order = ["dashboard", "network", "devices", "schedule", "qrcode", "setup"]
        for key in self.page_order:
            self.stack.addWidget(self.pages[key])

        self.toast = Toast(self)

        self.switch_page("dashboard")

        # ── timers ──────────────────────────────────────────
        # Note: the Setup page is intentionally excluded from this periodic
        # tick (see refresh_current_page_data) — its toggles (App Password,
        # Dark Mode) were being snapped back to their old state by a race
        # between the click's own write and this timer's read landing right
        # after it. Nothing on Setup changes on its own, so it only needs
        # to refresh on navigation / right after its own actions.
        self.data_timer = QTimer(self)
        self.data_timer.setInterval(3000)
        self.data_timer.timeout.connect(lambda: self.refresh_current_page_data(periodic=True))
        self.data_timer.start()

        self.log_timer = QTimer(self)
        self.log_timer.setInterval(2000)
        self.log_timer.timeout.connect(self.refresh_log)
        self.log_timer.start()
        self.refresh_log()

    def switch_page(self, key):
        self.nav_buttons[key].setChecked(True)
        idx = self.page_order.index(key)
        self.stack.setCurrentIndex(idx)
        self.refresh_current_page_data()

    def refresh_current_page_data(self, periodic=False):
        page = self.stack.currentWidget()
        if periodic and page is self.pages["setup"]:
            return
        if hasattr(page, "refresh"):
            page.refresh()

    def refresh_log(self):
        lines = backend.get_log(80)
        self.log_panel.setPlainText("\n".join(lines))
        sb = self.log_panel.verticalScrollBar()
        sb.setValue(sb.maximum())

    def apply_theme(self, dark=True):
        app = QApplication.instance()
        app.setStyleSheet(theme.stylesheet(dark))

    def on_exit(self):
        # Only closes the app window — the hotspot itself keeps running.
        QApplication.instance().quit()

    def closeEvent(self, event):
        QApplication.instance().quit()
        event.accept()
