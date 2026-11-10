"""Explicit golden-set comparisons; no LLM-as-judge claims.

Gold IDs must be human-verified. Business-level BRD requirements are reported
separately from FR/NFR implementation requirements. Existing response keys are
preserved for backwards compatibility.
"""
from __future__ import annotations


def safe_ratio(a, b):
    return round(a / b, 4) if b else None


def _f1(precision, recall):
    return (round(2 * precision * recall / (precision + recall), 4)
            if precision is not None and recall is not None and precision + recall
            else 0.0)


def _category(requirement_id: str) -> str:
    """Classify IDs by convention, without claiming semantic verification."""
    rid = requirement_id.upper()
    if rid.startswith('NFR-'):
        return 'non_functional'
    if rid.startswith('FR-'):
        return 'functional'
    if rid.startswith('BRD-') or rid.startswith('BR-'):
        return 'business'
    return 'other'


def _comparison(predicted: set[str], expected: set[str]) -> dict:
    tp = len(predicted & expected)
    p = safe_ratio(tp, len(predicted))
    r = safe_ratio(tp, len(expected))
    return {
        'golden_count': len(expected),
        'predicted_count': len(predicted),
        'true_positive': tp,
        'precision': p,
        'recall': r,
        'f1': _f1(p, r),
        'missing_requirement_ids': sorted(expected - predicted),
        'unexpected_requirement_ids': sorted(predicted - expected),
    }


def _category_comparisons(predicted: set[str], expected: set[str]) -> dict:
    names = ('business', 'functional', 'non_functional', 'other')
    return {
        name: _comparison(
            {rid for rid in predicted if _category(rid) == name},
            {rid for rid in expected if _category(rid) == name},
        )
        for name in names
    }


def evaluate(backlog: dict, expected_requirement_ids: list[str], analysis: dict | None = None):
    expected = {str(rid).strip() for rid in expected_requirement_ids if str(rid).strip()}
    if not expected:
        raise ValueError('Non-empty human-labeled expected_requirement_ids required')

    stories = backlog.get('stories', [])
    predicted = set().union(*(set(s.get('source_requirement_ids', [])) for s in stories)) if stories else set()
    overall = _comparison(predicted, expected)
    ac = backlog.get('acceptance_criteria', [])
    with_ac = {a.get('story_key') for a in ac if (a.get('criterion_text') or '').strip()}
    findings = backlog.get('validation', {}).get('issues', [])
    blocking = [f for f in findings if str(f.get('severity', '')).lower() in ('high', 'critical')]
    quality = backlog.get('story_clearances', {})

    reqs = (analysis or {}).get('requirements', [])
    extracted = {r.get('temporary_id') for r in reqs if r.get('temporary_id')}
    statuses = (analysis or {}).get('validation', {}).get('requirements', [])
    evidence = {v.get('temporary_id'): v.get('evidence_status') for v in statuses}
    grounded = sum(evidence.get(r) == 'supported' for r in extracted)
    extraction = _comparison(extracted, expected)
    gwt = sum(all(w in (a.get('criterion_text') or '').lower() for w in ('given', 'when', 'then')) for a in ac)

    implementation_expected = {r for r in expected if _category(r) in ('functional', 'non_functional')}
    implementation_predicted = {r for r in predicted if _category(r) in ('functional', 'non_functional')}
    implementation = _comparison(implementation_predicted, implementation_expected)

    return {
        # Original keys: retain their original meanings.
        'extraction_id_precision': extraction['precision'],
        'extraction_id_recall': extraction['recall'],
        'extraction_id_f1': extraction['f1'],
        'source_supported_ratio': safe_ratio(grounded, len(extracted)),
        'given_when_then_syntax_ratio': safe_ratio(gwt, len(ac)),
        **overall,
        'story_count': len(stories),
        'acceptance_criteria_count': len(ac),
        'stories_with_criteria_ratio': safe_ratio(
            sum(s.get('story_key') in with_ac for s in stories), len(stories)),
        'reported_blocking_findings': len(blocking),
        'quality_cleared_stories': sum(v.get('status') == 'quality_cleared' for v in quality.values()),
        # Additional metrics. These are not substitutes for human review.
        'requirement_categories': _category_comparisons(predicted, expected),
        'extraction_categories': _category_comparisons(extracted, expected),
        'implementation_backlog_coverage': implementation,
        'classification_method': 'ID prefixes only: BRD-/BR-=business, FR-=functional, NFR-=non-functional; verify against source.',
        'limitations': (
            'ID coverage and syntax are proxy metrics, not semantic correctness. '
            'Human-labeled reviews required for evidence grounding, category accuracy and AC quality.'
        ),
    }
