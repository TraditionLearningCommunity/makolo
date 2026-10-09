import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/features/settings/account_screen.dart';

import 'fakes.dart';

void main() {
  testWidgets('account exposes supported access capabilities only', (\n    tester,\n  ) async {
    final tokens = MemoryTokenStore();
    await tokens.saveAccount(
      DeviceAccount(
        profileId: 'profile-a',
        username: 'amina',
        email: 'amina@example.com',
        displayName: 'Amina',
        hasQuickAccess: false,
        lastUsedAt: DateTime.utc(2026, 10, 9),
      ),
    );
    await tokens.writeSession(
      const AuthSession(
        profileId: 'profile-a',
        accessToken: 'access',
        refreshToken: 'refresh',
      ),
    );
    final runtime = AppRuntime(
      tokens: tokens,
      session: await tokens.readSession(),
      recovery: SessionRecoveryController(),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AccountScreen(
          runtime: runtime,
          onChangePassword: () {},
          onRememberedAccounts: () {},
          onConnections: () {},
          onBilling: () {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Compte'), findsOneWidget);
    expect(find.text('@amina'), findsOneWidget);
    expect(find.text('amina@example.com'), findsOneWidget);
    expect(find.text('Changer le mot de passe'), findsOneWidget);
    expect(find.text('Comptes mémorisés'), findsOneWidget);
    expect(find.text('Connexions'), findsOneWidget);
    expect(find.text('Abonnement & facturation'), findsOneWidget);
    expect(find.text('Passkey'), findsNothing);
    expect(find.text('2FA'), findsNothing);
    expect(find.text('Supprimer le compte'), findsNothing);
  });
}
