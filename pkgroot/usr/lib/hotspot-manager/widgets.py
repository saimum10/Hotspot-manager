from PyQt5.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QCheckBox, QWidget,
    QGraphicsOpacityEffect,
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QRectF
from PyQt5.QtGui import QPainter, QColor

import theme


class Card(QFrame):
    """A simple rounded Material-3-ish container."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(18, 16, 18, 16)
        self.layout_.setSpacing(10)

    def addWidget(self, w):
        self.layout_.addWidget(w)

    def addLayout(self, lay):
        self.layout_.addLayout(lay)


class SectionTitle(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("SectionTitle")


class Hint(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("Hint")
        self.setWordWrap(True)


class Badge(QLabel):
    """variant: ok / off / danger / warn / info"""

    def __init__(self, text, variant="info", parent=None):
        super().__init__(text, parent)
        self.setProperty("badge", variant)
        self.setAlignment(Qt.AlignCenter)

    def set_variant(self, variant, text=None):
        self.setProperty("badge", variant)
        if text is not None:
            self.setText(text)
        self.style().unpolish(self)
        self.style().polish(self)


class StatCard(QFrame):
    def __init__(self, label, value="--", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)
        self.value_lbl = QLabel(value)
        self.value_lbl.setObjectName("StatValue")
        self.label_lbl = QLabel(label)
        self.label_lbl.setObjectName("StatLabel")
        lay.addWidget(self.value_lbl)
        lay.addWidget(self.label_lbl)

    def set_value(self, v):
        self.value_lbl.setText(str(v))


class ToggleSwitch(QCheckBox):
    """A small custom-painted pill toggle switch (no animation, instant state)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = theme.palette(True)  # colors are readable enough in both themes
        track_on = QColor(c["success"])
        track_off = QColor(c["border"])
        knob_color = QColor("#FFFFFF")

        rect = QRectF(0, 0, self.width(), self.height())
        p.setPen(Qt.NoPen)
        p.setBrush(track_on if self.isChecked() else track_off)
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        knob_d = self.height() - 6
        x = self.width() - knob_d - 3 if self.isChecked() else 3
        p.setBrush(knob_color)
        p.drawEllipse(int(x), 3, knob_d, knob_d)
        p.end()


class Toast(QLabel):
    """Small transient notification shown at the bottom of the window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "background: rgba(30,33,41,235); color: #fff; padding: 10px 18px;"
            "border-radius: 12px; font-weight: 600; font-size: 12px;"
        )
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text, kind="info", msecs=2600):
        colors = {
            "info": "rgba(34,38,46,235)",
            "success": "rgba(31,86,50,235)",
            "error": "rgba(92,19,11,235)",
        }
        bg = colors.get(kind, colors["info"])
        self.setStyleSheet(
            f"background: {bg}; color: #fff; padding: 10px 18px;"
            "border-radius: 12px; font-weight: 600; font-size: 12px;"
        )
        self.setText(text)
        self.adjustSize()
        if self.parent():
            p = self.parent()
            x = p.x() + (p.width() - self.width()) // 2
            y = p.y() + p.height() - self.height() - 40
            self.move(x, y)
        self.show()
        self.raise_()
        self._timer.start(msecs)


def make_button(text, variant=None, parent=None):
    from PyQt5.QtWidgets import QPushButton
    b = QPushButton(text, parent)
    if variant:
        b.setProperty("variant", variant)
    b.setCursor(Qt.PointingHandCursor)
    return b


def hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("background: transparent; border: none;")
    f.setFixedHeight(1)
    return f
