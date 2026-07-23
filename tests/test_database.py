"""Tests for the SQLite layer (database.py).

Each test runs against a throwaway database in a temporary directory,
created by redirecting database._get_db_path().
"""

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

import database as db
from models import (ArchivoAdjunto, Expediente, Gasto, Honorario, Parte,
                    PasoProcesal, Vencimiento)


def _fetchall(db_path, sql, params=()):
    """Runs a read query on a raw connection that is closed explicitly.

    `with sqlite3.connect(...)` manages the transaction but does NOT close
    the connection; on Windows the lingering handle locks the .db file and
    breaks TemporaryDirectory cleanup (WinError 32).
    """
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.db_path = os.path.join(self._tmpdir.name, "expedientes.db")

        self._original_get_db_path = db._get_db_path
        db._get_db_path = lambda: self.db_path
        self.addCleanup(self._restore_db_path)

        db.init_db()

    def _restore_db_path(self):
        db._get_db_path = self._original_get_db_path

    def _crear_expediente(self, **kwargs) -> int:
        defaults = {"caratula": "Test case", "estado": "active"}
        defaults.update(kwargs)
        return db.crear_expediente(Expediente(**defaults))


class TestInit(DatabaseTestCase):
    def test_creates_all_tables(self):
        tablas = {r[0] for r in _fetchall(
            self.db_path, "SELECT name FROM sqlite_master WHERE type='table'")}
        esperadas = {"expedientes", "partes", "pasos_procesales", "vencimientos",
                     "honorarios", "gastos", "archivos_adjuntos"}
        self.assertTrue(esperadas.issubset(tablas))

    def test_init_is_idempotent(self):
        exp_id = self._crear_expediente()
        db.init_db()  # second run must not fail nor lose data
        self.assertIsNotNone(db.obtener_expediente(exp_id))

    def test_backup_is_created_on_second_launch(self):
        db.init_db()  # first launch after creation: snapshots the existing db
        backup = os.path.join(self._tmpdir.name, "backups",
                              "expedientes_backup_1.db")
        self.assertTrue(os.path.exists(backup))


class TestExpedientes(DatabaseTestCase):
    def test_crud(self):
        exp_id = self._crear_expediente(numero="123/2026", caratula="Pérez c/ Gómez")
        exp = db.obtener_expediente(exp_id)
        self.assertEqual(exp.numero, "123/2026")
        self.assertEqual(exp.caratula, "Pérez c/ Gómez")

        exp.caratula = "Pérez c/ Gómez (apelación)"
        db.actualizar_expediente(exp)
        self.assertEqual(db.obtener_expediente(exp_id).caratula,
                         "Pérez c/ Gómez (apelación)")

        db.eliminar_expediente(exp_id)
        self.assertIsNone(db.obtener_expediente(exp_id))

    def test_empty_numero_is_null_and_coexists(self):
        a = self._crear_expediente(numero="")
        b = self._crear_expediente(numero="   ")
        self.assertNotEqual(a, b)
        self.assertEqual(db.obtener_expediente(a).numero, "")
        self.assertEqual(db.obtener_expediente(b).numero, "")

    def test_duplicate_numero_rejected_by_db(self):
        self._crear_expediente(numero="100")
        with self.assertRaises(sqlite3.IntegrityError):
            self._crear_expediente(numero="100")

    def test_numero_existe(self):
        exp_id = self._crear_expediente(numero="100")
        self.assertTrue(db.numero_existe("100"))
        self.assertFalse(db.numero_existe("100", excluir_id=exp_id))
        self.assertFalse(db.numero_existe("999"))
        self.assertFalse(db.numero_existe(""))

    def test_accent_insensitive_search(self):
        self._crear_expediente(caratula="Pérez c/ González")
        self._crear_expediente(caratula="Rodríguez c/ López")

        for termino in ("perez", "PEREZ", "Pérez"):
            resultados = db.listar_expedientes(filtro_caratula=termino)
            self.assertEqual(len(resultados), 1)
            self.assertEqual(resultados[0].caratula, "Pérez c/ González")

    def test_filtros_combinados(self):
        self._crear_expediente(caratula="Activo civil", fuero_juzgado="Civil 1")
        self._crear_expediente(caratula="Archivado laboral", estado="archived",
                               fuero_juzgado="Laboral 2")
        resultados = db.listar_expedientes(filtro_estado="active",
                                           filtro_juzgado="civil")
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0].caratula, "Activo civil")


class TestCascadeDelete(DatabaseTestCase):
    def test_deleting_case_removes_all_children(self):
        exp_id = self._crear_expediente()
        db.crear_parte(Parte(expediente_id=exp_id, nombre="Juan", tipo="plaintiff"))
        db.crear_paso(PasoProcesal(expediente_id=exp_id, fecha="2026-01-10",
                                   descripcion="Contestación"))
        db.crear_vencimiento(Vencimiento(expediente_id=exp_id, fecha="2026-02-01",
                                         descripcion="Traslado"))
        db.crear_honorario(Honorario(expediente_id=exp_id, fecha="2026-01-15",
                                     monto=1000, moneda="ARS"))
        db.crear_gasto(Gasto(expediente_id=exp_id, fecha="2026-01-15",
                             monto=500, moneda="ARS"))
        db.crear_adjunto(ArchivoAdjunto(expediente_id=exp_id, nombre_archivo="a.pdf",
                                        ruta="/tmp/a.pdf", fecha="2026-01-15"))

        db.eliminar_expediente(exp_id)

        for tabla in ("partes", "pasos_procesales", "vencimientos",
                      "honorarios", "gastos", "archivos_adjuntos"):
            count = _fetchall(
                self.db_path,
                f"SELECT COUNT(*) FROM {tabla} WHERE expediente_id=?",
                (exp_id,))[0][0]
            self.assertEqual(count, 0, f"rows left in {tabla}")


class TestConsultas(DatabaseTestCase):
    def test_ultimos_movimientos(self):
        a = self._crear_expediente()
        b = self._crear_expediente()
        db.crear_paso(PasoProcesal(expediente_id=a, fecha="2026-01-05", descripcion="x"))
        db.crear_paso(PasoProcesal(expediente_id=a, fecha="2026-03-01", descripcion="y"))
        db.crear_paso(PasoProcesal(expediente_id=b, fecha="2026-02-10", descripcion="z"))

        ultimos = db.obtener_ultimos_movimientos()
        self.assertEqual(ultimos[a], "2026-03-01")
        self.assertEqual(ultimos[b], "2026-02-10")
        self.assertEqual(db.obtener_ultimo_movimiento(a), "2026-03-01")

    def test_totales_honorarios_por_moneda(self):
        exp_id = self._crear_expediente()
        db.crear_honorario(Honorario(expediente_id=exp_id, fecha="2026-01-01",
                                     monto=1000, moneda="ARS"))
        db.crear_honorario(Honorario(expediente_id=exp_id, fecha="2026-01-02",
                                     monto=2500, moneda="ARS"))
        db.crear_honorario(Honorario(expediente_id=exp_id, fecha="2026-01-03",
                                     monto=300, moneda="USD"))
        totales = db.totales_honorarios(exp_id)
        self.assertEqual(totales["ARS"], 3500)
        self.assertEqual(totales["USD"], 300)

    def test_vencimientos_globales_solo_activos(self):
        activo = self._crear_expediente(estado="active")
        cerrado = self._crear_expediente(estado="closed")
        db.crear_vencimiento(Vencimiento(expediente_id=activo, fecha="2026-06-01",
                                         descripcion="Del activo"))
        db.crear_vencimiento(Vencimiento(expediente_id=cerrado, fecha="2026-06-01",
                                         descripcion="Del cerrado"))
        globales = db.listar_vencimientos_globales()
        self.assertEqual(len(globales), 1)
        self.assertEqual(globales[0]["descripcion"], "Del activo")

    def test_vencimientos_globales_filtro_overdue(self):
        exp_id = self._crear_expediente()
        ayer = (datetime.now().date() - timedelta(days=1)).isoformat()
        maniana = (datetime.now().date() + timedelta(days=1)).isoformat()
        db.crear_vencimiento(Vencimiento(expediente_id=exp_id, fecha=ayer,
                                         descripcion="Ya pasó", estado="pending"))
        db.crear_vencimiento(Vencimiento(expediente_id=exp_id, fecha=maniana,
                                         descripcion="Futuro", estado="pending"))

        overdue = db.listar_vencimientos_globales(filtro_estado="overdue")
        self.assertEqual([v["descripcion"] for v in overdue], ["Ya pasó"])

        pending = db.listar_vencimientos_globales(filtro_estado="pending")
        self.assertEqual([v["descripcion"] for v in pending], ["Futuro"])


class TestMigraciones(unittest.TestCase):
    """Legacy databases (Spanish statuses, NOT NULL numero) upgrade in place."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.db_path = os.path.join(self._tmpdir.name, "expedientes.db")

        self._original_get_db_path = db._get_db_path
        db._get_db_path = lambda: self.db_path
        self.addCleanup(self._restore_db_path)

        # Build a legacy database by hand. The connection is closed
        # explicitly so Windows does not keep the .db file locked.
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript("""
                CREATE TABLE expedientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero TEXT NOT NULL UNIQUE,
                    caratula TEXT NOT NULL,
                    fuero_juzgado TEXT DEFAULT '',
                    fecha_inicio TEXT DEFAULT '',
                    tipo_proceso TEXT DEFAULT '',
                    estado TEXT DEFAULT 'activo'
                        CHECK(estado IN ('activo','archivado','cerrado')),
                    observaciones TEXT DEFAULT ''
                );
                CREATE TABLE partes (
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
                CREATE TABLE vencimientos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expediente_id INTEGER NOT NULL,
                    fecha TEXT NOT NULL,
                    descripcion TEXT NOT NULL,
                    estado TEXT DEFAULT 'pendiente'
                        CHECK(estado IN ('pendiente','cumplido','vencido')),
                    FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE
                );
                CREATE TABLE honorarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expediente_id INTEGER NOT NULL,
                    fecha TEXT NOT NULL,
                    monto REAL NOT NULL,
                    moneda TEXT DEFAULT 'ARS' CHECK(moneda IN ('ARS','USD')),
                    concepto TEXT DEFAULT '',
                    forma_pago TEXT DEFAULT '',
                    FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE
                );
                INSERT INTO expedientes (numero, caratula, estado)
                    VALUES ('55/2020', 'Caso legado', 'activo');
                INSERT INTO partes (expediente_id, nombre, tipo)
                    VALUES (1, 'María', 'demandado');
                INSERT INTO vencimientos (expediente_id, fecha, descripcion, estado)
                    VALUES (1, '2020-05-01', 'Traslado', 'cumplido');
                INSERT INTO honorarios (expediente_id, fecha, monto, forma_pago)
                    VALUES (1, '2020-06-01', 5000, 'transferencia');
            """)
            conn.commit()
        finally:
            conn.close()

    def _restore_db_path(self):
        db._get_db_path = self._original_get_db_path

    def test_legacy_db_is_upgraded(self):
        db.init_db()

        exp = db.obtener_expediente(1)
        self.assertEqual(exp.estado, "active")

        parte = db.listar_partes(1)[0]
        self.assertEqual(parte.tipo, "defendant")

        venc = db.listar_vencimientos(1)[0]
        self.assertEqual(venc.estado, "completed")

        forma = _fetchall(self.db_path,
                          "SELECT forma_pago FROM honorarios WHERE id=1")[0][0]
        self.assertEqual(forma, "transfer")

    def test_numero_becomes_nullable(self):
        db.init_db()
        # Inserting a case without a number must now succeed
        exp_id = db.crear_expediente(Expediente(caratula="Sin número"))
        self.assertEqual(db.obtener_expediente(exp_id).numero, "")

    def test_child_fks_point_to_expedientes_after_migration(self):
        db.init_db()
        for tabla in ("partes", "vencimientos", "honorarios"):
            refs = _fetchall(self.db_path, f"PRAGMA foreign_key_list({tabla})")
            self.assertTrue(refs, f"{tabla} lost its foreign keys")
            self.assertEqual(refs[0][2], "expedientes",
                             f"{tabla} FK points to {refs[0][2]}")

    def test_migration_is_idempotent(self):
        db.init_db()
        db.init_db()  # second pass must leave everything intact
        self.assertEqual(db.obtener_expediente(1).estado, "active")
        self.assertEqual(db.listar_partes(1)[0].tipo, "defendant")

    def test_cascade_still_works_after_migration(self):
        db.init_db()
        db.eliminar_expediente(1)
        for tabla in ("partes", "vencimientos", "honorarios"):
            count = _fetchall(self.db_path,
                              f"SELECT COUNT(*) FROM {tabla}")[0][0]
            self.assertEqual(count, 0, f"rows left in {tabla}")


if __name__ == "__main__":
    unittest.main()
