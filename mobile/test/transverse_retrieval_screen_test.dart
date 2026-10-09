import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/transverse_retrieval_screen.dart';

import 'fakes.dart';

AppRuntime _runtime(ProfileStore store) => AppRuntime(
  tokens: MemoryTokenStore(),
  session: null,
  recovery: SessionRecoveryController(),
  store: store,
);

void main() {
  testWidgets('offline Search only returns synced personal owner results', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final alice = ProfileStore(db, 'alice');
    await alice.putProjection(
      kind: 'personal.history',
      resourceKey: 'offset:0:limit:24',
      schemaVersion: 1,
      payload: {
        'items': [
          {
            'source': {'kind': 'journey', 'id': 'journey-1'},
            'title': 'Atelier mémorable',
            'outcome': {'label': 'Démarche terminée'},
          },
        ],
        'page': {'offset': 0, 'limit': 24, 'has_more': false},
      },
    );
    await tester.pumpWidget(MaterialApp(
      home: TransverseRetrievalScreen(
        runtime: _runtime(alice),
        initialQuery: 'Atelier',
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Atelier mémorable'), findsOneWidget);
    expect(find.textContaining('Actualisation indisponible'), findsOneWidget);
  });

  testWidgets('account switch does not retain previous Search results', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final alice = ProfileStore(db, 'alice');
    final bob = ProfileStore(db, 'bob');
    await alice.putProjection(
      kind: 'personal.history',
      resourceKey: 'offset:0:limit:24',
      schemaVersion: 1,
      payload: {
        'items': [
          {
            'source': {'kind': 'journey', 'id': 'private-a'},
            'title': 'Privé Alice',
          },
        ],
      },
    );
    await tester.pumpWidget(MaterialApp(
      home: TransverseRetrievalScreen(
        runtime: _runtime(alice),
        initialQuery: 'Privé',
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Privé Alice'), findsOneWidget);

    await tester.pumpWidget(MaterialApp(
      home: TransverseRetrievalScreen(
        runtime: _runtime(bob),
        initialQuery: 'Privé',
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Privé Alice'), findsNothing);
  });

  testWidgets('1.6 text scale preserves search controls on Compact', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(360, 800);
    addTearDown(() {
      tester.view.resetDevicePixelRatio();
      tester.view.resetPhysicalSize();
    });
    await tester.pumpWidget(MaterialApp(
      home: MediaQuery(
        data: const MediaQueryData(
          textScaler: TextScaler.linear(1.6),
        ),
        child: TransverseRetrievalScreen(
          runtime: _runtime(ProfileStore(db, 'alice')),
        ),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.byType(TextField), findsOneWidget);
    expect(find.byTooltip('Lancer la recherche'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
