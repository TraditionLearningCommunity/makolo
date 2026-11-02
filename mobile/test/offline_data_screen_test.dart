import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/settings/offline_data_screen.dart';

import 'fakes.dart';

void main() {
  testWidgets('offline status uses only Profile-scoped cached copy metadata', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    await store.putProjection(
      kind: 'personal.me',
      schemaVersion: 1,
      payload: {
        'identity': {'display_name': 'Private Person'},
      },
    );
    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
      store: store,
    );
    await tester.pumpWidget(
      MaterialApp(home: OfflineDataScreen(runtime: runtime)),
    );
    await tester.pumpAndSettle();

    expect(find.text('Données hors ligne'), findsOneWidget);
    expect(find.text('Moi'), findsOneWidget);
    expect(find.text('Maintenant'), findsOneWidget);
    expect(find.text('En cours'), findsOneWidget);
    expect(find.text('Mes Espaces'), findsOneWidget);
    expect(find.textContaining('Copie reçue'), findsOneWidget);
    expect(find.text('Private Person'), findsNothing);
    await tester.scrollUntilVisible(
      find.textContaining('Une copie locale ne donne aucun nouveau droit'),
      200,
    );
    expect(
      find.textContaining('Une copie locale ne donne aucun nouveau droit'),
      findsOneWidget,
    );
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
