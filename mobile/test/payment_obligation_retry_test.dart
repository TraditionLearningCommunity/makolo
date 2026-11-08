import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/features/payments/payment_obligation_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  testWidgets(
    'a confirmed declined attempt may retry with a fresh payment key',
    (tester) async {
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          profileId: 'payer',
          accessToken: 'access',
          refreshToken: 'refresh',
        ),
      );
      final keys = <String>[];
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: tokens,
        dio: MockClient((request) async {
          if (request.url.path == '/api/v1/payments/configuration/') {
            return MockResponse(jsonEncode({'sandbox_enabled': true}), 200);
          }
          if (request.url.path == '/api/v1/payments/obligations/bill-1/' &&
              request.body.isEmpty) {
            return MockResponse(
              jsonEncode({
                'id': 'bill-1',
                'label': 'Abonnement DEMO',
                'amount': '18.00',
                'currency': 'USD',
                'status': 'pending',
                'processing_mode': 'makolo_provider',
                'capabilities': ['pay'],
                'active_payment': null,
              }),
              200,
            );
          }
          if (request.url.path == '/api/v1/payments/obligations/bill-1/') {
            final payload = jsonDecode(request.body) as Map<String, dynamic>;
            keys.add(payload['idempotency_key'] as String);
            return MockResponse(
              jsonEncode({
                'id': 'attempt-${keys.length}',
                'provider': 'sandbox',
                'status': 'failed',
              }),
              200,
            );
          }
          throw StateError('Unexpected payment request: ${request.url.path}');
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
        MaterialApp(
          home: PaymentObligationScreen(
            runtime: runtime,
            obligationId: 'bill-1',
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Payer en sandbox'));
      await tester.pumpAndSettle();
      expect(
        find.text('Paiement refusé. Vous pouvez réessayer.'),
        findsOneWidget,
      );
      await tester.tap(find.text('Payer en sandbox'));
      await tester.pumpAndSettle();
      expect(keys, hasLength(2));
      expect(keys[0], isNot(keys[1]));
    },
  );
}
