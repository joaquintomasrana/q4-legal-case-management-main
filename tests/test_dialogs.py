"""Tests for the amount helpers in ui/dialogs.py.

The helpers are pure functions, but the module imports tkinter at import
time; the suite is skipped on environments without it (headless CI).
"""

import unittest

try:
    from ui.dialogs import normalizar_monto, validar_monto
except ImportError as exc:  # pragma: no cover - tkinter not installed
    raise unittest.SkipTest(f"tkinter not available: {exc}")


class TestNormalizarMonto(unittest.TestCase):
    def test_puntos_como_separador_de_miles(self):
        self.assertEqual(normalizar_monto("1.500.000"), "1500000")
        self.assertEqual(normalizar_monto("1.000"), "1000")

    def test_sin_separadores(self):
        self.assertEqual(normalizar_monto("1500000"), "1500000")
        self.assertEqual(normalizar_monto("0"), "0")

    def test_coma_como_separador_decimal(self):
        self.assertEqual(normalizar_monto("1.500.000,50"), "1500000.50")
        self.assertEqual(normalizar_monto("10,5"), "10.5")
        self.assertEqual(normalizar_monto("0,99"), "0.99")

    def test_espacios_se_ignoran(self):
        self.assertEqual(normalizar_monto(" 1.000 "), "1000")
        self.assertEqual(normalizar_monto("1 500 000"), "1500000")

    def test_punto_decimal_es_rechazado(self):
        # "10.50" must NOT be silently read as 1050
        self.assertEqual(normalizar_monto("10.50"), "")
        self.assertEqual(normalizar_monto("1.5"), "")

    def test_agrupacion_de_miles_invalida(self):
        self.assertEqual(normalizar_monto("1.23.4"), "")
        self.assertEqual(normalizar_monto("12.3456"), "")
        self.assertEqual(normalizar_monto(".500"), "")

    def test_entradas_invalidas(self):
        self.assertEqual(normalizar_monto(""), "")
        self.assertEqual(normalizar_monto("abc"), "")
        self.assertEqual(normalizar_monto("-5"), "")
        self.assertEqual(normalizar_monto("1,2,3"), "")
        self.assertEqual(normalizar_monto("10,555"), "")  # too many decimals
        self.assertEqual(normalizar_monto(",50"), "")


class TestValidarMonto(unittest.TestCase):
    def test_validos(self):
        for monto in ("0", "1500", "1.500.000", "1.500.000,50", "10,5"):
            self.assertTrue(validar_monto(monto), monto)

    def test_invalidos(self):
        for monto in ("", "abc", "10.50", "1,2,3", "-5", "1.23.4"):
            self.assertFalse(validar_monto(monto), monto)


if __name__ == "__main__":
    unittest.main()
