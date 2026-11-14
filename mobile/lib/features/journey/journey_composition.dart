import 'journey_selector.dart';

/// Present useful human checks only; technical engine checks keep their
/// server-owned truth but do not become celebratory UI counters.
bool journeyUsefulReadySummary(String value) {
  final normalized = value.toLowerCase().trim();
  return normalized.isNotEmpty &&
      !normalized.startsWith("l'état de la démarche permet") &&
      !normalized.startsWith('aucun obstacle actif') &&
      !normalized.startsWith("l’occurrence est exploitable") &&
      !normalized.startsWith("l'occurrence est exploitable");
}

/// The same Journey N3 page adapts to owner facts; no new business status.
enum JourneySituation { completed, blocked, choices, action, waiting, calm }

class JourneyComposition {
  const JourneyComposition({
    required this.situation,
    required this.interventions,
    required this.hasBranches,
    required this.hasPreparation,
    required this.hasDocuments,
    required this.hasEngagements,
  });

  final JourneySituation situation;
  final List<JourneyReadinessItem> interventions;
  final bool hasBranches;
  final bool hasPreparation;
  final bool hasDocuments;
  final bool hasEngagements;

  bool get requiresAttention =>
      situation == JourneySituation.action ||
      situation == JourneySituation.choices ||
      situation == JourneySituation.blocked;

  static JourneyComposition from(
    JourneyDetailPresentation p, {
    bool resourcesKnown = false,
    int resourcesCount = 0,
  }) {
    // An intervention repeating the objective without an action is not a
    // useful separate card. The owner check itself is still kept intact.
    final interventions = p.actorInterventions
        .where((item) {
          final repeatsTitle =
              item.summary.trim().toLowerCase() == p.title.trim().toLowerCase();
          return !repeatsTitle || item.nextLink != null;
        })
        .toList(growable: false);
    // The owner link, not a check key, identifies a distinct next move.
    // Different readiness checks may point to the same authorized depth.
    final actionableLinks = <String>{
      for (final item in p.actorInterventions)
        if (item.nextLink != null && item.nextLink!.trim().isNotEmpty)
          item.nextLink!.trim(),
      if (p.nextActionLink != null &&
          p.nextActionLink!.trim().isNotEmpty)
        p.nextActionLink!.trim(),
    };
    final situation = p.isTerminal
        ? JourneySituation.completed
        : p.blockers.isNotEmpty || p.rejectedRequests > 0
        ? JourneySituation.blocked
        : actionableLinks.length > 1
        ? JourneySituation.choices
        : actionableLinks.isNotEmpty ||
              p.canRespondInvitation ||
              interventions.isNotEmpty
        ? JourneySituation.action
        : p.waiting.isNotEmpty || p.pendingRequests > 0
        ? JourneySituation.waiting
        : JourneySituation.calm;

    // Branching is represented by the real dependency graph, not by a
    // fabricated evenly spaced progress bar.
    final dependents = <String, int>{};
    for (final step in p.steps) {
      for (final parent in step.dependsOn) {
        dependents[parent] = (dependents[parent] ?? 0) + 1;
      }
    }
    final hasBranches =
        dependents.values.any((count) => count > 1) ||
        p.steps.any((step) => step.dependsOn.length > 1);
    return JourneyComposition(
      situation: situation,
      interventions: interventions,
      hasBranches: hasBranches,
      // Terminal Journey readiness no longer requires user preparation.
      // Keep only real owner forms and Requirements in that case.
      hasPreparation:
          p.forms.isNotEmpty ||
          p.requirements.isNotEmpty ||
          (!p.isTerminal &&
              (p.ready.any((item) => journeyUsefulReadySummary(item.summary)) ||
                  p.waiting.isNotEmpty ||
                  p.blockers.isNotEmpty ||
                  interventions.isNotEmpty)),
      hasDocuments:
          p.resourcesLink != null && (!resourcesKnown || resourcesCount > 0),
      hasEngagements:
          p.payments.isNotEmpty || p.order != null || p.access != null,
    );
  }
}
