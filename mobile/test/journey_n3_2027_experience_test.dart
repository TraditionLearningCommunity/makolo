import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/journey/journey_detail_screen.dart';
import 'package:makolo_mobile/features/journey/journey_repository.dart';
import 'package:makolo_mobile/features/preparation/preparation_repository.dart';

Future<void> pumpJourney(
  WidgetTester tester,
  Map<String, dynamic> payload, {
  Map<String, dynamic>? resources,
  void Function(String)? onForm,
  void Function(String)? onResources,
  void Function(String)? onPayment,
}) async {
  final db = MakoloDatabase.memory();
  addTearDown(db.close);
  final store = ProfileStore(db, 'journey-2027-test');
  await store.putProjection(
    kind: JourneyRepository.projectionKind,
    resourceKey: 'journey-2027',
    schemaVersion: 1,
    payload: payload,
  );
  if (resources != null) {
    await store.putProjection(
      kind: PreparationResourcesRepository.projectionKind,
      resourceKey: 'journey-2027',
      schemaVersion: 1,
      payload: resources,
    );
  }
  await tester.pumpWidget(
    MaterialApp(
      home: JourneyDetailScreen(
        journeyId: 'journey-2027',
        repository: JourneyRepository(
          database: db,
          store: store,
          profileId: 'journey-2027-test',
        ),
        resourcesRepository: PreparationResourcesRepository(
          database: db,
          store: store,
          profileId: 'journey-2027-test',
        ),
        onOpenPaymentObligation: onPayment,
        onOpenForm: (form) => onForm?.call(form.id),
        onOpenRequirement: (_) {},
        onOpenResources: (_) => onResources?.call('resources'),
        onOpenActivity: (_) {},
        onOpenOccurrence: (_) {},
        onOpenAccess: (_) {},
        onOpenDayOf: (_) {},
        onOpenLive: (_) {},
      ),
    ),
  );
  await tester.pumpAndSettle();
}

const _empty = <String, dynamic>{
  'identity': {'workflow': 'registration'},
  'representation': {'title': 'Inscription à une activité'},
  'state': {'code': 'confirmed', 'label': 'Confirmée'},
  'readiness': {
    'state': 'ready',
    'ready': [],
    'actor_interventions': [],
    'waiting': [],
    'blockers': [],
  },
  'steps': [],
  'forms': [],
  'requirements': [],
  'capabilities': [],
};

void main() {
  test('local Ongoing summary never resolves an unrelated Journey', () {
    final ongoing = StoredProjection(
      kind: 'personal.ongoing',
      schemaVersion: 1,
      receivedAt: DateTime.utc(2026, 11, 14),
      payload: const {
        'items': [
          {
            'source': {'kind': 'journey', 'id': 'known-journey'},
            'title': 'Inscription connue',
          },
          {
            'source': {'kind': 'access', 'id': 'other-journey'},
            'title': 'Accès sans Journey',
          },
        ],
      },
    );
    expect(
      JourneyRepository.knownOngoingSummary(
        ongoing,
        'known-journey',
      )?['title'],
      'Inscription connue',
    );
    expect(
      JourneyRepository.knownOngoingSummary(
        ongoing,
        'other-journey',
      ),
      isNull,
    );
  });

  testWidgets('local Ongoing cover remains visible before detail acquisition', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'profile-local');
    await store.putProjection(
      kind: 'personal.ongoing',
      resourceKey: '',
      schemaVersion: 1,
      payload: const {
        'items': [
          {
            'source': {'kind': 'journey', 'id': 'journey-local'},
            'title': 'Mon inscription locale',
            'timing': {'start_date': '2026-12-11'},
            'place': {'name': 'Lubumbashi'},
          },
        ],
      },
    );
    final journeys = JourneyRepository(
      database: db,
      store: store,
      profileId: 'profile-local',
    );
    await tester.pumpWidget(
      MaterialApp(
        home: JourneyDetailScreen(
          journeyId: 'journey-local',
          repository: journeys,
          onOpenForm: (_) {},
          onOpenRequirement: (_) {},
          onOpenResources: (_) {},
          onOpenActivity: (_) {},
          onOpenOccurrence: (_) {},
          onOpenAccess: (_) {},
          onOpenDayOf: (_) {},
          onOpenLive: (_) {},
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Mon inscription locale'), findsOneWidget);
    expect(find.byKey(const Key('journey-partial-local')), findsOneWidget);
    expect(find.byKey(const Key('journey-relative-day')), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('technical Readiness checks do not create a false preparation', (
    tester,
  ) async {
    await pumpJourney(tester, {
      ..._empty,
      'readiness': {
        'state': 'ready',
        'ready': [
          {
            'key': 'state-ok',
            'summary': "L'état de la démarche permet de continuer.",
          },
          {'key': 'no-blocker', 'summary': 'Aucun obstacle actif.'},
          {'key': 'occurrence-ok', 'summary': "L'occurrence est exploitable."},
        ],
        'actor_interventions': [],
        'waiting': [],
        'blockers': [],
      },
    });
    expect(find.text('Ma préparation'), findsNothing);
    expect(find.text('3 points vérifiés'), findsNothing);
    expect(find.byKey(const Key('journey-identity')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('small screens expose scrollable, owner-linked resources', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 760);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    var opened = false;
    await pumpJourney(
      tester,
      {
        ..._empty,
        'resources': {
          'link': '/api/v1/preparation/journeys/journey-2027/resources/',
        },
      },
      resources: const {
        'items': [
          {
            'id': 'pdf',
            'title': 'Guide de préparation',
            'kind': 'file',
            'mime_type': 'application/pdf',
          },
          {'id': 'notes', 'title': 'Informations pratiques', 'kind': 'text'},
          {'id': 'site', 'title': 'Plan du site', 'kind': 'url'},
          {'id': 'schedule', 'title': 'Planning', 'kind': 'text'},
        ],
      },
      onResources: (_) => opened = true,
    );
    expect(find.byKey(const Key('journey-resource-preview')), findsOneWidget);
    expect(find.text('Voir les 4 ressources'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('Guide de préparation'),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.text('Guide de préparation'));
    expect(opened, isTrue);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Form submission next link opens its known Form owner', (
    tester,
  ) async {
    String? openedForm;
    await pumpJourney(tester, {
      ..._empty,
      'readiness': {
        'state': 'action_required',
        'ready': [],
        'actor_interventions': [],
        'waiting': [],
        'blockers': [],
        'next': {
          'key': 'form-a',
          'label': 'Compléter le formulaire',
          'link': '/api/v1/questionnaires/requests/form-a/submit/',
        },
      },
      'forms': [
        {
          'id': 'form-a',
          'title': 'Mes informations',
          'required': true,
          'state': 'requested',
          'capabilities': ['complete_form'],
          'links': {
            'detail': '/api/v1/questionnaires/requests/form-a/',
            'save': '/api/v1/questionnaires/requests/form-a/save/',
            'submit': '/api/v1/questionnaires/requests/form-a/submit/',
          },
        },
      ],
    }, onForm: (id) => openedForm = id);
    expect(find.text('Pour avancer'), findsOneWidget);
    await tester.tap(find.text('Compléter le formulaire'));
    expect(openedForm, 'form-a');
    expect(tester.takeException(), isNull);
  });

  testWidgets('Payment action only opens a known obligation', (tester) async {
    String? openedPayment;
    await pumpJourney(tester, {
      ..._empty,
      'readiness': {
        'state': 'action_required',
        'ready': [],
        'actor_interventions': [],
        'waiting': [],
        'blockers': [],
        'next': {
          'key': 'payment-a',
          'label': 'Régler le montant',
          'link': '/api/v1/payments/obligations/pay-a/start/',
        },
      },
      'payment': {
        'obligations': [
          {
            'id': 'pay-a',
            'state': 'pending',
            'amount': '25.00',
            'currency': 'USD',
          },
        ],
      },
    }, onPayment: (id) => openedPayment = id);
    await tester.tap(find.text('Régler le montant'));
    expect(openedPayment, 'pay-a');
    expect(tester.takeException(), isNull);
  });
}
