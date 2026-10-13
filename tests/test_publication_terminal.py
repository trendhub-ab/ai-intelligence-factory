import pytest

from publication_terminal import automatic_regeneration_decision


@pytest.mark.parametrize('state', ['already_delivered', 'human_blocked', 'invalid', 'unknown', ''])
def test_terminal_states_block(state):
    allowed, reason = automatic_regeneration_decision('a'*32, classifier=lambda _: state, delivery_configured=lambda: True)
    assert allowed is False
    assert reason


def test_missing_authority_blocks():
    assert automatic_regeneration_decision('a'*32, classifier=lambda _: 'not_queued', delivery_configured=lambda: False) == (False, 'delivery_authority_unavailable')


def test_classifier_failure_blocks():
    def broken(_):
        raise RuntimeError('unavailable')
    assert automatic_regeneration_decision('a'*32, classifier=broken, delivery_configured=lambda: True)[0] is False


@pytest.mark.parametrize('state', ['not_queued', 'waiting'])
def test_prepublication_allowed(state):
    assert automatic_regeneration_decision('a'*32, classifier=lambda _: state, delivery_configured=lambda: True)[0] is True


def test_missing_identity_blocks():
    assert automatic_regeneration_decision('', classifier=lambda _: 'not_queued', delivery_configured=lambda: True)[0] is False
