import stale_ready_retirement as retire


def test_classify_only_stale_unrecoverable_as_retirable():
    assert retire.classify(stale=True,current=False,published=False,recoverable=False)=="retirable"
    assert retire.classify(stale=False,current=True,published=False,recoverable=False)=="protected_current"
    assert retire.classify(stale=True,current=False,published=True,recoverable=False)=="protected_published"
    assert retire.classify(stale=True,current=False,published=False,recoverable=True)=="recoverable"


def test_retirement_patch_demotes_without_archiving_page():
    patch=retire.retirement_patch()
    assert patch["archived"] is False
    assert patch["properties"]["記事状態"]["select"]["name"]=="Not Planned"
    assert patch["properties"]["コンテンツ状態"]["select"]["name"]=="Deep Dive"
