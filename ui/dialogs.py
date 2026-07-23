"""Reusable dialogs for forms and confirmations."""

import re
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime


# --- Date utilities ---
# Display format: DD/MM/YYYY  |  Internal format (SQLite): YYYY-MM-DD

def validar_fecha(fecha_str: str) -> bool:
    """Validates a date in DD/MM/YYYY format."""
    if not fecha_str:
        return True
    try:
        datetime.strptime(fecha_str, "%d/%m/%Y")
        return True
    except ValueError:
        return False


def fecha_hoy() -> str:
    """Returns today's date in DD/MM/YYYY format."""
    return datetime.now().strftime("%d/%m/%Y")


def fecha_display(fecha_iso: str) -> str:
    """Converts YYYY-MM-DD (DB) to DD/MM/YYYY (display)."""
    if not fecha_iso:
        return ""
    try:
        return datetime.strptime(fecha_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return fecha_iso


def fecha_to_iso(fecha_display_str: str) -> str:
    """Converts DD/MM/YYYY (display) to YYYY-MM-DD (DB)."""
    if not fecha_display_str:
        return ""
    try:
        return datetime.strptime(fecha_display_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return fecha_display_str


# --- Other validations ---

def normalizar_monto(monto_str: str) -> str:
    """Normalizes an amount in Argentine format to a plain decimal string.

    Dots are thousands separators and must group digits in threes
    ("1.500.000"); the comma is the decimal separator ("1.500.000,50" ->
    "1500000.50"). Returns "" for invalid input, so a mistyped decimal
    point like "10.50" is rejected instead of silently read as 1050.
    """
    if not monto_str:
        return ""
    s = monto_str.strip().replace(" ", "")
    entero, sep, decimal = s.partition(",")
    if sep and not re.fullmatch(r"\d{1,2}", decimal):
        return ""
    if "." in entero:
        if not re.fullmatch(r"\d{1,3}(\.\d{3})+", entero):
            return ""
        entero = entero.replace(".", "")
    elif not entero.isdigit():
        return ""
    return entero + (f".{decimal}" if sep else "")


def validar_monto(monto_str: str) -> bool:
    return normalizar_monto(monto_str) != ""


class FormDialog(tk.Toplevel):
    """Generic dialog with form fields."""

    def __init__(self, parent, title: str, fields: list[dict], values: dict | None = None):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.fields = fields
        self.widgets: dict[str, tk.Widget] = {}

        self.resizable(False, False)

        # Handle minimize/restore to release and re-apply the grab
        self.bind("<Unmap>", lambda e: self._release_grab())
        self.bind("<Map>", lambda e: self._reapply_grab())
        self.grab_set()

        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)

        for i, field in enumerate(fields):
            ttk.Label(main_frame, text=field["label"] + ":").grid(
                row=i, column=0, sticky="w", pady=4, padx=(0, 10)
            )

            if field.get("type") == "combo":
                widget = ttk.Combobox(main_frame, values=field["options"], state="readonly", width=30)
                default = (values or {}).get(field["name"], field.get("default", ""))
                if default and default in field["options"]:
                    widget.set(default)
                elif not values and field["options"]:
                    widget.set(field["options"][0])
            elif field.get("type") == "text":
                widget = tk.Text(main_frame, width=field.get("width", 33), height=field.get("height", 4), font=("Segoe UI", 10))
                default = (values or {}).get(field["name"], field.get("default", ""))
                if default:
                    widget.insert("1.0", default)
            else:
                widget = ttk.Entry(main_frame, width=33)
                default = (values or {}).get(field["name"], field.get("default", ""))
                if default:
                    widget.insert(0, str(default))

            widget.grid(row=i, column=1, sticky="ew", pady=4)
            self.widgets[field["name"]] = widget

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=(15, 0))

        ttk.Button(btn_frame, text="Save", command=self._on_save, style="Primary.TButton").pack(
            side="left", padx=5
        )
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        # Focus first widget
        first = list(self.widgets.values())[0]
        first.focus_set()

        self.bind("<Return>", lambda e: self._on_save() if not isinstance(e.widget, tk.Text) else None)
        self.bind("<Escape>", lambda e: self.destroy())

    def _on_save(self):
        result = {}
        for field in self.fields:
            w = self.widgets[field["name"]]
            if isinstance(w, tk.Text):
                val = w.get("1.0", "end-1c").strip()
            elif isinstance(w, ttk.Combobox):
                val = w.get()
            else:
                val = w.get().strip()
            result[field["name"]] = val

        # Validations
        for field in self.fields:
            if field.get("required") and not result[field["name"]]:
                messagebox.showwarning("Required field",
                                       f"The field '{field['label']}' is required.",
                                       parent=self)
                return
            if field.get("validate") == "fecha" and not validar_fecha(result[field["name"]]):
                messagebox.showwarning("Invalid date",
                                       f"The field '{field['label']}' must use the DD/MM/YYYY format.",
                                       parent=self)
                return
            if field.get("validate") == "monto" and not validar_monto(result[field["name"]]):
                messagebox.showwarning("Invalid amount",
                                       f"The field '{field['label']}' must be a valid amount, "
                                       "e.g. 1.500.000,50 (dots for thousands, comma for decimals).",
                                       parent=self)
                return

        # Convert dates to ISO format for storage
        for field in self.fields:
            if field.get("validate") == "fecha" and result[field["name"]]:
                result[field["name"]] = fecha_to_iso(result[field["name"]])

        self.result = result
        self.destroy()

    def _release_grab(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass

    def _reapply_grab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass


def confirmar(parent, mensaje: str) -> bool:
    return messagebox.askyesno("Confirm", mensaje, parent=parent)
