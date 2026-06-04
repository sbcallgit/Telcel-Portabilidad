"""Carga la tabla de LADAs para Región 4 (NL, Coahuila, Tamaulipas, SLP).

Fuente: Plan Nacional de Numeración de México (IFT) + CACs documentados en CLAUDE.md.

Nota sobre LADA de 2 dígitos (Monterrey = 81):
  El sistema de 10 dígitos de México usa LADA 81 para toda el área metropolitana
  de Monterrey. En la BD guardamos los 3 primeros dígitos del número (810-819)
  para facilitar la consulta con numero[:3].
"""

import logging

from integrations.postgres import client as db

logger = logging.getLogger(__name__)

# ── NUEVO LEÓN ────────────────────────────────────────────────────────────────
_NL_METRO = [  # Monterrey y zona metropolitana (LADA 81)
    ("810", "Monterrey", "Nuevo León"),
    ("811", "Monterrey", "Nuevo León"),
    ("812", "Monterrey", "Nuevo León"),
    ("813", "Monterrey", "Nuevo León"),
    ("814", "Monterrey", "Nuevo León"),
    ("815", "Monterrey", "Nuevo León"),
    ("816", "Monterrey", "Nuevo León"),
    ("817", "Monterrey", "Nuevo León"),
    ("818", "Monterrey", "Nuevo León"),
    ("819", "Monterrey", "Nuevo León"),
]

_NL_INTERIOR = [
    ("821", "Linares",              "Nuevo León"),
    ("822", "Cadereyta Jiménez",    "Nuevo León"),
    ("823", "Galeana",              "Nuevo León"),
    ("824", "Cadereyta Jiménez",    "Nuevo León"),
    ("825", "Cerralvo",             "Nuevo León"),
    ("826", "Salinas Victoria",     "Nuevo León"),
    ("827", "Sabinas Hidalgo",      "Nuevo León"),
    ("828", "Montemorelos",         "Nuevo León"),
    ("829", "General Escobedo",     "Nuevo León"),
]

# ── COAHUILA ──────────────────────────────────────────────────────────────────
_COAH = [
    ("844", "Saltillo",        "Coahuila"),
    ("845", "Saltillo",        "Coahuila"),
    ("846", "Ramos Arizpe",    "Coahuila"),
    ("861", "Sabinas",         "Coahuila"),
    ("862", "Muzquiz",         "Coahuila"),
    ("864", "Nava",            "Coahuila"),
    ("866", "Monclova",        "Coahuila"),
    ("877", "Acuña",           "Coahuila"),
    ("878", "Piedras Negras",  "Coahuila"),
]

# ── TAMAULIPAS ────────────────────────────────────────────────────────────────
_TAMPS = [
    ("831", "Mante",           "Tamaulipas"),
    ("832", "Ciudad Madero",   "Tamaulipas"),
    ("833", "Tampico",         "Tamaulipas"),
    ("834", "Ciudad Victoria", "Tamaulipas"),
    ("835", "Reynosa",         "Tamaulipas"),
    ("836", "Río Bravo",       "Tamaulipas"),
    ("867", "Nuevo Laredo",    "Tamaulipas"),
    ("868", "Matamoros",       "Tamaulipas"),
    ("869", "Matamoros",       "Tamaulipas"),
    ("899", "Reynosa",         "Tamaulipas"),
]

# ── SAN LUIS POTOSÍ (zona Cd. Valles) ────────────────────────────────────────
_SLP = [
    ("481", "Ciudad Valles",   "San Luis Potosí"),
    ("482", "Tamuín",          "San Luis Potosí"),
    ("483", "Ciudad del Maíz", "San Luis Potosí"),
]

# ── NO pertenecen a R4 (habilitada=False) ─────────────────────────────────────
_FUERA_R4 = [
    ("871", "Torreón",         "Coahuila"),   # R5 (Torreón-Durango)
    ("872", "Gómez Palacio",   "Durango"),    # R5
    ("55",  "Ciudad de México","CDMX"),       # No R4
    ("33",  "Guadalajara",     "Jalisco"),    # No R4
]


def _build_rows() -> list[tuple]:
    rows: list[tuple] = []
    for lada, ciudad, estado in (_NL_METRO + _NL_INTERIOR + _COAH + _TAMPS + _SLP):
        rows.append((lada, ciudad, estado, True))
    for lada, ciudad, estado in _FUERA_R4:
        rows.append((lada, ciudad, estado, False))
    return rows


LADAS_R4 = _build_rows()


async def load() -> None:
    rows = _build_rows()
    logger.info("loading_ladas", extra={"count": len(rows)})
    for lada, ciudad, estado, habilitada in rows:
        await db.execute(
            """
            INSERT INTO ladas (lada, ciudad, estado, habilitada)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (lada) DO UPDATE SET
                ciudad     = EXCLUDED.ciudad,
                estado     = EXCLUDED.estado,
                habilitada = EXCLUDED.habilitada
            """,
            lada,
            ciudad,
            estado,
            habilitada,
        )
    logger.info("ladas_loaded", extra={"total": len(rows)})
