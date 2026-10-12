import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/app/router.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/space/space_insight_surfaces.dart';
import 'package:makolo_mobile/features/space/space_work_surface.dart';
import 'package:makolo_mobile/features/space/space_work_collection_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/presentation/contracts/space_presentation.dart';

import 'dio_testing.dart';
import 'fakes.dart';

class _ActorStore implements ActorContextStore {
  ActorContext value = const PersonalActorContext();
  @override
  Future<ActorContext> readActorContext(String profileId) async => value;
  @override
  Future<void> writeActorContext(String profileId, ActorContext context) async {
    value = context;
  }

  @override
  Future<void> removeActorContext(String profileId) async {
    value = const PersonalActorContext();
  }
}

const _pilot = <String, dynamic>{
  'capabilities': {'view_financials': false},
  'sections': {
    'analytics': {
      'state': 'known',
      'generated_at': '2026-10-12T08:00:00Z',
      'coverage': {'kind': 'latest_visible_events', 'limit': 40},
      'signals': [
        {
          'title': 'Des personnes attendent une place disponible.',
          'summary': '3 demandes dans le portefeuille couvert.',
          'why': 'Vérifier les possibilités de délivrance.',
          'owner': 'Analytics',
          'evidence': {'metric_key': 'waitlist_waiting', 'value': 3},
          'uncertainty': 'Ce constat ne prouve pas une saturation globale.',
        },
      ],
      'metrics': [
        {
          'key': 'active_tickets',
          'state': 'known',
          'value': 0,
          'unit': 'count',
        },
        {
          'key': 'attendance_percent',
          'state': 'insufficient_data',
          'value': null,
        },
      ],
      'money': [
        {'currency': 'USD', 'gross': '10', 'refunds': '0', 'net': '10'},
      ],
    },
  },
};

void main() {
  testWidgets(
    'work continuation retries the same page and drops revoked content',
    (tester) async {
      final actors = await ActorContextController.restore(
        profileId: 'viewer',
        store: _ActorStore(),
      );
      addTearDown(actors.dispose);
      final space = SpaceActorIdentity(id: 'space-a', slug: 'atelier');
      await actors.selectSpace(
        space,
        perspective: ActorPerspective.opaque('mandate:viewer'),
      );
      var attempts = 0;
      var revoked = false;
      final client = MockClient((request) async {
        expect(request.url.queryParameters['responsibility'], 'mandate:viewer');
        final offset = int.parse(request.url.queryParameters['offset']!);
        if (offset == 20 && ++attempts == 1) {
          return const MockResponse('{"detail":"Unavailable"}', 503);
        }
        if (revoked) return const MockResponse('{"detail":"Not found"}', 404);
        return MockResponse(
          jsonEncode({
            'space': {'id': 'space-a', 'slug': 'atelier'},
            'responsibility': 'mandate:viewer',
            'primary_business_label': 'Créations',
            'page': {'offset': offset, 'limit': 20},
            'sections': {
              'preparation': {
                'representation': 'À préparer',
                'has_more': true,
                'items': [
                  {
                    'title': 'Œuvre A',
                    'source': {'kind': 'activity', 'id': 'a'},
                    'capabilities': ['view'],
                  },
                  if (offset > 0)
                    {
                      'title': 'Œuvre B',
                      'source': {'kind': 'activity', 'id': 'b'},
                      'capabilities': ['view'],
                    },
                ],
              },
            },
          }),
          200,
        );
      });
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'test',
          refreshToken: 'test',
          profileId: 'viewer',
        ),
      );
      final runtime = AppRuntime(
        tokens: tokens,
        session: null,
        recovery: SessionRecoveryController(),
        actorContext: actors,
        api: MakoloApiClient(
          baseUri: Uri.parse('https://makolo.invalid/'),
          dio: client.dio,
          tokenStore: tokens,
        ),
      );
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: SpaceWorkCollectionScreen(
            runtime: runtime,
            actor: actors.value as SpaceActorContext,
            section: 'preparation',
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Œuvre A'), findsOneWidget);
      await tester.tap(find.text('Afficher la suite'));
      await tester.pumpAndSettle();
      expect(find.textContaining('La suite est indisponible'), findsOneWidget);
      expect(find.text('Œuvre A'), findsOneWidget);
      await tester.tap(find.text('Réessayer'));
      await tester.pumpAndSettle();
      expect(find.text('Œuvre A'), findsOneWidget);
      expect(find.text('Œuvre B'), findsOneWidget);
      revoked = true;
      await tester.tap(find.text('Afficher la suite'));
      await tester.pumpAndSettle();
      expect(find.text('Œuvre A'), findsNothing);
      expect(find.textContaining('n’est plus accessible'), findsOneWidget);
    },
  );
  test(
    'knowledge labels preserve zero and distinguish unknown from insufficient',
    () {
      expect(spaceMetricValue({'state': 'known', 'value': 0}), '0');
      expect(spaceMetricValue({'state': 'known', 'value': null}), 'Inconnu');
      expect(
        spaceMetricValue({'state': 'insufficient_data'}),
        'Données insuffisantes',
      );
      expect(
        spaceTimingLines({
          'start_date': '2026-10-12',
          'start_time': '14:00',
          'timezone': 'Africa/Lubumbashi',
        }).single,
        contains('Africa/Lubumbashi'),
      );
      expect(
        spaceOwnerRoute(slug: 'a', kind: 'private_secret', id: '1'),
        isNull,
      );
    },
  );

  for (final width in [360.0, 800.0, 1280.0]) {
    testWidgets('Pilot evidence remains readable at $width with large text', (
      tester,
    ) async {
      tester.view.physicalSize = Size(width, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: MediaQuery(
            data: MediaQueryData(
              size: Size(width, 1000),
              textScaler: const TextScaler.linear(1.6),
            ),
            child: const Scaffold(body: SpacePilotSurface(payload: _pilot)),
          ),
        ),
      );
      expect(find.textContaining('40 derniers événements'), findsOneWidget);
      expect(find.text('Période de comparaison non établie.'), findsOneWidget);
      await tester.tap(
        find.text('Des personnes attendent une place disponible.'),
      );
      await tester.pumpAndSettle();
      expect(find.text('Demandes en liste d’attente : 3'), findsOneWidget);
      expect(
        find.text('Ce constat ne prouve pas une saturation globale.'),
        findsOneWidget,
      );
      expect(find.text('Montants par devise'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets(
    'two owner relations to one Profile remain independently recognizable',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: Scaffold(
            body: ListView(
              children: [
                SpaceRelationshipCard(
                  row: const {
                    'kind': 'team_member',
                    'profile': {'id': 'same', 'name': 'Alex'},
                    'relation_type': 'Collaborateur · Équipe',
                    'owner_identity': 'Équipe terrain',
                  },
                  onOpen: () {},
                ),
                SpaceRelationshipCard(
                  row: const {
                    'kind': 'crm_contact',
                    'profile': {'id': 'same', 'name': 'Alex'},
                    'relation_type': 'Contact CRM',
                    'owner_identity': 'Contact terrain',
                  },
                  onOpen: () {},
                ),
              ],
            ),
          ),
        ),
      );
      expect(find.text('Alex'), findsNWidgets(2));
      expect(find.text('Collaborateur · Équipe'), findsOneWidget);
      expect(find.text('Contact CRM'), findsOneWidget);
    },
  );

  for (final label in [
    'Activités',
    'Commerce',
    'Créations',
    'Initiatives',
    'Prestations',
    'Productions',
    'Programmes',
    'Transport',
  ]) {
    testWidgets('$label work opens the existing owner destination', (
      tester,
    ) async {
      final router = GoRouter(
        routes: [
          GoRoute(
            path: '/',
            builder: (_, _) => Scaffold(
              body: SpaceWorkSurface(
                payload: {
                  'space': {'slug': 'atelier'},
                  'primary_business_label': label,
                  'sections': {
                    'preparation': {
                      'representation': 'À préparer',
                      'has_more': true,
                      'items': [
                        {
                          'title': 'Travail concret',
                          'source': {'kind': 'activity', 'id': 'a-1'},
                          'capabilities': ['view'],
                        },
                      ],
                    },
                  },
                },
              ),
            ),
          ),
          GoRoute(
            path: '/space/:slug/retrieval/:kind/:id',
            builder: (_, state) =>
                Scaffold(body: Text('Owner ${state.pathParameters['id']}')),
          ),
        ],
      );
      addTearDown(router.dispose);
      await tester.pumpWidget(
        MaterialApp.router(theme: buildMakoloTheme(), routerConfig: router),
      );
      expect(find.textContaining('Aperçu partiel'), findsOneWidget);
      await tester.tap(find.text('Travail concret'));
      await tester.pumpAndSettle();
      expect(find.text('Owner a-1'), findsOneWidget);
    });
  }

  testWidgets(
    'production owner route revalidates responsibility and clears data on actor switch',
    (tester) async {
      final actors = await ActorContextController.restore(
        profileId: 'viewer',
        store: _ActorStore(),
      );
      addTearDown(actors.dispose);
      final space = SpaceActorIdentity(id: 'space-a', slug: 'atelier');
      await actors.selectSpace(space);
      final client = MockClient((request) async {
        expect(
          request.url.path,
          '/api/v1/organizations/workspaces/atelier/work/',
        );
        expect(request.url.queryParameters['kind'], 'activity');
        expect(request.url.queryParameters['id'], 'a-1');
        return MockResponse(
          jsonEncode({
            'space': {'id': 'space-a'},
            'primary_business_label': 'Créations',
            'selection': {
              'source': {'kind': 'activity', 'id': 'a-1'},
              'title': 'Œuvre autorisée',
              'state': 'draft',
              'timing': {},
              'context': {},
            },
          }),
          200,
        );
      });
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'test',
          refreshToken: 'test',
          profileId: 'viewer',
        ),
      );
      final runtime = AppRuntime(
        tokens: tokens,
        session: tokens.session,
        recovery: SessionRecoveryController()
          ..restoreLaunchLocation('/space/atelier/retrieval/activity/a-1'),
        actorContext: actors,
        api: MakoloApiClient(
          baseUri: Uri.parse('https://makolo.invalid/'),
          dio: client.dio,
          tokenStore: tokens,
        ),
      );
      final router = createMakoloRouter(
        runtime,
        onAuthenticationChanged: () {},
      );
      addTearDown(router.dispose);
      await tester.pumpWidget(
        MaterialApp.router(theme: buildMakoloTheme(), routerConfig: router),
      );
      await tester.pumpAndSettle();
      expect(find.text('Œuvre autorisée'), findsOneWidget);
      expect(find.text('À préparer'), findsOneWidget);
      await actors.selectPersonal();
      await tester.pumpAndSettle();
      expect(find.text('Œuvre autorisée'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );
}
