import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/me/me_profile_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  testWidgets(
    'privacy deep link lands on canonical Passport visibility controls',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          profileId: 'profile-a',
          accessToken: 'access',
          refreshToken: 'refresh',
        ),
      );
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: tokens,
        dio: MockClient((request) async {
          if (request.url.path == '/api/v1/accounts/auth/me/') {
            return MockResponse(
              jsonEncode({
                'first_name': 'Amina',
                'last_name': 'M.',
                'language': 'fr',
                'profile': {'public_profile': false, 'searchable': false},
              }),
              200,
            );
          }
          throw StateError('Unexpected request');
        }).dio,
      );
      addTearDown(api.close);

      await tester.pumpWidget(
        MaterialApp(
          home: MeProfileScreen(
            api: api,
            personal: PersonalRepository(store),
            focusVisibility: true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Confidentialité du Profil'), findsOneWidget);
      expect(find.text('Passeport public'), findsOneWidget);
      expect(find.text('Visible dans la recherche'), findsOneWidget);
      final visibility = tester.widget<SwitchListTile>(
        find.ancestor(
          of: find.text('Passeport public'),
          matching: find.byType(SwitchListTile),
        ),
      );
      expect(visibility.value, isFalse);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
  testWidgets(
    'validation shows field error and retries save without losing edits',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-validation');
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          profileId: 'profile-validation',
          accessToken: 'access',
          refreshToken: 'refresh',
        ),
      );
      int attempts = 0;
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: tokens,
        dio: MockClient((request) async {
          if (request.url.path == '/api/v1/accounts/auth/me/') {
            return MockResponse(
              jsonEncode({
                'first_name': 'Alex',
                'last_name': 'Exemple',
                'gender': 'unspecified',
                'bio': '',
                'language': 'en',
                'profile': {'public_profile': false, 'searchable': false},
              }),
              200,
            );
          }
          if (request.url.path == '/api/v1/accounts/auth/profile/update/') {
            final submitted = jsonDecode(request.body) as Map<String, dynamic>;
            expect(submitted['bio'], 'Ma présentation');
            expect(submitted.containsKey('language'), isFalse);
            attempts++;
            if (attempts == 1) {
              return const MockResponse(
                '{"bio":["Présentation à vérifier."]}',
                400,
              );
            }
            return MockResponse(
              jsonEncode({
                'message': 'Profil mis à jour.',
                'user': {
                  'first_name': 'Alex',
                  'last_name': 'Exemple',
                  'bio': 'Ma présentation',
                  'profile': {'public_profile': false, 'searchable': false},
                },
              }),
              200,
            );
          }
          if (request.url.path == '/api/v1/me/') {
            return MockResponse(
              jsonEncode({
                'meta': {
                  'projection': 'personal.me',
                  'schema_version': 1,
                  'scope': 'personal',
                  'generated_at': '2026-11-03T06:00:00Z',
                },
                'data': {
                  'actor': {'id': 'profile-validation'},
                  'identity': {'display_name': 'Alex Exemple'},
                },
              }),
              200,
            );
          }
          throw StateError('Unexpected request: ${request.url}');
        }).dio,
      );
      addTearDown(api.close);
      await tester.pumpWidget(
        MaterialApp(
          home: MeProfileScreen(api: api, personal: PersonalRepository(store)),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Langue'), findsNothing);
      await tester.enterText(
        find.widgetWithText(TextField, 'À propos'),
        'Ma présentation',
      );
      await tester.ensureVisible(find.text('Enregistrer'));
      await tester.tap(find.text('Enregistrer'));
      await tester.pumpAndSettle();
      expect(attempts, 1);
      expect(find.text('Présentation à vérifier.'), findsOneWidget);
      expect(find.text('Ma présentation'), findsOneWidget);
      expect(find.text('Réessayer l’enregistrement'), findsNothing);
      await tester.ensureVisible(find.text('Enregistrer'));
      await tester.tap(find.text('Enregistrer'));
      await tester.pumpAndSettle();
      expect(attempts, 2);
      expect(find.text('Modifications enregistrées.'), findsOneWidget);
      expect(find.text('Ma présentation'), findsOneWidget);
    },
  );

  testWidgets(
    'invalid local phone is blocked, HTTPS is normalized before PATCH',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-local-validation');
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          profileId: 'profile-local-validation',
          accessToken: 'access',
          refreshToken: 'refresh',
        ),
      );
      int patches = 0;
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: tokens,
        dio: MockClient((request) async {
          if (request.url.path == '/api/v1/accounts/auth/me/') {
            return MockResponse(
              jsonEncode({
                'first_name': 'Amina',
                'last_name': 'Exemple',
                'phone': '',
                'website': '',
                'profile': {'public_profile': true, 'searchable': true},
              }),
              200,
            );
          }
          if (request.url.path == '/api/v1/accounts/auth/profile/update/') {
            patches++;
            final data = jsonDecode(request.body) as Map<String, dynamic>;
            expect(data['phone'], '+243 810 000 000');
            expect(data['website'], 'https://exemple.com');
            expect(data.containsKey('language'), isFalse);
            return MockResponse(
              jsonEncode({
                'user': {
                  'first_name': 'Amina',
                  'last_name': 'Exemple',
                  'phone': '+243 810 000 000',
                  'website': 'https://exemple.com',
                  'profile': {'public_profile': true, 'searchable': true},
                },
              }),
              200,
            );
          }
          if (request.url.path == '/api/v1/me/') {
            return MockResponse(
              jsonEncode({
                'meta': {
                  'projection': 'personal.me',
                  'schema_version': 1,
                  'scope': 'personal',
                  'generated_at': '2026-11-03T06:00:00Z',
                },
                'data': {
                  'actor': {'id': 'profile-local-validation'},
                  'identity': {'display_name': 'Amina Exemple'},
                },
              }),
              200,
            );
          }
          throw StateError('Unexpected request: ${request.url}');
        }).dio,
      );
      addTearDown(api.close);

      await tester.pumpWidget(
        MaterialApp(
          home: MeProfileScreen(api: api, personal: PersonalRepository(store)),
        ),
      );
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.widgetWithText(TextField, 'Téléphone'),
        220,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Téléphone'),
        '123456',
      );
      await tester.ensureVisible(find.text('Enregistrer'));
      await tester.tap(find.text('Enregistrer'));
      await tester.pumpAndSettle();
      expect(patches, 0);
      expect(find.text('Réessayer l’enregistrement'), findsNothing);
      await tester.scrollUntilVisible(
        find.widgetWithText(TextField, 'Téléphone'),
        -250,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('7 à 15 chiffres.'), findsOneWidget);
      expect(find.text('Vérifier'), findsNothing);

      await tester.ensureVisible(find.widgetWithText(TextField, 'Téléphone'));
      await tester.enterText(
        find.widgetWithText(TextField, 'Téléphone'),
        '+243 810 000 000',
      );
      await tester.scrollUntilVisible(
        find.text('Liens et réseaux sociaux'),
        240,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.text('Liens et réseaux sociaux'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.widgetWithText(TextField, 'Site web'),
        220,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Site web'),
        'https://https://exemple.com',
      );
      await tester.ensureVisible(find.text('Enregistrer'));
      await tester.tap(find.text('Enregistrer'));
      await tester.pumpAndSettle();
      expect(patches, 1);
      await tester.scrollUntilVisible(
        find.widgetWithText(TextField, 'Site web'),
        -220,
        scrollable: find.byType(Scrollable).first,
      );
      expect(
        tester
            .widget<TextField>(find.widgetWithText(TextField, 'Site web'))
            .controller!
            .text,
        'https://exemple.com',
      );
      expect(find.text('Modifications enregistrées.'), findsOneWidget);
    },
  );

  testWidgets('editor groups all Accounts fields and keeps email read-only', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-editor-groups');
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        profileId: 'profile-editor-groups',
        accessToken: 'access',
        refreshToken: 'refresh',
      ),
    );
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: MockClient((request) async {
        if (request.url.path == '/api/v1/accounts/auth/me/') {
          return MockResponse(
            jsonEncode({
              'first_name': 'Amina',
              'last_name': 'Exemple',
              'username': 'amina-exemple',
              'email': 'amina@example.test',
              'phone': '+243800000000',
              'profession': 'Analyste',
              'profile': {
                'profession': 'Analyste',
                'public_profile': true,
                'searchable': true,
              },
            }),
            200,
          );
        }
        throw StateError('Unexpected request: ${request.url}');
      }).dio,
    );
    addTearDown(api.close);

    await tester.pumpWidget(
      MaterialApp(
        home: MeProfileScreen(api: api, personal: PersonalRepository(store)),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Modifier le Passeport'), findsOneWidget);
    expect(find.text('Identifiant Makolo'), findsOneWidget);
    expect(find.text('amina-exemple'), findsOneWidget);
    expect(find.text('Contact'), findsOneWidget);
    expect(find.text('Adresse e-mail'), findsOneWidget);
    expect(find.text('amina@example.test'), findsOneWidget);
    expect(find.widgetWithText(TextField, 'Adresse e-mail'), findsNothing);
    expect(find.text('Activité professionnelle'), findsOneWidget);
    expect(find.text('Activité et liens'), findsNothing);
    expect(find.text('Réseaux sociaux'), findsNothing);
    await tester.ensureVisible(find.text('Liens et réseaux sociaux'));
    await tester.tap(find.text('Liens et réseaux sociaux'));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.text('Site web'),
      220,
      scrollable: find
          .descendant(
            of: find.byType(ListView).first,
            matching: find.byType(Scrollable),
          )
          .first,
    );
    expect(find.text('Site web'), findsOneWidget);
    expect(find.text('LinkedIn'), findsWidgets);
  });

  testWidgets('identifier has a separate guarded Accounts action', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-identifier');
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        profileId: 'profile-identifier',
        accessToken: 'access',
        refreshToken: 'refresh',
      ),
    );
    int identifierPatches = 0;
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: MockClient((request) async {
        if (request.url.path == '/api/v1/accounts/auth/me/') {
          return MockResponse(
            jsonEncode({
              'first_name': 'Amina',
              'username': 'amina-actuelle',
              'email': 'amina@example.test',
              'profile': {'public_profile': false, 'searchable': false},
            }),
            200,
          );
        }
        if (request.url.path == '/api/v1/accounts/auth/identifier/') {
          final data =
              jsonDecode(request.data as String) as Map<String, dynamic>;
          expect(data, {'username': 'amina-nouvelle'});
          identifierPatches++;
          return MockResponse(
            jsonEncode({
              'message': 'Identifiant Makolo mis à jour.',
              'user': {'username': 'amina-nouvelle'},
            }),
            200,
          );
        }
        if (request.url.path == '/api/v1/me/') {
          return MockResponse(
            jsonEncode({
              'meta': {
                'projection': 'personal.me',
                'schema_version': 1,
                'scope': 'personal',
                'generated_at': '2026-11-03T06:00:00Z',
              },
              'data': {
                'actor': {'id': 'profile-identifier'},
                'identity': {'display_name': 'Amina'},
              },
            }),
            200,
          );
        }
        throw StateError('Unexpected request: ${request.url}');
      }).dio,
    );
    addTearDown(api.close);
    await tester.pumpWidget(
      MaterialApp(
        home: MeProfileScreen(api: api, personal: PersonalRepository(store)),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Modifier Identifiant Makolo'));
    await tester.pumpAndSettle();
    final usernameField = find.descendant(
      of: find.byType(AlertDialog),
      matching: find.byType(TextField),
    );
    await tester.enterText(usernameField, 'admin');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Modifier').last);
    await tester.pumpAndSettle();
    expect(identifierPatches, 0);
    expect(find.text('Identifiant réservé.'), findsOneWidget);
    expect(find.byType(AlertDialog), findsOneWidget);
    expect(find.text('Vérifier'), findsNothing);
    await tester.enterText(usernameField, '@Amina-Nouvelle');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Modifier').last);
    await tester.pumpAndSettle();
    expect(identifierPatches, 1);
    expect(find.text('amina-nouvelle'), findsOneWidget);
    expect(find.text('amina@example.test'), findsOneWidget);
  });

  testWidgets('Accounts gender and birth date are editable from Passport', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-gender');
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        profileId: 'profile-gender',
        accessToken: 'access',
        refreshToken: 'refresh',
      ),
    );
    Map<String, dynamic>? submitted;
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: MockClient((request) async {
        if (request.url.path == '/api/v1/accounts/auth/me/') {
          return MockResponse(
            jsonEncode({
              'first_name': 'Alex',
              'last_name': 'Exemple',
              'gender': 'unspecified',
              'birth_date': null,
              'language': 'fr',
              'profile': {'public_profile': false, 'searchable': false},
            }),
            200,
          );
        }
        if (request.url.path == '/api/v1/accounts/auth/profile/update/') {
          submitted =
              jsonDecode(request.data as String) as Map<String, dynamic>;
          return MockResponse(
            jsonEncode({
              'message': 'Profil mis à jour.',
              'user': {
                'first_name': 'Alex',
                'last_name': 'Exemple',
                'gender': submitted!['gender'],
                'birth_date': submitted!['birth_date'],
                'language': 'fr',
                'profile': {'public_profile': false, 'searchable': false},
              },
            }),
            200,
          );
        }
        throw StateError('Unexpected request');
      }).dio,
    );
    addTearDown(api.close);
    await tester.pumpWidget(
      MaterialApp(
        home: MeProfileScreen(api: api, personal: PersonalRepository(store)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Genre'), findsOneWidget);
    expect(find.text('Date de naissance'), findsOneWidget);
    await tester.tap(find.text('Non renseigné'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Femme').last);
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('Enregistrer'));
    await tester.tap(find.text('Enregistrer'));
    await tester.pumpAndSettle();
    expect(submitted, isNotNull);
    expect(submitted!['gender'], 'female');
    expect(submitted!.containsKey('birth_date'), isFalse);
  });
}
