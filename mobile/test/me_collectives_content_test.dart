import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/me/me_collectives_content.dart';
import 'package:makolo_mobile/features/me/me_selector.dart';
import 'package:makolo_mobile/navigation/destination.dart';

const _space = MeItemPresentation(
  destination: StructuredDestination(
    kind: 'space',
    id: 'space-1',
    link: 'atelier',
  ),
  title: 'Ateliers de proximité',
  subtitle: 'Peut agir pour cet Espace',
  canOpen: true,
);
const _team = MeItemPresentation(
  destination: StructuredDestination(kind: 'team', id: 'team-1'),
  title: 'Équipe principale',
  subtitle: 'Équipe · Ateliers de proximité',
);
const _group = MeItemPresentation(
  destination: StructuredDestination(kind: 'group', id: 'group-1'),
  title: 'Groupe mobilité',
  subtitle: 'Groupe · Ateliers de proximité',
  canOpen: true,
);

Map<String, dynamic> _data({
  int spaces = 1,
  int teams = 1,
  int groups = 1,
  bool partial = false,
}) => {
  'authorized_spaces': {
    'count': spaces,
    'has_more': partial,
    'items': [
      if (spaces > 0)
        {
          'id': 'space-1',
          'name': 'Ateliers de proximité',
          'can_act': true,
          'slug': 'atelier',
        },
    ],
  },
  'teams': {
    'count': teams,
    'has_more': false,
    'items': [
      if (teams > 0)
        {
          'id': 'team-1',
          'name': 'Équipe principale',
          'relationship': 'membership',
          'space': {
            'id': 'space-1',
            'name': 'Ateliers de proximité',
            'slug': 'atelier',
          },
        },
    ],
  },
  'groups': {
    'count': groups,
    'has_more': false,
    'items': [
      if (groups > 0)
        {
          'id': 'group-1',
          'name': 'Groupe mobilité',
          'owner': {'name': 'Ateliers de proximité'},
        },
    ],
  },
};

Future<void> _show(
  WidgetTester tester, {
  required Object? collectives,
  List<MeItemPresentation> items = const [_space, _team, _group],
  bool offline = false,
  bool hasMore = false,
  String query = '',
  bool alphabetical = false,
  bool descending = false,
  bool Function(StructuredDestination)? onOpen,
  ValueChanged<MeItemPresentation>? onAct,
}) async {
  await tester.binding.setSurfaceSize(const Size(430, 932));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: MeCollectivesContent(
              items: items,
              collectives: collectives,
              offline: offline,
              hasMore: hasMore,
              query: query,
              alphabetical: alphabetical,
              descending: descending,
              onOpen: onOpen ?? (_) => true,
              onActSpace: onAct,
            ),
          ),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  test('known counts are relational; partial counts are not inferred', () {
    expect(meCollectiveTotal(_data()), 3);
    expect(meCollectiveTotal(_data(spaces: 0, teams: 0, groups: 0)), 0);
    expect(
      meCollectiveTotal({
        'authorized_spaces': {
          'items': [
            {'id': 'one'},
          ],
          'has_more': true,
        },
        'teams': {'items': [], 'has_more': false},
        'groups': {'items': [], 'has_more': false},
      }),
      isNull,
    );
  });

  test('only the correct published owner media is eligible', () {
    Map<String, dynamic> record(String kind, String path) => {
      'media_bindings': [
        {
          'purpose': 'RECOGNIZE',
          'target': {'kind': kind, 'id': 'space-1'},
          'resource': {
            'kind': 'presentation_media_use',
            'mime_type': 'image/jpeg',
            'url': path,
          },
        },
      ],
    };
    expect(
      collectiveRecognitionPath(
        record('space', '/api/v1/presentation/media/one/image/'),
        'space',
        'space-1',
      ),
      '/api/v1/presentation/media/one/image/',
    );
    expect(
      collectiveRecognitionPath(
        record('activity', '/api/v1/presentation/media/one/image/'),
        'space',
        'space-1',
      ),
      isNull,
    );
    expect(
      collectiveRecognitionPath(
        record('space', 'https://foreign.example/image.jpg'),
        'space',
        'space-1',
      ),
      isNull,
    );
    expect(
      collectiveRecognitionPath(
        record('space', '//foreign.example/image.jpg'),
        'space',
        'space-1',
      ),
      isNull,
    );
    expect(
      collectiveRecognitionPath(
        record('space', '/api/v1/presentation/media/one/image/'),
        'space',
        'other-space',
      ),
      isNull,
    );
  });

  testWidgets('no duplicate dashboard or ornamental action menu', (
    tester,
  ) async {
    await _show(
      tester,
      collectives: _data(groups: 0),
      items: const [_space, _team],
    );
    expect(find.byKey(const Key('me-collectives-summary')), findsNothing);
    expect(find.text('2 collectifs'), findsNothing);
    expect(find.text('0 Groupes'), findsNothing);
    expect(find.text('Où on peut agir'), findsOneWidget);
    expect(find.text('Mes équipes'), findsOneWidget);
    expect(find.text('Mes groupes'), findsNothing);
    expect(find.byIcon(Icons.more_horiz), findsNothing);
    expect(find.text('Aperçu'), findsNothing);
  });

  testWidgets('Space action remains explicit and server-checked', (
    tester,
  ) async {
    MeItemPresentation? acted;
    await _show(tester, collectives: _data(), onAct: (item) => acted = item);
    await tester.tap(find.byKey(const Key('me-collectives-act-space-1')));
    expect(acted?.destination.id, 'space-1');
    expect(find.text('Voir l’Espace'), findsNothing);
  });

  testWidgets('offline keeps known relations without current action claims', (
    tester,
  ) async {
    await _show(
      tester,
      collectives: _data(),
      offline: true,
      onAct: (_) => fail('Offline must not grant Space action'),
    );
    expect(find.text('Agir'), findsNothing);
    expect(find.text('Espace lié à moi'), findsOneWidget);
    expect(find.textContaining('Autorisations à confirmer'), findsNothing);
  });

  testWidgets('Team opens parent Space without suggesting Team authority', (
    tester,
  ) async {
    StructuredDestination? opened;
    await _show(
      tester,
      collectives: _data(),
      onOpen: (destination) {
        opened = destination;
        return true;
      },
    );
    await tester.ensureVisible(find.text('Équipe principale'));
    await tester.tap(find.text('Équipe principale'));
    expect(opened?.kind, 'space');
    expect(opened?.link, 'atelier');
    expect(find.text('Gérer l’équipe'), findsNothing);
  });

  testWidgets('Group opens its owner depth with no extra menu', (tester) async {
    StructuredDestination? opened;
    await _show(
      tester,
      collectives: _data(),
      onOpen: (destination) {
        opened = destination;
        return true;
      },
    );
    await tester.ensureVisible(find.text('Groupe mobilité'));
    await tester.tap(find.text('Groupe mobilité'));
    expect(opened?.kind, 'group');
    expect(opened?.id, 'group-1');
    expect(find.byIcon(Icons.more_horiz), findsNothing);
  });

  testWidgets('horizontal filters and partial local search are honest', (
    tester,
  ) async {
    await _show(tester, collectives: _data(partial: true), hasMore: true);
    await tester.drag(
      find.byKey(const Key('me-collectives-filter-scroller')),
      const Offset(-500, 0),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('me-collectives-filter-groups')));
    await tester.pumpAndSettle();
    expect(find.text('Où on peut agir'), findsNothing);
    expect(find.text('Groupe mobilité'), findsOneWidget);
    await _show(
      tester,
      collectives: _data(partial: true),
      hasMore: true,
      query: 'introuvable',
    );
    expect(
      find.text('Aucun résultat parmi les collectifs chargés.'),
      findsOneWidget,
    );
  });

  testWidgets('each collective family has a swipeable horizontal carousel', (
    tester,
  ) async {
    const secondSpace = MeItemPresentation(
      destination: StructuredDestination(
        kind: 'space',
        id: 'space-2',
        link: 'autre',
      ),
      title: 'Autre espace',
      canOpen: true,
    );
    const secondTeam = MeItemPresentation(
      destination: StructuredDestination(kind: 'team', id: 'team-2'),
      title: 'Deuxième équipe',
    );
    const secondGroup = MeItemPresentation(
      destination: StructuredDestination(kind: 'group', id: 'group-2'),
      title: 'Deuxième groupe',
      canOpen: true,
    );
    await _show(
      tester,
      collectives: _data(spaces: 2, teams: 2, groups: 2),
      items: const [
        _space,
        secondSpace,
        _team,
        secondTeam,
        _group,
        secondGroup,
      ],
    );
    for (final kind in ['space', 'team', 'group']) {
      final scroller = find.byKey(Key('me-collectives-carousel-$kind'));
      expect(scroller, findsOneWidget);
      final widget = tester.widget<SingleChildScrollView>(scroller);
      expect(widget.scrollDirection, Axis.horizontal);
      final scrollable = find.descendant(
        of: scroller,
        matching: find.byType(Scrollable),
      );
      expect(scrollable, findsOneWidget);
      final before = tester.state<ScrollableState>(scrollable).position.pixels;
      await tester.ensureVisible(scroller);
      await tester.drag(scroller, const Offset(-180, 0));
      await tester.pumpAndSettle();
      final after = tester.state<ScrollableState>(scrollable).position.pixels;
      expect(after, greaterThan(before));
    }
  });

  testWidgets('alphabetical ordering includes descending, not a fake recency', (
    tester,
  ) async {
    const z = MeItemPresentation(
      destination: StructuredDestination(
        kind: 'space',
        id: 'space-z',
        link: 'z',
      ),
      title: 'Zulu',
      canOpen: true,
    );
    const a = MeItemPresentation(
      destination: StructuredDestination(
        kind: 'space',
        id: 'space-a',
        link: 'a',
      ),
      title: 'Alpha',
      canOpen: true,
    );
    await _show(
      tester,
      collectives: _data(spaces: 2, teams: 0, groups: 0),
      items: const [z, a],
      alphabetical: true,
    );
    final alphaFirst = tester.getTopLeft(find.text('Alpha')).dx;
    final zuluSecond = tester.getTopLeft(find.text('Zulu')).dx;
    expect(alphaFirst, lessThan(zuluSecond));
    await _show(
      tester,
      collectives: _data(spaces: 2, teams: 0, groups: 0),
      items: const [z, a],
      alphabetical: true,
      descending: true,
    );
    final alphaLast = tester.getTopLeft(find.text('Alpha')).dx;
    final zuluFirst = tester.getTopLeft(find.text('Zulu')).dx;
    expect(zuluFirst, lessThan(alphaLast));
  });

  testWidgets('empty collection has no zero counter or false result', (
    tester,
  ) async {
    await _show(
      tester,
      collectives: _data(spaces: 0, teams: 0, groups: 0),
      items: const [],
    );
    expect(find.text('0 collectifs'), findsNothing);
    expect(find.text('0 Espaces'), findsNothing);
    expect(find.text('0 Équipes'), findsNothing);
    expect(find.text('0 Groupes'), findsNothing);
    expect(find.text('Aucun collectif dans cette catégorie.'), findsOneWidget);
  });
}
