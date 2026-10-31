import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/behavior_primitives.dart';
import 'package:makolo_mobile/design/surface_states.dart';
import 'package:makolo_mobile/features/discovery/discovery_mature_view.dart';
import 'package:makolo_mobile/features/discovery/discovery_selector.dart';
import 'package:makolo_mobile/features/discovery/discovery_share_sheet.dart';
import 'package:makolo_mobile/presentation/possibilities/discovery_possibility_unit.dart';
import 'package:makolo_mobile/platform/maps/map_runtime_config.dart';

import 'support/presentation_harness.dart';

DiscoveryItemPresentation item(
  String id,
  String title, {
  bool mappable = false,
  String? imageUrl,
  String? routeLabel,
}) {
  return DiscoveryItemPresentation(
    family: 'activity',
    id: id,
    candidateKey: 'activity:$id',
    occurrenceId: mappable ? 'occ-$id' : null,
    representationKind: routeLabel == null ? 'event' : 'route',
    routeLabel: routeLabel,
    title: title,
    summary: 'Résumé de $title',
    imageUrl: imageUrl,
    eyebrow: 'À explorer',
    owner: 'Espace test',
    place: mappable ? 'Lubumbashi' : 'À distance',
    timing: '2026-10-05 09:00',
    availability: 'available',
    price: 'Gratuit',
    latitude: mappable ? -11.66 + id.length / 100 : null,
    longitude: mappable ? 27.48 + id.length / 100 : null,
    distanceKm: mappable ? 3 : null,
    savedState: 'not_saved',
    capabilities: const {'view', 'save'},
    links: const {'detail': '/api/v1/discovery/items/activity/test/'},
    wire: mappable
        ? {
            'place': {
              'latitude': -11.66 + id.length / 100,
              'longitude': 27.48 + id.length / 100,
              'locality': 'Lubumbashi',
            },
          }
        : const {},
  );
}

DiscoveryFieldSelection selection({
  List<DiscoveryItemPresentation>? items,
  Set<DiscoveryFieldState> states = const {},
  MakoloReachabilityCue reachability = MakoloReachabilityCue.unknown,
  MakoloFailureCue failure = MakoloFailureCue.none,
  bool hasNext = false,
}) {
  final values =
      items ??
      [
        item(
          'media',
          'Formation Data Science',
          imageUrl: 'fixture://discover/data-science',
          mappable: true,
        ),
        item(
          'route',
          'Voyage vers Kolwezi',
          routeLabel: 'Lubumbashi → Kolwezi',
          mappable: true,
        ),
        item('remote', 'Accompagnement à distance'),
      ];
  return DiscoveryFieldSelection(
    collection: DiscoveryCollectionPresentation(
      items: values,
      count: values.length,
      page: 1,
      pageSize: 24,
      hasNext: hasNext,
    ),
    surface: MakoloSurfacePresentation(
      availability: values.isEmpty
          ? MakoloAvailabilityCue.empty
          : MakoloAvailabilityCue.content,
      reachability: reachability,
      failure: failure,
    ),
    states: states,
  );
}

void main() {
  test('N1 added-at is relative without changing an Occurrence date', () {
    final now = DateTime(2026, 10, 31, 14);
    expect(
      discoveryAddedAtLabel(now.subtract(const Duration(minutes: 2)), now),
      'il y a 2 min',
    );
    expect(
      discoveryAddedAtLabel(now.subtract(const Duration(hours: 2)), now),
      'il y a 2 h',
    );
    expect(
      discoveryAddedAtLabel(now.subtract(const Duration(days: 1)), now),
      'Hier',
    );
    expect(
      discoveryAddedAtLabel(now.subtract(const Duration(days: 14)), now),
      'il y a 2 sem.',
    );
    expect(discoveryAddedAtLabel(now.add(const Duration(days: 1)), now), '');
    expect(
      discoveryAddedAtLabel(
        now.subtract(const Duration(hours: 2)),
        now,
        french: false,
      ),
      '2 h ago',
    );
  });

  testWidgets('N1 preserves established transport availability and place roles', (
    tester,
  ) async {
    final transport = DiscoveryItemPresentation(
      family: 'activity',
      id: 'transport-facts',
      candidateKey: 'activity:transport-facts',
      title: 'Déplacement vers Kolwezi',
      summary: 'Trajet confirmé.',
      owner: 'Transport Makolo',
      availability: 'Indisponible',
      savedState: 'unknown',
      capabilities: const {'view'},
      links: const {},
      wire: const {
        'availability': {'state': 'sold_out'},
        'spatial_facts': [
          {'role': 'departure', 'place': {'name': 'Lubumbashi'}},
          {'role': 'stopover', 'place': {'name': 'Likasi'}},
          {'role': 'stopover', 'place': {'name': 'Fungurume'}},
          {'role': 'arrival', 'place': {'name': 'Kolwezi'}},
        ],
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [transport]),
        onOpen: (_) {},
      ),
    );
    expect(find.text('Informations pratiques'), findsOneWidget);
    expect(find.text('Indisponible'), findsOneWidget);
    expect(find.text('Départ'), findsOneWidget);
    expect(find.text('Lubumbashi'), findsOneWidget);
    expect(find.text('Escale 1'), findsOneWidget);
    expect(find.text('Likasi'), findsOneWidget);
    expect(find.text('Escale 2'), findsOneWidget);
    expect(find.text('Fungurume'), findsOneWidget);
    expect(find.text('Arrivée'), findsOneWidget);
    expect(find.text('Kolwezi'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('N1 shows owner limitations and multiple variants as context', (
    tester,
  ) async {
    final possibility = DiscoveryItemPresentation(
      family: 'activity',
      id: 'contextual-n1',
      candidateKey: 'activity:contextual-n1',
      title: 'Formation avec deux sessions',
      summary: 'Des modalités établies.',
      savedState: 'unknown',
      capabilities: const {'view'},
      links: const {},
      wire: const {
        'assessment': [
          {'state': 'limiting', 'label': 'Inscription avant le départ'},
          {'state': 'unknown', 'label': 'Disponibilité à confirmer'},
        ],
        'variants': [
          {'occurrence': {'id': 'first'}},
          {'occurrence': {'id': 'second'}},
        ],
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [possibility]),
        onOpen: (_) {},
      ),
    );
    expect(find.text('Informations pratiques'), findsOneWidget);
    expect(find.text('Inscription avant le départ'), findsOneWidget);
    expect(find.text('2 variantes'), findsOneWidget);
    expect(find.text('Disponibilité à confirmer'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('N1 public Service start enters the same N3 login handoff', (
    tester,
  ) async {
    String? ownerPath;
    var detailOpened = false;
    final possibility = DiscoveryItemPresentation(
      family: 'service_activity',
      id: 'activity-id',
      candidateKey: 'service_activity:activity-id',
      title: 'Service visible sans connexion',
      summary: '',
      savedState: 'unknown',
      capabilities: const {'view'},
      links: const {},
      wire: const {
        'engagement': {
          'owner': 'services',
          'state': 'owner_api',
          'resource': {'kind': 'service', 'id': 'service-id'},
          'capabilities': ['start_after_auth'],
          'presentation': {
            'capability': 'start',
            'enabled': false,
            'requires_auth': true,
          },
          'primary_action': {
            'code': 'start',
            'label': 'Commencer',
            'destination': {
              'kind': 'native',
              'path': '/services/service-id/start',
            },
          },
        },
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryPossibilityUnit(
        item: possibility,
        onOpen: () => detailOpened = true,
        onNativeAction: (path) => ownerPath = path,
      ),
    );
    final action = find.byKey(const Key('discover-primary-n1'));
    expect(tester.widget<IconButton>(action).tooltip, 'Commencer');
    await tester.tap(action);
    expect(ownerPath, '/services/service-id/start');
    expect(detailOpened, isFalse);
  });

  testWidgets(
    'N2 opens the existing Activity owner N3 without inventing an action',
    (tester) async {
      String? ownerPath;
      final possibility = DiscoveryItemPresentation(
        family: 'service_activity',
        id: 'activity-123',
        candidateKey: 'service_activity:activity-123',
        title: 'Service réel',
        summary: '',
        savedState: 'unknown',
        capabilities: const {'view'},
        links: const {},
        wire: const {
          'identity': {
            'family': 'service_activity',
            'resource': {'kind': 'activity', 'id': 'activity-123'},
          },
          'engagement': {
            'state': 'owner_contract',
            'owner': 'services',
            'capabilities': <String>[],
          },
        },
      );
      await PresentationHarness.pump(
        tester,
        viewport: const Size(360, 800),
        child: DiscoveryPossibilityUnit(
          item: possibility,
          detailMode: true,
          onOpen: () => fail('N2 must not recursively open itself'),
          onOwnerDepth: (path) => ownerPath = path,
        ),
      );

      final action = find.byKey(const Key('discover-owner-n3'));
      expect(action, findsOneWidget);
      expect(find.byKey(const Key('discover-primary-n2')), findsNothing);
      await tester.tap(action);
      expect(ownerPath, '/activities/activity-123');
    },
  );

  testWidgets(
    'N2 never fabricates an Activity N3 for an external Opportunity',
    (tester) async {
      final possibility = DiscoveryItemPresentation(
        family: 'opportunity',
        id: 'opportunity-123',
        candidateKey: 'opportunity:opportunity-123',
        title: 'Candidature externe',
        summary: '',
        savedState: 'unknown',
        capabilities: const {'view'},
        links: const {},
        wire: const {
          'identity': {
            'family': 'opportunity',
            'resource': {'kind': 'opportunity', 'id': 'opportunity-123'},
          },
        },
      );
      await PresentationHarness.pump(
        tester,
        viewport: const Size(360, 800),
        child: DiscoveryPossibilityUnit(
          item: possibility,
          detailMode: true,
          onOpen: () {},
          onOwnerDepth: (_) =>
              fail('No owner Activity for external Opportunity'),
        ),
      );
      expect(find.byKey(const Key('discover-owner-n3')), findsNothing);
      expect(find.byKey(const Key('discover-primary-n2')), findsNothing);
    },
  );

  testWidgets(
    'N2 prioritizes an owner-native action over generic Activity N3',
    (tester) async {
      String? ownerPath;
      final possibility = DiscoveryItemPresentation(
        family: 'service_activity',
        id: 'activity-123',
        candidateKey: 'service_activity:activity-123',
        title: 'Service avec démarrage',
        summary: '',
        savedState: 'unknown',
        capabilities: const {'view'},
        links: const {},
        wire: const {
          'identity': {
            'family': 'service_activity',
            'resource': {'kind': 'activity', 'id': 'activity-123'},
          },
          'engagement': {
            'owner': 'services',
            'state': 'owner_api',
            'resource': {'kind': 'service', 'id': 'service-123'},
            'capabilities': ['start'],
            'presentation': {'capability': 'start', 'enabled': true},
            'primary_action': {
              'code': 'start',
              'label': 'Commencer',
              'destination': {
                'kind': 'native',
                'path': '/services/service-123/start',
              },
            },
          },
        },
      );
      await PresentationHarness.pump(
        tester,
        viewport: const Size(360, 800),
        child: DiscoveryPossibilityUnit(
          item: possibility,
          detailMode: true,
          onOpen: () {},
          onNativeAction: (path) => ownerPath = path,
          onOwnerDepth: (_) => fail('Native owner depth has priority'),
        ),
      );
      expect(find.byKey(const Key('discover-owner-n3')), findsNothing);
      final action = find.byKey(const Key('discover-primary-n2'));
      expect(action, findsOneWidget);
      await tester.tap(action);
      expect(ownerPath, '/services/service-123/start');
    },
  );

  testWidgets(
    'N2 shares media and resources with N1 without a second detail CTA',
    (tester) async {
      final detailed = DiscoveryItemPresentation(
        family: 'activity',
        id: 'depth',
        candidateKey: 'activity:depth',
        title: 'Voyage présenté',
        summary: 'Une option réelle.',
        imageUrl: 'https://example.test/discovery-cover.png',
        savedState: 'not_saved',
        capabilities: const {'view'},
        links: const {},
        wire: const {
          'detail': {
            'description':
                'Départ de Lubumbashi vers Kolwezi. Conditions et '
                'modalités de transport établies par le propriétaire.',
          },
          'variants': [
            {
              'occurrence': {'kind': 'occurrence', 'id': 'first'},
              'timing': {
                'start_at': '2026-10-30T08:00:00+02:00',
                'timezone': 'Africa/Lubumbashi',
              },
            },
            {
              'occurrence': {'kind': 'occurrence', 'id': 'second'},
              'timing': {
                'start_at': '2026-11-02T08:00:00+02:00',
                'timezone': 'Africa/Lubumbashi',
              },
            },
          ],
          'resources': [
            {
              'title': 'Guide de bord',
              'kind': 'text',
              'text_content': 'Texte réel',
            },
            {
              'title': 'Guide pratique',
              'kind': 'text',
              'text_content': 'Annexe',
            },
            {
              'title': 'Règlement',
              'kind': 'text',
              'text_content': 'Conditions',
            },
          ],
        },
      );
      await PresentationHarness.pump(
        tester,
        viewport: const Size(360, 800),
        child: SingleChildScrollView(
          child: DiscoveryPossibilityUnit(
            item: detailed,
            detailMode: true,
            onOpen: () => fail('Already in N2'),
          ),
        ),
      );

      expect(find.text('Voyage présenté'), findsOneWidget);
      expect(
        find.byKey(const Key('discover-description-text')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('discover-description-expand')),
        findsNothing,
      );
      expect(find.textContaining('30/10/2026'), findsOneWidget);
      expect(find.textContaining('02/11/2026'), findsOneWidget);
      expect(find.byKey(const Key('discover-media-main')), findsOneWidget);
      expect(
        find.byKey(const Key('discover-resources-section')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('discover-resources-expand')), findsNothing);
      expect(find.byKey(const Key('discover-primary-n1')), findsNothing);
      expect(find.byKey(const Key('discover-primary-n2')), findsNothing);
    },
  );

  testWidgets('N2 owner action reuses the exact native continuation', (
    tester,
  ) async {
    String? resumed;
    final detailed = DiscoveryItemPresentation(
      family: 'service_activity',
      id: 'service-depth',
      candidateKey: 'service_activity:service-depth',
      title: 'Service',
      summary: '',
      savedState: 'unknown',
      capabilities: const {'view'},
      links: const {},
      wire: const {
        'engagement': {
          'owner': 'services',
          'state': 'owner_api',
          'resource': {'kind': 'service', 'id': 'service-depth'},
          'capabilities': ['start'],
          'presentation': {'capability': 'start', 'enabled': true},
          'primary_action': {
            'code': 'start',
            'label': 'Commencer',
            'destination': {
              'kind': 'native',
              'path': '/services/service-depth/start',
            },
          },
        },
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryPossibilityUnit(
        item: detailed,
        detailMode: true,
        onOpen: () => fail('Do not fall back to N2'),
        onNativeAction: (path) => resumed = path,
      ),
    );

    final action = find.byKey(const Key('discover-primary-n2'));
    expect(action, findsOneWidget);
    expect(find.text('Commencer'), findsOneWidget);
    await tester.tap(action);
    await tester.pump();
    expect(resumed, '/services/service-depth/start');
    expect(find.byKey(const Key('discover-primary-n1')), findsNothing);
  });

  testWidgets('guest N2 save intent requests login, not an optimistic save', (
    tester,
  ) async {
    var signInRequests = 0;
    var saved = false;
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryPossibilityUnit(
        item: item('guest-depth', 'Séance publique'),
        detailMode: true,
        onOpen: () {},
        allowSavePrompt: true,
        onSignIn: () => signInRequests++,
        onSave: () async {
          saved = true;
        },
      ),
    );
    await tester.tap(find.byKey(const Key('discover-save-n2')));
    await tester.pump();
    expect(signInRequests, 1);
    expect(saved, isFalse);
  });

  testWidgets('G03 compact renders a natural possibility field', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(states: const {DiscoveryFieldState.endOfField}),
        onOpen: (_) {},
      ),
    );

    expect(find.text('Opportunités à découvrir'), findsOneWidget);
    expect(
      find.text(
        'Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?',
      ),
      findsNothing,
    );
    expect(find.byKey(const Key('discover-compact-field')), findsOneWidget);
    expect(find.byKey(const Key('discover-wide-grid')), findsNothing);
    expect(find.text('Formation Data Science'), findsOneWidget);
    // N1 scrolls a bounded page: off-screen cards are built on demand.
    await tester.scrollUntilVisible(
      find.text('Lubumbashi → Kolwezi'),
      180,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Lubumbashi → Kolwezi'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('Accompagnement à distance'),
      180,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Accompagnement à distance'), findsOneWidget);
    expect(find.text('S’inscrire'), findsNothing);
    // No Orphan Content: compact Discovery never invents filler cards.
    expect(find.textContaining('contenu de remplissage'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('N1 mobile shows price beside independent presentation facts', (
    tester,
  ) async {
    final rich = DiscoveryItemPresentation(
      family: 'service_activity',
      id: 'service-n1',
      candidateKey: 'service_activity:service-n1',
      title: 'Accompagnement très détaillé',
      summary: 'Une description utile du Service.',
      owner: 'Espace conseil',
      price: '25000 CDF',
      availability: 'Disponible',
      savedState: 'not_saved',
      capabilities: const {'view'},
      links: const {
        'detail': '/api/v1/discovery/items/service_activity/service-n1/',
      },
      wire: const {
        'presentation_facts': [
          {
            'code': 'condition',
            'label': 'Condition',
            'value': 'Document requis',
          },
          {'code': 'duration', 'label': 'Durée', 'value': 'Une semaine'},
        ],
        'date': {
          'kind': 'added_at',
          'label': 'Ajouté le',
          'value': '2026-10-10T10:30:00+02:00',
        },
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [rich]),
        onOpen: (_) {},
      ),
    );

    expect(find.text('Accompagnement très détaillé'), findsOneWidget);
    expect(find.text('25000 CDF'), findsOneWidget);
    expect(find.text('Document requis'), findsOneWidget);
    expect(find.text('Une semaine'), findsOneWidget);
    expect(find.byKey(const Key('discover-save-n1')), findsOneWidget);
    expect(find.byKey(const Key('discover-primary-n1')), findsOneWidget);
    expect(find.text('Voir plus'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('N1 practical facts do not change when description expands', (
    tester,
  ) async {
    final rich = DiscoveryItemPresentation(
      family: 'activity',
      id: 'steady-facts',
      candidateKey: 'activity:steady-facts',
      title: 'Une possibilité avec informations pratiques',
      summary: List.filled(30, 'Description détaillée.').join(' '),
      owner: 'Espace test',
      price: '25 USD',
      place: 'Lubumbashi',
      availability: 'Disponible',
      savedState: 'unknown',
      capabilities: const {'view'},
      links: const {},
      wire: const {
        'presentation_facts': [
          {'code': 'type', 'label': 'Type', 'value': 'Accompagnement'},
          {'code': 'price', 'label': 'Prix', 'value': '25 USD'},
        ],
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [rich]),
        onOpen: (_) {},
      ),
    );
    expect(find.byKey(const Key('discover-facts-section')), findsOneWidget);
    expect(find.text('Prix'), findsOneWidget);
    expect(find.text('25 USD'), findsOneWidget);
    expect(find.text('Lubumbashi'), findsOneWidget);
    expect(find.text('Disponible'), findsOneWidget);
    expect(find.text('Accompagnement'), findsOneWidget);
    expect(find.text('Type'), findsNothing);
    await tester.tap(find.byKey(const Key('discover-description-tap')));
    await tester.pump();
    expect(find.byKey(const Key('discover-facts-section')), findsOneWidget);
    expect(find.text('Prix'), findsOneWidget);
    expect(find.text('25 USD'), findsOneWidget);
    expect(find.text('Disponible'), findsOneWidget);
    expect(find.text('Voir moins'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'N1 places the addition date with the owner and merges type labels',
    (tester) async {
      final rich = DiscoveryItemPresentation(
        family: 'service_activity',
        id: 'owner-date',
        candidateKey: 'service_activity:owner-date',
        title: 'Assistance création dossier',
        summary: 'Une aide documentaire.',
        owner: 'Mwangaza Services',
        eyebrow: 'Accompagnement documentaire',
        savedState: 'not_saved',
        capabilities: const {'view'},
        links: const {},
        wire: const {
          'owner': {'display_name': 'Mwangaza Services'},
          'representation': {'vertical_label': 'Accompagnement'},
          'date': {
            'kind': 'added_at',
            'label': 'Ajouté le',
            'value': '2026-06-07T12:00:00+02:00',
          },
        },
      );
      await PresentationHarness.pump(
        tester,
        viewport: const Size(320, 760),
        child: DiscoveryExplorationView(
          selection: selection(items: [rich]),
          onOpen: (_) {},
        ),
      );

      expect(find.byKey(const Key('discover-owner-date-row')), findsOneWidget);
      expect(find.byKey(const Key('discover-type-row')), findsOneWidget);
      expect(find.text('Mwangaza Services'), findsOneWidget);
      expect(find.text('Accompagnement'), findsOneWidget);
      expect(find.text('Accompagnement documentaire'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('N1 long description expands inline without opening detail', (
    tester,
  ) async {
    var opened = false;
    final longSummary = List.filled(35, 'Une possibilité concrète.').join(' ');
    final rich = DiscoveryItemPresentation(
      family: 'activity',
      id: 'inline',
      candidateKey: 'activity:inline',
      title: 'Description dépliable',
      summary: longSummary,
      owner: 'Espace test',
      savedState: 'not_saved',
      capabilities: const {'view'},
      links: const {},
      wire: const {},
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [rich]),
        onOpen: (_) => opened = true,
      ),
    );

    expect(find.text('Voir plus'), findsOneWidget);
    expect(
      tester
          .widget<Text>(find.byKey(const Key('discover-description-text')))
          .maxLines,
      3,
    );
    await tester.tap(find.byKey(const Key('discover-description-tap')));
    await tester.pump();
    expect(find.text(longSummary), findsOneWidget);
    expect(find.text('Voir moins'), findsOneWidget);
    expect(opened, isFalse);
    await tester.ensureVisible(
      find.byKey(const Key('discover-description-tap')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('discover-description-tap')));
    await tester.pump();
    expect(
      tester
          .widget<Text>(find.byKey(const Key('discover-description-text')))
          .maxLines,
      3,
    );
    expect(find.text('Voir plus'), findsOneWidget);
    await tester.tap(find.byKey(const Key('discover-description-expand')));
    await tester.pump();
    expect(find.text(longSummary), findsOneWidget);
    await tester.ensureVisible(find.text('Voir moins'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Voir moins'));
    await tester.pump();
    expect(
      tester
          .widget<Text>(find.byKey(const Key('discover-description-text')))
          .maxLines,
      3,
    );
    expect(opened, isFalse);
    expect(tester.takeException(), isNull);
  });

  testWidgets('N1 shows two annexes then all seven after expansion', (
    tester,
  ) async {
    final rich = DiscoveryItemPresentation(
      family: 'activity',
      id: 'resources',
      candidateKey: 'activity:resources',
      title: 'Possibilité avec documents',
      summary: 'Résumé court.',
      owner: 'Espace test',
      savedState: 'unknown',
      capabilities: const {'view'},
      links: const {},
      wire: {
        'resources': [
          for (var index = 1; index <= 7; index++)
            {
              'title': 'Document $index',
              'kind': 'text',
              'text_content': 'Instructions $index',
            },
        ],
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [rich]),
        onOpen: (_) {},
      ),
    );

    expect(find.byKey(const Key('discover-resources-section')), findsOneWidget);
    expect(find.text('Document 1'), findsOneWidget);
    expect(find.text('Document 2'), findsOneWidget);
    expect(find.text('Document 3'), findsNothing);
    expect(find.text('Document 7'), findsNothing);
    expect(find.text('Voir les 7 ressources'), findsOneWidget);
    await tester.ensureVisible(
      find.byKey(const Key('discover-resources-expand')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('discover-resources-expand')));
    await tester.pump();
    for (var index = 1; index <= 7; index++) {
      expect(find.text('Document $index'), findsOneWidget);
    }
    expect(find.text('Voir moins de ressources'), findsOneWidget);
    await tester.ensureVisible(
      find.byKey(const Key('discover-resources-expand')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('discover-resources-expand')));
    await tester.pump();
    expect(find.text('Document 3'), findsNothing);
    expect(find.text('Document 7'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('N1 practical facts stay fixed while description unfolds', (
    tester,
  ) async {
    final longSummary = List.filled(30, 'Description développable.').join(' ');
    final rich = DiscoveryItemPresentation(
      family: 'service_activity',
      id: 'stable-facts',
      candidateKey: 'service_activity:stable-facts',
      title: 'Service avec informations',
      summary: longSummary,
      owner: 'Espace test',
      price: '25 USD',
      availability: 'Disponible',
      eyebrow: 'Accompagnement',
      savedState: 'not_saved',
      capabilities: const {'view'},
      links: const {},
      wire: const {
        'availability': {'state': 'available'},
        'presentation_facts': [
          {'code': 'type', 'label': 'Type', 'value': 'Accompagnement'},
          {
            'code': 'condition',
            'label': 'Condition',
            'value': 'Document requis',
          },
        ],
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [rich]),
        onOpen: (_) {},
      ),
    );

    expect(find.byKey(const Key('discover-facts-section')), findsOneWidget);
    expect(find.text('Prix'), findsOneWidget);
    expect(find.text('25 USD'), findsOneWidget);
    expect(find.text('Disponibilité'), findsOneWidget);
    expect(find.text('Document requis'), findsOneWidget);
    expect(find.text('Type'), findsNothing);
    await tester.tap(find.byKey(const Key('discover-description-tap')));
    await tester.pump();
    expect(find.byKey(const Key('discover-facts-section')), findsOneWidget);
    expect(find.text('Prix'), findsOneWidget);
    expect(find.text('25 USD'), findsOneWidget);
    expect(find.text('Document requis'), findsOneWidget);
    await tester.ensureVisible(
      find.byKey(const Key('discover-description-tap')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('discover-description-tap')));
    await tester.pump();
    expect(find.byKey(const Key('discover-facts-section')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('N1 omits unknown practical information entirely', (
    tester,
  ) async {
    final possibility = DiscoveryItemPresentation(
      family: 'service_activity',
      id: 'unknown-practical',
      candidateKey: 'service_activity:unknown-practical',
      title: 'Service sans horaire établi',
      summary: 'Une proposition à découvrir.',
      savedState: 'unknown',
      capabilities: const {'view'},
      links: const {},
      availability: 'Disponibilité à confirmer',
      wire: const {
        'availability': {'state': 'unknown'},
        'assessment': [
          {'state': 'unknown', 'label': 'Disponibilité à confirmer'},
        ],
        'presentation_facts': [
          {'code': 'price', 'label': 'Prix', 'value': 'À déterminer'},
          {'code': 'when', 'label': 'Heure', 'value': 'À compléter'},
        ],
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [possibility]),
        onOpen: (_) {},
      ),
    );
    expect(find.text('Informations pratiques'), findsNothing);
    expect(find.text('Disponibilité à confirmer'), findsNothing);
    expect(find.text('À déterminer'), findsNothing);
    expect(find.text('À compléter'), findsNothing);
    expect(find.byKey(const Key('discover-facts-section')), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('N1 center never opens an owner Web page inside Flutter', (
    tester,
  ) async {
    var openedDetail = false;
    final possibility = DiscoveryItemPresentation(
      family: 'funding_activity',
      id: 'funding-web',
      candidateKey: 'funding_activity:funding-web',
      title: 'Soutien au projet',
      summary: 'Contribuer au projet.',
      savedState: 'unknown',
      capabilities: const {'view'},
      links: const {},
      wire: const {
        'engagement': {
          'primary_action': {
            'code': 'contribute',
            'label': 'Contribuer',
            'destination': {
              'kind': 'web',
              'path': '/funding/projects/public/contribute/',
            },
          },
          'presentation': {
            'label': 'Contribuer',
            'web': '/funding/projects/public/contribute/',
            'web_enabled': true,
          },
        },
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [possibility]),
        baseUri: Uri.parse('https://makolo.invalid/'),
        onOpen: (_) => openedDetail = true,
      ),
    );
    expect(
      tester
          .widget<IconButton>(find.byKey(const Key('discover-primary-n1')))
          .tooltip,
      'Détails',
    );
    await tester.tap(find.byKey(const Key('discover-primary-n1')));
    await tester.pump();
    expect(openedDetail, isTrue);
    expect(tester.takeException(), isNull);
  });

  testWidgets('N1 center rejects foreign Web continuation and opens detail', (
    tester,
  ) async {
    var opened = false;
    final possibility = DiscoveryItemPresentation(
      family: 'funding_activity',
      id: 'foreign-web',
      candidateKey: 'funding_activity:foreign-web',
      title: 'Projet extérieur',
      summary: 'Projet à examiner.',
      savedState: 'unknown',
      capabilities: const {'view'},
      links: const {},
      wire: const {
        'engagement': {
          'primary_action': {
            'code': 'pay',
            'label': 'Payer',
            'destination': {
              'kind': 'web',
              'path': 'https://untrusted.invalid/checkout',
            },
          },
          'presentation': {
            'label': 'Payer',
            'web': 'https://untrusted.invalid/checkout',
            'web_enabled': true,
          },
        },
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [possibility]),
        baseUri: Uri.parse('https://makolo.invalid/'),
        onOpen: (_) => opened = true,
      ),
    );
    final button = find.byKey(const Key('discover-primary-n1'));
    expect(tester.widget<IconButton>(button).tooltip, 'Détails');
    await tester.tap(button);
    await tester.pump();
    expect(opened, isTrue);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'N1 center ignores an unsupported native action and opens details',
    (tester) async {
      var openedDetail = false;
      final item = DiscoveryItemPresentation(
        family: 'funding_activity',
        id: 'funding-item',
        candidateKey: 'funding_activity:funding-item',
        title: 'Financement professionnel',
        summary: 'Modalités du financement.',
        savedState: 'unknown',
        capabilities: const {'view'},
        links: const {},
        wire: const {
          'engagement': {
            'owner': 'funding',
            'state': 'owner_contract',
            'capabilities': ['pay'],
            'primary_action': {
              'code': 'pay',
              'label': 'Payer',
              'destination': {'kind': 'native', 'path': '/payments/unknown'},
            },
          },
        },
      );
      await PresentationHarness.pump(
        tester,
        viewport: const Size(360, 800),
        child: DiscoveryExplorationView(
          selection: selection(items: [item]),
          onOpen: (_) => openedDetail = true,
        ),
      );
      final primary = find.byKey(const Key('discover-primary-n1'));
      expect(tester.widget<IconButton>(primary).tooltip, 'Détails');
      await tester.tap(primary);
      await tester.pump();
      expect(openedDetail, isTrue);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('N1 center offers native Funding contribution', (tester) async {
    final item = DiscoveryItemPresentation(
      family: 'funding_activity',
      id: 'activity-funding',
      candidateKey: 'funding_activity:activity-funding',
      title: 'Financer une bibliothèque',
      summary: 'Contribution ouverte.',
      savedState: 'unknown',
      capabilities: const {'view'},
      links: const {},
      wire: const {
        'engagement': {
          'owner': 'funding',
          'state': 'owner_api',
          'capabilities': ['contribute'],
          'resource': {'kind': 'funding', 'id': 'funding-123'},
          'links': {
            'native': '/funding/funding-123/contribute',
            'contribute': '/api/v1/funding/funding-123/contributions/',
          },
          'primary_action': {
            'code': 'contribute',
            'label': 'Contribuer',
            'destination': {
              'kind': 'native',
              'path': '/funding/funding-123/contribute',
            },
          },
        },
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [item]),
        onOpen: (_) {},
      ),
    );
    expect(
      tester
          .widget<IconButton>(find.byKey(const Key('discover-primary-n1')))
          .tooltip,
      'Contribuer',
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('N1 center uses native Obtention and not universal Start', (
    tester,
  ) async {
    final item = DiscoveryItemPresentation(
      family: 'activity',
      id: 'activity-obtention',
      candidateKey: 'activity:activity-obtention',
      title: 'Un équipement à obtenir',
      summary: 'Choisir un mode d’obtention.',
      savedState: 'unknown',
      capabilities: const {'view'},
      links: const {},
      wire: const {
        'engagement': {
          'owner': 'obtention',
          'state': 'owner_api',
          'capabilities': ['start_journey'],
          'resource': {'kind': 'obtention', 'id': 'obtention-123'},
          'links': {
            'native': '/obtention/obtention-123/choose',
            'start_journey': '/api/v1/obtention/obtention-123/journeys/',
          },
          'primary_action': {
            'code': 'start_journey',
            'label': 'Obtenir',
            'destination': {
              'kind': 'native',
              'path': '/obtention/obtention-123/choose',
            },
          },
        },
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [item]),
        onOpen: (_) {},
      ),
    );
    expect(
      tester
          .widget<IconButton>(find.byKey(const Key('discover-primary-n1')))
          .tooltip,
      'Obtenir',
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'N1 center displays authorized Service start, not universal Start',
    (tester) async {
      final item = DiscoveryItemPresentation(
        family: 'service_activity',
        id: 'service-item',
        candidateKey: 'service_activity:service-item',
        title: 'Accompagnement administratif',
        summary: 'Aide à la constitution du dossier.',
        savedState: 'unknown',
        capabilities: const {'view'},
        links: const {},
        wire: const {
          'engagement': {
            'owner': 'services',
            'state': 'owner_api',
            'capabilities': ['start'],
            'resource': {'kind': 'service', 'id': 'service-id'},
            'presentation': {'capability': 'start', 'enabled': true},
            'primary_action': {
              'code': 'start',
              'label': 'Commencer',
              'destination': {
                'kind': 'native',
                'path': '/services/service-id/start',
              },
            },
          },
        },
      );
      await PresentationHarness.pump(
        tester,
        viewport: const Size(360, 800),
        child: DiscoveryExplorationView(
          selection: selection(items: [item]),
          onOpen: (_) {},
        ),
      );
      expect(
        tester
            .widget<IconButton>(find.byKey(const Key('discover-primary-n1')))
            .tooltip,
        'Commencer',
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('N1 center displays the owner-approved ticket action', (
    tester,
  ) async {
    final item = DiscoveryItemPresentation(
      family: 'activity',
      id: 'event-item',
      candidateKey: 'activity:event-item',
      title: 'Conférence professionnelle',
      summary: 'Inscription et billets.',
      savedState: 'unknown',
      capabilities: const {'view'},
      links: const {},
      wire: const {
        'engagement': {
          'owner': 'events',
          'state': 'owner_api',
          'capabilities': ['inspect_offers'],
          'resource': {'kind': 'event', 'id': 'event-id', 'slug': 'conf-2026'},
          'links': {'native': '/events/conf-2026/tickets'},
          'primary_action': {
            'code': 'inspect_offers',
            'label': 'Voir les billets',
            'destination': {
              'kind': 'native',
              'path': '/events/conf-2026/tickets',
            },
          },
        },
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [item]),
        onOpen: (_) {},
      ),
    );
    expect(
      tester
          .widget<IconButton>(find.byKey(const Key('discover-primary-n1')))
          .tooltip,
      'Voir les billets',
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'N1 center action uses server detail when no native handoff exists',
    (tester) async {
      var detailOpened = false;
      final item = DiscoveryItemPresentation(
        family: 'activity',
        id: 'detail-action',
        candidateKey: 'activity:detail-action',
        title: 'Détails de la possibilité',
        summary: 'Informations disponibles.',
        savedState: 'unknown',
        capabilities: const {'view'},
        links: const {},
        wire: const {
          'engagement': {
            'primary_action': {
              'code': 'detail',
              'label': 'Détails',
              'destination': {
                'kind': 'detail',
                'path': '/api/v1/discovery/items/activity/detail-action/',
              },
            },
          },
        },
      );
      await PresentationHarness.pump(
        tester,
        viewport: const Size(360, 800),
        child: DiscoveryExplorationView(
          selection: selection(items: [item]),
          onOpen: (_) => detailOpened = true,
        ),
      );
      final primary = find.byKey(const Key('discover-primary-n1'));
      expect(tester.widget<IconButton>(primary).tooltip, 'Détails');
      await tester.tap(primary);
      await tester.pump();
      expect(detailOpened, isTrue);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('N1 preserves text, facts, media, annexes, then actions order', (
    tester,
  ) async {
    final rich = DiscoveryItemPresentation(
      family: 'activity',
      id: 'ordered',
      candidateKey: 'activity:ordered',
      title: 'Possibilité illustrée',
      summary: 'Une présentation claire.',
      imageUrl: 'https://example.test/discovery-cover.png',
      place: 'Lubumbashi',
      owner: 'Espace test',
      savedState: 'not_saved',
      capabilities: const {'view'},
      links: const {},
      wire: const {
        'resources': [
          {
            'title': 'Guide public',
            'kind': 'text',
            'text_content': 'Guide de test',
          },
        ],
      },
    );
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(items: [rich]),
        onOpen: (_) {},
      ),
    );

    final title = find.text('Possibilité illustrée');
    final description = find.byKey(const Key('discover-description-text'));
    final facts = find.byKey(const Key('discover-facts-section'));
    final media = find.byKey(const Key('discover-media-main'));
    final annexes = find.byKey(const Key('discover-resources-section'));
    final action = find.byKey(const Key('discover-primary-n1'));
    expect(title, findsOneWidget);
    expect(description, findsOneWidget);
    expect(facts, findsOneWidget);
    expect(media, findsOneWidget);
    expect(annexes, findsOneWidget);
    expect(action, findsOneWidget);
    expect(
      tester.getTopLeft(title).dy,
      lessThan(tester.getTopLeft(description).dy),
    );
    expect(
      tester.getTopLeft(description).dy,
      lessThan(tester.getTopLeft(facts).dy),
    );
    expect(tester.getTopLeft(facts).dy, lessThan(tester.getTopLeft(media).dy));
    expect(
      tester.getTopLeft(media).dy,
      lessThanOrEqualTo(tester.getTopLeft(annexes).dy),
    );
    expect(
      tester.getTopLeft(annexes).dy,
      lessThan(tester.getTopLeft(action).dy),
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('G04 wide uses the shared adaptive grid', (tester) async {
    await PresentationHarness.pump(
      tester,
      viewport: const Size(1440, 900),
      child: DiscoveryExplorationView(selection: selection(), onOpen: (_) {}),
    );

    expect(find.byKey(const Key('discover-wide-grid')), findsOneWidget);
    expect(find.byKey(const Key('discover-compact-field')), findsNothing);
    expect(find.text('Formation Data Science'), findsOneWidget);
    expect(find.text('Accompagnement à distance'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('wide N2 keeps the field and opens shared focus depth', (
    tester,
  ) async {
    DiscoveryItemPresentation? opened;
    await PresentationHarness.pump(
      tester,
      viewport: const Size(1200, 800),
      child: DiscoveryExplorationView(
        selection: selection(),
        onOpen: (value) => opened = value,
      ),
    );

    await tester.tap(find.text('Formation Data Science').first);
    await tester.pump();

    expect(find.byKey(const Key('makolo-adaptive-split-row')), findsOneWidget);
    expect(find.byKey(const Key('discover-focus-depth')), findsOneWidget);
    expect(find.text('Accompagnement à distance'), findsOneWidget);
    expect(find.text('Ouvrir le détail'), findsOneWidget);

    await tester.tap(find.text('Ouvrir le détail'));
    await tester.pump();
    expect(opened?.id, 'media');

    await tester.tap(find.text('Découvrir').last);
    await tester.pump();
    expect(find.byKey(const Key('discover-focus-depth')), findsNothing);
    expect(find.text('Formation Data Science'), findsOneWidget);
  });

  testWidgets('map route renders a real map pane on compact devices', (
    tester,
  ) async {
    String? selected;
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoverySpatialView(
        selection: selection(),
        mapConfig: const MakoloMapsConfig(enabled: false, style: null),
        showMapOnCompact: true,
        fieldKey: 'one-filtered-context',
        initialSelectedCandidateKey: 'activity:route',
        onSelectionChanged: (key) => selected = key,
        onOpen: (_) {},
      ),
    );
    // The disabled MapLibre runtime displays its honest fallback, NOT
    // another duplicate field replacing the map on narrow layouts.
    expect(find.byKey(const Key('discover-compact-map')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('discover-map-one-filtered-context')),
      findsOneWidget,
    );
    expect(
      find.textContaining('La carte n’est pas disponible'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('discover-compact-field')), findsOneWidget);
    final mapAction = find.byKey(
      const ValueKey('discover-map-action-activity:media'),
    );
    await tester.scrollUntilVisible(
      mapAction, 160, scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(mapAction);
    await tester.pump();
    expect(selected, 'activity:media');
    expect(tester.takeException(), isNull);
  });

  testWidgets('wide field forwards its exact focused candidate to map', (
    tester,
  ) async {
    String? mapSelection;
    var mapOpened = false;
    await PresentationHarness.pump(
      tester,
      viewport: const Size(1200, 800),
      child: DiscoveryExplorationView(
        selection: selection(),
        onOpen: (_) {},
        fieldKey: 'criteria-a',
        onMap: (key) {
          mapOpened = true;
          mapSelection = key;
        },
      ),
    );
    await tester.tap(find.text('Formation Data Science').first);
    await tester.pump();
    expect(find.byKey(const Key('discover-focus-depth')), findsOneWidget);
    await tester.tap(find.byKey(const Key('discover-field-open-map')));
    await tester.pump();
    expect(mapOpened, isTrue);
    expect(mapSelection, 'activity:media');
    expect(tester.takeException(), isNull);
  });

  testWidgets('G05 uses the shared 1040 spatial threshold', (tester) async {
    for (final width in [1000.0, 1040.0, 1080.0]) {
      await PresentationHarness.pump(
        tester,
        viewport: Size(width, 800),
        child: DiscoverySpatialView(
          selection: selection(),
          mapConfig: const MakoloMapsConfig(enabled: false, style: null),
          onOpen: (_) {},
        ),
      );

      final expected = width >= 1040 ? findsOneWidget : findsNothing;
      expect(find.byKey(const Key('makolo-adaptive-split-row')), expected);
    }
  });

  testWidgets('G05 spatial split projects the same field and selection', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      viewport: const Size(1200, 800),
      child: DiscoverySpatialView(
        selection: selection(),
        mapConfig: const MakoloMapsConfig(enabled: false, style: null),
        onOpen: (_) {},
      ),
    );

    expect(find.byKey(const Key('makolo-adaptive-split-row')), findsOneWidget);
    expect(find.byKey(const Key('discover-spatial-pane')), findsOneWidget);
    expect(find.byKey(const Key('discover-spatial-stack')), findsOneWidget);
    expect(
      find.byKey(const ValueKey('discover-map-activity:media')),
      findsOneWidget,
    );
    expect(find.text('Voir sur la carte'), findsNWidgets(2));
    expect(find.text('Accompagnement à distance'), findsOneWidget);

    final secondMapAction = find.byKey(
      const ValueKey('discover-map-action-activity:route'),
    );
    await tester.scrollUntilVisible(
      secondMapAction,
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pump();
    await tester.tap(secondMapAction);
    await tester.pump();

    expect(
      find.byKey(const ValueKey('discover-map-activity:route')),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('NO_MATCH keeps criteria choice explicit', (tester) async {
    await PresentationHarness.pump(
      tester,
      child: DiscoveryFieldView(
        selection: selection(
          items: const [],
          states: const {DiscoveryFieldState.noMatch},
        ),
        onOpen: (_) {},
        onResetCriteria: () {},
      ),
    );

    expect(
      find.text('Aucun résultat pour ces critères.'),
      findsOneWidget,
    );
    expect(find.text('Modifier mes critères'), findsOneWidget);
    expect(find.textContaining('hors connexion'), findsNothing);
  });

  testWidgets('offline without snapshot is not rendered as no match', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      child: DiscoveryFieldView(
        selection: selection(
          items: const [],
          states: const {DiscoveryFieldState.offlineNoSnapshot},
          reachability: MakoloReachabilityCue.temporarilyUnavailable,
        ),
        onOpen: (_) {},
        onRetry: () {},
      ),
    );

    expect(
      find.text('Connexion indisponible.'),
      findsOneWidget,
    );
    expect(
      find.text('Aucun résultat pour ces critères.'),
      findsNothing,
    );
  });

  testWidgets('server unavailable names Makolo instead of blaming Internet', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      child: DiscoveryFieldView(
        selection: selection(
          items: const [],
          states: const {DiscoveryFieldState.serverUnavailableNoSnapshot},
          reachability: MakoloReachabilityCue.temporarilyUnavailable,
        ),
        onOpen: (_) {},
        onRetry: () {},
      ),
    );

    expect(
      find.text(
        'Service momentanément indisponible.',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('Hors connexion'), findsNothing);
  });

  testWidgets('offline with snapshot keeps acquired possibilities visible', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      child: DiscoveryFieldView(
        selection: selection(
          states: const {DiscoveryFieldState.offlineWithSnapshot},
          reachability: MakoloReachabilityCue.temporarilyUnavailable,
          failure: MakoloFailureCue.recoverable,
        ),
        onOpen: (_) {},
      ),
    );

    expect(find.text('Formation Data Science'), findsOneWidget);
    expect(find.textContaining('source distante'), findsNothing);
    expect(find.textContaining('hors connexion'), findsNothing);
    expect(find.byType(MakoloNotice), findsNothing);
  });

  testWidgets('critical text scale keeps compact field reachable', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      textScale: 1.6,
      child: DiscoveryExplorationView(selection: selection(), onOpen: (_) {}),
    );

    expect(find.text('Formation Data Science'), findsOneWidget);
    expect(find.byKey(const Key('discover-compact-field')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets('guest share presents external choices without signing in', (
    tester,
  ) async {
    final publicItem = DiscoveryItemPresentation(
      family: 'activity',
      id: 'public-one',
      candidateKey: 'activity:public-one',
      title: 'Possibilité publique',
      summary: 'Une possibilité visible par tous.',
      savedState: 'not_saved',
      capabilities: const {'view'},
      links: const {
        'web': '/discover/items/activity/public-one/',
        'web_share': '/discovery/share/activity/public-one/',
      },
    );
    var requestedSignIn = false;
    await PresentationHarness.pump(
      tester,
      child: DiscoveryShareControl(
        item: publicItem,
        api: null,
        authenticated: false,
        baseUri: Uri.parse('https://makolo.invalid/'),
        onSignIn: () => requestedSignIn = true,
      ),
    );
    await tester.tap(find.byType(PopupMenuButton<String>));
    await tester.pumpAndSettle();
    expect(find.text('Partager avec…'), findsOneWidget);
    expect(find.text('Copier le lien'), findsOneWidget);
    expect(find.text('Afficher le QR'), findsOneWidget);
    expect(find.text('Dans Makolo · connexion requise'), findsOneWidget);
    expect(requestedSignIn, isFalse);
  });

  testWidgets('personal Discovery automatically requests the server next lot', (
    tester,
  ) async {
    final requested = <int>[];
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(hasNext: true),
        onOpen: (_) {},
        onPage: requested.add,
        autoLoadMore: true,
      ),
    );

    expect(find.text('Suivant'), findsNothing);
    expect(find.text('Précédent'), findsNothing);
    expect(find.text('Page 1'), findsNothing);
    await tester.drag(find.byType(ListView).first, const Offset(0, -1800));
    await tester.pump();
    expect(requested, contains(2));
  });

  testWidgets('personal Discovery ends cleanly without further requests', (
    tester,
  ) async {
    final requested = <int>[];
    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: DiscoveryExplorationView(
        selection: selection(
          states: const {DiscoveryFieldState.endOfField},
        ),
        onOpen: (_) {},
        onPage: requested.add,
        autoLoadMore: true,
      ),
    );
    await tester.drag(find.byType(ListView).first, const Offset(0, -1800));
    await tester.pump();
    expect(find.text('Vous avez tout exploré.'), findsOneWidget);
    expect(requested, isEmpty);
    expect(find.text('Suivant'), findsNothing);
  });
}
