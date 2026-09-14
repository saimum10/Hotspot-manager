#!/usr/bin/env python3
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# PyQt5 itself must import cleanly before anything else — if this fails
# there is nothing we can show a dialog with, so write a crash log as a
# last resort (the app is launched via pkexec with no visible terminal).
CRASH_LOG = "/tmp/hotspot-manager-crash.log"


def _write_crash_log(text):
    try:
        with open(CRASH_LOG, "w") as f:
            f.write(text)
    except Exception:
        pass


try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QFont
    # Must be set before QApplication is constructed — fixes tiny/blurry
    # text and icons on HiDPI displays (a common cause of "everything
    # looks too small" on modern laptop screens).
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
except Exception:
    _write_crash_log(
        "PyQt5 import failed — python3-pyqt5 may not be installed correctly.\n\n"
        + traceback.format_exc()
    )
    sys.exit(1)


def show_fatal_error(title, text):
    """Show a dialog AND write a crash log, so the failure is never silent —
    this app has no terminal since it's launched via pkexec/sudo from the
    desktop menu."""
    _write_crash_log(text)
    try:
        QMessageBox.critical(None, title, text + f"\n\n(Details saved to: {CRASH_LOG})")
    except Exception:
        pass


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Hotspot Manager")
    app.setQuitOnLastWindowClosed(True)
    app.setFont(QFont("Noto Sans", 10))

    if os.geteuid() != 0:
        QMessageBox.critical(
            None, "Permission Required",
            "Hotspot Manager cannot run without root privilege.\n\n"
            "Please launch 'Hotspot Manager' from the Application Menu "
            "instead of running main.py directly.")
        sys.exit(1)

    # Everything below this point can fail for all sorts of reasons
    # (missing optional dependency, bad config file, etc.) — any of it
    # must end up in a visible dialog, never a silent exit.
    try:
        import backend
        import theme
        from main_window import MainWindow

        os.makedirs(backend.BASE_DIR, exist_ok=True)
        settings = backend.load_settings()
        backend.ensure_password_off_sudoers()
        app.setStyleSheet(theme.stylesheet(settings.get("dark_mode", True)))

        win = MainWindow()
        win.show()
        backend.add_log("Hotspot Manager started")
    except Exception:
        show_fatal_error(
            "Hotspot Manager — Startup Error",
            "Failed to start the app:\n\n" + traceback.format_exc())
        sys.exit(1)

    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Absolute last-resort catch (e.g. error thrown outside main()'s
        # own try/except, like QApplication construction itself failing).
        _write_crash_log(traceback.format_exc())
        raise
