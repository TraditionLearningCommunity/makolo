import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/navigation/avatar_sheet.dart';

import 'fakes.dart';

void main() {
  testWidgets('Avatar opens a compact account and actor-context sheet', (
    tester,
  ) async {
    var accountOpened = false;
    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => showMakoloAvatarSheet(
                context,
                runtime: runtime,
                onAccount: () => accountOpened = true,
              ),
              child: const Text('Avatar'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Avatar'));
    await tester.pumpAndSettle();

    expect(find.text('Agir en mon nom'), findsOneWidget);
    expect(find.text('Contexte actif'), findsNothing);
    expect(find.text('Compte et paramètres'), findsOneWidget);
    expect(find.text('Mes démarches'), findsNothing);
    expect(find.text('Mes accès'), findsNothing);
    expect(find.text('Bibliothèque'), findsNothing);

    await tester.tap(find.text('Compte et paramètres'));
    await tester.pumpAndSettle();
    expect(accountOpened, isTrue);
  });
}
