import 'package:drift/drift.dart' show Value;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/resources/trust_resource_collection_screen.dart';
import 'package:makolo_mobile/features/resources/trust_resource_detail_screen.dart';
import 'package:makolo_mobile/features/resources/trust_resource_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/platform/sharing/share_gateway.dart';

import 'fakes.dart';

MakoloApiClient _testApi() => MakoloApiClient(
  baseUri: Uri.parse('https://makolo.test/'),
  tokenStore: MemoryTokenStore(),
);

Future<void> _markDetailReachable(
  MakoloDatabase database,
  TrustResourceRepository repository,
  TrustResourceFamily family,
  String id,
) async {
  final source = repository.detailSourceFor(family, id);
  await database
      .into(database.syncSources)
      .insert(
        SyncSourcesCompanion.insert(
          profileId: 'profile-a',
          sourceKey: source.sourceKey,
          route: source.path,
          lastSuccessAt: Value(DateTime.now().toUtc()),
        ),
      );
}

class _RecordingShareGateway implements ShareGateway {
  final List<String> texts = [];
  final List<List<String>> files = [];
  final List<Uri> opened = [];

  @override
  Future<void> shareText(String text) async {
    texts.add(text);
  }

  @override
  Future<void> shareFiles({required List<String> paths, String? text}) async {
    files.add(List<String>.from(paths));
  }

  @override
  Future<bool> openExternal(Uri uri) async {
    opened.add(uri);
    return true;
  }
}

void main() {
  testWidgets(
    'cached proofs stay quiet on transport errors and disappear after revocation',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      addTearDown(() async {
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pump(const Duration(milliseconds: 1));
      });
      final store = ProfileStore(database, 'profile-a');
      final repository = TrustResourceRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        sync: null,
      );
      final family = TrustResourceFamily.proofs;
      final source = repository.collectionSourceFor(
        family: family,
        query: '',
        offset: 0,
      );
      await store.putProjection(
        kind: family.collectionProjection,
        resourceKey: repository.collectionResourceKey(
          family: family,
          query: '',
          status: 'all',
          type: '',
          sort: 'recent',
          offset: 0,
        ),
        schemaVersion: 1,
        payload: {
          'query': null,
          'status': 'all',
          'proof_type': null,
          'sort': 'recent',
          'count': 1,
          'items': [
            {
              'id': 'proof-known',
              'proof_type_label': 'Formation attestée',
              'status': 'active',
            },
          ],
          'page': {'offset': 0, 'limit': 24, 'has_more': false},
        },
      );
      await database
          .into(database.syncSources)
          .insert(
            SyncSourcesCompanion.insert(
              profileId: 'profile-a',
              sourceKey: source.sourceKey,
              route: source.path,
              lastSuccessAt: Value(DateTime.now().toUtc()),
              lastErrorCode: const Value('transport_unreachable'),
            ),
          );
      await tester.pumpWidget(
        MaterialApp(
          home: TrustResourceCollectionScreen(
            family: family,
            repository: repository,
            onOpenItem: (_) {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Formation attestée'), findsOneWidget);
      expect(find.textContaining('Mise à jour indisponible'), findsNothing);
      expect(find.textContaining('Données enregistrées'), findsNothing);

      await database
          .update(database.syncSources)
          .write(
            const SyncSourcesCompanion(
              invalidated: Value(true),
              lastErrorCode: Value('permission_denied'),
            ),
          );
      await tester.pumpAndSettle();
      expect(find.text('Formation attestée'), findsNothing);
      expect(
        find.text('Ces preuves ne sont plus disponibles.'),
        findsOneWidget,
      );
      expect(find.byTooltip('Rechercher'), findsNothing);
      expect(find.text('1'), findsNothing);
    },
  );

  testWidgets('Mes preuves is a searchable local-first Trust collection', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final repository = TrustResourceRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: null,
    );
    await store.putProjection(
      kind: TrustResourceFamily.proofs.collectionProjection,
      resourceKey: repository.collectionResourceKey(
        family: TrustResourceFamily.proofs,
        query: '',
        status: 'all',
        type: '',
        sort: 'recent',
        offset: 0,
      ),
      schemaVersion: 1,
      payload: {
        'count': 2,
        'query': null,
        'status': 'all',
        'proof_type': null,
        'sort': 'recent',
        'filter_options': {
          'types': [
            {'id': 'journey_completed', 'label': 'Journey accomplie'},
            {'id': 'service_completed', 'label': 'Service complété'},
          ],
        },
        'items': [
          {
            'id': 'proof-1',
            'proof_type': 'journey_completed',
            'proof_type_label': 'Journey accomplie',
            'status': 'active',
            'status_label': 'Active',
            'issued_at': '2026-11-01T10:00:00Z',
            'activity': {'title': 'Formation pratique'},
          },
          {
            'id': 'proof-2',
            'proof_type': 'service_completed',
            'proof_type_label': 'Service complété',
            'status': 'revoked',
            'status_label': 'Révoqué',
            'issued_at': '2026-10-01T10:00:00Z',
            'activity': {'title': 'Service administratif'},
          },
        ],
        'page': {'count': 2, 'offset': 0, 'limit': 24, 'has_more': false},
      },
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: TrustResourceCollectionScreen(
          family: TrustResourceFamily.proofs,
          repository: repository,
          onOpenItem: (_) {},
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Mes preuves'), findsOneWidget);
    expect(find.text('2'), findsOneWidget);
    expect(find.text('Toutes'), findsOneWidget);
    expect(find.text('Actives'), findsOneWidget);
    expect(find.text('Révoquées'), findsOneWidget);
    expect(find.text('Journey accomplie'), findsOneWidget);
    expect(find.text('Service complété'), findsOneWidget);
    expect(find.byTooltip('Rechercher'), findsOneWidget);
    expect(find.byTooltip('Actualiser'), findsOneWidget);
    expect(find.byTooltip('Filtrer'), findsOneWidget);
    expect(find.byTooltip('Trier'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);

    await tester.tap(find.byTooltip('Rechercher'));
    await tester.pump();
    expect(find.byType(TextField), findsOneWidget);
    expect(find.byTooltip('Fermer la recherche'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'Formation');
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('Journey accomplie'), findsOneWidget);
    expect(find.text('Service complété'), findsNothing);

    await tester.tap(find.byTooltip('Fermer la recherche'));
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.byType(TextField), findsNothing);
    expect(find.text('Mes preuves'), findsOneWidget);
    expect(find.text('Service complété'), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Mes titres keeps issuer status and type distinct', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final repository = TrustResourceRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: null,
    );
    await store.putProjection(
      kind: TrustResourceFamily.titles.collectionProjection,
      resourceKey: repository.collectionResourceKey(
        family: TrustResourceFamily.titles,
        query: '',
        status: 'all',
        type: '',
        sort: 'recent',
        offset: 0,
      ),
      schemaVersion: 1,
      payload: {
        'count': 1,
        'query': null,
        'status': 'all',
        'credential_type': null,
        'sort': 'recent',
        'filter_options': {
          'types': [
            {'id': 'completion', 'label': 'Certificat de complétion'},
          ],
        },
        'items': [
          {
            'id': 'credential-1',
            'title': 'Certificat Makolo',
            'credential_type': 'completion',
            'credential_type_label': 'Certificat de complétion',
            'status': 'issued',
            'status_label': 'Valide',
            'issued_at': '2026-11-02T10:00:00Z',
            'issuer': {'name': 'Institut Makolo'},
            'activity': {'title': 'Formation pratique'},
          },
        ],
        'page': {'count': 1, 'offset': 0, 'limit': 24, 'has_more': false},
      },
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: TrustResourceCollectionScreen(
          family: TrustResourceFamily.titles,
          repository: repository,
          onOpenItem: (_) {},
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Mes titres'), findsOneWidget);
    expect(find.text('1'), findsOneWidget);
    expect(find.text('Certificat Makolo'), findsOneWidget);
    expect(find.textContaining('Institut Makolo · Valide'), findsOneWidget);
    expect(find.text('Valides'), findsOneWidget);
    expect(find.text('Révoqués'), findsOneWidget);
    expect(find.byTooltip('Rechercher'), findsOneWidget);
    expect(find.byTooltip('Actualiser'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('proof detail is read-only and exposes public verification', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final repository = TrustResourceRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: null,
      api: _testApi(),
    );
    final sharing = _RecordingShareGateway();
    await store.putProjection(
      kind: TrustResourceFamily.proofs.detailProjection,
      resourceKey: 'proof-1',
      schemaVersion: 1,
      payload: {
        'id': 'proof-1',
        'proof_type': 'journey_completed',
        'proof_type_label': 'Journey accomplie',
        'status': 'active',
        'status_label': 'Active',
        'issued_at': '2026-11-01T10:00:00Z',
        'activity': {'title': 'Formation pratique'},
        'journey': {'id': 'journey-1'},
        'occurrence': {'label': 'Session finale'},
        'revocation': {'revoked_at': null, 'reason': null},
        'links': {
          'verify': '/trust/proofs/verify/public-proof/',
          'passport': '/api/v1/me/passport/',
        },
      },
    );
    await _markDetailReachable(
      database,
      repository,
      TrustResourceFamily.proofs,
      'proof-1',
    );

    var openedJourney = false;
    var openedPassport = false;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: TrustResourceDetailScreen(
          family: TrustResourceFamily.proofs,
          id: 'proof-1',
          repository: repository,
          sharing: sharing,
          onOpenJourney: (_) => openedJourney = true,
          onOpenPassport: () => openedPassport = true,
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Journey accomplie'), findsOneWidget);
    expect(find.text('Formation pratique'), findsOneWidget);
    expect(find.text('Session finale'), findsOneWidget);
    expect(find.byTooltip('Vérifier'), findsNothing);
    expect(find.byTooltip('Partager le lien de vérification'), findsOneWidget);
    expect(find.text('Passeport'), findsOneWidget);
    expect(find.text('Modifier'), findsNothing);
    expect(find.text('Supprimer'), findsNothing);

    await tester.tap(find.byTooltip('Partager le lien de vérification'));
    await tester.pump();
    expect(sharing.opened, isEmpty);
    expect(sharing.texts.single, contains('Journey accomplie'));
    expect(
      sharing.texts.single,
      contains('https://makolo.test/trust/proofs/verify/public-proof/'),
    );

    await tester.tap(find.text('Passeport'));
    expect(openedPassport, isTrue);
    await tester.tap(find.text('Voir la démarche'));
    expect(openedJourney, isTrue);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('revoked title detail keeps statement issuer and revocation', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    final repository = TrustResourceRepository(
      database: database,
      store: store,
      profileId: 'profile-a',
      sync: null,
      api: _testApi(),
    );
    await store.putProjection(
      kind: TrustResourceFamily.titles.detailProjection,
      resourceKey: 'credential-1',
      schemaVersion: 1,
      payload: {
        'id': 'credential-1',
        'title': 'Certificat Makolo',
        'credential_type': 'completion',
        'credential_type_label': 'Certificat de complétion',
        'status': 'revoked',
        'status_label': 'Révoquée',
        'statement': 'Formation terminée.',
        'issued_at': '2026-11-01T10:00:00Z',
        'issuer': {'name': 'Institut Makolo'},
        'activity': {'title': 'Formation pratique'},
        'journey': {'id': 'journey-1'},
        'occurrence': {'label': 'Session finale'},
        'revocation': {
          'revoked_at': '2026-11-05T10:00:00Z',
          'reason': 'Titre remplacé',
        },
        'links': {
          'verify': '/trust/credentials/verify/public-title/',
          'passport': '/api/v1/me/passport/',
        },
      },
    );
    await _markDetailReachable(
      database,
      repository,
      TrustResourceFamily.titles,
      'credential-1',
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: TrustResourceDetailScreen(
          family: TrustResourceFamily.titles,
          id: 'credential-1',
          repository: repository,
          onOpenJourney: (_) {},
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Certificat Makolo'), findsOneWidget);
    expect(find.text('Certificat de complétion'), findsOneWidget);
    expect(find.text('Institut Makolo'), findsWidgets);
    expect(find.text('Formation terminée.'), findsOneWidget);
    expect(find.text('Titre remplacé'), findsOneWidget);
    expect(find.byTooltip('Vérifier'), findsNothing);
    expect(find.byTooltip('Partager le lien de vérification'), findsOneWidget);
    expect(find.text('Modifier'), findsNothing);
    expect(find.text('Supprimer'), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
