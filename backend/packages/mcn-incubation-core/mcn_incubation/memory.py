"""Selective, project-local recall for reviewed incubation cases."""

from __future__ import annotations

from dataclasses import dataclass, field

from mcn_incubation.domain import CaseEpisode, CaseRecall, CaseStatus, SubjectKind


@dataclass(frozen=True, slots=True)
class CaseQuery:
    owner_id: str
    project_id: str
    subject_kind: SubjectKind | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    platform: str | None = None
    target_claims: tuple[str, ...] = field(default_factory=tuple)


def _overlap(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    return len({value.casefold() for value in left} & {value.casefold() for value in right})


class CaseMemory:
    """Recall cases with scope, status, and counterevidence controls."""

    def __init__(
        self,
        cases: tuple[CaseEpisode, ...],
        *,
        allow_cross_project: bool = False,
    ) -> None:
        if len({case.case_episode_id for case in cases}) != len(cases):
            raise ValueError("case episode ids must be unique")
        self._cases = cases
        self._allow_cross_project = allow_cross_project

    def recall(
        self,
        query: CaseQuery,
        *,
        support_limit: int = 3,
        counter_limit: int = 2,
    ) -> CaseRecall:
        if support_limit < 0 or counter_limit < 0:
            raise ValueError("recall limits cannot be negative")
        supporting: list[tuple[int, str, CaseEpisode]] = []
        counterexamples: list[tuple[int, str, CaseEpisode]] = []
        for case in self._cases:
            if not self._in_scope(case, query=query):
                continue
            if case.status in {CaseStatus.RETIRED, CaseStatus.SUPERSEDED}:
                continue
            score = self._score(case, query=query)
            if query.target_claims:
                supports = _overlap(case.supports_claims, query.target_claims) > 0
                contradicts = _overlap(case.contradicts_claims, query.target_claims) > 0
            else:
                supports = case.status is CaseStatus.ACTIVE
                contradicts = case.status is CaseStatus.CONTESTED
            if supports and case.status is CaseStatus.ACTIVE:
                supporting.append((score, case.case_episode_id, case))
            if contradicts or case.status is CaseStatus.CONTESTED:
                counterexamples.append((score, case.case_episode_id, case))
        supporting.sort(key=lambda item: (-item[0], item[1]))
        counterexamples.sort(key=lambda item: (-item[0], item[1]))
        return CaseRecall(
            supporting=tuple(item[2] for item in supporting[:support_limit]),
            counterexamples=tuple(item[2] for item in counterexamples[:counter_limit]),
        )

    def _in_scope(self, case: CaseEpisode, *, query: CaseQuery) -> bool:
        if case.owner_id != query.owner_id:
            return False
        if case.project_id == query.project_id:
            return True
        return self._allow_cross_project and case.cross_project_eligible

    @staticmethod
    def _score(case: CaseEpisode, *, query: CaseQuery) -> int:
        score = 0
        if query.subject_kind is not None and case.subject_kind is query.subject_kind:
            score += 5
        score += 2 * _overlap(case.tags, query.tags)
        if query.platform is not None and query.platform in case.platforms:
            score += 3
        score += 4 * _overlap(case.supports_claims, query.target_claims)
        score += 4 * _overlap(case.contradicts_claims, query.target_claims)
        return score


__all__ = ["CaseMemory", "CaseQuery"]
