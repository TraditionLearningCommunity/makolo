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

Future<AppRuntime> _runtimeWithActivation(int percentage) async {
  final database = MakoloDatabase.memory();
  final store = ProfileStore(database, 'profile-a');
  await store.putProjection(
    kind: 'personal.me',
    schemaVersion: 1,
    payload: {
      'identity': {
        'display_name': 'Amina',
        'activation': {'percentage': percentage},
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
  testWidgets('Avatar exposes global app actions without Compte et paramètres', (
    tester,
  ) async {
    var settingsOpened = false;
    final runtime = await _runtimeWithActivation(72);
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
    expect(find.text('Profil Makolo · 72 % activé'), findsOneWidget);
    expect(find.text('Agir comme'), findsOneWidget);
    expect(find.text('Connexions'), findsOneWidget);
    expect(find.text('Paramètres'), findsOneWidget);
    expect(find.text('Changer de compte'), findsOneWidget);
    expect(find.text('Se déconnecter'), findsOneWidget);
    expect(find.text('Compte et paramètres'), findsNothing);

    await tester.tap(find.text('Paramètres'));
    await tester.pumpAndSettle();
    expect(settingsOpened, isTrue);
  });

  testWidgets('100 percent activation disappears from Avatar', (tester) async {
    final runtime = await _runtimeWithActivation(100);
    addTearDown(runtime.close);

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

    expect(find.textContaining('activé'), findsNothing);

    Navigator.of(tester.element(find.byType(MakoloAvatarSheet))).pop();
    await tester.pump();
    await tester.pump();
  });
}
