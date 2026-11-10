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
    await tester.pumpWidget(
      MaterialApp(
        home: TransverseRetrievalScreen(
          runtime: _runtime(alice),
          initialQuery: 'Atelier',
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Atelier mémorable'), findsOneWidget);
    expect(find.textContaining('Actualisation indisponible'), findsOneWidget);
  });

  testWidgets(
    'offline Search reuses acquired Proof and Title owner snapshots',
    (tester) async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'alice');
      await store.putProjection(
        kind: 'personal.proofs',
        resourceKey: 'proofs:0:24',
        schemaVersion: 1,
        payload: {
          'items': [
            {
              'id': 'proof-1',
              'proof_type_label': 'Journey accomplie',
              'status_label': 'Active',
              'activity': {'title': 'Formation Makolo'},
            },
          ],
        },
      );
      await store.putProjection(
        kind: 'personal.titles',
        resourceKey: 'titles:0:24',
        schemaVersion: 1,
        payload: {
          'items': [
            {
              'id': 'credential-1',
              'title': 'Certificat pratique',
              'credential_type_label': 'Certificat de complétion',
              'status_label': 'Valide',
              'issuer': {'name': 'Institut Makolo'},
              'activity': {'title': 'Formation pratique'},
            },
          ],
        },
      );

      await tester.pumpWidget(
        MaterialApp(
          home: TransverseRetrievalScreen(
            runtime: _runtime(store),
            initialQuery: 'Makolo',
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Journey accomplie'), findsOneWidget);
      expect(find.text('Certificat pratique'), findsOneWidget);
      expect(find.byIcon(Icons.verified_outlined), findsOneWidget);
      expect(find.byIcon(Icons.workspace_premium_outlined), findsOneWidget);
      expect(find.byIcon(Icons.chevron_right), findsNWidgets(2));
    },
  );

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
    await tester.pumpWidget(
      MaterialApp(
        home: TransverseRetrievalScreen(
          runtime: _runtime(alice),
          initialQuery: 'Privé',
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Privé Alice'), findsOneWidget);

    await tester.pumpWidget(
      MaterialApp(
        home: TransverseRetrievalScreen(
          runtime: _runtime(bob),
          initialQuery: 'Privé',
        ),
      ),
    );
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
    await tester.pumpWidget(
      MaterialApp(
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(1.6)),
          child: TransverseRetrievalScreen(
            runtime: _runtime(ProfileStore(db, 'alice')),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byType(TextField), findsOneWidget);
    expect(find.byTooltip('Lancer la recherche'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets('offline Search reuses Moi documents but excludes Space groups', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final store = ProfileStore(db, 'alice');
    await store.putProjection(
      kind: 'personal.me',
      resourceKey: 'root',
      schemaVersion: 1,
      payload: {
        'resources': {
          'documents': {
            'items': [
              {'id': 'asset-1', 'title': 'Dossier personnel'},
            ],
          },
        },
        'collectives': {
          'groups': {
            'items': [
              {
                'id': 'space-group',
                'name': 'Dossier du Space',
                'owner': {'kind': 'space', 'id': 's'},
              },
            ],
          },
        },
      },
    );
    await tester.pumpWidget(
      MaterialApp(
        home: TransverseRetrievalScreen(
          runtime: _runtime(store),
          initialQuery: 'Dossier',
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Dossier personnel'), findsOneWidget);
    expect(find.text('Dossier du Space'), findsNothing);
    expect(find.text('Document'), findsWidgets);
  });
  testWidgets(
    'typing retains identifiable previous results until the new search',
    (tester) async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final store = ProfileStore(db, 'search-user');
      await store.putProjection(
        kind: 'personal.history',
        resourceKey: 'offset:0:limit:24',
        schemaVersion: 1,
        payload: {
          'items': [
            {
              'source': {'kind': 'journey', 'id': 'journey-prior'},
              'title': 'Atelier déjà connu',
              'outcome': {'label': 'Démarche terminée'},
            },
          ],
          'page': {'offset': 0, 'limit': 24, 'has_more': false},
        },
      );
      await tester.pumpWidget(
        MaterialApp(
          home: TransverseRetrievalScreen(
            runtime: _runtime(store),
            initialQuery: 'Atelier',
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Atelier déjà connu'), findsOneWidget);
      await tester.enterText(find.byType(TextField), 'Autre recherche');
      await tester.pump();
      expect(find.text('Atelier déjà connu'), findsOneWidget);
      expect(find.text('Résultats précédents'), findsOneWidget);

      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();
      expect(find.text('Atelier déjà connu'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );
}
