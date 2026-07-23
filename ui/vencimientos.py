"""Global view of deadlines across all cases."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

import database as db
from models import Vencimiento
from ui.dialogs import FormDialog, fecha_display, fecha_hoy
from ui.styles import COLOR_VENCIDO, COLOR_INMINENTE, COLOR_CUMPLIDO


class PanelVencimientosGlobales(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._venc_data: dict[str, dict] = {}
        self._build()

    def _build(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=15, pady=(15, 5))
        ttk.Label(header, text="All Deadlines", style="Title.TLabel").pack(side="left")

        # Status filter + change-status button
        filtro_frame = ttk.Frame(self)
        filtro_frame.pack(fill="x", padx=15, pady=5)
        ttk.Label(filtro_frame, text="Filter status:").pack(side="left", padx=(0, 5))
        self.filtro_estado = ttk.Combobox(
            filtro_frame, values=["", "pending", "completed", "overdue"],
            state="readonly", width=12)
        self.filtro_estado.set("")
        self.filtro_estado.pack(side="left")
        self.filtro_estado.bind("<<ComboboxSelected>>", lambda e: self.refrescar())

        self.mostrar_cumplidos = tk.BooleanVar(value=False)
        ttk.Checkbutton(filtro_frame, text="Show completed", variable=self.mostrar_cumplidos,
                        command=self.refrescar).pack(side="left", padx=(15, 0))

        ttk.Label(filtro_frame, text="   Change to:").pack(side="left", padx=(20, 5))
        self.combo_nuevo_estado = ttk.Combobox(
            filtro_frame, values=["pending", "completed", "overdue"],
            state="readonly", width=12)
        self.combo_nuevo_estado.set("completed")
        self.combo_nuevo_estado.pack(side="left", padx=(0, 5))
        ttk.Button(filtro_frame, text="Apply", command=self._cambiar_estado).pack(side="left")
        ttk.Button(filtro_frame, text="Edit", command=self._editar_vencimiento).pack(side="left", padx=(10, 0))

        # Table
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=10)

        cols = ("fecha", "caratula", "descripcion", "estado")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")

        self.tree.heading("fecha", text="Date")
        self.tree.column("fecha", width=110, minwidth=80)
        self.tree.heading("caratula", text="Case (Title)")
        self.tree.column("caratula", width=250, minwidth=120)
        self.tree.heading("descripcion", text="Description")
        self.tree.column("descripcion", width=300, minwidth=150)
        self.tree.heading("estado", text="Status")
        self.tree.column("estado", width=100, minwidth=70)

        self.tree.tag_configure("overdue", foreground="white", background=COLOR_VENCIDO)
        self.tree.tag_configure("upcoming", foreground="#000", background="#ffeaa7")
        self.tree.tag_configure("completed", foreground="white", background=COLOR_CUMPLIDO)
        self.tree.tag_configure("pending", foreground="#2c3e50")

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Legend
        leyenda = ttk.Frame(self)
        leyenda.pack(fill="x", padx=15, pady=(0, 15))
        for color, texto in [(COLOR_VENCIDO, "Overdue"), ("#ffeaa7", "Due within 5 days"),
                              (COLOR_CUMPLIDO, "Completed")]:
            tk.Canvas(leyenda, width=14, height=14, bg=color, highlightthickness=0).pack(
                side="left", padx=(0, 3))
            ttk.Label(leyenda, text=texto).pack(side="left", padx=(0, 15))

    def _editar_vencimiento(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Selection", "Select a deadline.", parent=self)
            return
        iid = sel[0]
        v_data = self._venc_data.get(iid)
        if not v_data:
            return
        campos = [
            {"name": "fecha", "label": "Date (DD/MM/YYYY)", "required": True,
             "validate": "fecha", "default": fecha_hoy()},
            {"name": "descripcion", "label": "Description", "required": True},
            {"name": "estado", "label": "Status", "type": "combo",
             "options": ["pending", "completed", "overdue"], "default": "pending"},
        ]
        values = {
            "fecha": fecha_display(v_data["fecha"]),
            "descripcion": v_data["descripcion"],
            "estado": v_data["estado"],
        }
        dlg = FormDialog(self, "Edit Deadline", campos, values)
        self.wait_window(dlg)
        if dlg.result:
            r = dlg.result
            venc = Vencimiento(id=v_data["id"], expediente_id=v_data["expediente_id"],
                               fecha=r["fecha"], descripcion=r["descripcion"],
                               estado=r["estado"])
            try:
                db.actualizar_vencimiento(venc)
            except Exception as e:
                messagebox.showerror("Error", f"Could not update the deadline:\n{e}", parent=self)
                return
            self.refrescar()

    def _cambiar_estado(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Selection", "Select a deadline.", parent=self)
            return
        nuevo_estado = self.combo_nuevo_estado.get()
        if not nuevo_estado:
            return
        iid = sel[0]
        v_data = self._venc_data.get(iid)
        if not v_data:
            return
        venc = Vencimiento(id=v_data["id"], expediente_id=v_data["expediente_id"],
                           fecha=v_data["fecha"], descripcion=v_data["descripcion"],
                           estado=nuevo_estado)
        try:
            db.actualizar_vencimiento(venc)
        except Exception as e:
            messagebox.showerror("Error", f"Could not change the status:\n{e}", parent=self)
            return
        self.refrescar()

    def refrescar(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._venc_data.clear()

        hoy = datetime.now().date()
        limite = hoy + timedelta(days=5)

        vencimientos = db.listar_vencimientos_globales(self.filtro_estado.get())
        for v in vencimientos:
            tag = "pending"
            if v["estado"] == "completed":
                tag = "completed"
            elif v["estado"] == "overdue":
                tag = "overdue"
            else:
                try:
                    fv = datetime.strptime(v["fecha"], "%Y-%m-%d").date()
                    if fv < hoy:
                        tag = "overdue"
                    elif fv <= limite:
                        tag = "upcoming"
                except ValueError:
                    pass

            if tag == "completed" and not self.mostrar_cumplidos.get() and self.filtro_estado.get() != "completed":
                continue

            iid = str(v["id"])
            self._venc_data[iid] = v
            estado_display = "overdue" if tag == "overdue" else v["estado"]
            self.tree.insert("", "end", iid=iid, values=(
                fecha_display(v["fecha"]), v["expediente_caratula"], v["descripcion"], estado_display
            ), tags=(tag,))
