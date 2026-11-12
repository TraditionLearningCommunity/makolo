import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/features/occurrence/occurrence_scanner_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';
import 'fakes.dart';

void main() {
  const occurrenceId = 'occ-1';
  const controlPath = '/api/v1/scanner/occurrences/occ-1/control/';

  Future<void> pumpScanner(
    WidgetTester tester, {
    required MockHandler handler,
  }) async {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final client = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: MockClient(handler).dio,
    );
    addTearDown(client.close);
    final runtime = AppRuntime(
      tokens: tokens,
      session: tokens.session,
      recovery: SessionRecoveryController(),
      api: client,
    );
    await tester.pumpWidget(
      MaterialApp(
        home: OccurrenceScannerScreen(
          runtime: runtime,
          occurrenceId: occurrenceId,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  MockResponse contextResponse() => MockResponse(
    jsonEncode({
      'data': {
        'identity': {'kind': 'occurrence', 'id': occurrenceId},
        'occurrence': {'label': 'Session terrain'},
        'links': {'scan': controlPath},
        'capabilities': ['scan'],
      },
    }),
    200,
  );

  Future<void> confirmManualControl(WidgetTester tester) async {
    await tester.enterText(find.byType(TextField), 'qr-test');
    await tester.ensureVisible(find.text('Contrôler ce code'));
    await tester.tap(find.text('Contrôler ce code'));
    await tester.pumpAndSettle();
    expect(find.text('Confirmer le contrôle'), findsOneWidget);
    await tester.tap(find.text('Contrôler').last);
    await tester.pumpAndSettle();
  }

  testWidgets('Invalid manual code is a known refusal, not uncertain use', (
    tester,
  ) async {
    var posts = 0;
    await pumpScanner(
      tester,
      handler: (request) async {
        if (request.url.path.endsWith('/context/')) {
          return contextResponse();
        }
        expect(request.url.path, controlPath);
        posts++;
        return const MockResponse('{"detail":"Code invalide"}', 400);
      },
    );
    await confirmManualControl(tester);
    expect(posts, 1);
    expect(find.textContaining('Code refusé'), findsOneWidget);
    expect(find.text('Contrôle précédent vérifié : reprendre'), findsNothing);
    expect(find.text('Contrôler ce code'), findsOneWidget);
  });

  testWidgets('Uncertain server response requires conscious recovery', (
    tester,
  ) async {
    var posts = 0;
    var contexts = 0;
    await pumpScanner(
      tester,
      handler: (request) async {
        if (request.url.path.endsWith('/context/')) {
          contexts++;
          return contextResponse();
        }
        expect(request.url.path, controlPath);
        posts++;
        return const MockResponse('{"detail":"Indisponible"}', 503);
      },
    );
    await confirmManualControl(tester);
    expect(posts, 1);
    expect(find.textContaining('Contrôle non confirmé'), findsWidgets);
    expect(find.text('Contrôle précédent vérifié : reprendre'), findsOneWidget);

    // Even a fresh authorization GET does not prove the previous POST result.
    await tester.tap(find.byTooltip('Vérifier les autorisations'));
    await tester.pumpAndSettle();
    expect(contexts, greaterThan(2));
    expect(find.text('Contrôle précédent vérifié : reprendre'), findsOneWidget);
    expect(posts, 1);

    await tester.ensureVisible(
      find.text('Contrôle précédent vérifié : reprendre'),
    );
    await tester.tap(find.text('Contrôle précédent vérifié : reprendre'));
    await tester.pumpAndSettle();
    expect(find.text('Contrôle précédent vérifié : reprendre'), findsNothing);
    expect(posts, 1);
  });
}
