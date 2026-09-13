import run387_reader_repair_queue as r387


def test_queue_contains_exactly_32_reader_candidates():
    queue = r387.build_queue()
    assert len(queue) == 32


def test_queue_is_sorted_by_non_decreasing_complexity():
    queue = r387.build_queue()
    assert [x.complexity for x in queue] == sorted(x.complexity for x in queue)


def test_all_queue_labels_are_repairable_reader_labels():
    queue = r387.build_queue()
    for item in queue:
        assert item.labels
        assert set(item.labels) <= r387.r386.REPAIRABLE_READER_LABELS


def test_tier_a_is_narrower_than_tier_b_or_c():
    queue = r387.build_queue()
    for item in queue:
        if item.tier == "A":
            assert item.complexity <= 2
        elif item.tier == "B":
            assert 3 <= item.complexity <= 4
        else:
            assert item.complexity >= 5
