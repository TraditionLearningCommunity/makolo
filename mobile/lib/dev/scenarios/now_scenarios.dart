import 'package:flutter/material.dart';

import '../../design/surface_states.dart';
import '../../features/now/now_screen.dart';
import '../../features/now/now_selector.dart';
import '../../navigation/destination.dart';
import '../../presentation/contracts/now_presentation.dart';

/// Deterministic Presentation-only examples; never consumed in production.
abstract final class NowGalleryScenarios {
  static NowSelection select(String id) {
    final isCalm = id == 'now-calm';
    final isWait = id == 'now-legitimate-waiting';
    final isMedia = id == 'now-media';
    final isCompose = id == 'now-multiple';
    final pending = id == 'now-pending-local';
    final offline = id == 'now-offline-known';
    final stale = id == 'now-stale';
    const ref = StructuredDestination(kind: 'now', id: 'gallery-now');
    final primary = NowSituationPresentation(
      identity: 'gallery-now',
      reference: ref,
      humanContext: isCompose ? 'Deux engagements' : 'Visa Canada',
      meaning: isCompose
          ? 'Les deux engagements se chevauchent.'
          : isWait
              ? 'La demande a été envoyée.'
              : isMedia
                  ? 'Ce document éclaire la situation.'
                  : 'Votre certificat doit être transmis aujourd’hui.',
      emphasis: NowPresentationEmphasis.primary,
      whyNow: isCompose
          ? 'Ils commencent à la même heure.'
          : 'Une échéance est ouverte.',
      consequence: isCompose ? 'Vous ne pouvez pas être aux deux endroits.' : null,
      responseType: isWait ? 'wait' : isCompose ? 'decide' : 'act',
      turnLabel: isWait ? 'L’organisme doit répondre.' : null,
      horizon: isWait ? 'En attente de sa réponse.' : null,
      businessActions: !isWait && !isMedia && !isCompose
          ? const [
              NowBusinessActionPresentation(
                capability: 'open_detail',
                label: 'Vérifier le dossier',
                interactionDepth: NowInteractionDepth.focused,
              ),
            ]
          : const [],
      mediaBindings: isMedia
          ? const [
              NowMediaBindingPresentation(
                resourceRef: 'gallery:document',
                target: NowMediaTarget.state,
                purpose: NowMediaPurpose.understand,
                kind: NowMediaKind.pdf,
                mimeType: 'application/pdf',
                authorized: true,
                label: 'Document de démonstration',
              ),
            ]
          : const [],
      relationMembers: isCompose
          ? const [
              NowRelationMemberPresentation(id: 'medical', label: 'Rendez-vous médical'),
              NowRelationMemberPresentation(id: 'meeting', label: 'Réunion'),
            ]
          : const [],
      relations: isCompose
          ? const [
              NowRelationPresentation(
                kind: 'conflict',
                memberIds: ['medical', 'meeting'],
                summary: 'Deux événements au même moment.',
              ),
            ]
          : const [],
    );
    return NowSelection(
      situations: isCalm ? const [] : [primary],
      selectionState: isCalm ? 'empty' : 'ready',
      actorAttentionState: isCalm ? 'calm' : 'active',
      state: MakoloSurfacePresentation(
        availability: isCalm ? MakoloAvailabilityCue.empty : MakoloAvailabilityCue.content,
        freshness: stale ? MakoloFreshnessCue.oldObservation : MakoloFreshnessCue.current,
        reachability: offline
            ? MakoloReachabilityCue.temporarilyUnavailable
            : MakoloReachabilityCue.unknown,
        commit: pending ? MakoloCommitCue.pending : MakoloCommitCue.none,
      ),
    );
  }
}

class NowGalleryScenarioPreview extends StatelessWidget {
  const NowGalleryScenarioPreview({required this.id, super.key});

  final String id;

  @override
  Widget build(BuildContext context) => NowView(
    selection: NowGalleryScenarios.select(id),
    initialSelectedKey: id == 'now-n2' ? 'gallery-now' : null,
  );
}
