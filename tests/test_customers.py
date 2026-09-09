from pipeline.customers import MONTHS, generate_customers


def test_same_seed_gives_identical_customers():
    assert generate_customers(50, seed=1) == generate_customers(50, seed=1)


def test_different_seed_gives_different_customers():
    assert generate_customers(50, seed=1) != generate_customers(50, seed=2)


def test_events_stay_inside_the_12_month_window():
    for p in generate_customers(500):
        assert 0 <= p.signup_month < MONTHS
        if p.event:
            assert p.signup_month < p.event_month < MONTHS
        else:
            assert p.event_month is None


def test_upgrade_and_downgrade_only_from_valid_plans():
    for p in generate_customers(500):
        if p.event == "upgrade":
            assert p.plan_id in ("basic", "pro")
        if p.event == "downgrade":
            assert p.plan_id in ("pro", "enterprise")


def test_distributions_roughly_match_the_dials():
    profiles = generate_customers(1000)
    basic = sum(p.plan_id == "basic" for p in profiles) / len(profiles)
    failing = sum(p.failing_card for p in profiles) / len(profiles)
    assert 0.40 < basic < 0.60
    assert 0.04 < failing < 0.12

def test_signup_from_limits_how_far_back_customers_sign_up():
    profiles = generate_customers(50, seed=1, signup_from=11)

    assert {p.signup_month for p in profiles} == {11}
    assert all(p.event is None for p in profiles)
