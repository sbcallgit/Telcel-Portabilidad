"""Tests unitarios del export CSV de KPIs."""

import csv

import pytest

from jobs import kpi_export


@pytest.mark.asyncio
async def test_export_to_csv_neutraliza_formula_injection(monkeypatch, tmp_path):
    async def fake_fetch(_query):
        return [{"nombre": "=cmd()", "mensajes_cliente": 1}]

    monkeypatch.setattr(kpi_export.db, "fetch", fake_fetch)
    filepath = tmp_path / "kpis.csv"

    await kpi_export.export_to_csv(str(filepath))

    with filepath.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    assert rows[0]["nombre"] == "'=cmd()"
