import 'dart:async';

import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/behavior_primitives.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/ongoing/ongoing_screen.dart';
import 'package:makolo_mobile/presentation/possibilities/discovery_save_icon.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

import 'support/presentation_harness.dart';

StoredProjection _projection({
  Map<String, dynamic>? continuation,
  List<Object> items = const [
    {
      'kind': 'journey',
      'source': {'kind': 'journey', 'id': '1'},
      'state': 'waiting',
      'title': 'Visa Canada',
      'ready': [
        {'title': 'Frais réglés'},
      ],
      'actor_interventions': [],
      'continuation': {
        'state': 'waiting',
        'summary': 'Le consulat examine votre dossier.',
      },
      'blocker': null,
      'next': {'title': 'Biométrie'},
      'timing': {'deadline_date': '2026-11-15'},
      'place': null,
      'capabilities': ['open_detail'],
      'links': {'detail': '/api/v1/me/journeys/1/'},
    },
  ],
}) => StoredProjection(
  kind: 'personal.ongoing',
  schemaVersion: 1,
  payload: {'items': items, 'continuation': ?continuation},
  receivedAt: DateTime.utc(2026, 10, 3),
  freshUntil: DateTime.utc(2026, 12, 1),
);

class _UnusedRepository extends PersonalRepository {
  _UnusedRepository() : super(_NeverUsedStore());
}

class _NeverUsedStore implements ProfileStore {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  setUpAll(() async {
    await initializeDateFormatting('fr');
  });
  test('N1 only resolves same-origin owner media over HTTP(S)', () {
    final api = Uri.parse('https://api.example.test/');
    expect(
      ongoingRecognitionImageUrl('/presentation/media/uses/u1/file/', api),
      'https://api.example.test/presentation/media/uses/u1/file/',
    );
    expect(
      ongoingRecognitionImageUrl('https://other.example.test/image.png', api),
      isNull,
    );
    expect(ongoingRecognitionImageUrl('file:///private/qr.png', api), isNull);
    expect(ongoingRecognitionImageUrl('javascript:alert(1)', api), isNull);
    expect(ongoingRecognitionImageUrl('/missing', null), isNull);
  });

  testWidgets('N1 uses the server cue without decorating an empty media slot', (
    tester,
  ) async {
    final projection = _projection(
      items: const [
        {
          'id': 'server-stable-identity',
          'kind': 'journey',
          'source': {'kind': 'journey', 'id': 'travel'},
          'state': 'available',
          'title': 'Lubumbashi → Kolwezi',
          'summary': 'Place confirmée.',
          'n1': {
            'cue': 'Accès disponible',
            'tone': 'ready',
            'when_label': '12/11/2026 · 14:00',
            'place_label': 'Lubumbashi',
          },
          'ready': [],
          'actor_interventions': [],
          'continuation': null,
          'blocker': null,
          'next': null,
          'timing': {},
          'place': {},
          'media_bindings': [],
          'capabilities': [],
          'links': {},
        },
      ],
    );
    await PresentationHarness.pump(
      tester,
      child: OngoingScreen(
        repository: _UnusedRepository(),
        projectionStream: Stream.value(projection),
      ),
    );
    await tester.pump();
    expect(find.text('Lubumbashi → Kolwezi'), findsOneWidget);
    expect(find.text('Accès disponible'), findsOneWidget);
    expect(find.text('12/11/2026 · 14:00'), findsOneWidget);
    expect(find.byKey(const Key('ongoing-n1-recognition-media')), findsNothing);
  });

  testWidgets('calm N1 omits unavailable actions and retains real detail', (
    tester,
  ) async {
    await PresentationHarness.pump(
      tester,
      child: OngoingScreen(
        repository: _UnusedRepository(),
        projectionStream: Stream.value(
          _projection(continuation: {'state': 'end', 'token': null}),
        ),
      ),
    );
    await tester.pump();
    expect(find.byKey(const Key('ongoing-n1-discover-actions')), findsNothing);
    expect(find.text('Vous avez tout exploré'), findsNothing);
    await tester.tap(find.text('Voir plus'));
    await tester.pump();
    expect(find.text('Voir moins'), findsOneWidget);
    expect(find.text('Frais réglés'), findsOneWidget);
  });

  testWidgets('available native action reuses the Discover orbit icon', (
    tester,
  ) async {
    final projection = _projection(
      items: const [
        {
          'kind': 'journey',
          'source': {
            'kind': 'journey',
            'id': '12345678-1234-1234-1234-123456789012',
          },
          'title': 'Voyage Kolwezi',
          'summary': 'Une suite est prévue.',
          'capabilities': ['open_detail'],
          'links': {},
        },
      ],
    );
    await PresentationHarness.pump(
      tester,
      child: OngoingScreen(
        repository: _UnusedRepository(),
        projectionStream: Stream.value(projection),
      ),
    );
    await tester.pump();
    expect(
      find.byKey(const Key('ongoing-n1-discover-actions')),
      findsOneWidget,
    );
    expect(find.byType(DiscoveryOrbitIcon), findsOneWidget);
    expect(
      tester.widget<DiscoveryOrbitIcon>(find.byType(DiscoveryOrbitIcon)).saved,
      isFalse,
    );
    expect(find.text('Enregistré'), findsNothing);
  });

  testWidgets(
    'compact media follows the title at full width, never a side thumbnail',
    (tester) async {
      final projection = _projection(
        items: const [
          {
            'id': 'media-continuity',
            'kind': 'journey',
            'source': {'kind': 'journey', 'id': 'media'},
            'state': 'waiting',
            'title': 'Mon voyage',
            'summary': 'Départ confirmé.',
            'media_bindings': [
              {
                'purpose': 'RECOGNIZE',
                'resource': {
                  'url': '/presentation/media/uses/abc/file/',
                  'alt_text': 'Véhicule',
                  'mime_type': 'image/png',
                },
              },
            ],
            'capabilities': [],
            'links': {},
          },
        ],
      );
      await PresentationHarness.pump(
        tester,
        child: OngoingScreen(
          repository: _UnusedRepository(),
          projectionStream: Stream.value(projection),
          baseUri: Uri.parse('https://api.example.test/'),
        ),
      );
      await tester.pump();
      final media = find.byKey(const Key('ongoing-n1-full-width-media'));
      final title = find.text('Mon voyage');
      expect(media, findsOneWidget);
      expect(title, findsOneWidget);
      final mediaRect = tester.getRect(media);
      final titleRect = tester.getRect(title);
      expect(mediaRect.top, greaterThanOrEqualTo(titleRect.bottom));
      expect(mediaRect.width, greaterThan(titleRect.width));
      // This fixture has neither actions nor owner routes. The compact
      // visual must not invent an empty action toolbar.
      expect(
        find.byKey(const Key('ongoing-n1-discover-actions')),
        findsNothing,
      );
    },
  );

  testWidgets('each ongoing unit owns its media, resources and action footer', (
    tester,
  ) async {
    final projection = _projection(
      items: const [
        {
          'id': 'first',
          'kind': 'journey',
          'source': {'kind': 'journey', 'id': 'first'},
          'title': 'Première continuité',
          'summary': 'Une action est attendue.',
          'media_bindings': [
            {
              'purpose': 'RECOGNIZE',
              'resource': {
                'url': '/presentation/media/uses/first/file/',
                'alt_text': 'Aperçu du premier dossier',
                'mime_type': 'image/png',
              },
            },
          ],
          'resources': [
            {'title': 'Notice de préparation'},
          ],
          'capabilities': [],
          'links': {},
        },
        {
          'id': 'second',
          'kind': 'journey',
          'source': {
            'kind': 'journey',
            'id': '12345678-1234-1234-1234-123456789012',
          },
          'title': 'Deuxième continuité',
          'summary': 'Une autre action est attendue.',
          'capabilities': ['open_detail'],
          'links': {},
        },
      ],
    );
    await PresentationHarness.pump(
      tester,
      child: OngoingScreen(
        repository: _UnusedRepository(),
        projectionStream: Stream.value(projection),
        baseUri: Uri.parse('https://api.example.test/'),
      ),
    );
    await tester.pump();
    final first = find.byKey(const ValueKey<String>('ongoing-unit-first'));
    final second = find.byKey(const ValueKey<String>('ongoing-unit-second'));
    expect(first, findsOneWidget);
    expect(second, findsOneWidget);
    expect(
      find.descendant(
        of: first,
        matching: find.byKey(const Key('ongoing-n1-full-width-media')),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(of: first, matching: find.text('Notice de préparation')),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: second,
        matching: find.byKey(const Key('ongoing-n1-resources')),
      ),
      findsNothing,
    );
    expect(
      find.descendant(
        of: second,
        matching: find.byKey(const Key('ongoing-n1-discover-actions')),
      ),
      findsOneWidget,
    );
    expect(
      tester.getRect(find.text('Première continuité')).top,
      lessThan(tester.getRect(find.text('Notice de préparation')).top),
    );
    final gutter = find.byKey(const Key('ongoing-unit-gutter'));
    expect(gutter, findsOneWidget);
    expect(tester.getSize(gutter).height, MakoloSpacing.md);
    expect(
      tester.widget<ColoredBox>(gutter).color,
      tester.element(gutter).makoloSurfaces.surface,
    );
    // The gutter is outside both units, with no side inset or intervening
    // action bar. The footer still belongs to the preceding continuity.
    expect(
      tester.getRect(gutter).top,
      closeTo(tester.getRect(first).bottom, 0.1),
    );
    expect(
      tester.getRect(second).top,
      closeTo(tester.getRect(gutter).bottom, 0.1),
    );
  });

  testWidgets('owner dates are preserved in the N2 continuity', (tester) async {
    final projection = _projection(
      items: const [
        {
          'id': 'time-continuity',
          'kind': 'journey',
          'source': {'kind': 'journey', 'id': 'time'},
          'title': 'Voyage Nairobi',
          'summary': 'Départ confirmé.',
          'temporal_facts': [
            {
              'kind': 'occurrence_start',
              'label': 'Début',
              'date': '2026-11-12',
            },
          ],
          'capabilities': [],
          'links': {},
        },
      ],
    );
    await PresentationHarness.pump(
      tester,
      child: OngoingScreen(
        repository: _UnusedRepository(),
        projectionStream: Stream.value(projection),
      ),
    );
    await tester.pump();
    await tester.tap(find.text('Voyage Nairobi'));
    await tester.pumpAndSettle();
    expect(find.text('Dates à retenir'), findsOneWidget);
    expect(find.textContaining('Début'), findsWidgets);
  });

  testWidgets(
    'a removed projection does not resurrect private cached content',
    (tester) async {
      final controller = StreamController<StoredProjection?>();
      await PresentationHarness.pump(
        tester,
        child: OngoingScreen(
          repository: _UnusedRepository(),
          projectionStream: controller.stream,
        ),
      );
      controller.add(_projection());
      await tester.pump();
      await tester.pump();
      expect(find.text('Visa Canada'), findsOneWidget);
      controller.add(null);
      await tester.pump();
      await tester.pump();
      expect(find.text('Visa Canada'), findsNothing);
      expect(find.textContaining('pas encore disponibles'), findsOneWidget);
      await controller.close();
    },
  );

  testWidgets('calm content and true empty stay distinct', (tester) async {
    final controller = StreamController<StoredProjection?>();

    await PresentationHarness.pump(
      tester,
      child: OngoingScreen(
        repository: _UnusedRepository(),
        projectionStream: controller.stream,
      ),
    );

    controller.add(_projection());
    await tester.pump();
    await tester.pump();

    expect(find.text('Visa Canada'), findsOneWidget);
    expect(find.text('Le consulat examine votre dossier.'), findsOneWidget);
    expect(find.text('Rien en cours pour le moment.'), findsNothing);

    controller.add(_projection(items: const []));
    await tester.pump();
    await tester.pump();

    expect(find.text('Rien en cours pour le moment.'), findsOneWidget);
    expect(find.text('Visa Canada'), findsNothing);

    await controller.close();
  });

  testWidgets('refresh error preserves known content', (tester) async {
    final controller = StreamController<StoredProjection?>();

    await PresentationHarness.pump(
      tester,
      child: OngoingScreen(
        repository: _UnusedRepository(),
        projectionStream: controller.stream,
      ),
    );

    controller.add(_projection());
    await tester.pump();
    await tester.pump();

    controller.addError(StateError('refresh failed'));
    await tester.pump();
    await tester.pump();

    expect(find.text('Visa Canada'), findsOneWidget);
    expect(find.textContaining('mise à jour a échoué'), findsNothing);
    expect(find.byType(MakoloNotice), findsNothing);

    await controller.close();
  });

  testWidgets('confirmation echo becomes a distinct calm status', (
    tester,
  ) async {
    final projection = _projection(
      items: const [
        {
          'kind': 'journey',
          'source': {'kind': 'journey', 'id': 'router'},
          'state': 'action_required',
          'title': 'Obtenir un routeur bureau',
          'ready': [],
          'actor_interventions': [
            {'summary': 'Confirmer : Obtenir un routeur bureau'},
          ],
          'continuation': {
            'state': 'action_required',
            'summary': 'Confirmer : Obtenir un routeur bureau',
          },
          'blocker': null,
          'next': null,
          'timing': {},
          'place': null,
          'capabilities': ['open_detail'],
          'links': {'detail': '/api/v1/me/journeys/router/'},
        },
      ],
    );

    await PresentationHarness.pump(
      tester,
      child: OngoingScreen(
        repository: _UnusedRepository(),
        projectionStream: Stream.value(projection),
      ),
    );
    await tester.pump();

    expect(find.text('Obtenir un routeur bureau'), findsOneWidget);
    expect(find.text('À confirmer'), findsOneWidget);
    expect(find.text('Confirmer : Obtenir un routeur bureau'), findsNothing);
  });

  testWidgets('wide split uses the shared 960dp content boundary', (
    tester,
  ) async {
    final viewportWidth =
        MakoloLayout.ongoingSplitMinWidth + (MakoloLayout.edgeWide * 2);

    await PresentationHarness.pump(
      tester,
      viewport: Size(viewportWidth, 900),
      child: OngoingScreen(
        repository: _UnusedRepository(),
        projectionStream: Stream.value(_projection()),
      ),
    );
    await tester.pump();

    // G07: no empty N2 pane before choosing a continuity.
    expect(find.byKey(const Key('makolo-adaptive-split-row')), findsNothing);
    await tester.tap(find.text('Visa Canada').first);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('makolo-adaptive-split-row')), findsOneWidget);
  });
}
