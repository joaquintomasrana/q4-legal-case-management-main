"""Imports cases from a CSV file with columns: case title, case type."""

import csv
import sys

import database as db
from models import Expediente


def importar(ruta_csv: str) -> None:
    db.init_db()
    count = 0
    with open(ruta_csv, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header
        print(f"Detected columns: {header}")
        for i, row in enumerate(reader, start=2):
            if len(row) < 2:
                print(f"  Row {i}: skipped (missing columns)")
                continue
            caratula = row[0].strip()
            tipo_proceso = row[1].strip()
            if not caratula:
                print(f"  Row {i}: skipped (empty case title)")
                continue
            exp = Expediente(caratula=caratula, tipo_proceso=tipo_proceso)
            db.crear_expediente(exp)
            count += 1
    print(f"\nImport complete: {count} cases created.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python importar_csv.py <file.csv>")
        sys.exit(1)
    importar(sys.argv[1])
