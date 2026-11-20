"""app/agent/relax.py — 재계획 완화 사다리 R1 → R2 → R3 (사용자 제약은 바꾸지 않음)."""

from app.agent.relax import next_relaxation

Q = {"region": "대학로", "genre": "연극", "page": 1, "has_more": False,
     "region_relaxed": False, "genre_relaxed": False}


def test_r1_uses_pending_candidates_first():
    step = next_relaxation(Q, {}, pending=5)
    assert step["step"] == "R1" and step["query"]["page"] == 1


def test_r1_next_page_only_when_last_page_was_full():
    step = next_relaxation({**Q, "has_more": True}, {}, pending=0)
    assert step["step"] == "R1" and step["query"]["page"] == 2


def test_r2_widens_district_to_city_and_resets_page():
    step = next_relaxation({**Q, "page": 3}, {}, pending=0)
    assert step["step"] == "R2"
    assert step["query"]["region"] == "서울" and step["query"]["page"] == 1 and step["query"]["region_relaxed"]


def test_r3_switches_to_adjacent_genre_after_region():
    step = next_relaxation({**Q, "region": "서울", "region_relaxed": True}, {}, pending=0)
    assert step["step"] == "R3" and step["query"]["genre"] == "뮤지컬"


def test_strict_preferences_are_skipped():
    step = next_relaxation(Q, {"region_strict": True, "genre_strict": True}, pending=0)
    assert step is None


def test_city_level_region_skips_r2():
    step = next_relaxation({**Q, "region": "서울"}, {}, pending=0)
    assert step["step"] == "R3"


def test_exhausted_returns_none():
    assert next_relaxation({**Q, "region": "서울", "genre": "클래식"}, {}, pending=0) is None
