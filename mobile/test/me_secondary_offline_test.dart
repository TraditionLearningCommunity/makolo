import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/me/me_considerations_screen.dart';
import 'package:makolo_mobile/features/me/me_passport_screen.dart';
import 'package:makolo_mobile/features/me/me_profile_screen.dart';
import 'package:makolo_mobile/features/me/me_saved_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

class _OfflineApi implements MakoloApiClient {
  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async => throw StateError('offline');

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Future<PersonalRepository> _seed(MakoloDatabase database) async {
  final store = ProfileStore(database, 'profile-a');
  await store.putProjection(
    kind: 'personal.me',
    schemaVersion: 1,
    payload: {
      'actor': {'type': 'profile', 'id': 'profile-a'},
      'identity': {
        'display_name': 'Profil hors ligne',
        'bio': 'Une description connue sur cet appareil.',
      },
      'considerations': {
        'interests': {
          'items': [
            {'id': 'topic-1', 'label': 'Éducation'},
          ],
          'count': 1,
        },
        'open_to': {
          'items': [
            {'id': 'collaborate', 'label': 'Collaborer'},
          ],
          'count': 1,
        },
        'bookmarks': {
          'items': [
            {
              'id': 'saved-1',
              'activity': {
                'id': 'activity-1',
                'title': 'Possibilité connue',
              },
            },
          ],
          'next_offset': 1,
          'has_more': false,
        },
      },
    },
  );
  return PersonalRepository(store);
}

void main() {
  testWidgets('choices keep locally known interests after HTTP failure', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final personal = await _seed(database);
    await tester.pumpWidget(MaterialApp(
      home: MeConsiderationsScreen(
        api: _OfflineApi(),
        personal: personal,
        onSaved: () {},
        onWatches: () {},
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Éducation'), findsOneWidget);
    expect(find.text('Collaborer'), findsOneWidget);
    expect(find.textContaining('Derniers choix connus'), findsNothing);
    expect(find.textContaining('Suggestions à actualiser'), findsNothing);
    expect(find.textContaining('Autres choix à actualiser'), findsNothing);
    expect(find.text('Aucun choix pour le moment.'), findsNothing);
  });

  testWidgets('complete selected settings survive offline beyond root preview', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final personal = await _seed(database);
    final titles = [
      'Culture', 'Design', 'Entrepreneuriat', 'Formation',
      'Logistique', 'Mines', 'Sport',
    ];
    final openings = [
      'Collaborer', 'Mentorat', 'Organiser', 'Participer', 'Bénévolat',
    ];
    await personal.store.putProjection(
      kind: 'personal.me.settings', schemaVersion: 1,
      payload: {
        'interests': [for (var i = 0; i < titles.length; i++) 'topic-$i'],
        'selected_topics': [
          for (var i = 0; i < titles.length; i++)
            {'id': 'topic-$i', 'label': titles[i]},
        ],
        'topics': const [],
        'open_to': [for (var i = 0; i < openings.length; i++) 'kind-$i'],
        'open_to_options': [
          for (var i = 0; i < openings.length; i++)
            {'id': 'kind-$i', 'label': openings[i]},
        ],
      },
    );
    await tester.pumpWidget(MaterialApp(home: MeConsiderationsScreen(
      api: _OfflineApi(), personal: personal,
      onSaved: () {}, onWatches: () {},
    )));
    await tester.pumpAndSettle();
    expect(find.text('7'), findsOneWidget);
    expect(find.text('5'), findsOneWidget);
    for (final title in [...titles, ...openings]) {
      await tester.scrollUntilVisible(
        find.text(title), 160,
        scrollable: find.byType(Scrollable).first,
        maxScrolls: 35,
      );
      expect(find.text(title), findsOneWidget);
    }
    expect(find.textContaining('à actualiser avec une connexion'),
        findsNothing);
  });

  testWidgets('protected Passport projection remains visible offline', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final personal = await _seed(database);
    await personal.store.putProjection(
      kind: 'personal.me.passport',
      resourceKey: 'variant=complete', schemaVersion: 1,
      payload: {
        'variant': 'complete',
        'identity': {
          'name': 'Profil hors ligne',
          'profession': 'Développeur',
          'bio': 'Une présentation connue',
          'avatar_url': '',
          'links': const [],
        },
        'private_details': {'language': 'Français'},
        'declared': {
          'interests': [
            {'topic': {'label': 'Culture'}},
            {'topic': {'label': 'Design'}},
          ],
          'open_to': [
            {'label': 'Collaborer'},
          ],
        },
        'activities': const [],
        'established': {'proofs': const []},
        'issued': {'credentials': const []},
      },
    );
    await tester.pumpWidget(MaterialApp(home: MePassportScreen(
      api: _OfflineApi(), personal: personal,
    )));
    await tester.pumpAndSettle();
    expect(find.text('Profil hors ligne'), findsOneWidget);
    expect(find.text('Développeur'), findsOneWidget);
    expect(find.text('Culture'), findsOneWidget);
    expect(find.text('Design'), findsOneWidget);
    expect(find.text('Collaborer'), findsOneWidget);
    expect(find.textContaining('Aperçu local de Moi'), findsNothing);
    expect(tester.widget<IconButton>(
      find.byTooltip('Exporter le Passeport en PDF'),
    ).onPressed, isNull);
  });

  testWidgets('saved opportunities remain readable offline', (tester) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final personal = await _seed(database);
    await tester.pumpWidget(MaterialApp(
      home: MeSavedScreen(
        api: _OfflineApi(),
        personal: personal,
        onOpen: (_) {},
        onDiscover: () {},
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Possibilité connue'), findsOneWidget);
    expect(find.textContaining('Derniers enregistrements connus'), findsNothing);
    expect(find.textContaining('indisponibles hors connexion'), findsNothing);
  });

  testWidgets('passport never exposes private export from a local summary', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final personal = await _seed(database);
    await tester.pumpWidget(MaterialApp(
      home: MePassportScreen(api: _OfflineApi(), personal: personal),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Profil hors ligne'), findsOneWidget);
    final share = tester.widget<IconButton>(
      find.byTooltip('Partager le Passeport'),
    );
    expect(share.onPressed, isNull);
    final export = tester.widget<IconButton>(
      find.byTooltip('Exporter le Passeport en PDF'),
    );
    expect(export.onPressed, isNull);
  });

  testWidgets('profile summary is read-only when its owner is unreachable', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final personal = await _seed(database);
    await tester.pumpWidget(MaterialApp(
      home: MeProfileScreen(api: _OfflineApi(), personal: personal),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Profil hors ligne'), findsOneWidget);
    expect(find.text('Enregistrer'), findsNothing);
    expect(find.text('Réessayer'), findsOneWidget);
  });
}
