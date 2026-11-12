import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/journey/journey_detail_screen.dart';
import 'package:makolo_mobile/features/journey/journey_repository.dart';
import 'package:makolo_mobile/features/journey/journey_selector.dart';

Widget _journey(String id, JourneyRepository repository) => MaterialApp(
  home: JourneyDetailScreen(
    journeyId: id,
    repository: repository,
    onOpenForm: (_) {},
    onOpenRequirement: (_) {},
    onOpenResources: (_) {},
    onOpenActivity: (_) {},
    onOpenOccurrence: (_) {},
    onOpenAccess: (_) {},
    onOpenDayOf: (_) {},
    onOpenLive: (_) {},
  ),
);

Map<String, dynamic> _payload(
  String title, {
  String status = 'in_progress',
  bool withSteps = false,
  bool withAction = false,
}) => {
  'representation': {'title': title, 'kind_label': 'Inscription'},
  'state': {
    'code': status,
    'label': status == 'fulfilled' ? 'Réalisée' : 'En cours',
  },
  'readiness': {
    'state': withAction ? 'action_required' : 'ready',
    'ready': [],
    'actor_interventions': withAction
        ? [
            {
              'key': 'form.1',
              'summary': 'Compléter une information',
              'next': {
                'label': 'Voir mon formulaire',
                'link': '/api/v1/questionnaires/requests/form-1/',
              },
            },
          ]
        : [],
    'waiting': [],
    'blockers': [],
    if (withAction)
      'next': {
        'key': 'form.1',
        'label': 'Voir mon formulaire',
        'link': '/api/v1/questionnaires/requests/form-1/',
      },
  },
  'steps': withSteps
      ? [
          {
            'id': 'step-1',
            'kind': 'submission',
            'title': 'Ma demande est enregistrée',
            'status': 'completed',
            'depends_on': [],
          },
        ]
      : [],
  'forms': withAction
      ? [
          {
            'id': 'form-1',
            'title': 'Mon formulaire',
            'state': 'requested',
            'required': true,
            'capabilities': ['complete_form'],
            'links': {'detail': '/api/v1/questionnaires/requests/form-1/'},
          },
        ]
      : [],
  'requirements': [],
  'capabilities': [],
};

void main() {
  test('an explicit owner denial always hides a retained Journey snapshot', () {
    final p = StoredProjection(
      kind: JourneyRepository.projectionKind,
      resourceKey: 'journey-one',
      schemaVersion: 1,
      receivedAt: DateTime.utc(2026, 11, 9),
      payload: _payload('Ma demande'),
    );
    final denied = const JourneyDetailSelector().select(
      projection: p,
      source: const JourneySourceState(
        invalidated: true,
        lastErrorCode: 'permission_denied',
      ),
      now: DateTime.utc(2026, 11, 9),
    );
    expect(denied.available, isFalse);
    expect(denied.title, isEmpty);

    final transportError = const JourneyDetailSelector().select(
      projection: p,
      source: const JourneySourceState(lastErrorCode: 'timeout'),
      now: DateTime.utc(2026, 11, 9),
    );
    expect(transportError.available, isTrue);
    expect(transportError.title, 'Ma demande');
  });

  test('a completed payment attempt cannot settle a pending obligation', () {
    final p = StoredProjection(
      kind: JourneyRepository.projectionKind,
      resourceKey: 'journey-payment',
      schemaVersion: 1,
      receivedAt: DateTime.utc(2026, 11, 9),
      payload: {
        ..._payload('Régler ma demande'),
        'payment': {
          'obligations': [
            {
              'id': 'payment-obligation',
              'amount': '25.00',
              'currency': 'USD',
              'state': 'pending',
              'payment': {'state': 'succeeded'},
            },
          ],
        },
      },
    );
    final presentation = const JourneyDetailSelector().select(
      projection: p,
      source: JourneySourceState.unknown,
      now: DateTime.utc(2026, 11, 9),
    );
    expect(presentation.payments.single.state, 'pending');
    expect(presentation.payments.single.obligationId, 'payment-obligation');
  });

  testWidgets('a terminal Journey has an outcome and no fabricated action', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    await store.putProjection(
      kind: JourneyRepository.projectionKind,
      resourceKey: 'journey-one',
      schemaVersion: 1,
      payload: _payload(
        'Recevoir mon badge',
        status: 'fulfilled',
        withAction: true,
      ),
    );
    final repo = JourneyRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
    );
    await tester.pumpWidget(_journey('journey-one', repo));
    await tester.pumpAndSettle();
    expect(find.text('Recevoir mon badge'), findsOneWidget);
    expect(find.text('Démarche réalisée'), findsOneWidget);
    expect(find.text('Pour avancer'), findsNothing);
  });

  testWidgets('Service decision remains distinct from an active Journey', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-service');
    await store.putProjection(
      kind: JourneyRepository.projectionKind,
      resourceKey: 'journey-service',
      schemaVersion: 1,
      payload: {
        ..._payload('Demander une bourse'),
        'service_result': {
          'code': 'under_review',
          'label': 'En revue',
        },
      },
    );
    final repository = JourneyRepository(
      database: database,
      store: store,
      profileId: 'profile-service',
    );
    await tester.pumpWidget(_journey('journey-service', repository));
    await tester.pumpAndSettle();
    expect(find.text('Réponse de l’organisme'), findsOneWidget);
    expect(find.text('En revue'), findsOneWidget);
    expect(find.text('Démarche réalisée'), findsNothing);
  });

  testWidgets('a Journey switches Profiles without showing old local facts', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final first = ProfileStore(database, 'profile-a');
    final second = ProfileStore(database, 'profile-b');
    for (final entry in [
      (first, 'Badge personnel A'),
      (second, 'Badge personnel B'),
    ]) {
      await entry.$1.putProjection(
        kind: JourneyRepository.projectionKind,
        resourceKey: 'same-id',
        schemaVersion: 1,
        payload: _payload(entry.$2),
      );
    }
    JourneyRepository repo(ProfileStore store, String profileId) =>
        JourneyRepository(
          database: database,
          store: store,
          profileId: profileId,
        );

    await tester.pumpWidget(_journey('same-id', repo(first, 'profile-a')));
    await tester.pumpAndSettle();
    expect(find.text('Badge personnel A'), findsOneWidget);
    await tester.pumpWidget(_journey('same-id', repo(second, 'profile-b')));
    await tester.pumpAndSettle();
    expect(find.text('Badge personnel B'), findsOneWidget);
    expect(find.text('Badge personnel A'), findsNothing);
  });

  testWidgets('compact and wide layouts show the same owner facts', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    await store.putProjection(
      kind: JourneyRepository.projectionKind,
      resourceKey: 'journey-one',
      schemaVersion: 1,
      payload: _payload(
        'Recevoir mon badge de conférence pour une participation très attendue',
        withSteps: true,
        withAction: true,
      ),
    );
    final repo = JourneyRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
    );
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    tester.view.devicePixelRatio = 1;
    for (final size in [const Size(340, 750), const Size(1140, 810)]) {
      tester.view.physicalSize = size;
      await tester.pumpWidget(_journey('journey-one', repo));
      await tester.pumpAndSettle();
      expect(find.text('MON OBJECTIF'), findsOneWidget);
      expect(find.text('Où j’en suis'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('Pour avancer'),
        160,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Pour avancer'), findsOneWidget);
      expect(tester.takeException(), isNull);
    }
  });
}
