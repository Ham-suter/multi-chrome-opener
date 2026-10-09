"""Chrome Multi Opener entry point."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import tempfile
import json
import tkinter as tk
import customtkinter as ctk

from app.config import ConfigStore, default_config_path
from app.gui import ChromeMultiOpener
from app.themes import PRESETS, get_preset


def run_application(path: Path, smoke_report: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    log_dir = path.parent.parent / "logs" if path.parent.name == "data" else path.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(handlers=[RotatingFileHandler(log_dir / "app.log", maxBytes=1024 * 1024,
                        backupCount=3, encoding="utf-8")], level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.info("Application started")
    store = ConfigStore(path)
    if smoke_report is not None:
        store.config.auto_paste_clipboard_url = False
    application = ChromeMultiOpener(store)
    logging.info("GUI ready: %d profiles", len(application.profiles))
    if smoke_report is not None:
        errors: list[str] = []
        transitions: list[str] = []
        preset_checks: list[list[str]] = []
        initial_preset = application.config_data.color_theme_preset
        initial_background = application.cget("fg_color")
        modes = iter(["System", "Dark", "Light", "System", "Light", "Dark", "System"])

        def callback_error(exc, value, traceback) -> None:
            errors.append(str(value))
            logging.error("Diagnostic callback failure", exc_info=(exc, value, traceback))

        application.report_callback_exception = callback_error

        def change_next() -> None:
            mode = next(modes, None)
            if mode is None:
                application.settings_dialog.destroy()
                application.select_all(False)
                application.tk.call(application.protocol("WM_DELETE_WINDOW"))
                smoke_report.write_text(json.dumps({
                    "ok": not errors, "transitions": transitions, "errors": errors,
                    "presets": preset_checks, "initial_preset": initial_preset,
                    "initial_background": initial_background,
                    "config_path": str(path.resolve()), "log_path": str((log_dir / "app.log").resolve()),
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                return
            application.theme_control.set(mode, from_button_callback=True)
            if application._theme_after is None:
                application.request_theme(mode)
            application.after(180, lambda: verify_mode(mode))

        def verify_mode(mode: str) -> None:
            if application.config_data.appearance_mode != mode or application._theme_after is not None:
                errors.append(f"Theme change failed: {mode}")
            application.select_all(True)
            application.select_all(False)
            application.geometry("470x650+100+100")
            application.open_settings()  # Existing settings window must be reused.
            if application.settings_dialog.grab_current() is not None:
                errors.append("Unexpected modal grab")
            transitions.append(mode)
            check_next_preset(mode, iter(PRESETS.values()))

        def check_next_preset(mode, presets) -> None:
            preset = next(presets, None)
            if preset is None:
                application.after(80, change_next)
                return
            application.preset_control._dropdown_callback(preset.name)

            def verify_preset() -> None:
                if (application._preset_after is not None
                        or application.config_data.color_theme_preset != preset.id
                        or application.cget("fg_color") != preset.window_bg
                        or application.open_button.cget("fg_color") != preset.primary
                        or application.url_entry.cget("fg_color") != preset.input_bg
                        or application.config_data.appearance_mode != mode):
                    errors.append(f"Preset change failed: {mode}/{preset.id}")
                if (application.profile_frame.cget("fg_color") != preset.surface
                        or tk.Frame.cget(application.profile_frame, "background").upper() != preset.surface
                        or application.profile_frame._parent_canvas.cget("background").upper() != preset.surface):
                    errors.append(f"Scrollable interior color failed: {preset.id}")
                for row in application.rows.values():
                    if row.cget("fg_color") != preset.surface:
                        errors.append(f"Row color failed: {preset.id}")
                    for child in row.winfo_children():
                        if isinstance(child, ctk.CTkCheckBox) and (child.cget("fg_color") != preset.accent or child.cget("bg_color") != preset.surface):
                            errors.append(f"Checkbox color failed: {preset.id}")
                        elif isinstance(child, ctk.CTkButton) and child.cget("fg_color") != preset.secondary:
                            errors.append(f"Edit button color failed: {preset.id}")
                        elif isinstance(child, ctk.CTkLabel):
                            expected = preset.muted_text if child.grid_info()["row"] == 1 else preset.text
                            if child.cget("text_color") != expected or child.cget("bg_color") != preset.surface:
                                errors.append(f"Profile label color failed: {preset.id}")
                preset_checks.append([mode, preset.id])
                check_next_preset(mode, presets)

            application.after(100, verify_preset)

        def start_smoke() -> None:
            application.open_settings()
            change_next()

        application.after(300, start_smoke)
    application.mainloop()
    logging.info("Application closed")


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--render-test":
        from app.render_check import run_render_check
        run_render_check(Path(sys.argv[2]).resolve())
        return
    # Explicit build diagnostic; never read or change a user's config or open URLs.
    if len(sys.argv) == 3 and sys.argv[1] in {"--portable-smoke-test", "--portable-restore-test"}:
        path = default_config_path()
        if path.exists() and sys.argv[1] != "--portable-restore-test":
            raise RuntimeError("Portable diagnostic requires a fresh folder without config.json")
        try:
            run_application(path, Path(sys.argv[2]).resolve())
        finally:
            logging.shutdown()
    elif len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        report = Path(sys.argv[2]).resolve()
        with tempfile.TemporaryDirectory(prefix="chrome-opener-check-") as folder:
            try:
                run_application(Path(folder) / "config.json", report)
            finally:
                logging.shutdown()
    else:
        run_application(default_config_path())


if __name__ == "__main__":
    main()
