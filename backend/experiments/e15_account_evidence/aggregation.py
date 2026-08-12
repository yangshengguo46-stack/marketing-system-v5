from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from .contracts import (
    AccountEvidencePack,
    AggregatedSignal,
    EpistemicStatus,
    VideoEvidenceRecord,
)


def aggregate_account_records(
    records: tuple[VideoEvidenceRecord, ...],
    *,
    generated_at: datetime | None = None,
) -> AccountEvidencePack:
    if not records:
        raise ValueError("account aggregation requires at least one video record")
    account_refs = {record.account_ref for record in records}
    if len(account_refs) != 1:
        raise ValueError("all video records must share the same account_ref")
    source_rights = {record.source_rights for record in records}
    rights_refs = {record.rights_ref for record in records}
    if len(source_rights) != 1 or len(rights_refs) != 1:
        raise ValueError("all video records must share the same source rights")
    post_ids = [record.post_id for record in records]
    if len(set(post_ids)) != len(post_ids):
        raise ValueError("account aggregation requires unique post ids")

    grouped: dict[
        tuple[object, str, EpistemicStatus],
        list[tuple[str, tuple[str, ...]]],
    ] = defaultdict(list)
    for record in records:
        seen_in_post: set[tuple[object, str, EpistemicStatus]] = set()
        for signal in record.signals:
            if signal.epistemic_status is EpistemicStatus.UNKNOWN:
                continue
            key = (signal.dimension, signal.label, signal.epistemic_status)
            if key in seen_in_post:
                continue
            seen_in_post.add(key)
            grouped[key].append((record.post_id, signal.evidence_refs))

    aggregates: list[AggregatedSignal] = []
    all_posts = set(post_ids)
    for (dimension, label, epistemic_status), observations in sorted(
        grouped.items(),
        key=lambda item: (str(item[0][0]), item[0][1], item[0][2].value),
    ):
        supporting = tuple(sorted(post_id for post_id, _ in observations))
        supporting_set = set(supporting)
        evidence_refs = tuple(sorted({ref for _, refs in observations for ref in refs}))
        count = len(supporting)
        sample_size = len(records)
        aggregates.append(
            AggregatedSignal(
                dimension=dimension,
                label=label,
                epistemic_status=epistemic_status,
                match_basis="exact_dimension_label_and_status",
                supporting_post_ids=supporting,
                sample_post_ids_without_exact_match=tuple(sorted(all_posts.difference(supporting_set))),
                support_count=count,
                sample_size=sample_size,
                sample_support_ratio=count / sample_size,
                support_status="repeated_support" if count >= 2 else "single_support",
                evidence_refs=evidence_refs,
            )
        )

    limitations = list(dict.fromkeys(limitation for record in records for limitation in record.media.limitations))
    if len(records) == 1:
        limitations.append("Only one video was sampled; account-level repetition is not established.")
    limitations.append("Aggregate support uses exact dimension, label, and epistemic-status matching; semantically similar labels are not merged.")
    return AccountEvidencePack(
        account_ref=next(iter(account_refs)),
        source_rights=next(iter(source_rights)),
        rights_ref=next(iter(rights_refs)),
        generated_at=generated_at or datetime.now(UTC),
        videos=records,
        aggregates=tuple(aggregates),
        limitations=tuple(limitations),
    )


__all__ = ["aggregate_account_records"]
