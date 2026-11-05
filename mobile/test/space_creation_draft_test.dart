import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/features/space/space_create_screen.dart';
import 'package:makolo_mobile/repositories/draft_repository.dart';
import 'package:makolo_mobile/sync/outbox/outbox_repository.dart';

import 'fakes.dart';

void main() {
  late MakoloDatabase database;
  late DraftRepository drafts;
  late AppRuntime runtime;

  setUp(() {
    database = MakoloDatabase.memory();
    final session = const AuthSession(
      accessToken: 'access',
      refreshToken: 'refresh',
      profileId: 'profile-a',
    );
    drafts = DraftRepository(
      database: database,
      outbox: OutboxRepository(database, 'profile-a'),
      profileId: 'profile-a',
    );
    runtime = AppRuntime(
      tokens: MemoryTokenStore(session: session),
      session: session,
      recovery: SessionRecoveryController(),
      database: database,
      drafts: drafts,
    );
  });
  tearDown(() async => database.close());

  testWidgets('Space creation draft survives screen disposal and re-entry',
      (tester) async {
    await tester.pumpWidget(MaterialApp(home: SpaceCreateScreen(runtime: runtime)));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField), 'Association Makolo');
    await tester.pump(const Duration(milliseconds: 500));
    await tester.pumpAndSettle();

    final first = await drafts.read(
      owner: 'Organizations',
      resourceKind: 'space.creation',
      resourceId: 'new',
    );
    expect(first?.payload['name'], 'Association Makolo');
    expect(first?.payload['submission_state'], 'editing');

    await tester.pumpWidget(const MaterialApp(home: SizedBox.shrink()));
    await tester.pumpAndSettle();
    await tester.pumpWidget(MaterialApp(home: SpaceCreateScreen(runtime: runtime)));
    await tester.pumpAndSettle();

    expect(find.text('Association Makolo'), findsOneWidget);
    expect(await database.select(database.outboxOperations).get(), isEmpty);
  });

  testWidgets('an ambiguous Space creation is not replayed on cold entry',
      (tester) async {
    await drafts.saveLocal(
      draftId: 'space:create',
      owner: 'Organizations',
      resourceKind: 'space.creation',
      resourceId: 'new',
      payload: {
        'name': 'Espace en verification',
        'public_profile': false,
        'submission_state': 'verification_required',
      },
    );

    await tester.pumpWidget(MaterialApp(home: SpaceCreateScreen(runtime: runtime)));
    await tester.pumpAndSettle();

    expect(find.text('Espace en verification'), findsOneWidget);
    expect(find.textContaining('Une demande précédente est incertaine'), findsOneWidget);
    final button = tester.widget<FilledButton>(find.byType(FilledButton));
    expect(button.onPressed, isNull,
        reason: 'A cold restart must never resend an ambiguous owner POST');
    expect(await database.select(database.outboxOperations).get(), isEmpty);
  });

  testWidgets('owner-created Space keeps verification identity, not authority',
      (tester) async {
    await drafts.saveLocal(
      draftId: 'space:create',
      owner: 'Organizations',
      resourceKind: 'space.creation',
      resourceId: 'new',
      payload: {
        'name': 'Espace existe',
        'public_profile': true,
        'submission_state': 'created_unverified',
        'created_space_id': 'space-1',
        'created_space_slug': 'espace-existe',
      },
    );
    await tester.pumpWidget(MaterialApp(home: SpaceCreateScreen(runtime: runtime)));
    await tester.pumpAndSettle();
    expect(find.text('Vérifier mon accès'), findsOneWidget);
    expect(find.text('Créer cet Espace'), findsOneWidget);
    final button = tester.widget<FilledButton>(find.byType(FilledButton));
    expect(button.onPressed, isNull);
  });
}
