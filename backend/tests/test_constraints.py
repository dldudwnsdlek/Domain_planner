"""app/agent/constraints.py — 제약 판정 순수 함수 (PLAN 5.4 계산 예시 기반)."""

from app.agent.constraints import (
    Conditions,
    count_fail_reasons,
    evaluate_performance,
    latest_start,
    plans_overlap,
    rank_passed,
    suggest_adjustments,
)

SAT = "2026-11-21"
S1 = Conditions(date=SAT, start_after="18:00", home_by="23:30", budget_max=50000)


def perf(pid="A", times=("15:00", "19:00"), runtime=100, price=45000, issues=(), day="sat",
         period=("2026-10-01", "2026-12-31")):
    schedule = {k: [] for k in ("mon", "tue", "wed", "thu", "fri", "sat", "sun", "holiday")}
    schedule[day] = list(times)
    return {"performance_id": pid, "title": f"연극 {pid}", "period_from": period[0], "period_to": period[1],
            "runtime_min": runtime, "schedule": schedule, "min_price": price, "issues": list(issues)}


# ── PLAN 5.4 계산 예시 ────────────────────────────────────────────────────────


def test_example_a_passes_on_19_00_with_arrival_time():
    ev = evaluate_performance(perf("A"), S1, transit_min=48)
    assert ev.verdict == "PASS"
    passed = [s for s in ev.showtimes if s.verdict == "PASS"]
    assert [(s.start, s.end, s.home_arrival) for s in passed] == [("19:00", "20:40", "21:38")]
    early = next(s for s in ev.showtimes if s.start == "15:00")
    assert early.verdict == "FAIL" and "START_TOO_EARLY" in early.reasons


def test_example_b_missing_runtime_is_unknown_not_fail():
    ev = evaluate_performance(perf("B", times=("19:30",), runtime=None, issues=("NO_RUNTIME",)), S1, transit_min=48)
    assert ev.verdict == "UNKNOWN"
    assert "NO_RUNTIME" in ev.reasons


def test_example_c_over_budget_fails():
    ev = evaluate_performance(perf("C", times=("20:00",), runtime=150, price=55000), S1, transit_min=48)
    assert ev.verdict == "FAIL"
    assert ev.reasons == ["OVER_BUDGET"]
    assert ev.showtimes[0].home_arrival == "23:28"


def test_example_d_unparsed_schedule_gives_back_calculated_latest_start():
    ev = evaluate_performance(perf("D", times=(), issues=("SCHEDULE_UNPARSED",)), S1, transit_min=48)
    assert ev.verdict == "UNKNOWN"
    assert ev.latest_start == "20:52"  # 23:30 − 48 − 10 − 100


# ── 개별 규칙 ─────────────────────────────────────────────────────────────────


def test_boundary_equal_passes():
    cond = Conditions(date=SAT, end_by="20:40")
    assert evaluate_performance(perf(times=("19:00",)), cond).verdict == "PASS"


def test_outside_period_fails():
    ev = evaluate_performance(perf(period=("2026-12-01", "2026-12-31")), S1, transit_min=48)
    assert ev.verdict == "FAIL" and ev.reasons == ["OUT_OF_PERIOD"]


def test_no_show_on_that_day_fails_when_schedule_fully_parsed():
    ev = evaluate_performance(perf(day="fri"), S1, transit_min=48)
    assert ev.verdict == "FAIL" and ev.reasons == ["NO_SHOW_ON_DAY"]


def test_runtime_not_needed_without_end_or_home_constraint():
    cond = Conditions(date=SAT, start_after="18:00", budget_max=50000)
    assert evaluate_performance(perf(runtime=None, issues=("NO_RUNTIME",)), cond).verdict == "PASS"


def test_missing_price_is_unknown_only_when_budget_given():
    no_price = perf(price=None, issues=("PRICE_UNPARSED",))
    assert evaluate_performance(no_price, S1, transit_min=48).verdict == "UNKNOWN"
    assert evaluate_performance(no_price, Conditions(date=SAT)).verdict == "PASS"


def test_home_check_skipped_in_first_stage():
    """2단계 판정: 1차에서는 이동시간 없이 C6를 건너뛴다."""
    ev = evaluate_performance(perf(), S1, transit_min=None, skip_home=True)
    assert ev.verdict == "PASS"


def test_missing_transit_in_second_stage_is_unknown():
    ev = evaluate_performance(perf(), S1, transit_min=None)
    assert ev.verdict == "UNKNOWN" and "NO_TRANSIT" in ev.reasons


def test_home_by_after_midnight_is_next_day():
    cond = Conditions(date=SAT, home_by="00:30")
    ev = evaluate_performance(perf(times=("21:30",), runtime=100), cond, transit_min=48)
    # 21:30 + 100 + 10 + 48 = 00:08 (다음 날) ≤ 00:30
    assert ev.verdict == "PASS"
    assert ev.showtimes[0].home_arrival == "00:08"


def test_end_by_fails():
    cond = Conditions(date=SAT, start_after="19:00", end_by="21:00")
    ev = evaluate_performance(perf(times=("19:30",), runtime=100), cond)
    assert ev.verdict == "FAIL" and ev.reasons == ["END_TOO_LATE"]


# ── 역산 · 정렬 · 통계 · 조정안 ────────────────────────────────────────────────


def test_latest_start_uses_tightest_limit_and_none_when_unknown():
    assert latest_start(Conditions(date=SAT, end_by="22:00", home_by="23:30"), 100, 48) == "20:20"
    assert latest_start(Conditions(date=SAT, home_by="23:30"), None, 48) is None
    assert latest_start(Conditions(date=SAT), 100, 48) is None


def test_rank_by_closeness_to_start_after_then_price_top5():
    evs = [evaluate_performance(perf(str(i), times=(t,), price=p), Conditions(date=SAT, start_after="18:00"))
           for i, (t, p) in enumerate([("20:00", 10000), ("18:30", 40000), ("18:30", 30000),
                                        ("19:00", 1), ("21:00", 1), ("22:00", 1)])]
    ranked = rank_passed(evs)
    assert [e.performance_id for e in ranked] == ["2", "1", "3", "0", "4"]


def test_fail_reason_stats_one_reason_per_performance():
    evs = [
        evaluate_performance(perf("1", times=("20:00",), runtime=150, price=55000), S1, transit_min=48),
        evaluate_performance(perf("2", times=("19:30",), runtime=None, issues=("NO_RUNTIME",)), S1, transit_min=48),
        evaluate_performance(perf("3", day="fri"), S1, transit_min=48),
    ]
    assert count_fail_reasons(evs) == {"OVER_BUDGET": 1, "NO_RUNTIME": 1, "NO_SHOW_ON_DAY": 1}


def test_suggestions_use_only_single_reason_failures():
    evs = [
        evaluate_performance(perf("C", times=("20:00",), runtime=150, price=55000), S1, transit_min=48),
        evaluate_performance(perf("E", times=("20:00",), runtime=150, price=70000), S1, transit_min=48),
        evaluate_performance(perf("F", times=("22:00",), runtime=100, price=80000), S1, transit_min=48),  # 귀가+예산 동시
    ]
    sugg = {s["field"]: s for s in suggest_adjustments(evs)}
    assert sugg["budget_max"]["value"] == 55000 and sugg["budget_max"]["count"] == 1
    assert "home_by" not in sugg  # F는 예산도 넘으므로 귀가 하나만 바꿔서는 가능해지지 않음


def test_suggestion_for_end_by():
    cond = Conditions(date=SAT, end_by="22:00")
    evs = [evaluate_performance(perf("G", times=("20:00",), runtime=160), cond),
           evaluate_performance(perf("H", times=("20:30",), runtime=130), cond)]
    sugg = {s["field"]: s for s in suggest_adjustments(evs)}
    assert sugg["end_by"]["value"] == "22:40" and sugg["end_by"]["count"] == 2


# ── 겹침 [start, end) ─────────────────────────────────────────────────────────


def plan(start, end, date=SAT):
    return {"date": date, "start_time": start, "end_time": end}


def test_overlap_half_open_interval():
    assert plans_overlap(plan("19:00", "21:00"), plan("20:00", "22:30"))
    assert not plans_overlap(plan("19:00", "21:00"), plan("21:00", "22:00"))
    assert not plans_overlap(plan("19:00", "21:00"), plan("20:00", "22:00", date="2026-11-22"))


def test_overlap_with_missing_end_uses_start_inside_other():
    assert plans_overlap(plan("20:00", None), plan("19:00", "21:00"))
    assert not plans_overlap(plan("21:00", None), plan("19:00", "21:00"))


def test_overlap_across_midnight():
    assert plans_overlap(plan("22:00", "00:30"), plan("23:00", "23:50"))
