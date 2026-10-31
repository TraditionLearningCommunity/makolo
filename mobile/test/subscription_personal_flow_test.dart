import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/features/settings/billing_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  testWidgets(
    'personal subscription consumes effective quotas, conditions and history',
    (tester) async {
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
          expect(request.url.path, '/api/v1/subscriptions/me/');
          return MockResponse(
            jsonEncode({
              'subscription': {
                'id': 'subscription-owner',
                'status': {'label': 'Actif', 'explanation': 'Disponible'},
                'current_base': {
                  'name': 'Formule canonique',
                  'billing_terms': {
                    'amount': '12.00',
                    'currency': 'USD',
                    'period_unit': 'month',
                    'period_count': 1,
                  },
                  'benefits': [
                    {'title': 'Avantage canonique'},
                  ],
                },
                'active_addons': [],
              },
              'capabilities': [
                {
                  'name': 'Capacité mesurée',
                  'value': 3,
                  'value_label': '3 opérations',
                  'usage': 4,
                  'usage_label': '4 utilisées sur 3',
                  'allowed': false,
                  'over_limit': true,
                },
              ],
              'ongoing_conditions': [
                {'label': 'Condition attendue', 'state': 'pending'},
              ],
              'transition': {
                'target_name': 'Option attendue',
                'status_label': 'En cours',
                'status_explanation': 'Vérification',
                'total_conditions': 1,
                'completed_conditions': 0,
                'conditions': [
                  {'label': 'Justificatif attendu', 'state': 'pending'},
                ],
              },
              'history': {
                'items': [
                  {
                    'id': 'transition-1',
                    'target_name': 'Ancienne formule',
                    'kind_label': 'Changement',
                    'status_label': 'Terminée',
                    'requested_at': '2026-10-12T10:00:00Z',
                  },
                ],
                'next_offset': null,
              },
              'catalog': [],
              'billing': {'items': [], 'next_offset': null},
            }),
            200,
          );
        }).dio,
      );
      final runtime = AppRuntime(
        tokens: tokens,
        session: null,
        recovery: SessionRecoveryController(),
        api: api,
      );
      addTearDown(runtime.close);
      await tester.pumpWidget(
        MaterialApp(home: BillingScreen(runtime: runtime)),
      );
      await tester.pumpAndSettle();

      expect(find.text('Formule canonique'), findsOneWidget);
      expect(find.text('USD 12.00 / mois'), findsOneWidget);
      expect(find.text('Avantage canonique'), findsOneWidget);
      expect(find.text('Capacité mesurée'), findsOneWidget);
      expect(find.textContaining('Limite dépassée'), findsOneWidget);
      expect(find.text('Justificatif attendu'), findsOneWidget);
      expect(find.text('Ancienne formule'), findsOneWidget);
      expect(find.text('Mes changements'), findsOneWidget);
    },
  );
}
