import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/features/mark/mark_repository.dart';
import 'package:makolo_mobile/features/mark/mark_screen.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/repositories/draft_repository.dart';
import 'package:makolo_mobile/sync/outbox/outbox_repository.dart';
import 'package:makolo_mobile/auth/token_store.dart';

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

  test(
    'a local document is never represented as a server submission',
    () async {
      final runtime = AppRuntime(
        tokens: MemoryTokenStore(),
        session: null,
        recovery: SessionRecoveryController(),
      );
      final repository = MarkRepository(runtime);
      final result = await repository.submit(
        actor: const PersonalActorContext(),
        input: '',
        inputKind: 'document',
        attachments: [
          {'file_id': 'local-only', 'purpose': 'mark_intake'},
        ],
      );
      expect(result.state, 'local_attachments_only');
      expect(result.message, contains('Aucun fichier n’a été transmis'));
    },
  );

  test('a local URL is not treated as an interpreted reference', () async {
    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
    );
    final result = await MarkRepository(runtime).submit(
      actor: const PersonalActorContext(),
      input: '',
      links: ['https://example.org/opportunity'],
    );
    expect(result.state, 'local_references_only');
    expect(result.message, contains('pas interprétés'));
  });

  testWidgets(
    'initial Mark keeps input dominant and exposes native intake actions',
    (tester) async {
      final runtime = AppRuntime(
        tokens: MemoryTokenStore(),
        session: null,
        recovery: SessionRecoveryController(),
      );

      await tester.pumpWidget(MaterialApp(home: MarkScreen(runtime: runtime)));
      await tester.pump();

      expect(find.text('Qu’est-ce que vous avez en tête ?'), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);
      expect(find.text('Joindre'), findsOneWidget);
      expect(find.text('Photo'), findsOneWidget);
      expect(find.text('Image'), findsOneWidget);
      expect(find.text('Lien'), findsOneWidget);
      expect(find.text('Voix'), findsOneWidget);
      expect(find.text('Continuer'), findsOneWidget);
      expect(find.textContaining('A1'), findsNothing);
      expect(find.textContaining('A2'), findsNothing);
    },
  );

  testWidgets(
    'microphone is never presented as a successful capture without storage',
    (tester) async {
      final runtime = AppRuntime(
        tokens: MemoryTokenStore(),
        session: null,
        recovery: SessionRecoveryController(),
      );
      await tester.pumpWidget(MaterialApp(home: MarkScreen(runtime: runtime)));
      await tester.pump();
      await tester.tap(find.text('Voix'));
      await tester.pumpAndSettle();
      expect(find.text('Enregistrer un audio'), findsOneWidget);
      await tester.tap(find.text('Enregistrer un audio'));
      await tester.pumpAndSettle();
      expect(
        find.text('L’enregistrement n’est pas disponible dans cette session.'),
        findsOneWidget,
      );
    },
  );

  testWidgets('Mark runtime switch does not display another Profile draft', (
    tester,
  ) async {
    final dbA = MakoloDatabase.memory();
    final dbB = MakoloDatabase.memory();
    addTearDown(dbA.close);
    addTearDown(dbB.close);

    DraftRepository makeDrafts(MakoloDatabase db, String profile) =>
        DraftRepository(
          database: db,
          outbox: OutboxRepository(db, profile),
          profileId: profile,
        );
    final draftsA = makeDrafts(dbA, 'profile-a');
    final draftsB = makeDrafts(dbB, 'profile-b');
    for (final entry in [
      (draftsA, 'Texte privé A'),
      (draftsB, 'Texte privé B'),
    ]) {
      await entry.$1.saveLocal(
        draftId: 'mark:personal',
        owner: 'profile',
        resourceKind: 'mark_intake',
        resourceId: 'mark:personal',
        payload: {'input': entry.$2, 'attachments': <Object>[]},
      );
    }
    AppRuntime runtime(String profile, DraftRepository drafts) => AppRuntime(
      tokens: MemoryTokenStore(),
      session: AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: profile,
      ),
      recovery: SessionRecoveryController(),
      drafts: drafts,
    );
    final first = runtime('profile-a', draftsA);
    final second = runtime('profile-b', draftsB);
    await tester.pumpWidget(MaterialApp(home: MarkScreen(runtime: first)));
    await tester.pumpAndSettle();
    expect(
      tester.widget<TextField>(find.byType(TextField)).controller?.text,
      'Texte privé A',
    );

    await tester.pumpWidget(MaterialApp(home: MarkScreen(runtime: second)));
    await tester.pumpAndSettle();
    final editor = tester.widget<TextField>(find.byType(TextField));
    expect(editor.controller?.text, 'Texte privé B');
    expect(editor.controller?.text, isNot(contains('Texte privé A')));
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Mark never renders a second Space design', (tester) async {
    final runtime = AppRuntime(
      tokens: MemoryTokenStore(),
      session: null,
      recovery: SessionRecoveryController(),
    );

    await tester.pumpWidget(MaterialApp(home: MarkScreen(runtime: runtime)));
    await tester.pump();

    expect(find.text('Makolo Mark'), findsNothing);
    expect(find.text('Agent'), findsNothing);
    expect(find.text('Thinking with AI'), findsNothing);
  });

  testWidgets('selected context is visible without granting authority', (
    tester,
  ) async {
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

    expect(
      find.textContaining('Élément sélectionné pour cette demande'),
      findsOneWidget,
    );
  });
}
