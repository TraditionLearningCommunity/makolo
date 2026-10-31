import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/discovery/discovery_repository.dart';
import 'package:makolo_mobile/features/discovery/discovery_screens.dart';
import 'package:makolo_mobile/features/me/me_considerations_screen.dart';
import 'package:makolo_mobile/features/me/me_passport_screen.dart';
import 'package:makolo_mobile/features/me/me_profile_screen.dart';
import 'package:makolo_mobile/features/me/me_saved_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';
import 'package:makolo_mobile/repositories/draft_repository.dart';
import 'package:makolo_mobile/sync/outbox/outbox_repository.dart';

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
    expect(tester.widget<IconButton>(
      find.byTooltip('Versions datées'),
    ).onPressed, isNull);
  });

  testWidgets('saved Activity opens its known local title without loading loop', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final personal = await _seed(database);
    final discovery = DiscoveryRepository(
      database: database,
      store: personal.store,
      profileId: personal.store.profileId,
      api: _OfflineApi(),
    );
    await tester.pumpWidget(MaterialApp(home: ActivityDetailScreen(
      activityId: 'activity-1',
      repository: discovery,
      onOpenOccurrence: (_) {},
    )));
    await tester.pumpAndSettle();
    expect(find.text('Possibilité connue'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(find.textContaining('Mise à jour'), findsNothing);
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

  testWidgets('saved list restores a persisted full owner collection offline', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final personal = await _seed(database);
    await personal.store.putProjection(
      kind: 'personal.me.preview',
      resourceKey: 'considerations:bookmarks:known', schemaVersion: 1,
      payload: {
        'actor': {'type': 'profile', 'id': 'profile-a'},
        'family': 'bookmarks',
        'next_offset': 3,
        'has_more': false,
        'items': [
          for (var i = 0; i < 3; i++)
            {
              'id': 'bookmark-$i',
              'activity': {'id': 'a-$i', 'title': 'Activité conservée $i'},
            },
        ],
      },
    );
    await tester.pumpWidget(MaterialApp(home: MeSavedScreen(
      api: _OfflineApi(), personal: personal,
      onOpen: (_) {}, onDiscover: () {},
    )));
    await tester.pumpAndSettle();
    for (var i = 0; i < 3; i++) {
      expect(find.text('Activité conservée $i'), findsOneWidget);
    }
    expect(find.textContaining('hors connexion'), findsNothing);
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

  testWidgets('the full Accounts editor remains native with stored owner fields', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final personal = await _seed(database);
    await personal.store.putProjection(
      kind: 'personal.me.account_editor',
      schemaVersion: 1,
      payload: {
        'first_name': 'Gilbra',
        'last_name': 'Makolo',
        'bio': 'Description conservée',
        'profession': 'Architecte',
        'city': 'Kinshasa',
        'country': 'CD',
        'phone': '',
        'website': '',
        'public_profile': false,
        'searchable': false,
      },
    );
    await tester.pumpWidget(MaterialApp(
      home: MeProfileScreen(api: _OfflineApi(), personal: personal),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Identité'), findsOneWidget);
    expect(find.text('Gilbra'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('Enregistrer'),
      200,
      scrollable: find.byType(Scrollable).first,
      maxScrolls: 40,
    );
    expect(find.text('Enregistrer'), findsOneWidget);
    expect(find.text('Réessayer'), findsNothing);
    expect(find.textContaining('Dernières informations du profil connues'),
        findsNothing);
  });

  testWidgets('profile edits remain local drafts across native editor restart', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final personal = await _seed(database);
    await personal.store.putProjection(
      kind: 'personal.me.account_editor',
      schemaVersion: 1,
      payload: {
        'first_name': 'Avant',
        'last_name': 'Makolo',
        'bio': '',
        'profession': '',
        'city': '',
        'country': 'CD',
        'public_profile': false,
        'searchable': false,
      },
    );
    final drafts = DraftRepository(
      database: database,
      outbox: OutboxRepository(database, 'profile-a'),
      profileId: 'profile-a',
    );
    await tester.pumpWidget(MaterialApp(
      home: MeProfileScreen(
        api: _OfflineApi(),
        personal: personal,
        drafts: drafts,
      ),
    ));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextField, 'Prénom'),
      'Brouillon conservé',
    );
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(milliseconds: 40));
    });
    final draft = await drafts.read(
      owner: 'Accounts',
      resourceKind: 'profile_editor',
      resourceId: 'profile-a',
    );
    expect(draft?.payload['first_name'], 'Brouillon conservé');

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpWidget(MaterialApp(
      home: MeProfileScreen(
        api: _OfflineApi(),
        personal: personal,
        drafts: drafts,
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Brouillon conservé'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('Enregistrer'),
      200,
      scrollable: find.byType(Scrollable).first,
      maxScrolls: 40,
    );
    expect(find.text('Enregistrer'), findsOneWidget);
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
