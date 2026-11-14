import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';

import 'fakes.dart';

import 'package:makolo_mobile/features/settings/billing_screen.dart';

void main() {
  testWidgets('billing stays human and does not invent commercial data', (
    tester,
  ) async {
    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
    );
    await tester.pumpWidget(MaterialApp(home: BillingScreen(runtime: runtime)));
    await tester.pumpAndSettle();

    expect(find.text('Abonnement & facturation'), findsOneWidget);
    expect(
      find.text('Aucune information fiable n’est disponible pour le moment.'),
      findsOneWidget,
    );
    expect(find.textContaining('provider'), findsNothing);
    expect(find.textContaining('capacité réelle'), findsNothing);
    expect(find.textContaining('prix'), findsNothing);
  });

  testWidgets('renders a server-backed plan and a real billing obligation', (
    tester,
  ) async {
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
              'status': {
                'label': 'Actif',
                'explanation': 'Votre abonnement est opérationnel.',
              },
              'current_base': {
                'name': 'Makolo Pro',
                'description': 'Formule personnelle',
              },
              'active_addons': [],
            },
            'billing': {
              'items': [
                {
                  'label': 'Cotisation octobre',
                  'amount': '12.00',
                  'currency': 'USD',
                  'status': 'due',
                },
              ],
              'next_offset': null,
            },
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
    await tester.pumpWidget(MaterialApp(home: BillingScreen(runtime: runtime)));
    await tester.pumpAndSettle();
    expect(find.text('Makolo Pro'), findsOneWidget);
    expect(find.text('Actif'), findsOneWidget);
    await tester.ensureVisible(find.text('Facturation'));
    await tester.tap(find.text('Facturation'));
    await tester.pumpAndSettle();
    expect(find.text('Cotisation octobre'), findsOneWidget);
    expect(find.textContaining('12.00 USD'), findsOneWidget);
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(find.text('Abonnement & facturation'), findsOneWidget);
    expect(find.text('Changer de formule'), findsOneWidget);
  });

  testWidgets('empty billing stays compact and hides implementation language', (
    tester,
  ) async {
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
              'status': {'label': 'Actif'},
              'current_base': {'name': 'Makolo Base'},
              'active_addons': <Object>[],
            },
            'billing': {'items': <Object>[], 'next_offset': null},
            'catalog': <Object>[],
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
    await tester.pumpWidget(MaterialApp(home: BillingScreen(runtime: runtime)));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Facturation'));
    await tester.tap(find.text('Facturation'));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('Aucun montant enregistré pour cet abonnement'),
      findsOneWidget,
    );
    expect(find.textContaining('ceux du serveur'), findsNothing);
    expect(find.textContaining('hors ligne'), findsNothing);
  });
}
