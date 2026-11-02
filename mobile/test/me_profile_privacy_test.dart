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
            return MockResponse(jsonEncode({
              'first_name': 'Amina',
              'last_name': 'M.',
              'language': 'fr',
              'profile': {
                'public_profile': false,
                'searchable': false,
              },
            }), 200);
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
}
