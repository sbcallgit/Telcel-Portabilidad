"""Unit tests deterministas para helpers puros de objeciones."""

from agents.portabilidad.nodes import objeciones


def test_word_match_compra_respeta_fronteras_de_palabra():
    assert objeciones._word_match("sí, acepto", objeciones._BUY_WORDS)
    assert objeciones._word_match("me convenciste", objeciones._BUY_WORDS)
    assert not objeciones._word_match("así no", objeciones._BUY_WORDS)


def test_word_match_compra_no_cierra_por_ok_aislado():
    assert not objeciones._word_match("ok pero caro", objeciones._BUY_WORDS)
    assert objeciones._word_match("ok, acepto", objeciones._BUY_WORDS)
