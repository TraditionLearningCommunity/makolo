import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/action_controls.dart';
import 'package:makolo_mobile/features/continuity/objective_create_screen.dart';
import 'package:makolo_mobile/features/continuity/objective_creation_draft.dart';
import 'package:makolo_mobile/features/continuity/objective_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/repositories/draft_repository.dart';
import 'package:makolo_mobile/sync/outbox/outbox_repository.dart';

import 'fakes.dart';

class _CreateApi extends MakoloApiClient {
  _CreateApi()
    : super(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: MemoryTokenStore(
          session: const AuthSession(
            accessToken: 'test',
            refreshToken: 'test',
            profileId: 'viewer',
          ),
        ),
      );

  final Completer<ApiResponse> response = Completer<ApiResponse>();
  int calls = 0;

  @override
  Future<ApiResponse> post(
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) {
    calls += 1;
    return response.future;
  }
}

void main() {
  late MakoloDatabase db;
  late DraftRepository drafts;
  late ObjectiveRepository objectives;
  late _CreateApi api;

  setUp(() {
    db = MakoloDatabase.memory();
    drafts = DraftRepository(
      database: db,
      outbox: OutboxRepository(db, 'viewer'),
      profileId: 'viewer',
    );
    objectives = ObjectiveRepository(
      database: db,
      store: ProfileStore(db, 'viewer'),
      profileId: 'viewer',
    );
    api = _CreateApi();
  });

  tearDown(() async {
    api.close(force: true);
    await db.close();
  });

  Widget createScreen({String kind = 'dossier'}) => MaterialApp(
    home: ObjectiveCreateScreen(
      kind: kind,
      api: api,
      drafts: drafts,
      repository: objectives,
      onCreated: (_) {},
    ),
  );

  testWidgets('unsent Objectives fields resume quietly on cold entry', (
    tester,
  ) async {
    await tester.pumpWidget(createScreen(kind: 'project'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField).first, 'Projet en cours');
    await tester.enterText(
      find.byType(TextFormField).last,
      'Une intention conservée',
    );
    await tester.pump(const Duration(milliseconds: 450));
    await tester.pumpAndSettle();

    final first = await drafts.read(
      owner: 'Objectives',
      resourceKind: 'objective.creation',
      resourceId: 'project:personal',
    );
    expect(first?.payload['title'], 'Projet en cours');
    expect(first?.payload['description'], 'Une intention conservée');
    expect(first?.payload['submission_state'], 'editing');
    expect(api.calls, 0);

    await tester.pumpWidget(const MaterialApp(home: SizedBox.shrink()));
    await tester.pumpAndSettle();
    await tester.pumpWidget(createScreen(kind: 'project'));
    await tester.pumpAndSettle();
    expect(find.text('Projet en cours'), findsOneWidget);
    expect(find.text('Une intention conservée'), findsOneWidget);
    expect(api.calls, 0);
    expect(await db.select(db.outboxOperations).get(), isEmpty);
  });

  testWidgets('a possibly sent creation is not replayed on reopening', (
    tester,
  ) async {
    final draft = ObjectiveCreationDraft(
      repository: drafts,
      profileId: 'viewer',
      kind: 'dossier',
    );
    await draft.save({
      'title': 'Dossier à vérifier',
      'description': 'Préparation',
      'submission_state': 'verification_required',
    });
    await tester.pumpWidget(createScreen());
    await tester.pumpAndSettle();

    expect(find.text('Dossier à vérifier'), findsOneWidget);
    expect(find.text('À vérifier'), findsOneWidget);
    expect(
      tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
      isNull,
    );
    expect(api.calls, 0);

    await tester.tap(find.text('Reprendre'));
    await tester.pumpAndSettle();
    expect(find.text('Reprendre ?'), findsOneWidget);
    await tester.tap(find.text('Annuler'));
    await tester.pumpAndSettle();
    expect(api.calls, 0);

    await tester.tap(find.text('Reprendre'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('J’ai vérifié'));
    await tester.pumpAndSettle();
    expect(api.calls, 0);
    expect((await draft.read())?.payload['submission_state'], 'editing');
    expect(
      tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
      isNotNull,
    );
    expect(await db.select(db.outboxOperations).get(), isEmpty);
  });

  testWidgets('uncertain POST is kept for review, never auto-sent again', (
    tester,
  ) async {
    await tester.pumpWidget(createScreen());
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byType(TextFormField).first,
      'Dossier incertain',
    );
    await tester.tap(
      find.widgetWithText(MakoloActionButton, 'Créer un dossier'),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 160));
    expect(api.calls, 1);

    api.response.completeError(StateError('transport interrupted'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 150));
    final draft = ObjectiveCreationDraft(
      repository: drafts,
      profileId: 'viewer',
      kind: 'dossier',
    );
    expect(
      (await draft.read())?.payload['submission_state'],
      'verification_required',
    );
    await tester.pumpWidget(const MaterialApp(home: SizedBox.shrink()));
    await tester.pumpAndSettle();
    await tester.pumpWidget(createScreen());
    await tester.pumpAndSettle();
    expect(find.text('À vérifier'), findsOneWidget);
    expect(api.calls, 1);
  });

  testWidgets('confirmed identity survives restart without new creation', (
    tester,
  ) async {
    await tester.pumpWidget(createScreen());
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byType(TextFormField).first,
      'Dossier confirmé',
    );
    await tester.tap(
      find.widgetWithText(MakoloActionButton, 'Créer un dossier'),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 160));
    expect(api.calls, 1);
    api.response.complete(
      const ApiResponse(201, '{"id":"dossier-confirmed"}', {}),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 180));

    final draft = ObjectiveCreationDraft(
      repository: drafts,
      profileId: 'viewer',
      kind: 'dossier',
    );
    expect((await draft.read())?.payload['submission_state'], 'confirmed');
    expect((await draft.read())?.payload['confirmed_id'], 'dossier-confirmed');
    await tester.pumpWidget(const MaterialApp(home: SizedBox.shrink()));
    await tester.pumpAndSettle();
    await tester.pumpWidget(createScreen());
    await tester.pumpAndSettle();
    expect(find.text('La réalisation a été créée.'), findsOneWidget);
    expect(api.calls, 1);

    await tester.tap(find.text('Créer un autre'));
    await tester.pumpAndSettle();
    expect(await draft.read(), isNull);
    expect(find.text('Créer un dossier'), findsWidgets);
  });

  test('stale screens cannot downgrade pending or confirmed drafts', () async {
    final first = ObjectiveCreationDraft(
      repository: drafts, profileId: 'viewer', kind: 'dossier',
    );
    final second = ObjectiveCreationDraft(
      repository: drafts, profileId: 'viewer', kind: 'dossier',
    );
    await first.save({'title': 'En préparation', 'submission_state': 'editing'});
    await second.save({
      'title': 'En préparation',
      'submission_state': 'verification_required',
    });
    await expectLater(
      first.save({'title': 'Ancien écran', 'submission_state': 'editing'}),
      throwsStateError,
    );
    expect(
      (await second.read())?.payload['submission_state'],
      'verification_required',
    );
    await second.save(
      {'title': 'Vérifié', 'submission_state': 'editing'},
      verifiedReopen: true,
    );
    await second.save({
      'title': 'Vérifié',
      'submission_state': 'verification_required',
    });
    await second.save({
      'title': 'Vérifié',
      'submission_state': 'confirmed',
      'confirmed_id': 'owner-id',
    });
    await expectLater(
      first.save(
        {'title': 'Autre', 'submission_state': 'editing'},
        verifiedReopen: true,
      ),
      throwsStateError,
    );
    expect((await first.read())?.payload['confirmed_id'], 'owner-id');
  });

  test('creation drafts are isolated by Profile, kind and Space', () async {
    final dossier = ObjectiveCreationDraft(
      repository: drafts,
      profileId: 'viewer',
      kind: 'dossier',
    );
    final project = ObjectiveCreationDraft(
      repository: drafts,
      profileId: 'viewer',
      kind: 'project',
    );
    final inSpace = ObjectiveCreationDraft(
      repository: drafts,
      profileId: 'viewer',
      kind: 'dossier',
      spaceId: 'space-a',
    );
    final anotherProfile = DraftRepository(
      database: db,
      outbox: OutboxRepository(db, 'other'),
      profileId: 'other',
    );
    final other = ObjectiveCreationDraft(
      repository: anotherProfile,
      profileId: 'other',
      kind: 'dossier',
    );
    await dossier.save({'title': 'Moi', 'submission_state': 'editing'});
    await project.save({'title': 'Projet', 'submission_state': 'editing'});
    await inSpace.save({'title': 'Espace A', 'submission_state': 'editing'});
    await other.save({'title': 'Autre Profil', 'submission_state': 'editing'});
    expect((await dossier.read())?.payload['title'], 'Moi');
    expect((await project.read())?.payload['title'], 'Projet');
    expect((await inSpace.read())?.payload['title'], 'Espace A');
    expect((await other.read())?.payload['title'], 'Autre Profil');
    expect(await db.select(db.outboxOperations).get(), isEmpty);
  });
}
