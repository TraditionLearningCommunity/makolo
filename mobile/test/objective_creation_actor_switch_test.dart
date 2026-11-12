import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/action_controls.dart';
import 'package:makolo_mobile/features/continuity/objective_create_screen.dart';
import 'package:makolo_mobile/features/continuity/objective_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'fakes.dart';

class _ActorStore implements ActorContextStore {
  ActorContext context = const PersonalActorContext();

  @override
  Future<ActorContext> readActorContext(String profileId) async => context;

  @override
  Future<void> writeActorContext(String profileId, ActorContext next) async {
    context = next;
  }

  @override
  Future<void> removeActorContext(String profileId) async {
    context = const PersonalActorContext();
  }
}

class _DelayedObjectiveApi extends MakoloApiClient {
  _DelayedObjectiveApi()
    : super(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: MemoryTokenStore(
          session: const AuthSession(
            accessToken: 'test',
            refreshToken: 'test',
            profileId: 'viewer',
          ),
        ),
      );

  final Completer<ApiResponse> response = Completer<ApiResponse>();
  int calls = 0;
  String? postedPath;

  @override
  Future<ApiResponse> post(
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) {
    calls++;
    postedPath = path;
    return response.future;
  }
}

void main() {
  testWidgets(
    'confirmed Space creation remains visible after actor changes mid-request',
    (tester) async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'viewer');
      final repository = ObjectiveRepository(
        database: db,
        store: store,
        profileId: 'viewer',
      );
      final controller = await ActorContextController.restore(
        profileId: 'viewer',
        store: _ActorStore(),
      );
      addTearDown(controller.dispose);
      final space = SpaceActorIdentity(id: 'space-a', slug: 'atelier-test');
      await controller.selectSpace(space);
      final api = _DelayedObjectiveApi();
      addTearDown(() => api.close(force: true));
      String? opened;

      await tester.pumpWidget(
        MaterialApp(
          home: ObjectiveCreateScreen(
            kind: 'dossier',
            api: api,
            repository: repository,
            spaceActor: space,
            actorContext: controller,
            onCreated: (id) => opened = id,
          ),
        ),
      );
      await tester.enterText(
        find.byType(TextFormField).first,
        'Réalisation commune',
      );
      await tester.tap(
        find.widgetWithText(MakoloActionButton, 'Créer un dossier'),
      );
      await tester.pump();

      expect(api.calls, 1);
      expect(api.postedPath, contains('context=space&space=atelier-test'));

      await controller.selectPersonal();
      await tester.pump();
      expect(find.text('La création doit être rouverte.'), findsOneWidget);

      // Server confirms the old selected Space, not the newly active actor.
      api.response.complete(
        const ApiResponse(201, '{"id":"confirmed-dossier"}', {}),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('La réalisation a été créée.'), findsOneWidget);
      expect(find.textContaining('l’Espace atelier-test'), findsOneWidget);
      expect(opened, isNull);
      expect(
        tester
            .widget<MakoloActionButton>(
              find.widgetWithText(MakoloActionButton, 'Ouvrir la réalisation'),
            )
            .onPressed,
        isNull,
      );

      // Re-selecting the original actor only opens the confirmed result;
      // it never submits a second POST.
      await controller.selectSpace(space);
      await tester.pump();
      await tester.tap(find.text('Ouvrir la réalisation'));
      expect(opened, 'confirmed-dossier');
      expect(api.calls, 1);
    },
  );
}
