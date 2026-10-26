import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/behavior_primitives.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/ongoing/ongoing_screen.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';

import 'support/presentation_harness.dart';

StoredProjection _projection({
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
  payload: {'items': items},
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
    final projection = _projection(items: const [
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
    ]);
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

    expect(find.byKey(const Key('makolo-adaptive-split-row')), findsOneWidget);
  });
}
