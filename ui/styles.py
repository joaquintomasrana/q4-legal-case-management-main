"""ttk style configuration for the application."""

import tkinter as tk
from tkinter import ttk


# Colors
COLOR_SIDEBAR_BG = "#2c3e50"
COLOR_SIDEBAR_FG = "#ecf0f1"
COLOR_SIDEBAR_ACTIVE = "#34495e"
COLOR_PRIMARY = "#2980b9"
COLOR_SUCCESS = "#27ae60"
COLOR_WARNING = "#f39c12"
COLOR_DANGER = "#e74c3c"
COLOR_BG = "#f5f6fa"
COLOR_CARD_BG = "#ffffff"
COLOR_TEXT = "#2c3e50"
COLOR_VENCIDO = "#e74c3c"
COLOR_INMINENTE = "#f39c12"
COLOR_CUMPLIDO = "#27ae60"


def configurar_estilos(root: tk.Tk) -> None:
    style = ttk.Style(root)
    style.theme_use("clam")

    # General
    style.configure(".", font=("Segoe UI", 10), background=COLOR_BG, foreground=COLOR_TEXT)

    # Frames
    style.configure("Card.TFrame", background=COLOR_CARD_BG)
    style.configure("Sidebar.TFrame", background=COLOR_SIDEBAR_BG)

    # Labels
    style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), background=COLOR_BG)
    style.configure("Subtitle.TLabel", font=("Segoe UI", 12, "bold"), background=COLOR_BG)
    style.configure("Card.TLabel", background=COLOR_CARD_BG)
    style.configure("CardTitle.TLabel", font=("Segoe UI", 11, "bold"), background=COLOR_CARD_BG)
    style.configure("Total.TLabel", font=("Segoe UI", 11, "bold"), background=COLOR_CARD_BG,
                     foreground=COLOR_PRIMARY)

    # Buttons
    style.configure("Primary.TButton", font=("Segoe UI", 10))
    style.configure("Danger.TButton", font=("Segoe UI", 10))
    style.configure("Success.TButton", font=("Segoe UI", 10))

    # Sidebar buttons
    style.configure("Sidebar.TButton", font=("Segoe UI", 11), background=COLOR_SIDEBAR_BG,
                     foreground=COLOR_SIDEBAR_FG, borderwidth=0, padding=(15, 10))
    style.map("Sidebar.TButton",
              background=[("active", COLOR_SIDEBAR_ACTIVE)],
              foreground=[("active", COLOR_SIDEBAR_FG)])

    style.configure("SidebarActive.TButton", font=("Segoe UI", 11, "bold"),
                     background=COLOR_PRIMARY, foreground=COLOR_SIDEBAR_FG,
                     borderwidth=0, padding=(15, 10))
    style.map("SidebarActive.TButton",
              background=[("active", COLOR_PRIMARY)],
              foreground=[("active", COLOR_SIDEBAR_FG)])

    # Treeview
    style.configure("Treeview", font=("Segoe UI", 10), rowheight=28, background=COLOR_CARD_BG,
                     fieldbackground=COLOR_CARD_BG)
    style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
    style.map("Treeview", background=[("selected", COLOR_PRIMARY)],
              foreground=[("selected", "white")])

    # Notebook
    style.configure("TNotebook", background=COLOR_BG)
    style.configure("TNotebook.Tab", font=("Segoe UI", 10), padding=(12, 6))

    # Entry
    style.configure("TEntry", padding=5)

    # Combobox
    style.configure("TCombobox", padding=5)
