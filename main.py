"""
TubeMeasurementTimer
====================
A desktop GUI tool for running multiple production timers simultaneously
and capturing user-entered measurements at configurable checkpoints.

Designed for manufacturing / process monitoring workflows where multiple
parts or tubes must be measured at repeatable elapsed times after a process
step.

Author  : Hemy Gulati
GitHub  : https://github.com/HemyGulati/TubeMeasurementTimer
Date    : 16 April 2026
Version : 1.0.0
Licence : MIT — see LICENSE.txt

Dependencies
------------
    tkinter     Standard Python GUI toolkit (usually bundled with Python)
    csv         CSV logging
    json        Config save/load
    datetime    Local timestamps
    webbrowser  Open GitHub link from About popup

Usage
-----
    python main.py
"""

import csv
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

UNIT_SECONDS = {"seconds": 1.0, "minutes": 60.0, "hours": 3600.0}
UNIT_LABELS = {"seconds": "s", "minutes": "min", "hours": "hr"}

APP_TITLE = "Tube Measurement Timer v1"
CSV_HEADERS = ["timer name", "time", "duration since start", "user input value"]
TICK_MS = 200
DEFAULT_MILESTONES = [5, 10, 15, 25, 27, 30, 32, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150]


def app_settings_path() -> str:
    base = os.path.join(os.path.expanduser("~"), ".tube_timer_app")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "settings.json")


class CSVLogger:
    def __init__(self):
        self.csv_path = ""

    def set_path(self, path: str):
        self.csv_path = path
        self._ensure_file()

    def _ensure_file(self):
        if not self.csv_path:
            return
        folder = os.path.dirname(self.csv_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        if not os.path.exists(self.csv_path) or os.path.getsize(self.csv_path) == 0:
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)
                f.flush()
                os.fsync(f.fileno())

    def append_row(self, timer_name: str, local_time: str, duration: str, value: str):
        if not self.csv_path:
            raise ValueError("No CSV save location selected.")
        self._ensure_file()
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timer_name, local_time, duration, value])
            f.flush()
            os.fsync(f.fileno())


@dataclass
class TimerState:
    milestones: list[float]
    name_var: tk.StringVar
    running: bool = False
    start_monotonic: float | None = None
    paused_elapsed: float = 0.0
    triggered: set[float] = field(default_factory=set)
    pending: list[float] = field(default_factory=list)
    flash_on: bool = False
    last_alerted_milestone: float | None = None


class EditableMilestoneTable(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.edit_var = tk.StringVar()
        self.edit_entry = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(self, columns=("time",), show="headings", height=10, selectmode="browse")
        self.tree.heading("time", text=self.app.unit_label())
        self.tree.column("time", anchor="center", width=58)
        self.tree.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        btns = ttk.Frame(self)
        btns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Button(btns, text="+", command=self.add_row, width=3).pack(side="left")
        ttk.Button(btns, text="-", command=self.remove_selected, width=3).pack(side="left", padx=4)
        ttk.Button(btns, text="Sort", command=self.sort_clean, width=6).pack(side="left")

        self.tree.bind("<Double-1>", self._begin_edit)
        self.tree.bind("<Delete>", lambda _e: self.remove_selected())

    def load_values(self, values: list[int]):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for value in values:
            self.tree.insert("", "end", values=(value,))

    def get_values(self) -> list[float]:
        values = []
        for item in self.tree.get_children():
            raw = str(self.tree.item(item, "values")[0]).strip()
            if not raw:
                continue
            try:
                val = float(raw)
            except ValueError:
                continue
            if val >= 0:
                values.append(round(val, 6))
        return values

    def add_row(self, value: str = ""):
        item = self.tree.insert("", "end", values=(value,))
        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)
        self.app.sync_milestones_from_table_to_text()

    def remove_selected(self):
        for item in self.tree.selection():
            self.tree.delete(item)
        self.app.sync_milestones_from_table_to_text()

    def sort_clean(self):
        values = sorted({round(v, 6) for v in self.get_values()})
        self.load_values(values)
        self.app.sync_milestones_from_table_to_text()

    def _begin_edit(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item or column != "#1":
            return
        bbox = self.tree.bbox(item, column)
        if not bbox:
            return
        x, y, width, height = bbox
        value = self.tree.item(item, "values")[0]
        if self.edit_entry is not None:
            self.edit_entry.destroy()
        self.edit_var.set(value)
        self.edit_entry = ttk.Entry(self.tree, textvariable=self.edit_var)
        self.edit_entry.place(x=x, y=y, width=width, height=height)
        self.edit_entry.focus_set()
        self.edit_entry.select_range(0, "end")
        self.edit_entry.bind("<Return>", lambda _e: self._commit_edit(item))
        self.edit_entry.bind("<FocusOut>", lambda _e: self._commit_edit(item))
        self.edit_entry.bind("<Escape>", lambda _e: self._cancel_edit())

    def _commit_edit(self, item):
        if self.edit_entry is None:
            return
        self.tree.item(item, values=(self.edit_var.get().strip(),))
        self.edit_entry.destroy()
        self.edit_entry = None
        self.app.sync_milestones_from_table_to_text()

    def _cancel_edit(self):
        if self.edit_entry is not None:
            self.edit_entry.destroy()
            self.edit_entry = None


class TimerRow:
    def __init__(self, master, app, row_index: int):
        self.app = app
        self.row_index = row_index
        self.frame = ttk.Frame(master, style="TimerCard.TFrame", padding=(6, 4))
        self.name_var = tk.StringVar(value=f"T{row_index + 1}")
        self.elapsed_var = tk.StringVar(value="0.0 s")
        self.status_var = tk.StringVar(value="Idle")
        self.prompt_var = tk.StringVar(value="No input due")
        self.input_var = tk.StringVar(value="")
        self.next_due_var = tk.StringVar(value="Next: -")
        self.pending_list_var = tk.StringVar(value="Pending: -")
        self.duplicate_var = tk.StringVar(value="")
        self.state = TimerState(self.app.get_milestones(), self.name_var)
        self._build_ui()
        self._show_prompt(False)
        self._set_frame_style("normal")
        self._refresh_due_display()
        self.name_var.trace_add("write", self._on_name_change)

    def _build_ui(self):
        for idx in (1, 7):
            self.frame.columnconfigure(idx, weight=1)

        ttk.Entry(self.frame, textvariable=self.name_var, width=10).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Label(self.frame, textvariable=self.elapsed_var, style="Value.TLabel", width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(self.frame, textvariable=self.status_var, width=14).grid(row=0, column=2, sticky="w", padx=(2, 4))
        ttk.Label(self.frame, textvariable=self.next_due_var, width=10).grid(row=0, column=3, sticky="w")
        ttk.Label(self.frame, textvariable=self.duplicate_var, style="Warn.TLabel", width=12).grid(row=0, column=4, sticky="w")

        ttk.Button(self.frame, text="Start", width=5, command=self.start).grid(row=0, column=5, padx=1)
        ttk.Button(self.frame, text="Stop", width=5, command=self.stop).grid(row=0, column=6, padx=1)
        ttk.Button(self.frame, text="Reset", width=5, command=self.reset).grid(row=0, column=7, padx=1)
        ttk.Button(self.frame, text="X", width=3, command=self.remove).grid(row=0, column=8, padx=(3, 0))

        ttk.Label(self.frame, textvariable=self.prompt_var, style="Alert.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 0))
        ttk.Label(self.frame, textvariable=self.pending_list_var, width=18).grid(row=1, column=3, columnspan=2, sticky="w", pady=(3, 0))
        self.entry = ttk.Entry(self.frame, textvariable=self.input_var, width=10, state="disabled")
        self.entry.grid(row=1, column=5, sticky="w", pady=(3, 0))
        self.entry.bind("<Return>", lambda _e: self.submit_value())
        self.entry.bind("<Button-1>", self._on_entry_click)
        self.save_button = ttk.Button(self.frame, text="Save", width=5, command=self.submit_value, state="disabled")
        self.save_button.grid(row=1, column=6, padx=1, pady=(3, 0))
        self.skip_button = ttk.Button(self.frame, text="Skip", width=5, command=self.skip_pending, state="disabled")
        self.skip_button.grid(row=1, column=7, padx=1, pady=(3, 0))

    def _on_name_change(self, *_args):
        self.app.update_duplicate_warnings()
        self.app.schedule_settings_save()

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def remove(self):
        self.frame.destroy()
        self.app.remove_timer(self)

    def _show_prompt(self, show: bool):
        state = "normal" if show else "disabled"
        self.entry.configure(state=state)
        self.save_button.configure(state=state)
        self.skip_button.configure(state=state)

    def _on_entry_click(self, _event):
        if self.state.pending:
            self.app.set_manual_override(self)

    def _set_frame_style(self, mode: str):
        style_map = {
            "normal": "TimerCard.TFrame",
            "flash": "TimerCardFlash.TFrame",
            "due": "TimerCardDue.TFrame",
            "soon": "TimerCardSoon.TFrame",
        }
        self.frame.configure(style=style_map.get(mode, "TimerCard.TFrame"))

    def refresh_milestones(self, milestones: list[int]):
        elapsed = self.elapsed_seconds()
        self.state.milestones = milestones[:]
        self.state.triggered = {m for m in self.state.triggered if m in milestones}
        self.state.pending = [m for m in self.state.pending if m in milestones]
        if self.state.running:
            for m in milestones:
                if elapsed >= m and m not in self.state.triggered and m not in self.state.pending:
                    self.state.pending.append(m)
                    self.app.register_due_event(self, m)
            self.state.pending.sort()
        self.update_prompt()

    def start(self):
        if self.state.running:
            return
        self.state.start_monotonic = self.app.now_monotonic() - self.state.paused_elapsed
        self.state.running = True
        self.update_prompt()

    def stop(self):
        if not self.state.running:
            return
        self.state.paused_elapsed = self.elapsed_seconds()
        self.state.running = False
        self.update_prompt(force_no_flash=True)

    def reset(self):
        self.state.running = False
        self.state.start_monotonic = None
        self.state.paused_elapsed = 0.0
        self.state.triggered.clear()
        self.state.pending.clear()
        self.app.remove_due_events_for_timer(self)
        self.state.flash_on = False
        self.state.last_alerted_milestone = None
        self.elapsed_var.set("0.0 s")
        self.status_var.set("Idle")
        self.prompt_var.set("No input due")
        self.input_var.set("")
        self._show_prompt(False)
        self._set_frame_style("normal")
        self._refresh_due_display()

    def elapsed_seconds(self) -> float:
        if self.state.running and self.state.start_monotonic is not None:
            return max(0.0, self.app.now_monotonic() - self.state.start_monotonic)
        return max(0.0, self.state.paused_elapsed)

    @staticmethod
    def format_duration(seconds: float) -> str:
        if abs(seconds - round(seconds)) < 1e-9:
            return str(int(round(seconds)))
        return f"{seconds:.1f}"

    def update(self):
        elapsed = self.elapsed_seconds()
        self.elapsed_var.set(self.app.format_elapsed_seconds(elapsed))
        if self.state.running:
            for m in self.state.milestones:
                if elapsed >= m and m not in self.state.triggered and m not in self.state.pending:
                    self.state.pending.append(m)
                    self.app.register_due_event(self, m)
            self.state.pending.sort()
        self._refresh_due_display()

    def _refresh_due_display(self):
        next_due = None
        elapsed = self.elapsed_seconds()
        for m in self.state.milestones:
            if m not in self.state.triggered and m not in self.state.pending and m > elapsed:
                next_due = m
                break
        if self.state.pending:
            self.next_due_var.set(f"Due: {self.app.format_checkpoint(self.state.pending[0])}")
            shown = ", ".join(self.app.format_checkpoint(m) for m in self.state.pending[:4])
            if len(self.state.pending) > 4:
                shown += "..."
            self.pending_list_var.set(f"Pending: {shown}")
        else:
            self.next_due_var.set(f"Next: {self.app.format_checkpoint(next_due)}" if next_due is not None else "Next: done")
            self.pending_list_var.set("Pending: -")

    def update_prompt(self, force_no_flash: bool = False):
        if self.state.pending:
            milestone = self.state.pending[0]
            is_active = self.app.is_active_due(self, milestone)
            waiting_due = self.app.is_waiting_due(self, milestone)
            self.prompt_var.set(f"Reading due now: {self.app.format_checkpoint(milestone)}")
            self._show_prompt(True)

            if self.state.running:
                if is_active:
                    self.status_var.set("Input due")
                elif waiting_due:
                    self.status_var.set("Queued - due")
                else:
                    self.status_var.set("Input due")
            else:
                if is_active:
                    self.status_var.set("Stopped - due")
                elif waiting_due:
                    self.status_var.set("Queued - stopped")
                else:
                    self.status_var.set("Stopped - due")

            if self.state.running and is_active and not force_no_flash:
                self.state.flash_on = not self.state.flash_on
                self._set_frame_style("flash" if self.state.flash_on else "due")
            elif is_active or waiting_due:
                self.state.flash_on = False
                self._set_frame_style("due")
            elif self.app.is_next_soon(self):
                self.state.flash_on = False
                self._set_frame_style("soon")
            else:
                self.state.flash_on = False
                self._set_frame_style("normal")

            if is_active and self.state.last_alerted_milestone != milestone:
                self.state.last_alerted_milestone = milestone
                self.app.alert_user(self)
            if is_active:
                self.app.focus_due_timer(self)
        else:
            self.app.remove_due_events_for_timer(self, only_resolved=True)
            self.prompt_var.set("No input due")
            if self.state.running:
                self.status_var.set("Running")
            elif self.state.start_monotonic is None and self.state.paused_elapsed == 0.0:
                self.status_var.set("Idle")
            else:
                self.status_var.set("Stopped")
            self._show_prompt(False)
            self.state.flash_on = False
            if self.app.is_next_soon(self):
                self._set_frame_style("soon")
            else:
                self._set_frame_style("normal")
        self._refresh_due_display()

    def skip_pending(self):
        if not self.state.pending:
            return
        milestone = self.state.pending.pop(0)
        self.app.remove_due_event(self, milestone)
        self.state.triggered.add(milestone)
        self.state.last_alerted_milestone = None
        self.input_var.set("")
        self.app.clear_manual_override_if_matches(self)
        self.update_prompt(force_no_flash=not self.state.running)
        self.app.advance_due_queue()

    def submit_value(self):
        if not self.state.pending:
            return
        value = self.input_var.get().strip()
        if not value:
            messagebox.showwarning(APP_TITLE, "Please enter a value before saving.")
            return
        timer_name = self.name_var.get().strip() or f"Timer {self.row_index + 1}"
        milestone = self.state.pending.pop(0)
        local_time = datetime.now().strftime("%H:%M")
        try:
            self.app.logger.append_row(timer_name, local_time, self.app.format_duration_for_csv(float(milestone)), value)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not save to CSV:\n{e}")
            self.state.pending.insert(0, milestone)
            return
        self.app.remove_due_event(self, milestone)
        self.state.triggered.add(milestone)
        self.state.last_alerted_milestone = None
        self.input_var.set("")
        self.app.clear_manual_override_if_matches(self)
        self.update_prompt(force_no_flash=not self.state.running)
        self.app.advance_due_queue()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1320x780")
        self.minsize(1120, 680)
        self.logger = CSVLogger()
        self.timers: list[TimerRow] = []
        self.settings_after_id = None
        self.current_alert_name = tk.StringVar(value="No timer due")
        self.fullscreen_var = tk.BooleanVar(value=False)
        self.theme_var = tk.StringVar(value="dark")
        self.unit_var = tk.StringVar(value="seconds")
        self.last_config_path = ""
        self.due_event_queue: list[dict] = []
        self.due_event_counter = 0
        self.focused_due_timer: TimerRow | None = None
        self.manual_override_timer: TimerRow | None = None
        self.soon_timer: TimerRow | None = None

        settings = self.load_settings()
        self.unit_var.set(settings.get("checkpoint_unit", "seconds"))
        self.milestone_text = tk.StringVar(value=settings.get("milestone_text", ",".join(str(v) for v in DEFAULT_MILESTONES)))
        default_csv = settings.get("csv_path") or os.path.join(os.path.expanduser("~"), "Desktop", "tube_timer_data.csv")
        self.csv_path_var = tk.StringVar(value=default_csv)
        self.logger.set_path(default_csv)

        self._build_style()
        self._build_ui()

        self.last_config_path = settings.get("last_config_path", "")
        self._autoload_last_config()

        milestones = self.get_milestones()
        self.milestone_table.load_values(milestones)
        restored_names = settings.get("timer_names") or ["R1T1"]
        for name in restored_names:
            self.add_timer(name=name)
        self.theme_var.set(settings.get("theme", "dark"))
        self.apply_theme(self.theme_var.get())
        if settings.get("fullscreen"):
            self.set_fullscreen(True)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(TICK_MS, self._tick)
        self.update_duplicate_warnings()

    def load_settings(self) -> dict:
        path = app_settings_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_settings(self):
        data = {
            "milestone_text": self.milestone_text.get(),
            "csv_path": self.csv_path_var.get().strip(),
            "timer_names": [t.name_var.get().strip() for t in self.timers],
            "theme": self.theme_var.get(),
            "fullscreen": bool(self.fullscreen_var.get()),
            "last_config_path": self.last_config_path,
            "checkpoint_unit": self.unit_var.get(),
        }
        with open(app_settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def schedule_settings_save(self):
        if self.settings_after_id is not None:
            self.after_cancel(self.settings_after_id)
        self.settings_after_id = self.after(400, self._save_settings_safe)

    def _save_settings_safe(self):
        self.settings_after_id = None
        try:
            self.save_settings()
        except Exception:
            pass

    def _build_style(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

    def unit_key(self) -> str:
        value = self.unit_var.get().strip().lower()
        return value if value in UNIT_SECONDS else "seconds"

    def unit_label(self) -> str:
        return UNIT_LABELS[self.unit_key()]

    def unit_seconds_factor(self) -> float:
        return UNIT_SECONDS[self.unit_key()]

    def display_to_seconds(self, value: float) -> float:
        return float(value) * self.unit_seconds_factor()

    def seconds_to_display(self, seconds: float) -> float:
        return float(seconds) / self.unit_seconds_factor()

    @staticmethod
    def _format_number(value: float) -> str:
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f"{value:.3f}".rstrip("0").rstrip(".")

    def format_checkpoint(self, seconds_value: float) -> str:
        return f"{self._format_number(self.seconds_to_display(seconds_value))}{self.unit_label()}"

    def format_elapsed_seconds(self, seconds_value: float) -> str:
        return f"{self._format_number(self.seconds_to_display(seconds_value))} {self.unit_label()}"

    def format_duration_for_csv(self, seconds_value: float) -> str:
        return self._format_number(self.seconds_to_display(seconds_value))

    def on_unit_change(self, *_args):
        if hasattr(self, "milestone_table"):
            self.milestone_table.tree.heading("time", text=self.unit_label())
        for timer in getattr(self, "timers", []):
            timer.update_prompt(force_no_flash=not timer.state.running)
        self.schedule_settings_save()


    def register_due_event(self, timer, milestone: float):
        for event in self.due_event_queue:
            if event["timer"] is timer and event["milestone"] == milestone:
                return
        self.due_event_counter += 1
        self.due_event_queue.append({"order": self.due_event_counter, "timer": timer, "milestone": milestone})

    def remove_due_event(self, timer, milestone: float):
        self.due_event_queue = [
            event for event in self.due_event_queue
            if not (event["timer"] is timer and event["milestone"] == milestone)
        ]
        if self.manual_override_timer is timer and milestone not in timer.state.pending:
            self.manual_override_timer = None
        if self.manual_override_timer is timer:
            self.manual_override_timer = None
        if self.active_due_event() is None:
            self.focused_due_timer = None

    def remove_due_events_for_timer(self, timer, only_resolved: bool = False):
        if only_resolved:
            pending_set = set(timer.state.pending)
            self.due_event_queue = [
                event for event in self.due_event_queue
                if not (event["timer"] is timer and event["milestone"] not in pending_set)
            ]
        else:
            self.due_event_queue = [event for event in self.due_event_queue if event["timer"] is not timer]
        if self.active_due_event() is None:
            self.focused_due_timer = None

    def active_due_event(self):
        filtered = []
        for event in self.due_event_queue:
            timer = event["timer"]
            milestone = event["milestone"]
            if timer in self.timers and milestone in timer.state.pending:
                filtered.append(event)
        self.due_event_queue = filtered
        if self.manual_override_timer is not None and (self.manual_override_timer not in self.timers or not self.manual_override_timer.state.pending):
            self.manual_override_timer = None
        return self.due_event_queue[0] if self.due_event_queue else None

    def active_due_timer(self):
        event = self.active_due_event()
        return event["timer"] if event else None

    def is_active_due(self, timer, milestone: float | None = None):
        event = self.active_due_event()
        if not event or event["timer"] is not timer:
            return False
        if milestone is not None and event["milestone"] != milestone:
            return False
        return True

    def is_waiting_due(self, timer, milestone: float | None = None):
        active = self.active_due_event()
        for event in self.due_event_queue:
            if event["timer"] is not timer:
                continue
            if milestone is not None and event["milestone"] != milestone:
                continue
            return active is None or event is not active
        return False

    def focus_active_due_timer(self):
        target = self.manual_override_timer or self.active_due_timer()
        if target is not None:
            self.focus_due_timer(target, force=True)

    def set_manual_override(self, timer):
        if timer is None or not timer.state.pending:
            return
        self.manual_override_timer = timer
        self.focused_due_timer = None

    def clear_manual_override_if_matches(self, timer):
        if self.manual_override_timer is timer:
            self.manual_override_timer = None

    def focus_due_timer(self, timer, force: bool = False):
        if timer is None or not timer.state.pending:
            return
        if self.manual_override_timer is not None and timer is not self.manual_override_timer:
            return
        if self.manual_override_timer is None and self.active_due_timer() is not timer:
            return
        if self.focused_due_timer is timer and not force:
            return
        try:
            timer.entry.focus_force()
            timer.entry.icursor("end")
            self.focused_due_timer = timer
        except Exception:
            pass

    def advance_due_queue(self):
        self.manual_override_timer = None
        active = self.active_due_timer()
        if active is not None:
            self.focused_due_timer = None
            self.after_idle(lambda: self.focus_due_timer(active, force=True))
        else:
            self.focused_due_timer = None

    def _compute_soon_timer(self):
        best_timer = None
        best_delta = None
        for timer in self.timers:
            if timer.state.pending:
                continue
            elapsed = timer.elapsed_seconds()
            next_due = None
            for m in timer.state.milestones:
                if m not in timer.state.triggered and m > elapsed:
                    next_due = m
                    break
            if next_due is None:
                continue
            delta = next_due - elapsed
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_timer = timer
        self.soon_timer = best_timer

    def is_next_soon(self, timer):
        return self.soon_timer is timer and not timer.state.pending

    def show_about_popup(self):
        dark = self.theme_var.get() == "dark"
        colors = {
            "bg": "#171717" if dark else "#efefef",
            "panel": "#232323" if dark else "#ffffff",
            "border": "#3a3a3a" if dark else "#cfcfcf",
            "text": "#f0f0f0" if dark else "#1f1f1f",
            "muted": "#bdbdbd" if dark else "#555555",
            "link": "#8bbcff" if dark else "#005bbb",
        }

        about = tk.Toplevel(self)
        about.title("About TubeMeasurementTimer")
        about.geometry("430x275")
        about.resizable(False, False)
        about.configure(bg=colors["bg"])
        about.transient(self)
        about.grab_set()
        try:
            about.iconbitmap(os.path.join(os.path.dirname(__file__), "assets", "icon.ico"))
        except Exception:
            pass

        about.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - 215
        y = self.winfo_rooty() + (self.winfo_height() // 2) - 137
        about.geometry(f"430x275+{x}+{y}")

        outer = tk.Frame(about, bg=colors["bg"], padx=16, pady=16)
        outer.pack(fill="both", expand=True)

        panel = tk.Frame(
            outer,
            bg=colors["panel"],
            highlightthickness=1,
            highlightbackground=colors["border"],
            highlightcolor=colors["border"],
            padx=16,
            pady=14,
        )
        panel.pack(fill="both", expand=True)

        tk.Label(panel, text="TubeMeasurementTimer", font=("Segoe UI", 14, "bold"), bg=colors["panel"], fg=colors["text"], anchor="w").pack(anchor="w")
        tk.Label(panel, text="Version 1.0.0", font=("Segoe UI", 10), bg=colors["panel"], fg=colors["muted"], anchor="w").pack(anchor="w", pady=(2, 12))
        tk.Label(
            panel,
            text=(
                "Desktop production timer and checkpoint logging tool.\n"
                "Designed for manufacturing and process-monitoring workflows."
            ),
            font=("Segoe UI", 10),
            bg=colors["panel"],
            fg=colors["text"],
            justify="left",
            anchor="w",
        ).pack(anchor="w", pady=(0, 12))
        tk.Label(panel, text="Author: Hemy Gulati", font=("Segoe UI", 10), bg=colors["panel"], fg=colors["text"], anchor="w").pack(anchor="w")
        tk.Label(panel, text="Licence: MIT", font=("Segoe UI", 10), bg=colors["panel"], fg=colors["text"], anchor="w").pack(anchor="w", pady=(2, 10))

        github = tk.Label(
            panel,
            text="GitHub: github.com/HemyGulati/TubeMeasurementTimer",
            font=("Segoe UI", 10, "underline"),
            bg=colors["panel"],
            fg=colors["link"],
            cursor="hand2",
            anchor="w",
        )
        github.pack(anchor="w", pady=(0, 12))
        github.bind("<Button-1>", lambda _e: webbrowser.open("https://github.com/HemyGulati/TubeMeasurementTimer"))

        tk.Label(panel, text="© 2026 Hemy Gulati", font=("Segoe UI", 9), bg=colors["panel"], fg=colors["muted"], anchor="w").pack(anchor="w", pady=(0, 14))

        close_btn = tk.Button(
            panel,
            text="Close",
            font=("Segoe UI", 10),
            bg=colors["border"],
            fg=colors["text"],
            activebackground=colors["muted"],
            activeforeground=colors["text"],
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            command=about.destroy,
        )
        close_btn.pack(anchor="e")
        about.bind("<Escape>", lambda _e: about.destroy())

    def apply_theme(self, mode: str):
        dark = mode == "dark"
        self.theme_var.set(mode)
        bg = "#171717" if dark else "#f2f2f2"
        panel = "#232323" if dark else "#e4e4e4"
        panel2 = "#333333" if dark else "#d2d2d2"
        fg = "#f0f0f0" if dark else "#171717"
        subfg = "#bdbdbd" if dark else "#4a4a4a"
        flash = "#7a2f2f" if dark else "#f2bcbc"
        due = "#5d2626" if dark else "#e6b1b1"
        soon = "#5f5324" if dark else "#e8ddb0"
        accent = "#5a5a5a" if dark else "#9f9f9f"
        warn = "#e2b85b" if dark else "#8f5f00"
        ok = "#d6d6d6" if dark else "#242424"

        self.configure(bg=bg)
        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabel", background=bg, foreground=fg)
        self.style.configure("Header.TLabel", background=bg, foreground=fg, font=("Segoe UI", 18, "bold"))
        self.style.configure("SubHeader.TLabel", background=bg, foreground=subfg, font=("Segoe UI", 9))
        self.style.configure("Banner.TFrame", background=accent)
        self.style.configure("Banner.TLabel", background=accent, foreground="#ffffff", font=("Segoe UI", 12, "bold"))
        self.style.configure("Card.TLabelframe", background=panel, foreground=fg, bordercolor=panel2, relief="solid")
        self.style.configure("Card.TLabelframe.Label", background=panel, foreground=fg)
        self.style.configure("Inner.TFrame", background=panel)
        self.style.configure("TimerCard.TFrame", background=panel, relief="solid", borderwidth=1)
        self.style.configure("TimerCardFlash.TFrame", background=flash, relief="solid", borderwidth=2)
        self.style.configure("TimerCardDue.TFrame", background=due, relief="solid", borderwidth=2)
        self.style.configure("TimerCardSoon.TFrame", background=soon, relief="solid", borderwidth=2)
        self.style.configure("Alert.TLabel", background=panel, foreground=warn, font=("Segoe UI", 9, "bold"))
        self.style.configure("Warn.TLabel", background=panel, foreground=warn, font=("Segoe UI", 8, "bold"))
        self.style.configure("Value.TLabel", background=panel, foreground=ok, font=("Segoe UI", 10, "bold"))
        self.style.configure("TEntry", fieldbackground=panel2, foreground=fg, insertcolor=fg)
        self.style.configure("TCombobox", fieldbackground=panel2, foreground=fg)
        self.style.map("TCombobox", fieldbackground=[("readonly", panel2)], foreground=[("readonly", fg)])
        self.style.configure("Treeview", background=panel2, fieldbackground=panel2, foreground=fg, rowheight=24)
        self.style.configure("Treeview.Heading", background=panel, foreground=fg)
        self.style.map("TButton", background=[("active", accent)])
        self.style.configure("TButton", padding=5)

        if hasattr(self, "root_frame"):
            self.root_frame.configure(style="TFrame")
            for widget in (self.sidebar, self.main_panel, self.topbar, self.banner):
                try:
                    widget.configure(style="Inner.TFrame")
                except Exception:
                    pass

        self.schedule_settings_save()

    def _build_ui(self):
        self.root_frame = ttk.Frame(self, padding=8)
        self.root_frame.pack(fill="both", expand=True)
        self.root_frame.columnconfigure(0, weight=0)
        self.root_frame.columnconfigure(1, weight=1)
        self.root_frame.rowconfigure(1, weight=1)

        self.topbar = ttk.Frame(self.root_frame, style="Inner.TFrame")
        self.topbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.topbar.columnconfigure(1, weight=1)
        ttk.Label(self.topbar, text=APP_TITLE, style="Header.TLabel").grid(row=0, column=0, sticky="w")

        right_top = ttk.Frame(self.topbar, style="Inner.TFrame")
        right_top.grid(row=0, column=2, rowspan=2, sticky="e")
        ttk.Button(right_top, text="Dark", width=7, command=lambda: self.apply_theme("dark")).pack(side="left", padx=2)
        ttk.Button(right_top, text="Light", width=7, command=lambda: self.apply_theme("light")).pack(side="left", padx=2)
        ttk.Button(right_top, text="Fullscreen", width=10, command=lambda: self.set_fullscreen(not self.fullscreen_var.get())).pack(side="left", padx=2)
        ttk.Button(right_top, text="ⓘ", width=4, command=self.show_about_popup).pack(side="left", padx=(6, 0))

        self.sidebar = ttk.LabelFrame(self.root_frame, text="Checkpoints", style="Card.TLabelframe")
        self.sidebar.grid(row=1, column=0, sticky="nsw", padx=(0, 8))
        self.sidebar.configure(width=150)
        self.sidebar.grid_propagate(False)
        self.sidebar.columnconfigure(0, weight=1)
        self.sidebar.rowconfigure(1, weight=1)

        sidebar_inner = ttk.Frame(self.sidebar, style="Inner.TFrame")
        sidebar_inner.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        sidebar_inner.columnconfigure(0, weight=1)
        sidebar_inner.rowconfigure(3, weight=1)

        ttk.Label(sidebar_inner, text="Checkpoint unit", style="SubHeader.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Combobox(sidebar_inner, textvariable=self.unit_var, values=["seconds", "minutes", "hours"], state="readonly", width=10).grid(row=1, column=0, sticky="ew", pady=(4, 8))
        ttk.Label(sidebar_inner, text="Editor", style="SubHeader.TLabel").grid(row=2, column=0, sticky="w")
        self.milestone_table = EditableMilestoneTable(sidebar_inner, self)
        self.milestone_table.grid(row=3, column=0, sticky="nsew", pady=(4, 4))
        ttk.Label(sidebar_inner, text="Raw list", style="SubHeader.TLabel").grid(row=4, column=0, sticky="w")
        ttk.Entry(sidebar_inner, textvariable=self.milestone_text).grid(row=5, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(sidebar_inner, text="Use table", command=self.apply_milestones_from_table).grid(row=6, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(sidebar_inner, text="Use text", command=self.apply_milestones_from_text).grid(row=7, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(sidebar_inner, text="Load config", command=self.load_config_file).grid(row=8, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(sidebar_inner, text="Save config", command=self.save_config_file).grid(row=9, column=0, sticky="ew", pady=(4, 0))

        self.main_panel = ttk.Frame(self.root_frame, style="Inner.TFrame")
        self.main_panel.grid(row=1, column=1, sticky="nsew")
        self.main_panel.columnconfigure(0, weight=1)
        self.main_panel.rowconfigure(2, weight=1)

        self.banner = ttk.Frame(self.main_panel, style="Banner.TFrame")
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(self.banner, text="Due now:", style="Banner.TLabel").pack(side="left", padx=(10, 8), pady=8)
        ttk.Label(self.banner, textvariable=self.current_alert_name, style="Banner.TLabel").pack(side="left", padx=(0, 10), pady=8)

        save_frame = ttk.LabelFrame(self.main_panel, text="CSV output", style="Card.TLabelframe")
        save_frame.grid(row=1, column=0, sticky="ew")
        save_inner = ttk.Frame(save_frame, style="Inner.TFrame")
        save_inner.pack(fill="x", expand=True, padx=6, pady=6)
        save_inner.columnconfigure(0, weight=1)
        ttk.Entry(save_inner, textvariable=self.csv_path_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(save_inner, text="Choose file", command=self.choose_save_file).grid(row=0, column=1, padx=4)
        ttk.Button(save_inner, text="Open folder", command=self.open_save_folder).grid(row=0, column=2)

        timer_panel = ttk.LabelFrame(self.main_panel, text="Tube timers", style="Card.TLabelframe")
        timer_panel.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        timer_panel.rowconfigure(1, weight=1)
        timer_panel.columnconfigure(0, weight=1)

        header = ttk.Frame(timer_panel, style="Inner.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4), padx=6)
        ttk.Button(header, text="+ Add timer", command=self.add_timer).pack(side="left")
        ttk.Button(header, text="Start all", command=self.start_all).pack(side="left", padx=4)
        ttk.Button(header, text="Stop all", command=self.stop_all).pack(side="left", padx=4)
        ttk.Button(header, text="Reset all", command=self.reset_all).pack(side="left", padx=4)

        self.canvas = tk.Canvas(timer_panel, highlightthickness=0, bd=0)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=(6, 0), pady=(0, 6))
        scrollbar = ttk.Scrollbar(timer_panel, orient="vertical", command=self.canvas.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 6), pady=(0, 6))
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.timer_container = ttk.Frame(self.canvas, style="Inner.TFrame")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.timer_container, anchor="nw")
        self.timer_container.bind("<Configure>", self._on_container_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_scroll_recursive(self.canvas)
        self.bind("<F11>", lambda _e: self.set_fullscreen(not self.fullscreen_var.get()))
        self.bind("<Escape>", lambda _e: self.set_fullscreen(False) if self.fullscreen_var.get() else None)
        self.milestone_text.trace_add("write", lambda *_: self.schedule_settings_save())
        self.csv_path_var.trace_add("write", lambda *_: self.schedule_settings_save())
        self.unit_var.trace_add("write", self.on_unit_change)

    def _bind_scroll_recursive(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        widget.bind("<Button-4>", self._on_mousewheel, add="+")
        widget.bind("<Button-5>", self._on_mousewheel, add="+")

    def _on_mousewheel(self, event):
        if hasattr(event, "delta") and event.delta:
            step = -1 if event.delta > 0 else 1
        elif getattr(event, "num", None) == 4:
            step = -1
        else:
            step = 1
        self.canvas.yview_scroll(step, "units")
        return "break"

    def set_fullscreen(self, value: bool):
        self.fullscreen_var.set(bool(value))
        self.attributes("-fullscreen", bool(value))
        self.schedule_settings_save()

    def sync_milestones_from_table_to_text(self):
        self.milestone_text.set(",".join(str(v) for v in self.milestone_table.get_values()))

    def now_monotonic(self) -> float:
        import time
        return time.monotonic()

    def parse_milestones(self, text: str) -> list[float]:
        numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
        values = []
        for n in numbers:
            f = float(n)
            if f >= 0:
                values.append(round(f, 6))
        return sorted(set(values))

    def get_milestones(self) -> list[float]:
        display_values = self.parse_milestones(self.milestone_text.get())
        if not display_values:
            display_values = [float(v) for v in DEFAULT_MILESTONES]
        return [self.display_to_seconds(v) for v in display_values]

    def apply_milestones(self, values: list[float]):
        clean_display = sorted({round(float(v), 6) for v in values if float(v) >= 0}) or [float(v) for v in DEFAULT_MILESTONES]
        self.milestone_text.set(",".join(self._format_number(v) for v in clean_display))
        self.milestone_table.load_values(clean_display)
        timer_values = [self.display_to_seconds(v) for v in clean_display]
        for timer in self.timers:
            timer.refresh_milestones(timer_values)
        self.schedule_settings_save()
        messagebox.showinfo(APP_TITLE, f"Loaded {len(clean_display)} checkpoint times ({self.unit_label()}).")

    def apply_milestones_from_text(self):
        self.apply_milestones(self.parse_milestones(self.milestone_text.get()))

    def apply_milestones_from_table(self):
        self.apply_milestones(self.milestone_table.get_values())

    def _apply_config_dict(self, data: dict, *, source_path: str = ""):
        unit = data.get("checkpoint_unit")
        if unit in UNIT_SECONDS:
            self.unit_var.set(unit)
        values = data.get("milestones")
        if values is None:
            values = self.parse_milestones(data.get("milestone_text", ""))
        values = sorted({round(float(v), 6) for v in values if float(v) >= 0}) if values else []
        if not values:
            values = [float(v) for v in DEFAULT_MILESTONES]
        self.milestone_text.set(",".join(self._format_number(v) for v in values))
        self.milestone_table.load_values(values)
        timer_values = [self.display_to_seconds(v) for v in values]
        for timer in list(self.timers):
            timer.frame.destroy()
        self.timers.clear()
        for name in (data.get("timer_names") or ["R1T1"]):
            self.add_timer(name=name)
        for timer in self.timers:
            timer.refresh_milestones(timer_values)
        csv_path = (data.get("csv_path") or "").strip()
        if csv_path:
            self.csv_path_var.set(csv_path)
            self.logger.set_path(csv_path)
        theme = data.get("theme")
        if theme in {"dark", "light"}:
            self.theme_var.set(theme)
            self.apply_theme(theme)
        fullscreen = data.get("fullscreen")
        if fullscreen is not None:
            self.set_fullscreen(bool(fullscreen))
        if source_path:
            self.last_config_path = source_path
        self.schedule_settings_save()
        self.update_duplicate_warnings()

    def _load_config_from_path(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        data = None
        if path.lower().endswith(".json"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    data = parsed
            except Exception:
                data = None
        if data is None:
            values = self.parse_milestones(raw)
            if not values:
                raise ValueError("No numeric times found in that file.")
            data = {"milestones": values, "checkpoint_unit": self.unit_var.get()}
        self._apply_config_dict(data, source_path=path)

    def _autoload_last_config(self):
        if not self.last_config_path:
            return
        if not os.path.exists(self.last_config_path):
            return
        try:
            self._load_config_from_path(self.last_config_path)
        except Exception:
            pass

    def load_config_file(self):
        path = filedialog.askopenfilename(
            title="Load checkpoint config file",
            filetypes=[("Config files", "*.txt *.csv *.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self._load_config_from_path(path)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not load config file:\n{e}")
            return
        messagebox.showinfo(APP_TITLE, f"Loaded config file:\n{os.path.basename(path)}")

    def save_config_file(self):
        initial_name = os.path.basename(self.last_config_path) if self.last_config_path else "tube_timer_config.json"
        path = filedialog.asksaveasfilename(
            title="Save config file",
            defaultextension=".json",
            initialfile=initial_name,
            filetypes=[("JSON config", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        data = {
            "milestones": self.parse_milestones(self.milestone_text.get()),
            "milestone_text": self.milestone_text.get(),
            "checkpoint_unit": self.unit_var.get(),
            "timer_names": [t.name_var.get().strip() or f"T{i+1}" for i, t in enumerate(self.timers)],
            "csv_path": self.csv_path_var.get().strip(),
            "theme": self.theme_var.get(),
            "fullscreen": bool(self.fullscreen_var.get()),
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.last_config_path = path
            self.schedule_settings_save()
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not save config file:\n{e}")
            return
        messagebox.showinfo(APP_TITLE, f"Saved config file:\n{os.path.basename(path)}")

    def choose_save_file(self):
        path = filedialog.asksaveasfilename(
            title="Choose CSV save file",
            defaultextension=".csv",
            initialfile=os.path.basename(self.csv_path_var.get()) or "tube_timer_data.csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        self.csv_path_var.set(path)
        try:
            self.logger.set_path(path)
            self.schedule_settings_save()
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not set CSV path:\n{e}")

    def open_save_folder(self):
        path = self.csv_path_var.get().strip()
        if not path:
            return
        folder = os.path.dirname(path)
        if not folder:
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", folder])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not open folder:\n{e}")

    def add_timer(self, name: str | None = None):
        timer = TimerRow(self.timer_container, self, len(self.timers))
        if name:
            timer.name_var.set(name)
        self.timers.append(timer)
        timer.grid(row=len(self.timers) - 1, column=0, sticky="ew", pady=3)
        self.timer_container.columnconfigure(0, weight=1)
        self._bind_scroll_recursive(timer.frame)
        for child in timer.frame.winfo_children():
            self._bind_scroll_recursive(child)
        self.update_duplicate_warnings()
        self.schedule_settings_save()
        return timer

    def remove_timer(self, timer: TimerRow):
        self.remove_due_events_for_timer(timer)
        if timer in self.timers:
            self.timers.remove(timer)
        for idx, row in enumerate(self.timers):
            row.row_index = idx
            row.frame.grid_configure(row=idx)
        self.update_duplicate_warnings()
        self.schedule_settings_save()

    def update_duplicate_warnings(self):
        counts = {}
        for timer in self.timers:
            name = timer.name_var.get().strip()
            if name:
                counts[name] = counts.get(name, 0) + 1
        for timer in self.timers:
            name = timer.name_var.get().strip()
            timer.duplicate_var.set("Duplicate" if name and counts.get(name, 0) > 1 else "")

    def start_all(self):
        for timer in self.timers:
            timer.start()

    def stop_all(self):
        for timer in self.timers:
            timer.stop()

    def reset_all(self):
        for timer in self.timers:
            timer.reset()
        self.current_alert_name.set("No timer due")

    def alert_user(self, timer: TimerRow):
        self.current_alert_name.set(timer.name_var.get().strip() or f"Timer {timer.row_index + 1}")
        try:
            self.bell()
            self.after(120, self.bell)
        except Exception:
            pass

    def _on_container_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def _tick(self):
        any_due = False
        for timer in self.timers:
            timer.update()
            if timer.state.pending:
                any_due = True
        self._compute_soon_timer()
        for timer in self.timers:
            timer.update_prompt(force_no_flash=not timer.state.running)
        self.focus_active_due_timer()
        active = self.active_due_timer()
        if active is not None:
            self.current_alert_name.set(active.name_var.get().strip() or f"Timer {active.row_index + 1}")
        elif self.current_alert_name.get() != "No timer due":
            self.current_alert_name.set("No timer due")
            self.focused_due_timer = None
        self.after(TICK_MS, self._tick)

    def on_close(self):
        try:
            self.save_settings()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
