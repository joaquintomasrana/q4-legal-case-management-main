"""Data models for the legal case management application."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Expediente:
    id: Optional[int] = None
    numero: str = ""
    caratula: str = ""
    fuero_juzgado: str = ""
    fecha_inicio: str = ""
    tipo_proceso: str = ""
    estado: str = "active"  # active / archived / closed
    observaciones: str = ""

    def __post_init__(self):
        # SQLite NULL arrives as None; normalize to empty string
        if self.numero is None:
            self.numero = ""
        if self.fuero_juzgado is None:
            self.fuero_juzgado = ""
        if self.observaciones is None:
            self.observaciones = ""


@dataclass
class Parte:
    id: Optional[int] = None
    expediente_id: Optional[int] = None
    nombre: str = ""
    tipo: str = ""  # plaintiff / defendant / third party / expert / etc.
    dni_cuit: str = ""
    domicilio: str = ""
    telefono: str = ""
    email: str = ""


@dataclass
class PasoProcesal:
    id: Optional[int] = None
    expediente_id: Optional[int] = None
    fecha: str = ""
    descripcion: str = ""
    observaciones: str = ""


@dataclass
class Vencimiento:
    id: Optional[int] = None
    expediente_id: Optional[int] = None
    fecha: str = ""
    descripcion: str = ""
    estado: str = "pending"  # pending / completed / overdue


@dataclass
class Honorario:
    id: Optional[int] = None
    expediente_id: Optional[int] = None
    fecha: str = ""
    monto: float = 0.0
    moneda: str = "ARS"  # ARS / USD
    concepto: str = ""
    forma_pago: str = ""


@dataclass
class Gasto:
    id: Optional[int] = None
    expediente_id: Optional[int] = None
    fecha: str = ""
    monto: float = 0.0
    moneda: str = "ARS"  # ARS / USD
    descripcion: str = ""


@dataclass
class ArchivoAdjunto:
    id: Optional[int] = None
    expediente_id: Optional[int] = None
    nombre_archivo: str = ""
    ruta: str = ""
    fecha: str = ""
    descripcion: str = ""
