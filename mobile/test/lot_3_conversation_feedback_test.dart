import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/continuity/conversation_composer.dart';
import 'package:makolo_mobile/features/continuity/conversation_local_delivery.dart';
import 'package:makolo_mobile/features/continuity/conversation_repository.dart';

class _DeferredComposerRepository implements ConversationRepository {
  @override
  ConversationLocalDelivery? delivery;

  final Completer<String> response = Completer<String>();
  int attempts = 0;

  @override
  Future<String> compose({
    required String conversationId,
    required String clientReference,
    required String mode,
    String? kind,
    String? body,
    String? title,
    List<String>? options,
    bool multipleChoice = false,
    String? audienceId,
    String? pointId,
    String? representedSpaceId,
  }) {
    attempts++;
    return response.future;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  Future<void> render(
    WidgetTester tester,
    ConversationRepository repository,
  ) => tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: ConversationComposer(
          repository: repository,
          conversationId: 'conversation-a',
          capabilities: const {'text_mode': 'information'},
          onPublished: (_) {},
        ),
      ),
    ),
  );

  testWidgets('one pending conversation send cannot be tapped twice', (
    tester,
  ) async {
    final repository = _DeferredComposerRepository();
    await render(tester, repository);
    await tester.enterText(
      find.byKey(const Key('conversation-compose-text')),
      'Un message à envoyer',
    );
    await tester.tap(find.byKey(const Key('conversation-compose-send')));
    await tester.pump();
    expect(repository.attempts, 1);
    await tester.tap(
      find.byKey(const Key('conversation-compose-send')),
      warnIfMissed: false,
    );
    expect(repository.attempts, 1);

    repository.response.complete('confirmed-point');
    await tester.pump();
    expect(find.text('Envoi confirmé'), findsOneWidget);
    expect(find.text('Un message à envoyer'), findsNothing);
  });

  testWidgets('unconfirmed send preserves the text and offers safe retry', (
    tester,
  ) async {
    final repository = _DeferredComposerRepository();
    await render(tester, repository);
    await tester.enterText(
      find.byKey(const Key('conversation-compose-text')),
      'Texte important à conserver',
    );
    await tester.tap(find.byKey(const Key('conversation-compose-send')));
    repository.response.completeError(StateError('test server failure'));
    await tester.pump();
    expect(repository.attempts, 1);
    expect(find.text('Texte important à conserver'), findsOneWidget);
    expect(find.text('Envoi non conservé. Réessayer.'), findsOneWidget);
  });
}
