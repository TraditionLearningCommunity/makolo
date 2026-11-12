import 'journey_selector.dart';

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
    final interventions = p.actorInterventions.where((item) {
      if (item.key == p.nextActionKey && p.nextActionKey != null) return false;
      final repeatsTitle = item.summary.trim().toLowerCase() ==
          p.title.trim().toLowerCase();
      return !repeatsTitle || item.nextLink != null;
    }).toList(growable: false);
    final actionableKeys = <String>{
      for (final item in p.actorInterventions)
        if (item.nextLink != null && item.nextLink!.isNotEmpty)
          item.key.isEmpty ? item.nextLink! : item.key,
      if (p.nextActionLink != null && p.nextActionLink!.isNotEmpty)
        p.nextActionKey ?? p.nextActionLink!,
    };
    final situation = p.isTerminal
        ? JourneySituation.completed
        : p.blockers.isNotEmpty || p.rejectedRequests > 0
        ? JourneySituation.blocked
        : actionableKeys.length > 1
        ? JourneySituation.choices
        : actionableKeys.isNotEmpty ||
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
    final hasBranches = dependents.values.any((count) => count > 1) ||
        p.steps.any((step) => step.dependsOn.length > 1);
    return JourneyComposition(
      situation: situation,
      interventions: interventions,
      hasBranches: hasBranches,
      hasPreparation: p.ready.isNotEmpty ||
          p.waiting.isNotEmpty ||
          p.blockers.isNotEmpty ||
          interventions.isNotEmpty ||
          p.forms.isNotEmpty ||
          p.requirements.isNotEmpty,
      hasDocuments: p.resourcesLink != null &&
          (!resourcesKnown || resourcesCount > 0),
      hasEngagements: p.payments.isNotEmpty || p.order != null || p.access != null,
    );
  }
}
