import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/navigation/avatar_sheet.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

import 'fakes.dart';

Future<AppRuntime> _runtimeWithIdentity({bool complete = false}) async {
  final database = MakoloDatabase.memory();
  final store = ProfileStore(database, 'profile-a');
  await store.putProjection(
    kind: 'personal.me',
    schemaVersion: 1,
    payload: {
      'identity': {
        'display_name': 'Amina',
        'username': 'amina',
        'activation': {
          'percentage': complete ? 100 : 33,
          'is_complete': complete,
        },
      },
    },
  );
  return AppRuntime(
    tokens: MemoryTokenStore(),
    session: null,
    recovery: SessionRecoveryController(),
    database: database,
    store: store,
    personal: PersonalRepository(store),
  );
}

void main() {
  testWidgets(
    'Avatar exposes global app actions without Compte et paramètres',
    (tester) async {
      var settingsOpened = false;
      final runtime = await _runtimeWithIdentity();
      addTearDown(runtime.close);

      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () => showMakoloAvatarSheet(
                  context,
                  runtime: runtime,
                  onConnections: () {},
                  onBilling: () {},
                  onSettings: () => settingsOpened = true,
                  onSwitchAccount: () {},
                  onLogout: () {},
                ),
                child: const Text('Avatar'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Avatar'));
      await tester.pumpAndSettle();

      expect(find.text('Amina'), findsOneWidget);
      expect(find.text('33 % renseigné'), findsOneWidget);
      expect(find.text('@amina'), findsOneWidget);
      expect(find.text('Agir comme'), findsOneWidget);
      expect(find.text('Connexions'), findsOneWidget);
      expect(find.text('Abonnement & facturation'), findsOneWidget);
      expect(find.text('Compte'), findsNothing);
      expect(find.text('Paramètres'), findsOneWidget);
      expect(find.text('Changer de compte'), findsOneWidget);
      expect(find.text('Se déconnecter'), findsOneWidget);
      expect(find.text('Compte et paramètres'), findsNothing);

      await tester.tap(find.text('Paramètres'));
      await tester.pumpAndSettle();
      expect(settingsOpened, isTrue);
    },
  );

  testWidgets('Avatar hides 100 percent when applicable profile steps are complete', (
    tester,
  ) async {
    final runtime = await _runtimeWithIdentity(complete: true);

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => showMakoloAvatarSheet(context, runtime: runtime),
              child: const Text('Avatar'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Avatar'));
    await tester.pumpAndSettle();

    expect(find.text('Amina'), findsOneWidget);
    expect(find.textContaining('renseigné'), findsNothing);

    Navigator.of(tester.element(find.byType(MakoloAvatarSheet))).pop();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(milliseconds: 1));
    await tester.runAsync(runtime.close);
  });
}
