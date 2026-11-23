from __future__ import annotations

import tkinter.messagebox as messagebox
from collections import defaultdict
from datetime import date, datetime, timedelta

import customtkinter as ctk

from calendar_utils import format_persian_digits, parse_date, to_jalali
from storage import (
    AuthenticationError,
    DataIntegrityError,
    EncryptedTaskStore,
    StorageError,
    Task,
    get_database_path,
)


APP_TITLE = "Daymark Todo"
MAX_TITLE_LENGTH = 4000
FONT_FAMILY = "Segoe UI"

COLORS = {
    "background": ("#F4F6FA", "#101722"),
    "surface": ("#FFFFFF", "#182231"),
    "surface_alt": ("#F8FAFD", "#202D3E"),
    "text": ("#192435", "#EDF2F8"),
    "muted": ("#68778B", "#9AAAC0"),
    "border": ("#DCE3EC", "#2B3A4D"),
    "accent": ("#356AE6", "#6F94FF"),
    "danger": ("#C23B4B", "#F07882"),
    "low": ("#DCEFE5", "#244638"),
    "normal": ("#E5ECFA", "#293D62"),
    "high": ("#FBE4E5", "#5B2D36"),
}


class DaymarkApp(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title(APP_TITLE)
        self.geometry("1120x790")
        self.minsize(900, 650)
        self.configure(fg_color=COLORS["background"])
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        try:
            self.storage = EncryptedTaskStore(get_database_path())
        except StorageError as exc:
            self._show_startup_error(str(exc))
            return

        self.current_date = date.today()
        self.date_mode = "Gregorian"
        self.theme = "dark"
        self.current_tasks: dict[str, Task] = {}
        self.status_label: ctk.CTkLabel | None = None

        self.show_auth_screen()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def _clear_window(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()

    def _show_startup_error(self, message: str) -> None:
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        page = ctk.CTkFrame(self, fg_color="transparent")
        page.pack(fill="both", expand=True, padx=24, pady=24)
        card = ctk.CTkFrame(
            page,
            fg_color=COLORS["surface"],
            corner_radius=18,
            border_width=1,
            border_color=COLORS["border"],
            width=520,
            height=250,
        )
        card.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(
            card,
            text="Daymark could not start",
            text_color=COLORS["text"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
        ).pack(pady=(28, 12))
        ctk.CTkLabel(
            card,
            text=message,
            text_color=COLORS["muted"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            wraplength=440,
            justify="center",
        ).pack(padx=24, pady=(0, 18))
        ctk.CTkButton(card, text="Close", width=120, command=self.destroy).pack(pady=(0, 24))

    def show_auth_screen(self) -> None:
        self._clear_window()
        try:
            first_run = self.storage.is_first_run()
        except StorageError as exc:
            self._show_database_error(str(exc))
            return

        page = ctk.CTkFrame(self, fg_color="transparent")
        page.pack(fill="both", expand=True, padx=24, pady=24)

        card = ctk.CTkFrame(
            page,
            width=480,
            corner_radius=22,
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["border"],
        )
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)
        card.configure(height=510 if first_run else 390)

        ctk.CTkLabel(
            card,
            text="DAYMARK",
            font=ctk.CTkFont(family=FONT_FAMILY, size=27, weight="bold"),
            text_color=COLORS["text"],
        ).pack(pady=(32, 4))
        ctk.CTkLabel(
            card,
            text="Your day, clearly organized.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=COLORS["muted"],
        ).pack(pady=(0, 22))

        heading = "Create your master password" if first_run else "Unlock your tasks"
        ctk.CTkLabel(
            card,
            text=heading,
            font=ctk.CTkFont(family=FONT_FAMILY, size=19, weight="bold"),
            text_color=COLORS["text"],
        ).pack(pady=(0, 8))

        explanation = (
            "This password encrypts your task data. It is not stored by the app."
            if first_run
            else "Enter the master password you created for this database."
        )
        ctk.CTkLabel(
            card,
            text=explanation,
            text_color=COLORS["muted"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            wraplength=390,
            justify="center",
        ).pack(padx=28, pady=(0, 18))

        self.password_entry = ctk.CTkEntry(
            card,
            width=360,
            height=43,
            placeholder_text="Master password",
            show="●",
        )
        self.password_entry.pack(pady=7)

        self.confirm_password_entry: ctk.CTkEntry | None = None
        if first_run:
            self.confirm_password_entry = ctk.CTkEntry(
                card,
                width=360,
                height=43,
                placeholder_text="Confirm master password",
                show="●",
            )
            self.confirm_password_entry.pack(pady=7)

        self.auth_status = ctk.CTkLabel(
            card,
            text="",
            text_color=COLORS["danger"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            wraplength=390,
        )
        self.auth_status.pack(padx=24, pady=(8, 2))

        action_text = "Create secure database" if first_run else "Unlock"
        ctk.CTkButton(
            card,
            text=action_text,
            width=360,
            height=44,
            corner_radius=10,
            command=self._submit_password,
        ).pack(pady=(10, 15))

        note = (
            "Important: if you forget this password, encrypted task data cannot be recovered."
            if first_run
            else "Your database remains stored inside this app folder."
        )
        ctk.CTkLabel(
            card,
            text=note,
            text_color=COLORS["muted"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            wraplength=390,
            justify="center",
        ).pack(padx=26, pady=(0, 22))

        self.password_entry.bind("<Return>", lambda _event: self._submit_password())
        if self.confirm_password_entry is not None:
            self.confirm_password_entry.bind("<Return>", lambda _event: self._submit_password())
        self.password_entry.focus_set()

    def _show_database_error(self, message: str) -> None:
        page = ctk.CTkFrame(self, fg_color="transparent")
        page.pack(fill="both", expand=True, padx=24, pady=24)
        card = ctk.CTkFrame(
            page,
            fg_color=COLORS["surface"],
            corner_radius=18,
            border_width=1,
            border_color=COLORS["border"],
            width=540,
            height=260,
        )
        card.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(
            card,
            text="Database configuration problem",
            text_color=COLORS["text"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=19, weight="bold"),
        ).pack(pady=(28, 12))
        ctk.CTkLabel(
            card,
            text=message,
            text_color=COLORS["muted"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            wraplength=460,
            justify="center",
        ).pack(padx=24, pady=(0, 18))
        ctk.CTkButton(card, text="Close app", width=120, command=self.on_close).pack(pady=(0, 24))

    def _submit_password(self) -> None:
        password = self.password_entry.get()
        try:
            if self.storage.is_first_run():
                confirmation = self.confirm_password_entry.get() if self.confirm_password_entry else ""
                if password != confirmation:
                    self.auth_status.configure(text="The passwords do not match.")
                    return
                self.storage.setup_password(password)
            else:
                self.storage.unlock(password)
        except (AuthenticationError, DataIntegrityError, StorageError, ValueError) as exc:
            self.auth_status.configure(text=str(exc))
            return

        self.password_entry.delete(0, "end")
        if self.confirm_password_entry is not None:
            self.confirm_password_entry.delete(0, "end")
        self.password_entry = None
        self.confirm_password_entry = None
        self.auth_status = None

        try:
            self.theme = self.storage.get_theme()
        except StorageError:
            self.theme = "dark"
        ctk.set_appearance_mode(self.theme)
        self.build_main_ui()

    # ------------------------------------------------------------------
    # Main window
    # ------------------------------------------------------------------
    def build_main_ui(self) -> None:
        self._clear_window()
        self.configure(fg_color=COLORS["background"])

        page = ctk.CTkFrame(self, fg_color="transparent")
        page.pack(fill="both", expand=True, padx=28, pady=(20, 24))

        topbar = ctk.CTkFrame(page, fg_color="transparent")
        topbar.pack(fill="x", pady=(0, 18))
        brand = ctk.CTkFrame(topbar, fg_color="transparent")
        brand.pack(side="left")
        ctk.CTkLabel(
            brand,
            text="DAYMARK",
            text_color=COLORS["text"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=23, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand,
            text="A calm space for daily progress",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
        ).pack(anchor="w", pady=(1, 0))

        actions = ctk.CTkFrame(topbar, fg_color="transparent")
        actions.pack(side="right")
        self.theme_button = ctk.CTkButton(
            actions,
            text=self._theme_button_text(),
            width=132,
            height=36,
            fg_color=COLORS["surface_alt"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=self.toggle_theme,
        )
        self.theme_button.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            actions,
            text="Backup",
            width=82,
            height=36,
            fg_color=COLORS["surface_alt"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=self.create_backup,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            actions,
            text="Lock",
            width=76,
            height=36,
            fg_color="transparent",
            border_width=1,
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            hover_color=COLORS["surface_alt"],
            command=self.lock_app,
        ).pack(side="left")

        date_card = ctk.CTkFrame(
            page,
            fg_color=COLORS["surface"],
            corner_radius=18,
            border_width=1,
            border_color=COLORS["border"],
        )
        date_card.pack(fill="x", pady=(0, 14))

        date_top = ctk.CTkFrame(date_card, fg_color="transparent")
        date_top.pack(fill="x", padx=20, pady=(17, 10))
        date_texts = ctk.CTkFrame(date_top, fg_color="transparent")
        date_texts.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            date_texts,
            text="YOUR DAY",
            text_color=COLORS["accent"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
        ).pack(anchor="w")
        self.date_title_label = ctk.CTkLabel(
            date_texts,
            text="",
            text_color=COLORS["text"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"),
        )
        self.date_title_label.pack(anchor="w", pady=(3, 1))
        self.date_subtitle_label = ctk.CTkLabel(
            date_texts,
            text="",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
        )
        self.date_subtitle_label.pack(anchor="w")

        nav = ctk.CTkFrame(date_top, fg_color="transparent")
        nav.pack(side="right", padx=(12, 0))
        ctk.CTkButton(
            nav,
            text="‹",
            width=38,
            height=36,
            font=ctk.CTkFont(family=FONT_FAMILY, size=21),
            fg_color=COLORS["surface_alt"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=lambda: self.change_day(-1),
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            nav,
            text="Today",
            width=72,
            height=36,
            fg_color=COLORS["surface_alt"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=self.go_to_today,
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            nav,
            text="›",
            width=38,
            height=36,
            font=ctk.CTkFont(family=FONT_FAMILY, size=21),
            fg_color=COLORS["surface_alt"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=lambda: self.change_day(1),
        ).pack(side="left", padx=3)

        date_controls = ctk.CTkFrame(date_card, fg_color="transparent")
        date_controls.pack(fill="x", padx=20, pady=(2, 17))
        self.date_mode_control = ctk.CTkSegmentedButton(
            date_controls,
            values=["Gregorian", "Persian"],
            command=self._on_date_mode_change,
            width=205,
            height=34,
        )
        self.date_mode_control.set(self.date_mode)
        self.date_mode_control.pack(side="left")
        self.date_entry = ctk.CTkEntry(
            date_controls,
            width=190,
            height=34,
            placeholder_text="YYYY/MM/DD",
        )
        self.date_entry.pack(side="left", padx=(10, 8))
        self.date_entry.bind("<Return>", lambda _event: self.jump_to_date())
        ctk.CTkButton(
            date_controls,
            text="Go to date",
            width=94,
            height=34,
            command=self.jump_to_date,
        ).pack(side="left")

        add_card = ctk.CTkFrame(
            page,
            fg_color=COLORS["surface"],
            corner_radius=16,
            border_width=1,
            border_color=COLORS["border"],
        )
        add_card.pack(fill="x", pady=(0, 13))
        add_inner = ctk.CTkFrame(add_card, fg_color="transparent")
        add_inner.pack(fill="x", padx=15, pady=14)
        self.new_task_entry = ctk.CTkEntry(
            add_inner,
            height=43,
            placeholder_text="Write a task and press Enter...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
        )
        self.new_task_entry.pack(side="left", fill="x", expand=True, padx=(0, 9))
        self.new_task_entry.bind("<Return>", lambda _event: self.add_root_task())
        self.new_priority_menu = ctk.CTkOptionMenu(
            add_inner,
            values=["Low", "Normal", "High"],
            width=112,
            height=43,
        )
        self.new_priority_menu.set("Normal")
        self.new_priority_menu.pack(side="left", padx=(0, 9))
        ctk.CTkButton(
            add_inner,
            text="＋  Add task",
            width=130,
            height=43,
            command=self.add_root_task,
        ).pack(side="left")

        list_header = ctk.CTkFrame(page, fg_color="transparent")
        list_header.pack(fill="x", pady=(3, 8))
        ctk.CTkLabel(
            list_header,
            text="Tasks",
            text_color=COLORS["text"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
        ).pack(side="left")
        self.task_count_label = ctk.CTkLabel(
            list_header,
            text="",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
        )
        self.task_count_label.pack(side="left", padx=(10, 0), pady=(2, 0))

        self.task_list = ctk.CTkScrollableFrame(
            page,
            fg_color="transparent",
            corner_radius=0,
        )
        self.task_list.pack(fill="both", expand=True)

        self.status_label = ctk.CTkLabel(
            page,
            text="All task data is encrypted and stored locally in this app folder.",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            anchor="w",
        )
        self.status_label.pack(fill="x", pady=(8, 0))

        self._refresh_date_header()
        self.refresh_tasks()
        self.new_task_entry.focus_set()

    def _theme_button_text(self) -> str:
        return "☀  Switch to light" if self.theme == "dark" else "☾  Switch to dark"

    def toggle_theme(self) -> None:
        self.theme = "light" if self.theme == "dark" else "dark"
        ctk.set_appearance_mode(self.theme)
        try:
            self.storage.set_theme(self.theme)
        except StorageError as exc:
            self._set_status(str(exc), error=True)
        self.theme_button.configure(text=self._theme_button_text())

    def create_backup(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = (
            self.storage.database_path.parent
            / "backups"
            / f"daymark_backup_{timestamp}.sqlite3"
        )
        try:
            self.storage.backup_to(backup_path)
            relative_path = backup_path.relative_to(self.storage.database_path.parent.parent)
            self._set_status(f"Encrypted backup created: {relative_path}")
        except StorageError as exc:
            self._set_status(str(exc), error=True)

    def lock_app(self) -> None:
        self.current_tasks.clear()
        self.status_label = None
        self.storage.lock()
        self.show_auth_screen()

    # ------------------------------------------------------------------
    # Calendar controls
    # ------------------------------------------------------------------
    def _on_date_mode_change(self, choice: str) -> None:
        self.date_mode = choice
        self._refresh_date_header()

    def _refresh_date_header(self) -> None:
        self.date_title_label.configure(
            text=self.current_date.strftime("%A, %d %B %Y")
        )
        jalali = to_jalali(self.current_date)
        jalali_text = format_persian_digits(
            f"{jalali.year:04d}/{jalali.month:02d}/{jalali.day:02d}"
        )
        self.date_subtitle_label.configure(text=f"Persian calendar: {jalali_text}")

        if self.date_mode == "Gregorian":
            self.date_entry.configure(placeholder_text="YYYY/MM/DD")
            self.date_entry.delete(0, "end")
            self.date_entry.insert(0, self.current_date.strftime("%Y/%m/%d"))
        else:
            self.date_entry.configure(placeholder_text="1405/01/01")
            self.date_entry.delete(0, "end")
            self.date_entry.insert(0, f"{jalali.year:04d}/{jalali.month:02d}/{jalali.day:02d}")
            self.date_entry.icursor("end")

    def change_day(self, amount: int) -> None:
        self.current_date += timedelta(days=amount)
        self._refresh_date_header()
        self.refresh_tasks()

    def go_to_today(self) -> None:
        self.current_date = date.today()
        self._refresh_date_header()
        self.refresh_tasks()

    def jump_to_date(self) -> None:
        try:
            self.current_date = parse_date(self.date_entry.get(), self.date_mode)
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        self._refresh_date_header()
        self.refresh_tasks()

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------
    def _next_position(self, parent_id: str | None) -> int:
        positions = [
            task.position
            for task in self.current_tasks.values()
            if task.date == self.current_date.isoformat() and task.parent_id == parent_id
        ]
        return max(positions, default=-1) + 1

    def add_root_task(self) -> None:
        title = self.new_task_entry.get().strip()
        if not title:
            self._set_status("Type a task before adding it.", error=True)
            return
        if len(title) > MAX_TITLE_LENGTH:
            self._set_status(f"A task can contain up to {MAX_TITLE_LENGTH} characters.", error=True)
            return

        task = Task.create(
            task_date=self.current_date.isoformat(),
            title=title,
            priority=self.new_priority_menu.get(),
            parent_id=None,
            position=self._next_position(None),
        )
        try:
            self.storage.save_task(task)
            self.new_task_entry.delete(0, "end")
            self._set_status("Task added.")
            self.refresh_tasks()
            self.new_task_entry.focus_set()
        except StorageError as exc:
            self._set_status(str(exc), error=True)

    def _open_task_dialog(self, *, task: Task | None = None, parent_id: str | None = None) -> None:
        is_edit = task is not None
        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit task" if is_edit else "Add subtask")
        dialog.geometry("560x430")
        dialog.minsize(500, 390)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=COLORS["background"])

        panel = ctk.CTkFrame(
            dialog,
            fg_color=COLORS["surface"],
            corner_radius=16,
            border_width=1,
            border_color=COLORS["border"],
        )
        panel.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            panel,
            text="Edit task" if is_edit else "Create a subtask",
            font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=18, pady=(18, 12))
        ctk.CTkLabel(
            panel,
            text="Task text",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
        ).pack(anchor="w", padx=18, pady=(0, 5))

        text_box = ctk.CTkTextbox(
            panel, height=205, wrap="word", font=ctk.CTkFont(family=FONT_FAMILY, size=13)
        )
        text_box.pack(fill="both", expand=True, padx=18)
        if task is not None:
            text_box.insert("1.0", task.title)

        priority_row = ctk.CTkFrame(panel, fg_color="transparent")
        priority_row.pack(fill="x", padx=18, pady=(12, 10))
        ctk.CTkLabel(
            priority_row,
            text="Priority",
            text_color=COLORS["muted"],
        ).pack(side="left")
        priority_menu = ctk.CTkOptionMenu(
            priority_row,
            values=["Low", "Normal", "High"],
            width=125,
        )
        priority_menu.set(task.priority if task else "Normal")
        priority_menu.pack(side="right")

        error_label = ctk.CTkLabel(
            panel,
            text="",
            text_color=COLORS["danger"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
        )
        error_label.pack(anchor="w", padx=18)

        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.pack(fill="x", padx=18, pady=(8, 16))
        ctk.CTkButton(
            buttons,
            text="Cancel",
            width=100,
            fg_color="transparent",
            border_width=1,
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            hover_color=COLORS["surface_alt"],
            command=dialog.destroy,
        ).pack(side="right", padx=(8, 0))

        def save() -> None:
            title = text_box.get("1.0", "end-1c").strip()
            if not title:
                error_label.configure(text="Task text cannot be empty.")
                return
            if len(title) > MAX_TITLE_LENGTH:
                error_label.configure(text=f"Maximum length is {MAX_TITLE_LENGTH} characters.")
                return

            if task is not None:
                new_task = task.with_changes(title=title, priority=priority_menu.get())
            else:
                new_task = Task.create(
                    task_date=self.current_date.isoformat(),
                    title=title,
                    priority=priority_menu.get(),
                    parent_id=parent_id,
                    position=self._next_position(parent_id),
                )
            try:
                self.storage.save_task(new_task)
            except StorageError as exc:
                error_label.configure(text=str(exc))
                return

            dialog.destroy()
            self._set_status("Task updated." if is_edit else "Subtask added.")
            self.refresh_tasks()

        ctk.CTkButton(
            buttons,
            text="Save task",
            width=120,
            command=save,
        ).pack(side="right")
        dialog.bind("<Control-Return>", lambda _event: save())
        text_box.focus_set()

    def edit_task(self, task_id: str) -> None:
        task = self.current_tasks.get(task_id)
        if task is not None:
            self._open_task_dialog(task=task)

    def add_subtask(self, parent_id: str) -> None:
        self._open_task_dialog(parent_id=parent_id)

    def toggle_task(self, task_id: str, completed: bool) -> None:
        task = self.current_tasks.get(task_id)
        if task is None:
            return
        try:
            self.storage.save_task(task.with_changes(completed=completed))
            self.refresh_tasks()
        except StorageError as exc:
            self._set_status(str(exc), error=True)
            self.refresh_tasks()

    def delete_task(self, task_id: str) -> None:
        task = self.current_tasks.get(task_id)
        if task is None:
            return
        descendants = self._collect_descendants(task_id)
        count = len(descendants)
        question = (
            f"Delete this task and its {count} subtask(s)? This cannot be undone."
            if count
            else "Delete this task? This cannot be undone."
        )
        if not messagebox.askyesno("Delete task", question, parent=self):
            return
        try:
            self.storage.delete_tasks(descendants)
            self._set_status("Task deleted.")
            self.refresh_tasks()
        except StorageError as exc:
            self._set_status(str(exc), error=True)

    def _collect_descendants(self, task_id: str) -> list[str]:
        children: dict[str, list[str]] = defaultdict(list)
        for item in self.current_tasks.values():
            if item.parent_id is not None:
                children[item.parent_id].append(item.id)

        result: list[str] = []
        stack = [task_id]
        while stack:
            current = stack.pop()
            result.append(current)
            stack.extend(children.get(current, []))
        return result

    # ------------------------------------------------------------------
    # Task list rendering
    # ------------------------------------------------------------------
    def refresh_tasks(self) -> None:
        for widget in self.task_list.winfo_children():
            widget.destroy()

        try:
            all_tasks = self.storage.get_all_tasks()
        except (StorageError, AuthenticationError, DataIntegrityError) as exc:
            self._set_status(str(exc), error=True)
            return

        selected_iso = self.current_date.isoformat()
        todays_tasks = [task for task in all_tasks if task.date == selected_iso]
        self.current_tasks = {task.id: task for task in todays_tasks}

        completed_count = sum(1 for task in todays_tasks if task.completed)
        self.task_count_label.configure(
            text=f"{len(todays_tasks)} total  ·  {completed_count} completed"
        )

        children: dict[str | None, list[Task]] = defaultdict(list)
        for task in todays_tasks:
            children[task.parent_id].append(task)
        for sibling_list in children.values():
            sibling_list.sort(key=lambda item: (item.position, item.created_at, item.id))

        roots = children.get(None, [])
        if not roots:
            empty = ctk.CTkFrame(
                self.task_list,
                fg_color=COLORS["surface"],
                corner_radius=14,
                border_width=1,
                border_color=COLORS["border"],
            )
            empty.pack(fill="x", padx=3, pady=16)
            ctk.CTkLabel(
                empty,
                text="Nothing planned for this day",
                text_color=COLORS["text"],
                font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            ).pack(pady=(22, 5))
            ctk.CTkLabel(
                empty,
                text="Add a task above to get started.",
                text_color=COLORS["muted"],
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            ).pack(pady=(0, 22))
            return

        def draw_branch(items: list[Task], depth: int) -> None:
            for item in items:
                self._draw_task_row(item, depth)
                nested = children.get(item.id, [])
                if nested:
                    draw_branch(nested, depth + 1)

        draw_branch(roots, 0)

    def _draw_task_row(self, task: Task, depth: int) -> None:
        row = ctk.CTkFrame(
            self.task_list,
            fg_color=COLORS["surface"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
        )
        row.pack(fill="x", padx=(min(depth * 23, 115) + 3, 3), pady=3)
        row.grid_columnconfigure(2, weight=1)

        priority_color = {
            "Low": COLORS["low"],
            "Normal": COLORS["normal"],
            "High": COLORS["high"],
        }[task.priority]
        stripe_color = {
            "Low": ("#63A985", "#5FC698"),
            "Normal": ("#5B83D6", "#7EA4FF"),
            "High": ("#D65C65", "#F07882"),
        }[task.priority]
        ctk.CTkFrame(
            row,
            width=4,
            corner_radius=4,
            fg_color=stripe_color,
        ).grid(row=0, column=0, sticky="ns", padx=(8, 7), pady=8)

        checkbox = ctk.CTkCheckBox(
            row,
            text="",
            width=22,
            checkbox_width=19,
            checkbox_height=19,
            command=lambda current_id=task.id: self.toggle_task(current_id, bool(checkbox.get())),
        )
        if task.completed:
            checkbox.select()
        checkbox.grid(row=0, column=1, padx=(0, 7), pady=10)

        task_color = COLORS["muted"] if task.completed else COLORS["text"]
        ctk.CTkLabel(
            row,
            text=task.title,
            text_color=task_color,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, overstrike=task.completed),
            justify="left",
            anchor="w",
            wraplength=500,
        ).grid(row=0, column=2, sticky="ew", padx=(0, 10), pady=10)

        ctk.CTkLabel(
            row,
            text=task.priority,
            text_color=COLORS["text"],
            fg_color=priority_color,
            corner_radius=7,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            width=66,
            height=25,
        ).grid(row=0, column=3, padx=(0, 8), pady=8)

        ctk.CTkButton(
            row,
            text="＋ Child",
            width=72,
            height=29,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=COLORS["surface_alt"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=lambda current_id=task.id: self.add_subtask(current_id),
        ).grid(row=0, column=4, padx=(0, 5), pady=8)
        ctk.CTkButton(
            row,
            text="Edit",
            width=50,
            height=29,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color="transparent",
            border_width=1,
            border_color=COLORS["border"],
            hover_color=COLORS["surface_alt"],
            text_color=COLORS["text"],
            command=lambda current_id=task.id: self.edit_task(current_id),
        ).grid(row=0, column=5, padx=(0, 5), pady=8)
        ctk.CTkButton(
            row,
            text="Delete",
            width=58,
            height=29,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color="transparent",
            border_width=1,
            border_color=COLORS["danger"],
            hover_color=COLORS["high"],
            text_color=COLORS["danger"],
            command=lambda current_id=task.id: self.delete_task(current_id),
        ).grid(row=0, column=6, padx=(0, 8), pady=8)

    def _set_status(self, text: str, *, error: bool = False) -> None:
        if self.status_label is not None and self.status_label.winfo_exists():
            self.status_label.configure(
                text=text,
                text_color=COLORS["danger"] if error else COLORS["muted"],
            )

    def on_close(self) -> None:
        self.current_tasks.clear()
        self.storage.close()
        self.destroy()


def main() -> None:
    app = DaymarkApp()
    app.mainloop()


if __name__ == "__main__":
    main()
