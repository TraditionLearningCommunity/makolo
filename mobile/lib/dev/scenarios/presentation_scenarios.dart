import '../../design/surface_states.dart';
import '../../navigation/destination.dart';
import '../../presentation/contracts/mark_presentation.dart';
import '../../presentation/contracts/me_presentation.dart';
import '../../presentation/contracts/now_presentation.dart';
import '../../presentation/contracts/ongoing_presentation.dart';

enum PresentationScenarioDataKind { targetPresentation, runtimeCompatible }

class PresentationScenarioDescriptor {
  const PresentationScenarioDescriptor({
    required this.id,
    required this.surface,
    required this.dataKind,
  });

  final String id;
  final String surface;
  final PresentationScenarioDataKind dataKind;
}

abstract final class PresentationScenarioClock {
  static final DateTime fixedNow = DateTime.utc(2026, 11, 12, 13, 42);
}

abstract final class PresentationFixtureUniverse {
  static const demoProfileId = 'demo-profile-001';
  static const demoSpaceId = 'demo-space-mulykap';
  static const demoVisaId = 'demo-visa-canada';
  static const demoTripId = 'demo-trip-lubumbashi-kolwezi';
  static const demoDataScienceId = 'demo-data-science-nairobi';

  static const visaJourney = StructuredDestination(
    kind: 'Journey',
    id: demoVisaId,
  );
  static const tripOccurrence = StructuredDestination(
    kind: 'Occurrence',
    id: demoTripId,
  );
  static const dataScienceActivity = StructuredDestination(
    kind: 'Activity',
    id: demoDataScienceId,
  );
  static const demoProfile = StructuredDestination(
    kind: 'Profile',
    id: demoProfileId,
  );
  static const demoSpace = StructuredDestination(
    kind: 'Space',
    id: demoSpaceId,
  );

  static const visaNow = NowSituationPresentation(
    identity: 'now:$demoVisaId',
    reference: visaJourney,
    humanContext: 'Visa Canada',
    meaning: 'Votre certificat doit être transmis aujourd’hui.',
    whyNow: 'La fenêtre de transmission est ouverte aujourd’hui.',
    emphasis: NowPresentationEmphasis.primary,
    responseLabel: 'Vérifier et envoyer',
    responseCapability: 'submit_required_document',
    metadata: ['Échéance aujourd’hui'],
    freshness: MakoloFreshnessCue.current,
    ownerDestination: visaJourney,
  );

  static const visaOngoing = OngoingContinuityPresentation(
    reference: visaJourney,
    title: 'Visa Canada',
    currentSynthesis:
        'Le dossier continue après la transmission du certificat.',
    settled: ['Passeport identifié', 'Formulaire préparé'],
    mySide: ['Transmettre le certificat'],
    elsewhere: ['Examen par l’autorité compétente'],
    next: ['Attendre la confirmation après envoi'],
    timing: 'Aujourd’hui',
    freshness: MakoloFreshnessCue.current,
    ownerDestination: visaJourney,
  );

  static const me = MePresentation(
    identityLabel: 'Profil de démonstration',
    territories: [
      MeTerritoryPresentation(
        key: 'passport',
        label: 'Passeport Makolo',
        summary: 'Éléments établis et partageables selon le contexte.',
        items: [visaJourney],
        depth: demoProfile,
        state: MakoloSurfacePresentation(
          availability: MakoloAvailabilityCue.content,
          freshness: MakoloFreshnessCue.current,
        ),
      ),
      MeTerritoryPresentation(
        key: 'considerations',
        label: 'Ce qui compte pour moi',
        summary: 'Intérêts, ouvertures et veilles déjà connus.',
        items: [dataScienceActivity],
        state: MakoloSurfacePresentation(
          availability: MakoloAvailabilityCue.content,
          freshness: MakoloFreshnessCue.current,
        ),
      ),
      MeTerritoryPresentation(
        key: 'collectives',
        label: 'Mes collectifs',
        summary: 'Espaces et groupes visibles pour ce Profil.',
        items: [demoSpace],
        depth: demoSpace,
        state: MakoloSurfacePresentation(
          availability: MakoloAvailabilityCue.content,
          freshness: MakoloFreshnessCue.current,
        ),
      ),
      MeTerritoryPresentation(
        key: 'resources',
        label: 'Mes ressources',
        summary: 'Ressources déjà disponibles pour la suite.',
        items: [visaJourney],
        state: MakoloSurfacePresentation(
          availability: MakoloAvailabilityCue.content,
          freshness: MakoloFreshnessCue.oldObservation,
        ),
      ),
    ],
  );

  static const mark = MarkPresentationInput(
    text: 'Je veux envoyer cette attestation pour mon dossier.',
    attachments: [
      MarkAttachmentPresentation(
        id: 'demo-attachment-attestation',
        name: 'attestation.pdf',
        mediaRef: 'fixture://mark/attestation',
      ),
    ],
    draftCommit: MakoloCommitCue.savedOnDevice,
    authority: MakoloAuthorityCue.remoteConfirmationRequired,
    clarification: 'Souhaitez-vous l’ajouter au dossier Visa Canada ?',
    interpretation: 'Une attestation a été fournie comme source possible.',
    consequence:
        'L’envoi doit rester confirmé par le propriétaire de la démarche.',
    intents: [
      MarkIntentPresentation(
        label: 'Ajouter une pièce au dossier',
        consequence: 'Préparer la remise au propriétaire Journey.',
      ),
      MarkIntentPresentation(
        label: 'Conserver la ressource',
        consequence: 'Garder la pièce disponible sans la soumettre.',
      ),
    ],
    handoff: visaJourney,
  );

  static const Map<String, dynamic> nowRuntimePayload = {
    'items': [
      {
        'key': 'demo-now-visa',
        'kind': 'journey',
        'source': {'kind': 'Journey', 'id': demoVisaId},
        'state': 'action',
        'title': 'Visa Canada',
        'summary': 'Votre certificat doit être transmis aujourd’hui.',
        'capabilities': ['open_detail'],
        'links': {'detail': '/api/v1/journeys/$demoVisaId/'},
      },
    ],
  };

  static const Map<String, dynamic> ongoingRuntimePayload = {
    'items': [
      {
        'kind': 'journey',
        'source': {'kind': 'Journey', 'id': demoVisaId},
        'state': 'active',
        'title': 'Visa Canada',
        'continuation': 'Le dossier continue après votre transmission.',
        'actor_interventions': ['Transmettre le certificat'],
        'next': ['Attendre la confirmation'],
        'links': {'detail': '/api/v1/journeys/$demoVisaId/'},
      },
    ],
  };

  static const Map<String, dynamic> discoverRuntimePayload = {
    'count': 1,
    'page': 1,
    'page_size': 24,
    'has_next': false,
    'results': [
      {
        'identity': {
          'family': 'activity',
          'resource': {'id': demoDataScienceId},
          'occurrence': {'id': 'demo-data-science-nairobi-session'},
        },
        'representation': {
          'kind': 'activity',
          'title': 'Data Science Nairobi',
          'summary': 'Formation intensive en science des données.',
          'eyebrow': 'Formation',
          'image_url': 'fixture://discover/data-science-nairobi',
        },
        'place': {
          'name': 'Nairobi',
          'locality': 'Nairobi',
          'latitude': -1.286389,
          'longitude': 36.817223,
        },
        'timing': {'start_date': '2026-11-20', 'start_time': '09:00'},
        'owner': {'display_name': 'Demo Learning Space'},
        'availability': {'state': 'available'},
        'price': {'state': 'unknown'},
        'saved': {'state': 'not_saved'},
        'capabilities': ['open_detail', 'save'],
        'links': {'detail': '/api/v1/activities/$demoDataScienceId/'},
      },
    ],
  };

  static const Map<String, dynamic> meRuntimePayload = {
    'identity': {
      'display_name': 'Profil de démonstration',
      'profile_id': demoProfileId,
    },
    'passport': {'count': 1},
    'considerations': {'count': 1},
    'collectives': {'count': 1},
    'resources': {'count': 1},
    'support': {},
    'links': {},
  };

  static const Map<String, dynamic> dayOfRuntimePayload = {
    'activity': {'title': 'Lubumbashi → Kolwezi'},
    'occurrence': {
      'id': demoTripId,
      'label': 'Départ 14:00',
      'state': 'scheduled',
    },
    'situation': {
      'temporal_relation': 'today',
      'next': {'label': 'Présentez votre accès à la Porte B'},
    },
    'spatial': {
      'destination': {
        'name': 'Porte B',
        'locality': 'Lubumbashi',
        'access_instructions': 'Quai 4',
      },
      'hazards': [],
    },
    'readiness': {'actor_interventions': [], 'blockers': []},
    'checkpoints': {
      'next': {
        'id': 'demo-checkpoint-gate-b',
        'label': 'Porte B',
        'state': 'ready',
      },
    },
    'access': [
      {
        'identity': {'id': 'demo-access-trip'},
        'state': 'active',
        'usable': true,
        'credential': {'type': 'qr'},
        'capabilities': ['open_access', 'present_credential'],
        'links': {
          'detail': '/api/v1/me/accesses/demo-access-trip/',
          'credential': '/api/v1/me/accesses/demo-access-trip/credential/',
        },
      },
    ],
    'placement': [
      {'plan': 'Bus', 'unit': '14A', 'parent_unit': 'Quai 4'},
    ],
    'queue': [],
    'capabilities': ['open_live'],
    'links': {'live': '/api/v1/operations/occurrences/$demoTripId/live/'},
  };
}

abstract final class PresentationScenarioCatalog {
  static const Map<String, List<String>> _matrix = {
    'now': [
      'now-g01-s1-min',
      'now-g01-s1-rich',
      'now-g01-s2-min',
      'now-g01-s2-rich',
      'now-g01-s3-min',
      'now-g01-s3-rich',
      'now-g01-s4-min',
      'now-g01-s4-rich',
      'now-g01-s5-min',
      'now-g01-s5-rich',
      'now-current-action',
      'now-calm',
      'now-pending-local',
      'now-offline-known',
      'now-stale',
      'now-multiple',
      'now-media',
      'now-legitimate-waiting',
      'now-wide-root',
      'now-n2',
    ],
    'discover': [
      'discover-compact-field',
      'discover-media-standard',
      'discover-media-document',
      'discover-media-landscape',
      'discover-no-match',
      'discover-end-field',
      'discover-no-current-proposal',
      'discover-offline-snapshot',
      'discover-offline-no-snapshot',
      'discover-multi-location',
      'discover-remote',
      'discover-wide-grid',
      'discover-wide-spatial',
      'discover-compact-map-fallback',
      'discover-selected',
      'discover-n2',
    ],
    'ongoing': [
      'ongoing-multiple',
      'ongoing-calm-with-content',
      'ongoing-true-empty',
      'ongoing-offline-known',
      'ongoing-local-error',
      'ongoing-blocker',
      'ongoing-waiting',
      'ongoing-parallel-movements',
      'ongoing-n2',
      'ongoing-single-pane',
      'ongoing-split',
      'ongoing-day-of-handoff',
    ],
    'me': [
      'me-full',
      'me-sparse',
      'me-offline',
      'me-local-section-empty',
      'me-local-section-error',
      'me-identity',
      'me-passport',
      'me-considerations',
      'me-collectives',
      'me-resources',
      'me-resource-n2',
      'me-single-column',
      'me-two-territories',
    ],
    'day-of-participant': [
      'day-of-planned',
      'day-of-estimated',
      'day-of-live',
      'day-of-unknown',
      'day-of-unavailable',
      'day-of-offline',
      'day-of-orientation',
      'day-of-placement',
      'day-of-access',
      'day-of-queue',
      'day-of-single-pane',
      'day-of-split',
    ],
    'day-of-operator': [
      'operator-ready',
      'operator-checking',
      'operator-access-valid-confirmation-pending',
      'operator-passage-confirmed',
      'operator-invalid',
      'operator-unreadable',
      'operator-network-failure',
      'operator-authority-lost',
    ],
    'mark': [
      'mark-root-text',
      'mark-attachment',
      'mark-clarification',
      'mark-offline-draft',
      'mark-local-error',
      'mark-source-consequence',
      'mark-multi-intent',
      'mark-space-context',
      'mark-permission-denied',
      'mark-handoff',
      'mark-voice-placeholder',
    ],
  };

  static const Set<String> _runtimeCompatibleIds = {
    'now-current-action',
    'discover-compact-field',
    'ongoing-multiple',
    'me-full',
    'day-of-planned',
  };

  static const Map<String, String> goldenScenarioIds = {
    'G01': 'now-current-action',
    'G02': 'now-n2',
    'G03': 'discover-compact-field',
    'G04': 'discover-wide-grid',
    'G05': 'discover-wide-spatial',
    'G06': 'ongoing-multiple',
    'G07': 'ongoing-n2',
    'G08': 'me-full',
    'G09': 'me-two-territories',
    'G10': 'day-of-planned',
    'G11': 'day-of-split',
    'G12': 'operator-ready',
    'G13': 'mark-root-text',
    'G14': 'mark-space-context',
  };

  static final List<PresentationScenarioDescriptor> all = List.unmodifiable(
    _matrix.entries.expand(
      (entry) => entry.value.map(
        (id) => PresentationScenarioDescriptor(
          id: id,
          surface: entry.key,
          dataKind: _runtimeCompatibleIds.contains(id)
              ? PresentationScenarioDataKind.runtimeCompatible
              : PresentationScenarioDataKind.targetPresentation,
        ),
      ),
    ),
  );

  static PresentationScenarioDescriptor byId(String id) =>
      all.firstWhere((scenario) => scenario.id == id);
}
