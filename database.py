"""SQLite database layer for the case management application."""

import shutil
import sqlite3
import sys
import os
import unicodedata
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional


def _normalize(text: str) -> str:
    """Strips accents and lowercases for comparisons."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

from models import Expediente, Parte, PasoProcesal, Vencimiento, Honorario, Gasto, ArchivoAdjunto

DB_NAME = "expedientes.db"


def _get_db_path() -> str:
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, DB_NAME)


@contextmanager
def _connect():
    """Context manager that guarantees connection close and rollback on error."""
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("normalize", 1, _normalize)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _fix_fk_references(conn) -> None:
    """Repairs child tables whose FKs point to _expedientes_old instead of expedientes.

    ALTER TABLE RENAME in SQLite automatically updates the FKs of child tables,
    which corrupts the references when using the rename-recreate-drop pattern.
    """
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM sqlite_master WHERE sql LIKE '%expedientes_old%'"
    ).fetchone()
    if row["cnt"] > 0:
        conn.execute("PRAGMA writable_schema = ON")
        conn.execute(
            "UPDATE sqlite_master SET sql = REPLACE(sql, '_expedientes_old', 'expedientes') "
            "WHERE sql LIKE '%expedientes_old%'"
        )
        conn.execute("PRAGMA writable_schema = OFF")


def _migrate_db(conn) -> None:
    """Migrations for existing databases."""
    # Repair FKs corrupted by previous migrations
    _fix_fk_references(conn)

    # Recreate expedientes when it still has the legacy NOT NULL numero
    # or Spanish status values in its CHECK constraint
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='expedientes'"
    ).fetchone()
    if row and ("numero TEXT NOT NULL UNIQUE" in row["sql"] or "'activo'" in row["sql"]):
        conn.executescript("""
            PRAGMA foreign_keys = OFF;
            ALTER TABLE expedientes RENAME TO _expedientes_old;
            CREATE TABLE expedientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT UNIQUE,
                caratula TEXT NOT NULL,
                fuero_juzgado TEXT DEFAULT '',
                fecha_inicio TEXT DEFAULT '',
                tipo_proceso TEXT DEFAULT '',
                estado TEXT DEFAULT 'active' CHECK(estado IN ('active','archived','closed')),
                observaciones TEXT DEFAULT ''
            );
            INSERT INTO expedientes
                SELECT id, numero, caratula, fuero_juzgado, fecha_inicio, tipo_proceso,
                       CASE estado
                           WHEN 'activo' THEN 'active'
                           WHEN 'archivado' THEN 'archived'
                           WHEN 'cerrado' THEN 'closed'
                           ELSE estado
                       END,
                       observaciones
                FROM _expedientes_old;
            DROP TABLE _expedientes_old;
        """)
        # RENAME updated the FKs of child tables -> repair
        _fix_fk_references(conn)
        conn.execute("PRAGMA foreign_keys = ON")

    # Recreate vencimientos when it still has Spanish status values in its CHECK
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='vencimientos'"
    ).fetchone()
    if row and "'pendiente'" in row["sql"]:
        conn.executescript("""
            PRAGMA foreign_keys = OFF;
            ALTER TABLE vencimientos RENAME TO _vencimientos_old;
            CREATE TABLE vencimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediente_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                estado TEXT DEFAULT 'pending' CHECK(estado IN ('pending','completed','overdue')),
                FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE
            );
            INSERT INTO vencimientos
                SELECT id, expediente_id, fecha, descripcion,
                       CASE estado
                           WHEN 'pendiente' THEN 'pending'
                           WHEN 'cumplido' THEN 'completed'
                           WHEN 'vencido' THEN 'overdue'
                           ELSE estado
                       END
                FROM _vencimientos_old;
            DROP TABLE _vencimientos_old;
            PRAGMA foreign_keys = ON;
        """)

    # Translate legacy Spanish values in free-text columns (idempotent)
    conn.executescript("""
        UPDATE partes SET tipo = CASE tipo
            WHEN 'actor' THEN 'plaintiff'
            WHEN 'demandado' THEN 'defendant'
            WHEN 'tercero' THEN 'third party'
            WHEN 'perito' THEN 'expert'
            WHEN 'testigo' THEN 'witness'
            WHEN 'otro' THEN 'other'
            ELSE tipo END;
        UPDATE honorarios SET forma_pago = CASE forma_pago
            WHEN 'efectivo' THEN 'cash'
            WHEN 'transferencia' THEN 'transfer'
            WHEN 'cheque' THEN 'check'
            WHEN 'otro' THEN 'other'
            ELSE forma_pago END;
    """)


_BACKUP_COUNT = 10


def _backup_db() -> None:
    """Rotates up to _BACKUP_COUNT backup copies of the database."""
    db_path = Path(_get_db_path())
    if not db_path.exists():
        return

    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)

    stem = db_path.stem  # "expedientes"
    suffix = db_path.suffix  # ".db"

    # Rotate: 9→10, 8→9, ..., 1→2
    for i in range(_BACKUP_COUNT, 1, -1):
        src = backup_dir / f"{stem}_backup_{i - 1}{suffix}"
        dst = backup_dir / f"{stem}_backup_{i}{suffix}"
        if src.exists():
            shutil.move(str(src), str(dst))

    # Copy the current DB as _backup_1
    shutil.copy2(str(db_path), str(backup_dir / f"{stem}_backup_1{suffix}"))


def init_db() -> None:
    _backup_db()
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS expedientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT UNIQUE,
                caratula TEXT NOT NULL,
                fuero_juzgado TEXT DEFAULT '',
                fecha_inicio TEXT DEFAULT '',
                tipo_proceso TEXT DEFAULT '',
                estado TEXT DEFAULT 'active' CHECK(estado IN ('active','archived','closed')),
                observaciones TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS partes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediente_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                tipo TEXT DEFAULT '',
                dni_cuit TEXT DEFAULT '',
                domicilio TEXT DEFAULT '',
                telefono TEXT DEFAULT '',
                email TEXT DEFAULT '',
                FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS pasos_procesales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediente_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                observaciones TEXT DEFAULT '',
                FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS vencimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediente_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                estado TEXT DEFAULT 'pending' CHECK(estado IN ('pending','completed','overdue')),
                FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS honorarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediente_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                monto REAL NOT NULL,
                moneda TEXT DEFAULT 'ARS' CHECK(moneda IN ('ARS','USD')),
                concepto TEXT DEFAULT '',
                forma_pago TEXT DEFAULT '',
                FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediente_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                monto REAL NOT NULL,
                moneda TEXT DEFAULT 'ARS' CHECK(moneda IN ('ARS','USD')),
                descripcion TEXT DEFAULT '',
                FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS archivos_adjuntos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediente_id INTEGER NOT NULL,
                nombre_archivo TEXT NOT NULL,
                ruta TEXT NOT NULL,
                fecha TEXT NOT NULL,
                descripcion TEXT DEFAULT '',
                FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE
            );
        """)
        _migrate_db(conn)


# --- Cases ---

def crear_expediente(exp: Expediente) -> int:
    with _connect() as conn:
        numero = exp.numero if exp.numero and exp.numero.strip() else None
        c = conn.execute(
            "INSERT INTO expedientes (numero, caratula, fuero_juzgado, fecha_inicio, tipo_proceso, estado, observaciones) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (numero, exp.caratula, exp.fuero_juzgado, exp.fecha_inicio,
             exp.tipo_proceso, exp.estado, exp.observaciones),
        )
        return c.lastrowid


def actualizar_expediente(exp: Expediente) -> None:
    with _connect() as conn:
        numero = exp.numero if exp.numero and exp.numero.strip() else None
        conn.execute(
            "UPDATE expedientes SET numero=?, caratula=?, fuero_juzgado=?, fecha_inicio=?, "
            "tipo_proceso=?, estado=?, observaciones=? WHERE id=?",
            (numero, exp.caratula, exp.fuero_juzgado, exp.fecha_inicio,
             exp.tipo_proceso, exp.estado, exp.observaciones, exp.id),
        )


def eliminar_expediente(exp_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM expedientes WHERE id=?", (exp_id,))


def obtener_expediente(exp_id: int) -> Optional[Expediente]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM expedientes WHERE id=?", (exp_id,)).fetchone()
        if row:
            return Expediente(**dict(row))
        return None


def listar_expedientes(filtro_numero: str = "", filtro_caratula: str = "",
                       filtro_estado: str = "", filtro_juzgado: str = "") -> list[Expediente]:
    with _connect() as conn:
        query = "SELECT * FROM expedientes WHERE 1=1"
        params: list = []
        if filtro_numero:
            query += " AND normalize(numero) LIKE ?"
            params.append(f"%{_normalize(filtro_numero)}%")
        if filtro_caratula:
            query += " AND normalize(caratula) LIKE ?"
            params.append(f"%{_normalize(filtro_caratula)}%")
        if filtro_estado:
            query += " AND estado = ?"
            params.append(filtro_estado)
        if filtro_juzgado:
            query += " AND normalize(fuero_juzgado) LIKE ?"
            params.append(f"%{_normalize(filtro_juzgado)}%")
        query += " ORDER BY fecha_inicio DESC, id DESC"
        rows = conn.execute(query, params).fetchall()
        return [Expediente(**dict(r)) for r in rows]


def obtener_ultimo_movimiento(expediente_id: int) -> Optional[str]:
    """Returns the date of the case's latest procedural step, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT MAX(fecha) as ultima FROM pasos_procesales WHERE expediente_id=?",
            (expediente_id,),
        ).fetchone()
        if row and row["ultima"]:
            return row["ultima"]
        return None


def obtener_ultimos_movimientos() -> dict[int, str]:
    """Returns a dict {case_id: last_activity_date} for all cases."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT expediente_id, MAX(fecha) as ultima FROM pasos_procesales GROUP BY expediente_id"
        ).fetchall()
        return {r["expediente_id"]: r["ultima"] for r in rows}


def numero_existe(numero: str, excluir_id: Optional[int] = None) -> bool:
    if not numero or not numero.strip():
        return False
    with _connect() as conn:
        if excluir_id:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM expedientes WHERE numero=? AND id!=?",
                (numero, excluir_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM expedientes WHERE numero=?", (numero,)
            ).fetchone()
        return row["cnt"] > 0


# --- Parties ---

def crear_parte(parte: Parte) -> int:
    with _connect() as conn:
        c = conn.execute(
            "INSERT INTO partes (expediente_id, nombre, tipo, dni_cuit, domicilio, telefono, email) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (parte.expediente_id, parte.nombre, parte.tipo, parte.dni_cuit,
             parte.domicilio, parte.telefono, parte.email),
        )
        return c.lastrowid


def actualizar_parte(parte: Parte) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE partes SET nombre=?, tipo=?, dni_cuit=?, domicilio=?, telefono=?, email=? WHERE id=?",
            (parte.nombre, parte.tipo, parte.dni_cuit, parte.domicilio,
             parte.telefono, parte.email, parte.id),
        )


def eliminar_parte(parte_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM partes WHERE id=?", (parte_id,))


def listar_partes(expediente_id: int) -> list[Parte]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM partes WHERE expediente_id=? ORDER BY tipo, nombre", (expediente_id,)
        ).fetchall()
        return [Parte(**dict(r)) for r in rows]


# --- Procedural Steps ---

def crear_paso(paso: PasoProcesal) -> int:
    with _connect() as conn:
        c = conn.execute(
            "INSERT INTO pasos_procesales (expediente_id, fecha, descripcion, observaciones) "
            "VALUES (?, ?, ?, ?)",
            (paso.expediente_id, paso.fecha, paso.descripcion, paso.observaciones),
        )
        return c.lastrowid


def actualizar_paso(paso: PasoProcesal) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE pasos_procesales SET fecha=?, descripcion=?, observaciones=? WHERE id=?",
            (paso.fecha, paso.descripcion, paso.observaciones, paso.id),
        )


def eliminar_paso(paso_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM pasos_procesales WHERE id=?", (paso_id,))


def listar_pasos(expediente_id: int) -> list[PasoProcesal]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM pasos_procesales WHERE expediente_id=? ORDER BY fecha DESC, id DESC",
            (expediente_id,),
        ).fetchall()
        return [PasoProcesal(**dict(r)) for r in rows]


# --- Deadlines ---

def crear_vencimiento(venc: Vencimiento) -> int:
    with _connect() as conn:
        c = conn.execute(
            "INSERT INTO vencimientos (expediente_id, fecha, descripcion, estado) VALUES (?, ?, ?, ?)",
            (venc.expediente_id, venc.fecha, venc.descripcion, venc.estado),
        )
        return c.lastrowid


def actualizar_vencimiento(venc: Vencimiento) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE vencimientos SET fecha=?, descripcion=?, estado=? WHERE id=?",
            (venc.fecha, venc.descripcion, venc.estado, venc.id),
        )


def eliminar_vencimiento(venc_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM vencimientos WHERE id=?", (venc_id,))


def listar_vencimientos(expediente_id: int) -> list[Vencimiento]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM vencimientos WHERE expediente_id=? ORDER BY fecha ASC",
            (expediente_id,),
        ).fetchall()
        return [Vencimiento(**dict(r)) for r in rows]


def listar_vencimientos_globales(filtro_estado: str = "") -> list[dict]:
    hoy = datetime.now().date().isoformat()
    with _connect() as conn:
        query = (
            "SELECT v.*, e.caratula as expediente_caratula, COALESCE(e.numero, '') as expediente_numero FROM vencimientos v "
            "JOIN expedientes e ON v.expediente_id = e.id "
            "WHERE e.estado = 'active'"
        )
        params: list = []
        if filtro_estado == "overdue":
            query += " AND (v.estado = 'overdue' OR (v.estado = 'pending' AND v.fecha < ?))"
            params.append(hoy)
        elif filtro_estado == "pending":
            query += " AND v.estado = 'pending' AND v.fecha >= ?"
            params.append(hoy)
        elif filtro_estado:
            query += " AND v.estado = ?"
            params.append(filtro_estado)
        query += " ORDER BY v.fecha ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


# --- Fees ---

def crear_honorario(hon: Honorario) -> int:
    with _connect() as conn:
        c = conn.execute(
            "INSERT INTO honorarios (expediente_id, fecha, monto, moneda, concepto, forma_pago) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (hon.expediente_id, hon.fecha, hon.monto, hon.moneda, hon.concepto, hon.forma_pago),
        )
        return c.lastrowid


def eliminar_honorario(hon_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM honorarios WHERE id=?", (hon_id,))


def listar_honorarios(expediente_id: int) -> list[Honorario]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM honorarios WHERE expediente_id=? ORDER BY fecha DESC",
            (expediente_id,),
        ).fetchall()
        return [Honorario(**dict(r)) for r in rows]


def totales_honorarios(expediente_id: int) -> dict[str, float]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT moneda, SUM(monto) as total FROM honorarios WHERE expediente_id=? GROUP BY moneda",
            (expediente_id,),
        ).fetchall()
        return {r["moneda"]: r["total"] for r in rows}


def listar_honorarios_globales(filtro_moneda: str = "") -> list[dict]:
    with _connect() as conn:
        query = (
            "SELECT h.*, e.caratula as expediente_caratula "
            "FROM honorarios h "
            "JOIN expedientes e ON h.expediente_id = e.id "
            "WHERE 1=1"
        )
        params: list = []
        if filtro_moneda:
            query += " AND h.moneda = ?"
            params.append(filtro_moneda)
        query += " ORDER BY h.fecha DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


# --- Expenses ---

def crear_gasto(gasto: Gasto) -> int:
    with _connect() as conn:
        c = conn.execute(
            "INSERT INTO gastos (expediente_id, fecha, monto, moneda, descripcion) "
            "VALUES (?, ?, ?, ?, ?)",
            (gasto.expediente_id, gasto.fecha, gasto.monto, gasto.moneda, gasto.descripcion),
        )
        return c.lastrowid


def eliminar_gasto(gasto_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM gastos WHERE id=?", (gasto_id,))


def listar_gastos(expediente_id: int) -> list[Gasto]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM gastos WHERE expediente_id=? ORDER BY fecha DESC",
            (expediente_id,),
        ).fetchall()
        return [Gasto(**dict(r)) for r in rows]


def totales_gastos(expediente_id: int) -> dict[str, float]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT moneda, SUM(monto) as total FROM gastos WHERE expediente_id=? GROUP BY moneda",
            (expediente_id,),
        ).fetchall()
        return {r["moneda"]: r["total"] for r in rows}


# --- File Attachments ---

def _get_adjuntos_dir() -> str:
    """Returns the base path for storing file attachments."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "adjuntos")


def crear_adjunto(adj: ArchivoAdjunto) -> int:
    with _connect() as conn:
        c = conn.execute(
            "INSERT INTO archivos_adjuntos (expediente_id, nombre_archivo, ruta, fecha, descripcion) "
            "VALUES (?, ?, ?, ?, ?)",
            (adj.expediente_id, adj.nombre_archivo, adj.ruta, adj.fecha, adj.descripcion),
        )
        return c.lastrowid


def eliminar_adjunto(adj_id: int) -> Optional[str]:
    """Deletes the record and returns the file path for external deletion."""
    with _connect() as conn:
        row = conn.execute("SELECT ruta FROM archivos_adjuntos WHERE id=?", (adj_id,)).fetchone()
        if row:
            conn.execute("DELETE FROM archivos_adjuntos WHERE id=?", (adj_id,))
            return row["ruta"]
        return None


def listar_adjuntos(expediente_id: int) -> list[ArchivoAdjunto]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM archivos_adjuntos WHERE expediente_id=? ORDER BY fecha DESC, id DESC",
            (expediente_id,),
        ).fetchall()
        return [ArchivoAdjunto(**dict(r)) for r in rows]
