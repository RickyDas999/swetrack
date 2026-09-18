from __future__ import annotations

import pytest

from swetrack.domains.learning.services import (
    create_activity,
    get_interview_readiness_summary,
    list_mastery,
    record_attempt,
    record_system_design_attempt,
)
from swetrack.domains.skills.taxonomy import TAXONOMY

_ALL_CATEGORIES = {skill.category for skill in TAXONOMY}


def test_list_mastery_includes_every_taxonomy_skill_defaulted_when_unpracticed(db_session):
    summaries = list_mastery(db_session)

    assert len(summaries) == len(TAXONOMY)
    assert all(summary.has_history is False for summary in summaries)
    assert all(summary.mastery == pytest.approx(0.3) for summary in summaries)  # default BKT p_init


def test_list_mastery_sorts_weakest_first_and_marks_real_history(db_session):
    activity = create_activity(
        db_session, slug="python-review", title="Python Review", activity_type="concept_review", skill_ids=["python"]
    )
    for _ in range(10):
        record_attempt(db_session, activity_id=activity.id, success=True)

    summaries = list_mastery(db_session)

    python_summary = next(s for s in summaries if s.skill_id == "python")
    assert python_summary.has_history is True
    assert python_summary.mastery > 0.3
    # Every other skill stays at the 0.3 default, so the one practiced skill
    # (now strictly the highest mastery) sorts last in a weakest-first list.
    assert summaries[-1].skill_id == "python"
    assert [s.mastery for s in summaries] == sorted(s.mastery for s in summaries)


def test_list_mastery_top_k_and_category_filters_are_caller_side(db_session):
    summaries = list_mastery(db_session)
    algorithms_only = [s for s in summaries if s.category == "algorithms"]

    assert algorithms_only
    assert all(s.category == "algorithms" for s in algorithms_only)


def test_get_interview_readiness_summary_defaults_every_category_to_p_init(db_session):
    summary = get_interview_readiness_summary(db_session)

    assert summary.coding == pytest.approx(0.3)
    assert summary.system_design == pytest.approx(0.3)
    assert set(summary.by_category.keys()) == _ALL_CATEGORIES
    assert all(value == pytest.approx(0.3) for value in summary.by_category.values())


def test_get_interview_readiness_summary_reflects_practiced_coding_skill_only(db_session):
    activity = create_activity(
        db_session, slug="graph-practice", title="Graph Practice", activity_type="concept_review", skill_ids=["graphs"]
    )
    for _ in range(10):
        record_attempt(db_session, activity_id=activity.id, success=True)

    summary = get_interview_readiness_summary(db_session)

    assert summary.coding > 0.3
    assert summary.system_design == pytest.approx(0.3)


def test_get_interview_readiness_summary_reflects_practiced_system_design_skill_only(db_session):
    activity = create_activity(
        db_session,
        slug="rate-limiter-design",
        title="Design a Rate Limiter",
        activity_type="system_design",
        skill_ids=["requirements"],
    )
    record_system_design_attempt(db_session, activity_id=activity.id, scores={"requirements": 0.9})

    summary = get_interview_readiness_summary(db_session)

    assert summary.system_design > 0.3
    assert summary.coding == pytest.approx(0.3)
