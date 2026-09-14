from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QSpinBox,
    QRadioButton, QButtonGroup, QMessageBox,
)
from PyQt5.QtCore import QThreadPool

import backend
from worker import Worker
from widgets import Card, SectionTitle, Hint, Badge, make_button, ToggleSwitch

IDLE_OPTIONS = [5, 10, 15, 30]


class SchedulePage(QWidget):
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

        self.v.addWidget(SectionTitle("Schedule"))
        self.v.addWidget(Hint(
            "This schedule runs via cron — it keeps working even if the app is closed."))

        # Auto ON
        on_card = Card()
        on_card.addWidget(SectionTitle("Auto Turn ON"))
        row = QHBoxLayout()
        self.on_h = QSpinBox(); self.on_h.setRange(0, 23); self.on_h.setSuffix(" h")
        self.on_m = QSpinBox(); self.on_m.setRange(0, 59); self.on_m.setSuffix(" m")
        row.addWidget(QLabel("Time:")); row.addWidget(self.on_h); row.addWidget(self.on_m)
        row.addStretch()
        set_on = make_button("Set", "primary")
        clear_on = make_button("Clear")
        set_on.clicked.connect(self.on_set_on)
        clear_on.clicked.connect(lambda: self.on_clear("on"))
        row.addWidget(set_on); row.addWidget(clear_on)
        on_card.addLayout(row)
        self.on_status = Hint("Not set")
        on_card.addWidget(self.on_status)
        self.v.addWidget(on_card)

        # Auto OFF
        off_card = Card()
        off_card.addWidget(SectionTitle("Auto Turn OFF"))
        row2 = QHBoxLayout()
        self.off_h = QSpinBox(); self.off_h.setRange(0, 23); self.off_h.setSuffix(" h")
        self.off_m = QSpinBox(); self.off_m.setRange(0, 59); self.off_m.setSuffix(" m")
        row2.addWidget(QLabel("Time:")); row2.addWidget(self.off_h); row2.addWidget(self.off_m)
        row2.addStretch()
        set_off = make_button("Set", "primary")
        clear_off = make_button("Clear")
        set_off.clicked.connect(self.on_set_off)
        clear_off.clicked.connect(lambda: self.on_clear("off"))
        row2.addWidget(set_off); row2.addWidget(clear_off)
        off_card.addLayout(row2)
        self.off_status = Hint("Not set")
        off_card.addWidget(self.off_status)
        self.v.addWidget(off_card)

        # Idle timeout
        idle_card = Card()
        idle_card.addWidget(SectionTitle("Idle Timeout"))
        idle_card.addWidget(Hint("If no devices stay connected for this long, the hotspot turns off automatically."))
        idle_row = QHBoxLayout()
        self.idle_group = QButtonGroup(self)
        self.idle_radios = {}
        for mins in IDLE_OPTIONS:
            r = QRadioButton(f"{mins} min")
            self.idle_group.addButton(r)
            self.idle_radios[mins] = r
            idle_row.addWidget(r)
        idle_card.addLayout(idle_row)
        idle_btn_row = QHBoxLayout()
        idle_btn_row.addStretch()
        set_idle = make_button("Set", "primary")
        clear_idle = make_button("Clear")
        set_idle.clicked.connect(self.on_set_idle)
        clear_idle.clicked.connect(lambda: self.on_clear("idle"))
        idle_btn_row.addWidget(set_idle)
        idle_btn_row.addWidget(clear_idle)
        idle_card.addLayout(idle_btn_row)
        self.idle_status = Hint("Not set")
        idle_card.addWidget(self.idle_status)
        self.v.addWidget(idle_card)

        # Sleep block
        sleep_card = Card()
        sleep_row = QHBoxLayout()
        sleep_row.addWidget(SectionTitle("Prevent Sleep While Active"))
        sleep_row.addStretch()
        self.sleep_toggle = ToggleSwitch()
        self.sleep_toggle.stateChanged.connect(self.on_toggle_sleep)
        sleep_row.addWidget(self.sleep_toggle)
        sleep_card.addLayout(sleep_row)
        sleep_card.addWidget(Hint("The laptop won't sleep/suspend while the hotspot is active."))
        self.v.addWidget(sleep_card)

        # Clear all
        clear_card = Card()
        clear_card.addWidget(SectionTitle("Clear All Schedules"))
        clear_all_btn = make_button("Clear All", "danger")
        clear_all_btn.clicked.connect(self.on_clear_all)
        clear_card.addWidget(clear_all_btn)
        self.v.addWidget(clear_card)

        self.v.addStretch()
        self.refresh()

    def refresh(self):
        w = Worker(lambda: {"sched": backend.get_schedule(),
                             "status": backend.get_status()})
        w.signals.finished.connect(self._apply)
        self.pool.start(w)

    def _apply(self, data):
        s = data["sched"]
        if s["on_h"] is not None:
            self.on_status.setText(f"Currently set: {s['on_h']:02d}:{s['on_m']:02d}")
        else:
            self.on_status.setText("Not set")
        if s["off_h"] is not None:
            self.off_status.setText(f"Currently set: {s['off_h']:02d}:{s['off_m']:02d}")
        else:
            self.off_status.setText("Not set")
        if s["idle_mins"] is not None:
            self.idle_status.setText(f"Currently set: {s['idle_mins']} min")
            if s["idle_mins"] in self.idle_radios:
                self.idle_radios[s["idle_mins"]].setChecked(True)
        else:
            self.idle_status.setText("Not set")

        self.sleep_toggle.blockSignals(True)
        self.sleep_toggle.setChecked(data["status"]["sleep_block"])
        self.sleep_toggle.blockSignals(False)

    def on_set_on(self):
        w = Worker(backend.set_schedule_on, self.on_h.value(), self.on_m.value())
        w.signals.finished.connect(lambda r: (
            self.mw.toast.show_message("✓ Auto ON scheduled", "success"), self.refresh()))
        self.pool.start(w)

    def on_set_off(self):
        w = Worker(backend.set_schedule_off, self.off_h.value(), self.off_m.value())
        w.signals.finished.connect(lambda r: (
            self.mw.toast.show_message("✓ Auto OFF scheduled", "success"), self.refresh()))
        self.pool.start(w)

    def on_set_idle(self):
        checked = self.idle_group.checkedButton()
        if not checked:
            self.mw.toast.show_message("Please select a time", "error")
            return
        mins = next(m for m, r in self.idle_radios.items() if r is checked)
        w = Worker(backend.set_idle_timeout, mins)
        w.signals.finished.connect(lambda r: (
            self.mw.toast.show_message("✓ Idle timeout set", "success"), self.refresh()))
        self.pool.start(w)

    def on_clear(self, what):
        w = Worker(backend.clear_schedule, what)
        w.signals.finished.connect(lambda r: self.refresh())
        self.pool.start(w)

    def on_clear_all(self):
        reply = QMessageBox.question(self, "Clear All", "Clear all schedules?",
                                      QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        w = Worker(backend.clear_schedule, "all")
        w.signals.finished.connect(lambda r: (
            self.mw.toast.show_message("✓ All schedules cleared", "success"), self.refresh()))
        self.pool.start(w)

    def on_toggle_sleep(self, state):
        w = Worker(backend.toggle_sleep_block)
        w.signals.finished.connect(lambda r: self.refresh())
        self.pool.start(w)
