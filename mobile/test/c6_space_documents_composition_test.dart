import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/resources/resource_presentation.dart';
import 'package:makolo_mobile/features/space/space_document_detail_screen.dart';
import 'package:makolo_mobile/features/space/space_documents_screen.dart';
import 'package:makolo_mobile/features/space/space_repository.dart';
import 'package:makolo_mobile/features/space/space_us_resources_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

import 'dio_testing.dart';
import 'fakes.dart';

class _LocalActorStore implements ActorContextStore {
  ActorContext current = const PersonalActorContext();

  @override
  Future<ActorContext> readActorContext(String profileId) async => current;

  @override
  Future<void> writeActorContext(String profileId, ActorContext value) async {
    current = value;
  }

  @override
  Future<void> removeActorContext(String profileId) async {
    current = const PersonalActorContext();
  }
}

void main() {
  testWidgets('Nous resources uses the shared Resources hub presentation', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final actor = await ActorContextController.restore(
      profileId: 'profile-a',
      store: _LocalActorStore(),
    );
    addTearDown(actor.dispose);
    await actor.selectSpace(SpaceActorIdentity(id: 'space-a', slug: 'atelier'));
    final repository = WorkspaceContextRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      actorContext: actor,
    );
    await store.putProjection(
      kind: SpaceSyncKeys.resourcesProjectionKind,
      resourceKey: SpaceSyncKeys.resourcesResourceKey('space-a'),
      schemaVersion: 1,
      payload: {
        'space_id': 'space-a',
        'visibility': 'visible',
        'kind': 'document',
        'count': 2,
        'total_count': 6,
        'counts': {
          'document': 2,
          'asset': 0,
          'template': 2,
          'theme': 1,
          'credential': 0,
          'received_title': 0,
        },
        'items': const [],
        'has_more': false,
        'next_offset': 0,
      },
    );
    await store.putProjection(
      kind: SpaceProjectionKind.us.wireValue,
      resourceKey: SpaceSyncKeys.resourceKey('space-a'),
      schemaVersion: 1,
      payload: {
        'handoffs': {
          'resources': '/space/atelier/us/resources',
        },
      },
    );
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final runtime = AppRuntime(
      tokens: tokens,
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
      recovery: SessionRecoveryController(),
      actorContext: actor,
      database: database,
      store: store,
      space: repository,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: SpaceUsResourcesScreen(runtime: runtime, slug: 'atelier'),
      ),
    );
    await tester.pump();

    expect(find.text('Nos ressources'), findsOneWidget);
    expect(find.byType(ResourceHubEntry), findsNWidgets(6));
    expect(find.text('Nos documents'), findsOneWidget);
    expect(find.text('Nos médias'), findsOneWidget);
    expect(find.text('Nos modèles'), findsOneWidget);
    expect(find.text('Nos thèmes'), findsOneWidget);
    expect(find.text('Passeports émis'), findsNothing);
    expect(find.text('Titres émis'), findsOneWidget);
    expect(find.text('Titres reçus'), findsOneWidget);
    expect(find.text('0'), findsNothing);
    expect(find.text('Ressources de cet Espace'), findsNothing);
    expect(find.byType(ChoiceChip), findsNothing);
    expect(find.byTooltip('Actualiser'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets(
    'Space document detail shares the Resources presentation without duplicate versions',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final actor = await ActorContextController.restore(
        profileId: 'profile-a',
        store: _LocalActorStore(),
      );
      addTearDown(actor.dispose);
      await actor.selectSpace(
        SpaceActorIdentity(id: 'space-a', slug: 'atelier'),
      );
      const documentId = '00000000-0000-4000-8000-000000000001';
      final repository = WorkspaceContextRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        actorContext: actor,
      );
      await store.putProjection(
        kind: SpaceSyncKeys.documentDetailProjectionKind,
        resourceKey: SpaceSyncKeys.documentDetailResourceKey(
          'space-a',
          documentId,
        ),
        schemaVersion: 1,
        payload: {
          'document': {
            'id': documentId,
            'title': 'Statuts du collectif',
            'visibility': 'restricted',
            'latest_version': 1,
            'versions': [
              {
                'id': '00000000-0000-4000-8000-000000000002',
                'number': 1,
                'mime_type': 'application/pdf',
              },
            ],
          },
          'can_manage': true,
          'shares': <Object>[],
        },
      );
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final runtime = AppRuntime(
        tokens: tokens,
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
        recovery: SessionRecoveryController(),
        actorContext: actor,
        database: database,
        store: store,
        space: repository,
      );

      await tester.pumpWidget(
        MaterialApp(
          home: SpaceDocumentDetailScreen(
            runtime: runtime,
            slug: 'atelier',
            documentId: documentId,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byType(ResourceDocumentHeader), findsOneWidget);
      expect(find.text('Statuts du collectif'), findsOneWidget);
      expect(find.text('Version 1'), findsOneWidget);
      expect(find.text('Versions précédentes'), findsNothing);
      expect(find.byTooltip('Historique des versions'), findsNothing);
      expect(find.text('Nouvelle version'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );

  testWidgets(
    'Space documents retain prior list on outage but revoke on 403 or switch',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final actor = await ActorContextController.restore(
        profileId: 'profile-a',
        store: _LocalActorStore(),
      );
      addTearDown(actor.dispose);
      await actor.selectSpace(
        SpaceActorIdentity(id: 'space-a', slug: 'atelier'),
      );
      var failure = 0;
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: tokens,
        dio: MockClient((request) async {
          expect(
            request.url.path,
            '/api/v1/organizations/workspaces/atelier/documents/',
          );
          if (failure != 0) {
            return MockResponse('{"detail":"owner unavailable"}', failure);
          }
          return MockResponse(
            jsonEncode({
              'space_id': 'space-a',
              'count': 1,
              'items': [
                {
                  'id': '00000000-0000-4000-8000-000000000001',
                  'title': 'Document déjà connu',
                  'visibility': 'restricted',
                  'latest_version': 1,
                },
              ],
              'can_manage': true,
              'has_more': false,
              'next_offset': 1,
            }),
            200,
          );
        }).dio,
      );
      addTearDown(api.close);
      final sync = SyncEngine(
        api: api,
        store: store,
        database: database,
        profileId: 'profile-a',
      );
      final repository = WorkspaceContextRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        actorContext: actor,
        sync: sync,
      );
      final runtime = AppRuntime(
        tokens: tokens,
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
        recovery: SessionRecoveryController(),
        actorContext: actor,
        api: api,
        database: database,
        store: store,
        sync: sync,
        space: repository,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: SpaceDocumentsScreen(runtime: runtime, slug: 'atelier'),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Nos documents'), findsOneWidget);
      expect(find.text('1'), findsOneWidget);
      expect(find.text('Document déjà connu'), findsOneWidget);
      expect(find.byTooltip('Ajouter'), findsOneWidget);
      expect(find.byTooltip('Rechercher'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);

      failure = 503;
      await tester.tap(find.byTooltip('Actualiser'));
      await tester.pumpAndSettle();
      expect(find.text('Document déjà connu'), findsOneWidget);
      expect(find.textContaining('dernière consultation'), findsNothing);
      expect(find.textContaining('Actualisation indisponible'), findsNothing);
      expect(
        find.byTooltip('Ajouter'),
        findsNothing,
        reason: 'Old list never grants fresh upload authority',
      );

      failure = 403;
      await tester.tap(find.byTooltip('Actualiser'));
      await tester.pumpAndSettle();
      expect(find.text('Document déjà connu'), findsNothing);
      expect(find.textContaining('non accessibles'), findsOneWidget);

      await actor.selectPersonal();
      await tester.pumpAndSettle();
      expect(find.text('Document déjà connu'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
  testWidgets(
    'An empty Space document snapshot stops claiming completeness after a failed refresh',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final actor = await ActorContextController.restore(
        profileId: 'profile-a',
        store: _LocalActorStore(),
      );
      addTearDown(actor.dispose);
      await actor.selectSpace(
        SpaceActorIdentity(id: 'space-a', slug: 'atelier'),
      );
      var unavailable = false;
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: tokens,
        dio: MockClient((request) async {
          if (unavailable) {
            return MockResponse('{"detail":"unavailable"}', 503);
          }
          return MockResponse(
            jsonEncode({
              'space_id': 'space-a',
              'count': 0,
              'items': <Object>[],
              'can_manage': false,
              'has_more': false,
              'next_offset': 0,
            }),
            200,
          );
        }).dio,
      );
      addTearDown(api.close);
      final sync = SyncEngine(
        api: api,
        store: store,
        database: database,
        profileId: 'profile-a',
      );
      final repository = WorkspaceContextRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        actorContext: actor,
        sync: sync,
      );
      final runtime = AppRuntime(
        tokens: tokens,
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
        recovery: SessionRecoveryController(),
        actorContext: actor,
        api: api,
        database: database,
        store: store,
        sync: sync,
        space: repository,
      );

      await tester.pumpWidget(
        MaterialApp(
          home: SpaceDocumentsScreen(runtime: runtime, slug: 'atelier'),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Aucun document pour le moment.'), findsOneWidget);

      unavailable = true;
      await tester.tap(find.byTooltip('Actualiser'));
      await tester.pumpAndSettle();
      expect(find.text('Aucun document pour le moment.'), findsNothing);
      expect(find.text('Aucun document à afficher.'), findsOneWidget);
      expect(find.textContaining('dernière consultation'), findsNothing);
      expect(find.text('0'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
