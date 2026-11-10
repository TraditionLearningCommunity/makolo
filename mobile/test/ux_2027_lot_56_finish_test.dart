import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/behavior_primitives.dart';
import 'package:makolo_mobile/features/continuity/conversation_media_group.dart';
import 'package:makolo_mobile/presentation/media/retained_public_discovery_image.dart';

import 'support/presentation_harness.dart';

void main() {
  final gallery = List<Map<String, dynamic>>.generate(
    5,
    (index) => {
      'id': 'preview-$index',
      'kind': 'video',
      'caption': 'Une légende utile à lire',
      'name': 'video-$index.mp4',
    },
  );

  for (final brightness in [Brightness.light, Brightness.dark]) {
    for (final width in [180.0, 280.0, 360.0]) {
      testWidgets(
        'five private media tiles stay readable at $width / $brightness',
        (tester) async {
          await PresentationHarness.pump(
            tester,
            viewport: Size(width, 740),
            brightness: brightness,
            textScale: 1.6,
            reduceMotion: true,
            child: SingleChildScrollView(
              child: ConversationMediaGroup(attachments: gallery),
            ),
          );
          expect(find.byType(GridView), findsOneWidget);
          expect(find.text('+2'), findsOneWidget);
          expect(tester.takeException(), isNull);
          final grid = tester.widget<GridView>(find.byType(GridView));
          expect(grid.shrinkWrap, isTrue);
          expect(grid.physics, isA<NeverScrollableScrollPhysics>());
        },
      );
    }
  }

  testWidgets(
    'published media respects motion settings without fetching an untrusted URL',
    (tester) async {
      const url = 'https://other.example/image.jpg';
      await PresentationHarness.pump(
        tester,
        viewport: const Size(280, 500),
        reduceMotion: true,
        child: SizedBox(
          width: 180,
          height: 120,
          child: RetainedPublicDiscoveryImage(
            url: _RejectedUrl.value,
            trustedOrigin: _TrustedUrl.value,
            placeholder: const Icon(Icons.image_not_supported_outlined),
          ),
        ),
      );
      expect(find.byIcon(Icons.image_not_supported_outlined), findsOneWidget);
      final transition = tester.widget<AnimatedSwitcher>(
        find.byKey(const ValueKey<String>('published-image-$url')),
      );
      expect(transition.duration, Duration.zero);
      expect(tester.takeException(), isNull);
    },
  );
}

abstract final class _RejectedUrl {
  static final value = Uri.parse('https://other.example/image.jpg');
}

abstract final class _TrustedUrl {
  static final value = Uri.parse('https://makolo.example/');
}
