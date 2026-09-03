from dataclasses import dataclass

from personal_assets.action_memory import ActionMemorySource, action_memory_for_journey
from requirements.trusted_reuse import TrustedReuseDecisionCode, TrustedReuseReasonCode

from .trusted_reuse import evaluate_trusted_reuse


@dataclass(frozen=True)
class TrustedReuseOption:
    candidate: object
    decision: object
    message: str
    can_apply: bool


_REASON_MESSAGES = {
    TrustedReuseReasonCode.NO_POLICY: "Makolo ne peut pas vérifier automatiquement que cet élément répond à cette condition.",
    TrustedReuseReasonCode.SOURCE_NOT_ALLOWED: "Cette source n’est pas acceptée pour cette condition.",
    TrustedReuseReasonCode.SUBJECT_MISMATCH: "Cet élément ne concerne pas le bénéficiaire de cette démarche.",
    TrustedReuseReasonCode.KIND_MISMATCH: "Ce type de document n’est pas accepté pour cette condition.",
    TrustedReuseReasonCode.EXPIRED: "Ce document est expiré.",
    TrustedReuseReasonCode.FRESHNESS_UNKNOWN: "Makolo ne dispose pas des faits nécessaires pour confirmer la fraîcheur de cet élément.",
    TrustedReuseReasonCode.TOO_OLD: "Cet élément est trop ancien selon les conditions de cette demande.",
    TrustedReuseReasonCode.PROOF_REVOKED: "Cette attestation a été révoquée.",
    TrustedReuseReasonCode.SENSITIVITY_NOT_ALLOWED: "Cette condition ne permet pas la réutilisation automatique de cet élément sensible.",
    TrustedReuseReasonCode.RESTRICTED_NOT_ALLOWED: "Cette condition ne permet pas la réutilisation de cet élément à accès restreint.",
    TrustedReuseReasonCode.HUMAN_REVIEW_REQUIRED: "Une validation humaine reste nécessaire après l’envoi.",
}


def _message(decision):
    if decision.decision == TrustedReuseDecisionCode.ACCEPTABLE_WITH_CONFIRMATION:
        return "Cet élément correspond aux conditions déclarées. Votre confirmation est requise avant de le joindre à cette démarche."
    if decision.decision == TrustedReuseDecisionCode.ACCEPTABLE:
        if TrustedReuseReasonCode.PROOF_TYPE_MATCH in decision.reasons:
            return "Makolo reconnaît cette attestation pour cette condition. Une validation normale reste nécessaire."
        return "Cet élément correspond aux conditions déclarées de cette demande."
    for reason in decision.reasons:
        if reason in _REASON_MESSAGES:
            return _REASON_MESSAGES[reason]
    if decision.decision == TrustedReuseDecisionCode.UNKNOWN:
        return "Makolo ne peut pas conclure automatiquement pour cette condition."
    return "Cet élément ne peut pas être réutilisé automatiquement dans ce contexte."


def trusted_reuse_options_for_assessment(*, assessment, actor, observed_at=None):
    journey = assessment.context.journey
    candidates = action_memory_for_journey(actor=actor, journey=journey, observed_at=observed_at)
    options = []
    for candidate in candidates:
        decision = evaluate_trusted_reuse(
            assessment=assessment,
            candidate=candidate,
            actor=actor,
            observed_at=observed_at,
        )
        can_apply = bool(
            decision.acceptable
            and candidate.source != ActionMemorySource.PROOF
        )
        options.append(
            TrustedReuseOption(
                candidate=candidate,
                decision=decision,
                message=_message(decision),
                can_apply=can_apply,
            )
        )
    return tuple(options)
