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
    expect(find.textContaining('Derniers choix connus'), findsOneWidget);
    expect(find.text('Aucun choix pour le moment.'), findsNothing);
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
    expect(find.textContaining('Derniers enregistrements connus'), findsOneWidget);
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
