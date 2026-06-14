"""Unit tests deterministas para helpers puros de seguimientos."""

from datetime import datetime

import pytz
from freezegun import freeze_time

from jobs.seguimientos import _en_ventana


def _now_utc() -> datetime:
    return datetime.now(tz=pytz.utc)


def test_en_ventana_lunes_9am_monterrey():
    with freeze_time("2026-06-08 15:00:00+00:00"):
        assert _en_ventana(_now_utc())


def test_en_ventana_sabado_20pm_monterrey():
    with freeze_time("2026-06-14 02:00:00+00:00"):
        assert _en_ventana(_now_utc())


def test_en_ventana_rechaza_domingo():
    with freeze_time("2026-06-07 18:00:00+00:00"):
        assert not _en_ventana(_now_utc())


def test_en_ventana_rechaza_antes_de_9am():
    with freeze_time("2026-06-08 14:59:00+00:00"):
        assert not _en_ventana(_now_utc())


def test_en_ventana_rechaza_21pm_en_punto():
    with freeze_time("2026-06-09 03:00:00+00:00"):
        assert not _en_ventana(_now_utc())

