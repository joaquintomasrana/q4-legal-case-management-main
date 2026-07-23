"""Main application window with sidebar navigation."""

import tkinter as tk
from tkinter import ttk

from ui.styles import configurar_estilos, COLOR_SIDEBAR_BG, COLOR_SIDEBAR_FG, COLOR_BG
from ui.expedientes import PanelExpedientes
from ui.vencimientos import PanelVencimientosGlobales
from ui.honorarios import PanelHonorariosGlobales


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Q4 Legal Case Management")
        self.geometry("1200x700")
        self.minsize(900, 550)
        self.state("zoomed")  # Start maximized
        self.configure(bg=COLOR_BG)

        configurar_estilos(self)

        # Main layout
        self.sidebar = tk.Frame(self, bg=COLOR_SIDEBAR_BG, width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.content = ttk.Frame(self)
        self.content.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._panels: dict[str, ttk.Frame] = {}
        self._current_panel: str | None = None

        self.mostrar_panel("expedientes")

    def _build_sidebar(self):
        # Title
        title_frame = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR_BG)
        title_frame.pack(fill="x", pady=(20, 30))
        tk.Label(title_frame, text="Q4", font=("Segoe UI", 14, "bold"),
                 bg=COLOR_SIDEBAR_BG, fg=COLOR_SIDEBAR_FG).pack(padx=15)
        tk.Label(title_frame, text="Legal Case Management", font=("Segoe UI", 9),
                 bg=COLOR_SIDEBAR_BG, fg="#95a5a6").pack(padx=15)

        # Separator
        tk.Frame(self.sidebar, bg="#34495e", height=1).pack(fill="x", padx=15, pady=5)

        # Navigation buttons
        self.nav_buttons: dict[str, tk.Button] = {}

        nav_items = [
            ("expedientes", "Cases"),
            ("vencimientos", "Deadlines"),
            ("honorarios", "Fees"),
        ]

        for key, label in nav_items:
            btn = tk.Button(
                self.sidebar, text=f"  {label}", anchor="w",
                font=("Segoe UI", 11), bg=COLOR_SIDEBAR_BG, fg=COLOR_SIDEBAR_FG,
                activebackground="#34495e", activeforeground=COLOR_SIDEBAR_FG,
                bd=0, padx=20, pady=10, cursor="hand2",
                command=lambda k=key: self.mostrar_panel(k),
            )
            btn.pack(fill="x")
            self.nav_buttons[key] = btn

    def mostrar_panel(self, nombre: str):
        if self._current_panel == nombre:
            return

        # Update buttons
        for key, btn in self.nav_buttons.items():
            if key == nombre:
                btn.configure(bg="#2980b9", font=("Segoe UI", 11, "bold"))
            else:
                btn.configure(bg=COLOR_SIDEBAR_BG, font=("Segoe UI", 11))

        # Hide current panel
        for panel in self._panels.values():
            panel.pack_forget()

        # Create or show panel
        if nombre not in self._panels:
            if nombre == "expedientes":
                self._panels[nombre] = PanelExpedientes(self.content, self)
            elif nombre == "vencimientos":
                self._panels[nombre] = PanelVencimientosGlobales(self.content, self)
            elif nombre == "honorarios":
                self._panels[nombre] = PanelHonorariosGlobales(self.content, self)

        self._panels[nombre].pack(fill="both", expand=True)
        if hasattr(self._panels[nombre], "refrescar"):
            self._panels[nombre].refrescar()

        self._current_panel = nombre
