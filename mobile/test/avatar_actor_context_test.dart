import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/space/space_repository.dart';
import 'package:makolo_mobile/navigation/avatar_sheet.dart';
import 'package:makolo_mobile/navigation/profile_avatar_image.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

import 'fakes.dart';

class _ActorPreferences implements ActorContextStore {
  ActorContext _actor = const PersonalActorContext();

  @override
  Future<ActorContext> readActorContext(String _) async => _actor;

  @override
  Future<void> writeActorContext(String _, ActorContext value) async {
    _actor = value;
  }

  @override
  Future<void> removeActorContext(String _) async {
    _actor = const PersonalActorContext();
  }
}

void main() {
  testWidgets(
    'Avatar sheet shows active Space and connected Profile separately',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      await store.putProjection(
        kind: 'personal.me',
        schemaVersion: 1,
        payload: {
          'identity': {
            'display_name': 'Grace',
            'username': 'grace',
            'activation': {'percentage': 42, 'is_complete': false},
          },
        },
      );
      final controller = await ActorContextController.restore(
        profileId: 'profile-a',
        store: _ActorPreferences(),
      );
      await controller.selectSpace(
        SpaceActorIdentity(id: 'space-e', slug: 'orchestre-e'),
      );
      final runtime = AppRuntime(
        tokens: MemoryTokenStore(),
        session: null,
        recovery: SessionRecoveryController(),
        database: database,
        store: store,
        personal: PersonalRepository(store),
        actorContext: controller,
        space: WorkspaceContextRepository(
          database: database,
          store: store,
          profileId: 'profile-a',
          actorContext: controller,
        ),
      );
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () =>
                    showMakoloAvatarSheet(context, runtime: runtime),
                child: const Text('Avatar'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Avatar'));
      await tester.pumpAndSettle();
      expect(find.text('Espace actif'), findsOneWidget);
      expect(find.text('orchestre-e'), findsWidgets);
      expect(find.text('Compte connecté : Grace'), findsOneWidget);
      expect(find.byType(ProfileAvatarImage), findsNothing);
      expect(find.text('42 % renseigné'), findsNothing);

      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
