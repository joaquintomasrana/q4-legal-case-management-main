"""Global view of fees across all cases."""

import tkinter as tk
from tkinter import ttk
from locale import setlocale, LC_NUMERIC, format_string

import database as db
from ui.dialogs import fecha_display

# Try to set a locale for number formatting
try:
    setlocale(LC_NUMERIC, "en_US.UTF-8")
except Exception:
    try:
        setlocale(LC_NUMERIC, "English_United States")
    except Exception:
        pass


def _fmt_monto(valor: float) -> str:
    """Formats an amount with 2 decimals and thousands separator."""
    try:
        return format_string("%.2f", valor, grouping=True)
    except Exception:
        return f"{valor:,.2f}"


class PanelHonorariosGlobales(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=15, pady=(15, 5))
        ttk.Label(header, text="Collected Fees", style="Title.TLabel").pack(side="left")

        # Currency filter
        filtro_frame = ttk.Frame(self)
        filtro_frame.pack(fill="x", padx=15, pady=5)
        ttk.Label(filtro_frame, text="Filter currency:").pack(side="left", padx=(0, 5))
        self.filtro_moneda = ttk.Combobox(
            filtro_frame, values=["", "ARS", "USD"],
            state="readonly", width=10)
        self.filtro_moneda.set("")
        self.filtro_moneda.pack(side="left")
        self.filtro_moneda.bind("<<ComboboxSelected>>", lambda e: self.refrescar())

        # Table
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=10)

        cols = ("fecha", "caratula", "monto", "moneda", "forma_pago", "concepto")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")

        self.tree.heading("fecha", text="Date")
        self.tree.column("fecha", width=100, minwidth=80)
        self.tree.heading("caratula", text="Case (Title)")
        self.tree.column("caratula", width=250, minwidth=120)
        self.tree.heading("monto", text="Amount")
        self.tree.column("monto", width=120, minwidth=80, anchor="e")
        self.tree.heading("moneda", text="Currency")
        self.tree.column("moneda", width=70, minwidth=50, anchor="center")
        self.tree.heading("forma_pago", text="Payment Method")
        self.tree.column("forma_pago", width=140, minwidth=80)
        self.tree.heading("concepto", text="Concept")
        self.tree.column("concepto", width=200, minwidth=100)

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Totals footer
        self.totales_frame = ttk.Frame(self)
        self.totales_frame.pack(fill="x", padx=15, pady=(0, 15))
        self.lbl_totales = ttk.Label(self.totales_frame, text="", font=("Segoe UI", 11, "bold"))
        self.lbl_totales.pack(side="left")

    def refrescar(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        filtro = self.filtro_moneda.get()
        honorarios = db.listar_honorarios_globales(filtro)

        total_ars = 0.0
        total_usd = 0.0

        for h in honorarios:
            monto = h["monto"] or 0.0
            if h["moneda"] == "ARS":
                total_ars += monto
            elif h["moneda"] == "USD":
                total_usd += monto

            self.tree.insert("", "end", iid=str(h["id"]), values=(
                fecha_display(h["fecha"]),
                h["expediente_caratula"],
                _fmt_monto(monto),
                h["moneda"],
                h.get("forma_pago", ""),
                h.get("concepto", ""),
            ))

        # Show totals
        partes = []
        if not filtro or filtro == "ARS":
            partes.append(f"ARS: $ {_fmt_monto(total_ars)}")
        if not filtro or filtro == "USD":
            partes.append(f"USD: $ {_fmt_monto(total_usd)}")
        self.lbl_totales.configure(text="Totals:  " + "   |   ".join(partes))
