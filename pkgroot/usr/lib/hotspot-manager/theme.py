"""
Material 3 inspired color tokens + QSS stylesheet.
Minimal, flat, rounded — no gradients, no heavy shadows, no excessive animation.
"""

DARK = {
    "bg":            "#121212",
    "surface":       "#1E1E1E",
    "surface_hi":    "#2A2A2C",
    "card":          "#1E1E1E",
    "border":        "#38383A",
    "text":          "#F0F0F0",
    "text_dim":      "#ABABAF",
    "primary":       "#82AAFF",
    "on_primary":    "#0A1B3D",
    "primary_container": "#26407A",
    "success":       "#7FDD9A",
    "on_success":    "#0B3B1D",
    "danger":        "#FF9E92",
    "on_danger":     "#5C130B",
    "warn":          "#F4C77C",
    "on_warn":       "#4A3200",
    "sidebar":       "#181818",
}

LIGHT = {
    "bg":            "#F7F8FC",
    "surface":       "#FFFFFF",
    "surface_hi":    "#F0F2F8",
    "card":          "#FFFFFF",
    "border":        "#DFE2EA",
    "text":          "#1B1C1F",
    "text_dim":      "#5C5F66",
    "primary":       "#3E64C7",
    "on_primary":    "#FFFFFF",
    "primary_container": "#DCE4FF",
    "success":       "#1C8B45",
    "on_success":    "#FFFFFF",
    "danger":        "#C43A2C",
    "on_danger":     "#FFFFFF",
    "warn":          "#8C5A00",
    "on_warn":       "#FFFFFF",
    "sidebar":       "#EEF0F6",
}


def palette(dark=True):
    return DARK if dark else LIGHT


def stylesheet(dark=True):
    c = palette(dark)
    return f"""
    * {{
        font-family: "Noto Sans", "Segoe UI", sans-serif;
        outline: none;
    }}
    QWidget {{
        background: {c['bg']};
        color: {c['text']};
        font-size: 14px;
    }}
    QLabel, QCheckBox, QRadioButton {{
        background: transparent;
    }}
    #Sidebar {{
        background: {c['sidebar']};
        border-right: 1px solid {c['border']};
    }}
    #BrandTitle {{
        font-size: 19px;
        font-weight: 700;
        color: {c['text']};
        padding: 2px 4px;
    }}
    #BrandSubtitle {{
        font-size: 12px;
        color: {c['text_dim']};
        padding: 0 4px 6px 4px;
    }}
    QPushButton#NavButton {{
        text-align: left;
        padding: 10px 14px;
        border: none;
        border-radius: 10px;
        background: transparent;
        color: {c['text_dim']};
        font-size: 14px;
        font-weight: 600;
    }}
    QPushButton#NavButton:hover {{
        background: {c['surface_hi']};
        color: {c['text']};
    }}
    QPushButton#NavButton:checked {{
        background: {c['primary_container']};
        color: {c['primary']};
    }}
    QFrame#Card {{
        background: {c['card']};
        border: 1px solid {c['border']};
        border-radius: 14px;
    }}
    QFrame#StatCard {{
        background: {c['card']};
        border: 1px solid {c['border']};
        border-radius: 14px;
    }}
    QLabel#StatValue {{
        font-size: 26px;
        font-weight: 700;
        color: {c['text']};
    }}
    QLabel#StatLabel {{
        font-size: 12px;
        color: {c['text_dim']};
        font-weight: 600;
    }}
    QLabel#SectionTitle {{
        font-size: 17px;
        font-weight: 700;
        color: {c['text']};
        padding: 2px 0;
    }}
    QLabel#Hint {{
        font-size: 12.5px;
        color: {c['text_dim']};
    }}
    QPushButton {{
        border-radius: 10px;
        padding: 9px 18px;
        font-weight: 600;
        border: 1px solid {c['border']};
        background: {c['surface_hi']};
        color: {c['text']};
    }}
    QPushButton:hover {{
        background: {c['border']};
    }}
    QPushButton:disabled {{
        color: {c['text_dim']};
        background: {c['surface']};
    }}
    QPushButton[variant="primary"] {{
        background: {c['primary']};
        color: {c['on_primary']};
        border: none;
    }}
    QPushButton[variant="primary"]:hover {{
        background: {c['primary']};
    }}
    QPushButton[variant="danger"] {{
        background: transparent;
        color: {c['danger']};
        border: 1px solid {c['danger']};
    }}
    QPushButton[variant="danger"]:hover {{
        background: {c['danger']};
        color: {c['on_danger']};
    }}
    QPushButton[variant="success"] {{
        background: {c['success']};
        color: {c['on_success']};
        border: none;
    }}
    QPushButton[variant="flat"] {{
        background: transparent;
        border: none;
        padding: 6px 10px;
    }}
    QPushButton[variant="flat"]:hover {{
        background: {c['surface_hi']};
    }}
    QLineEdit, QComboBox, QSpinBox {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 10px;
        padding: 8px 10px;
        color: {c['text']};
        selection-background-color: {c['primary']};
    }}
    QLineEdit:focus, QComboBox:focus {{
        border: 1px solid {c['primary']};
    }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        selection-background-color: {c['primary_container']};
        outline: none;
    }}
    QRadioButton, QCheckBox {{
        spacing: 8px;
        color: {c['text']};
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {c['border']};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QPlainTextEdit#LogPanel {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 10px;
        color: {c['text_dim']};
        font-family: "DejaVu Sans Mono", monospace;
        font-size: 11.5px;
        padding: 6px;
    }}
    QLabel[badge="ok"] {{
        background: {c['success']}; color: {c['on_success']};
        border-radius: 9px; padding: 3px 10px; font-size: 12px; font-weight: 700;
    }}
    QLabel[badge="off"] {{
        background: {c['border']}; color: {c['text_dim']};
        border-radius: 9px; padding: 3px 10px; font-size: 12px; font-weight: 700;
    }}
    QLabel[badge="danger"] {{
        background: {c['danger']}; color: {c['on_danger']};
        border-radius: 9px; padding: 3px 10px; font-size: 12px; font-weight: 700;
    }}
    QLabel[badge="warn"] {{
        background: {c['warn']}; color: {c['on_warn']};
        border-radius: 9px; padding: 3px 10px; font-size: 12px; font-weight: 700;
    }}
    QLabel[badge="info"] {{
        background: {c['primary_container']}; color: {c['primary']};
        border-radius: 9px; padding: 3px 10px; font-size: 12px; font-weight: 700;
    }}
    QToolTip {{
        background: {c['surface_hi']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 4px 8px;
    }}
    """
