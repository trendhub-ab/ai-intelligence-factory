import pytest

from publication_terminal import automatic_regeneration_decision


@pytest.mark.parametrize("state", ["already_delivered", "human_blocked", "invalid"])
def test_existing_article_terminal_states_block_automatic_regeneration(state):
    allowed, reason = automatic_regeneration_decision(
        "a" * 32,
        classifier=lambda _: state,
        delivery_configured=lambda: True,
    )
    assert allowed is False
    assert reason


def test_missing_delivery_authority_fails_closed():
    allowed, reason = automatic_regeneration_decision(
        "a" * 32,
        classifier=lambda _: "not_queued",
        delivery_configured=lambda: False,
    )
    assert allowed is False
    assert reason == "delivery_authority_unavailable"


def test_delivery_read_exception_fails_closed():
    def broken(_):
        raise RuntimeError("unavailable")

    allowed, reason = automatic_regeneration_decision(
        "a" * 32,
        classifier=broken,
        delivery_configured=lambda: True,
    )
    assert allowed is False
    assert reason == "delivery_state_unavailable"


@pytest.mark.parametrize("state", ["not_queued", "waiting"])
def test_prepublication_states_remain_recoverable(state):
    allowed, reason = automatic_regeneration_decision(
        "a" * 32,
        classifier=lambda _: state,
        delivery_configured=lambda: True,
    )
    assert allowed is True
    assert reason == state


def test_blank_delivery_state_fails_closed():
    allowed, reason = automatic_regeneration_decision(
        "a" * 32,
        classifier=lambda _: "",
        delivery_configured=lambda: True,
    )
    assert allowed is False
    assert reason == "delivery_state_invalid"
