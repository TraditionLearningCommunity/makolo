import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/features/mark/mark_repository.dart';
import 'package:makolo_mobile/features/mark/mark_screen.dart';

import 'fakes.dart';

void main() {
  test('offline submission remains an honest local draft', () async {
    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
    );

    final result = await MarkRepository(runtime).submit(
      actor: const PersonalActorContext(),
      input: 'Retrouve mon billet.',
    );

    expect(result.state, 'offline_draft');
    expect(result.offline, isTrue);
    expect(result.message, contains('Enregistré sur cet appareil'));
  });

  testWidgets(
    'initial Mark keeps input dominant and exposes native intake actions',
    (tester) async {
    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: MarkScreen(runtime: runtime),
      ),
    );
    await tester.pump();

    expect(find.text('Qu’est-ce que vous avez en tête ?'), findsOneWidget);
    expect(find.byType(TextField), findsOneWidget);
    expect(find.text('Joindre'), findsOneWidget);
    expect(find.text('Photo'), findsOneWidget);
    expect(find.text('Voix'), findsOneWidget);
    expect(find.text('Continuer'), findsOneWidget);
    expect(find.textContaining('A1'), findsNothing);
    expect(find.textContaining('A2'), findsNothing);
  });

  testWidgets('Mark never renders a second Space design', (tester) async {
    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: MarkScreen(runtime: runtime),
      ),
    );
    await tester.pump();

    expect(find.text('Makolo Mark'), findsNothing);
    expect(find.text('Agent'), findsNothing);
    expect(find.text('Thinking with AI'), findsNothing);
  });

  testWidgets(
    'selected context is visible without granting authority',
    (tester) async {
    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: MarkScreen(
          runtime: runtime,
          selectedContext: const {'kind': 'journey', 'id': '42'},
        ),
      ),
    );
    await tester.pump();

    expect(find.textContaining('Contexte sélectionné : journey'), findsOneWidget);
  });
}
