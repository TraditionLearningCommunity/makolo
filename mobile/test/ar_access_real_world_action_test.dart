import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/access/access_repository.dart';
import 'package:makolo_mobile/features/access/access_selector.dart';
import 'package:makolo_mobile/features/day_of/day_of_repository.dart';
import 'package:makolo_mobile/features/day_of/day_of_screen.dart';
import 'package:makolo_mobile/features/day_of/day_of_selector.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
import 'fakes.dart';

Map<String, dynamic> envelope(String projection, Map<String, dynamic> data) {
  return {
    'meta': {
      'projection': projection,
      'schema_version': 1,
      'generated_at': '2026-09-30T15:00:00Z',
    },
    'data': data,
  };
}

Map<String, dynamic> accessPayload({
  String relationship = 'beneficiary',
  bool openDayOf = true,
}) {
  return {
    'identity': {'kind': 'access', 'id': 'access-1'},
    'right': {
      'state': 'valid',
      'single_use': true,
      'valid_from': '2026-09-30T14:00:00Z',
      'valid_until': '2026-10-01T14:00:00Z',
    },
    'holder': {'relationship': relationship},
    'activity': {
      'kind': 'activity',
      'id': 'activity-1',
      'title': 'Départ Lubumbashi — Kolwezi',
      'link': '/api/v1/activities/activity-1/',
    },
    'occurrence': {
      'kind': 'occurrence',
      'id': 'occurrence-1',
      'link': '/api/v1/occurrences/occurrence-1/',
    },
    'journey': relationship == 'beneficiary'
        ? {
            'kind': 'journey',
            'id': 'journey-1',
            'link': '/api/v1/me/journeys/journey-1/',
          }
        : null,
    'capabilities': openDayOf ? ['open_day_of'] : <String>[],
    'links': {
      'self': '/api/v1/me/accesses/access-1/',
      if (openDayOf) 'day_of': '/api/v1/me/occurrences/occurrence-1/day-of/',
    },
  };
}

Map<String, dynamic> dayOfPayload({bool presentCredentialCapability = true}) {
  return {
    'identity': {'kind': 'occurrence_day_of', 'occurrence_id': 'occurrence-1'},
    'activity': {
      'kind': 'activity',
      'id': 'activity-1',
      'title': 'Départ Lubumbashi — Kolwezi',
    },
    'occurrence': {
      'kind': 'occurrence',
      'id': 'occurrence-1',
      'label': 'Départ de 16 h',
      'state': 'scheduled',
    },
    'situation': {
      'temporal_relation': 'arrival',
      'occurrence_state': 'scheduled',
      'current_position': {
        'state': 'unknown',
        'truth': 'unknown',
        'reason': 'participant_position_not_observed',
      },
      'next': {
        'type': 'access',
        'reason': 'access_required',
        'label': 'Présentez votre billet',
        'source': 'access',
        'truth': 'observed',
      },
      'representation': {'kind': 'access', 'reason': 'access_required'},
    },
    'timing': {
      'truth': 'planned',
      'kind': 'datetime',
      'timezone': 'Africa/Lubumbashi',
      'start_at': '2026-09-30T16:00:00+02:00',
    },
    'spatial': {
      'current_position': {
        'state': 'unknown',
        'truth': 'unknown',
        'reason': 'participant_position_not_observed',
      },
      'destination': {
        'truth': 'planned',
        'id': 'place-1',
        'name': 'Agence Mulykap',
        'address_line': 'Centre-ville',
        'locality': 'Lubumbashi',
        'timezone': 'Africa/Lubumbashi',
        'access_instructions': 'Présentez-vous au guichet départ.',
      },
      'zone': null,
      'mobility': {
        'truth': 'unknown',
        'state': 'unknown',
        'recommended_departure': null,
        'itinerary_url': null,
      },
      'hazards': [
        {
          'kind': 'traffic',
          'severity': 'medium',
          'summary': 'Circulation dense à proximité.',
          'source': 'operations',
          'truth': 'observed',
        },
      ],
    },
    'access': [
      {
        'identity': {'kind': 'access', 'id': 'access-1'},
        'state': 'valid',
        'usable': true,
        'truth': 'observed',
        'validity': {
          'from': '2026-09-30T14:00:00Z',
          'until': '2026-10-01T14:00:00Z',
        },
        'credential': {'available': true, 'type': 'qr', 'presentable': true},
        'capabilities': [
          'open_access',
          if (presentCredentialCapability) 'present_credential',
        ],
        'links': {
          'detail': '/api/v1/me/accesses/access-1/',
          'credential': '/api/v1/me/accesses/access-1/credential/',
        },
      },
    ],
    'queue': [
      {
        'id': 'entry-1',
        'queue_id': 'queue-1',
        'label': 'Embarquement',
        'checkpoint_id': null,
        'state': 'waiting',
        'position': 4,
        'called_at': null,
        'truth': 'observed',
        'links': {
          'collection':
              '/api/v1/operations/occurrences/occurrence-1/queues/me/',
          'entry': '/api/v1/operations/queues/queue-1/entries/me/',
        },
      },
    ],
    'placement': [
      {
        'plan_id': 'plan-1',
        'plan': 'Bus 1',
        'unit_id': 'unit-1',
        'unit': 'Siège 12',
        'parent_unit': 'Rangée 3',
        'truth': 'observed',
        'links': {
          'collection':
              '/api/v1/operations/occurrences/occurrence-1/placements/me/',
        },
      },
    ],
    'checkpoints': {
      'items': [],
      'next': {
        'id': 'checkpoint-1',
        'label': 'Contrôle billet',
        'state': 'pending',
        'blocked_reason': null,
        'truth': 'observed',
      },
      'links': {
        'collection':
            '/api/v1/operations/occurrences/occurrence-1/checkpoints/me/',
      },
    },
    'readiness': {
      'state': 'action_required',
      'ready': [],
      'actor_interventions': [
        {
          'key': 'access.present',
          'state': 'action_required',
          'reason': 'present_access',
          'summary': 'Présentez votre billet au contrôle.',
          'source': 'access',
        },
      ],
      'waiting': [],
      'blockers': [],
    },
    'completion': null,
    'capabilities': [
      'open_occurrence',
      'open_live',
      if (presentCredentialCapability) 'present_credential',
    ],
    'links': {
      'self': '/api/v1/me/occurrences/occurrence-1/day-of/',
      'occurrence': '/api/v1/occurrences/occurrence-1/',
      'activity': '/api/v1/activities/activity-1/',
      'operational_readiness':
          '/api/v1/operations/occurrences/occurrence-1/readiness/',
      'live': '/api/v1/operations/occurrences/occurrence-1/live/',
    },
  };
}

void main() {
  test(
    'Access detail is stored as a Profile-scoped keyed owner snapshot',
    () async {
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final client = MockClient((request) async {
        expect(request.url.path, '/api/v1/me/accesses/access-1/');
        return MockResponse(
          jsonEncode(
            envelope(AccessRepository.projectionKind, accessPayload()),
          ),
          200,
        );
      });
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final storeA = ProfileStore(database, 'profile-a');
      final storeB = ProfileStore(database, 'profile-b');
      final sync = SyncEngine(
        api: MakoloApiClient(
          baseUri: Uri.parse('https://makolo.invalid/'),
          dio: client.dio,
          tokenStore: tokens,
        ),
        store: storeA,
        database: database,
        profileId: 'profile-a',
      );
      final repository = AccessRepository(
        database: database,
        store: storeA,
        profileId: 'profile-a',
        sync: sync,
      );

      await repository.refreshDetail('access-1');

      final local = await repository.readDetail('access-1');
      final otherProfile = await storeB.readProjection(
        AccessRepository.projectionKind,
        resourceKey: 'access-1',
      );
      final presentation = const AccessDetailSelector().select(
        projection: local,
        source: await repository.readSource('access-1'),
        now: DateTime.utc(2026, 9, 30, 15, 5),
      );

      expect(local?.payload.toString(), isNot(contains('credential')));
      expect(local?.payload.toString(), isNot(contains('qr')));
      expect(otherProfile, isNull);
      expect(presentation.activityTitle, 'Départ Lubumbashi — Kolwezi');
      expect(presentation.canOpenDayOf, isTrue);
      expect(presentation.dayOf?.occurrenceId, 'occurrence-1');
    },
  );

  test(
    'buyer visibility never becomes beneficiary action authority locally',
    () {
      final projection = StoredProjection(
        kind: AccessRepository.projectionKind,
        resourceKey: 'access-1',
        schemaVersion: 1,
        payload: accessPayload(
          relationship: 'purchased_for_other',
          openDayOf: true,
        ),
        receivedAt: DateTime.utc(2026, 9, 30, 15),
      );

      final presentation = const AccessDetailSelector().select(
        projection: projection,
        source: AccessSourceState.unknown,
        now: DateTime.utc(2026, 9, 30, 15, 5),
      );

      expect(presentation.isBeneficiary, isFalse);
      expect(presentation.canOpenDayOf, isFalse);
      expect(presentation.journeyId, isNull);
    },
  );

  test(
    'credential is fetched directly and never persisted in the general store',
    () async {
      const secretPayload = 'signed-credential-secret';
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final client = MockClient((request) async {
        expect(request.url.path, '/api/v1/me/accesses/access-1/credential/');
        return MockResponse(
          jsonEncode(
            envelope(AccessRepository.credentialProjectionKind, {
              'access': {'kind': 'access', 'id': 'access-1'},
              'relationship': 'beneficiary',
              'holder': null,
              'representation': {
                'credential_type': 'qr',
                'payload': secretPayload,
                'issued_at': '2026-09-30T15:00:00Z',
              },
            }),
          ),
          200,
          headers: const {
            'content-type': 'application/json',
            'cache-control': 'private, no-store',
          },
        );
      });
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final repository = AccessRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        api: MakoloApiClient(
          baseUri: Uri.parse('https://makolo.invalid/'),
          dio: client.dio,
          tokenStore: tokens,
        ),
      );

      final credential = await repository.fetchCredential(
        accessId: 'access-1',
        path: '/api/v1/me/accesses/access-1/credential/',
      );

      expect(credential.payload, secretPayload);
      expect(credential.credentialType, 'qr');
      expect(
        await store.readProjection(
          AccessRepository.credentialProjectionKind,
          resourceKey: 'access-1',
        ),
        isNull,
      );
    },
  );

  test(
    'Day-of keeps owner-provided operational facts without local inference',
    () async {
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final client = MockClient((request) async {
        expect(request.url.path, '/api/v1/me/occurrences/occurrence-1/day-of/');
        return MockResponse(
          jsonEncode(envelope(DayOfRepository.projectionKind, dayOfPayload())),
          200,
        );
      });
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final sync = SyncEngine(
        api: MakoloApiClient(
          baseUri: Uri.parse('https://makolo.invalid/'),
          dio: client.dio,
          tokenStore: tokens,
        ),
        store: store,
        database: database,
        profileId: 'profile-a',
      );
      final repository = DayOfRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        sync: sync,
      );

      await repository.refreshDetail('occurrence-1');

      final presentation = const DayOfSelector().select(
        projection: await repository.readDetail('occurrence-1'),
        source: await repository.readSource('occurrence-1'),
        now: DateTime.utc(2026, 9, 30, 15, 5),
      );

      expect(presentation.nextLabel, 'Présentez votre billet');
      expect(presentation.queue.single.position, 4);
      expect(presentation.placements.single.unit, 'Siège 12');
      expect(presentation.nextCheckpoint?.label, 'Contrôle billet');
      expect(presentation.accesses.single.canPresentCredential, isTrue);
      expect(presentation.canOpenLive, isTrue);
    },
  );

  testWidgets('Day Of keeps remote live action visible but disabled offline', (
    tester,
  ) async {
    var openedLive = false;

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: DayOfLiveAction(
            livePath: '/api/v1/operations/occurrences/occurrence-1/live/',
            remoteActionsAvailable: false,
            onOpenLive: (_) => openedLive = true,
          ),
        ),
      ),
    );

    final live = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Voir la situation en direct'),
    );
    expect(live.onPressed, isNull);
    expect(find.text('Connexion requise'), findsOneWidget);
    expect(openedLive, isFalse);
  });

  test('credential presentation requires the owner capability even when summary says presentable', () {
    final projection = StoredProjection(
      kind: DayOfRepository.projectionKind,
      resourceKey: 'occurrence-1',
      schemaVersion: 1,
      payload: dayOfPayload(presentCredentialCapability: false),
      receivedAt: DateTime.utc(2026, 9, 30, 15),
    );

    final presentation = const DayOfSelector().select(
      projection: projection,
      source: DayOfSourceState.unknown,
      now: DateTime.utc(2026, 9, 30, 15, 5),
    );

    expect(presentation.accesses.single.canPresentCredential, isFalse);
    expect(presentation.canOpenLive, isTrue);
  });

  test('owner 404 invalidates only the keyed Access snapshot', () async {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    await store.putProjection(
      kind: AccessRepository.projectionKind,
      resourceKey: 'access-1',
      schemaVersion: 1,
      payload: accessPayload(),
    );
    await store.putProjection(
      kind: AccessRepository.projectionKind,
      resourceKey: 'access-2',
      schemaVersion: 1,
      payload: accessPayload(),
    );
    final sync = SyncEngine(
      api: MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        dio: MockClient(
          (_) async => const MockResponse('{"detail":"Not found."}', 404),
        ).dio,
        tokenStore: tokens,
      ),
      store: store,
      database: database,
      profileId: 'profile-a',
    );
    final repository = AccessRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: sync,
    );

    await repository.refreshDetail('access-1');

    expect(await repository.readDetail('access-1'), isNull);
    expect(
      await store.readProjection(
        AccessRepository.projectionKind,
        resourceKey: 'access-2',
      ),
      isNotNull,
    );
    expect((await repository.readSource('access-1')).invalidated, isTrue);
  });
}
