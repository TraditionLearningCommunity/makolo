import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/continuity/conversation_list_tile.dart';

import 'support/presentation_harness.dart';

void main() {
  const longTitle =
      'Marché des coopératives, préparation des démarches collectives à Lubumbashi';
  const longContext = 'Lubumbashi — modalités et conditions d’accès au marché';

  Widget tile({
    required VoidCallback onTap,
    List<String> mediaKinds = const ['image', 'voice', 'file', 'poll', 'form'],
    int attentionCount = 2,
    String title = longTitle,
    String contextKind = 'activity',
  }) => ConversationListTile(
    title: title,
    contextKind: contextKind,
    subtitle: longContext,
    preview: 'Les documents nécessaires sont prêts pour la suite.',
    previewKind: 'result',
    mediaKinds: mediaKinds,
    attentionCount: attentionCount,
    updatedAt: DateTime.utc(2026, 11, 4, 9),
    onTap: onTap,
  );

  testWidgets(
    'visual C5: one recognizable title, compact preview, real media icon affordances',
    (tester) async {
      var taps = 0;
      await PresentationHarness.pump(tester, child: tile(onTap: () => taps++));
      expect(find.text(longTitle), findsOneWidget);
      expect(find.byIcon(Icons.local_activity_rounded), findsOneWidget);
      expect(find.byIcon(Icons.image_rounded), findsOneWidget);
      expect(find.byIcon(Icons.mic_rounded), findsOneWidget);
      expect(find.byIcon(Icons.attach_file_rounded), findsOneWidget);
      expect(find.byIcon(Icons.poll_rounded), findsOneWidget);
      expect(find.textContaining('2 à faire'), findsOneWidget);

      final titleWidget = tester.widget<Text>(find.text(longTitle));
      expect(titleWidget.maxLines, 2);
      final preview = tester.widget<Text>(
        find.text('Les documents nécessaires sont prêts pour la suite.'),
      );
      expect(preview.maxLines, 1);

      await tester.tap(find.byType(ConversationListTile));
      expect(taps, 1);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'visual C5: no fabricated media and direct identity keeps intuitive avatar icon',
    (tester) async {
      await PresentationHarness.pump(
        tester,
        child: tile(
          onTap: () {},
          contextKind: 'direct',
          title: 'Mado Kalala',
          mediaKinds: const [],
          attentionCount: 0,
        ),
      );
      expect(find.byIcon(Icons.person_rounded), findsOneWidget);
      expect(find.byIcon(Icons.mic_rounded), findsNothing);
      expect(find.byIcon(Icons.image_rounded), findsNothing);
      expect(find.textContaining('à faire'), findsNothing);
    },
  );

  testWidgets('visual C5: compact, medium and wide at 1.6x do not overflow', (
    tester,
  ) async {
    for (final size in <Size>[
      const Size(320, 700),
      const Size(360, 800),
      const Size(430, 932),
      const Size(834, 1112),
      const Size(1440, 900),
    ]) {
      await PresentationHarness.pump(
        tester,
        viewport: size,
        textScale: 1.6,
        reduceMotion: true,
        brightness: size.width > 800 ? Brightness.dark : Brightness.light,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: tile(onTap: () {}),
        ),
      );
      expect(
        tester.takeException(),
        isNull,
        reason: 'Overflow at ${size.width}',
      );
      expect(find.byType(ConversationListTile), findsOneWidget);
    }
  });

  testWidgets('visual C5: semantic single action and content signal label', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    await PresentationHarness.pump(tester, child: tile(onTap: () {}));
    expect(
      find.bySemanticsLabel(RegExp('Marché des coopératives.*Contenus :')),
      findsOneWidget,
    );
    handle.dispose();
  });

  test('context and media icons are canonical, not message-unread cues', () {
    expect(ConversationListTile.contextIcon('space'), Icons.business_rounded);
    expect(ConversationListTile.contextIcon('group'), Icons.groups_rounded);
    expect(ConversationListTile.mediaLabel('voice'), 'Vocal');
    expect(ConversationListTile.mediaLabel('image'), 'Photo');
    expect(ConversationListTile.mediaLabel('form'), 'Formulaire');
  });
}
