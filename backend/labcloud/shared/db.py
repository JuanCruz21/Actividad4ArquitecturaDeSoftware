"""Persistencia SQLite con el patrón *database per service*.

Cada servicio posee su propia base de datos y ningún servicio consulta las
tablas de otro: la información se intercambia únicamente por REST o por eventos.
Esta separación es la que permite desplegar y escalar los servicios de forma
independiente (RNF02, RNF04).

SQLite se abre en modo WAL y con ``check_same_thread=False`` porque el Servicio
de Solicitudes escribe desde varios hilos del pool de procesamiento.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from labcloud.shared.config import asegurar_directorio_datos, servicio


class Base(DeclarativeBase):
    """Clase base declarativa para los modelos de todos los servicios."""


class Database:
    """Envoltorio del motor y la fábrica de sesiones de un servicio."""

    def __init__(self, service_id: str) -> None:
        self.service_id = service_id
        asegurar_directorio_datos()
        self.ruta = servicio(service_id).db_path
        self.engine: Engine = create_engine(
            f"sqlite:///{self.ruta}",
            connect_args={"check_same_thread": False, "timeout": 30},
            pool_pre_ping=True,
            future=True,
        )
        _activar_pragmas(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False, future=True
        )

    def crear_tablas(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def sesion(self) -> Iterator[Session]:
        """Sesión transaccional: confirma al salir y revierte ante cualquier error."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dependencia(self) -> Iterator[Session]:
        """Dependencia de FastAPI (``Depends``) para inyectar la sesión."""
        with self.sesion() as session:
            yield session


def _activar_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        # WAL permite lecturas concurrentes mientras un hilo escribe.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
