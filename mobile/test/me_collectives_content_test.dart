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
  testWidgets('positive counts only and separate relationships', (
    tester,
  ) async {
    await _show(
      tester,
      collectives: _data(groups: 0),
      items: const [_space, _team],
    );
    expect(find.text('2 collectifs'), findsOneWidget);
    expect(find.text('Espaces'), findsWidgets);
    expect(find.text('Équipes'), findsWidgets);
    expect(find.text('0 Groupes'), findsNothing);
    expect(find.text('Espaces où je peux agir'), findsOneWidget);
    expect(find.text('Mes équipes'), findsOneWidget);
    expect(find.text('Mes groupes'), findsNothing);
    expect(find.text('Espace autorisé'), findsOneWidget);
    expect(find.text('Membre'), findsOneWidget);
    expect(find.text('Agir'), findsNothing);
  });

  testWidgets('Space action uses the verified actor picker callback', (
    tester,
  ) async {
    MeItemPresentation? acted;
    await _show(tester, collectives: _data(), onAct: (item) => acted = item);
    await tester.tap(find.text('Agir'));
    expect(acted?.destination.id, 'space-1');
  });

  testWidgets('offline never asserts current permission on a cached Space', (
    tester,
  ) async {
    var acted = false;
    await _show(
      tester,
      collectives: _data(),
      offline: true,
      onAct: (_) => acted = true,
    );
    expect(find.text('Agir'), findsNothing);
    expect(find.text('Espace autorisé'), findsNothing);
    expect(find.textContaining('Autorisations à confirmer'), findsOneWidget);
    expect(acted, isFalse);
  });

  testWidgets('team affiliation opens parent Space, not Team management', (
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
    await tester.ensureVisible(find.text('Voir l’Espace'));
    await tester.tap(find.text('Voir l’Espace'));
    expect(opened?.kind, 'space');
    expect(opened?.link, 'atelier');
    expect(find.text('Gérer l’équipe'), findsNothing);
  });

  testWidgets('filters and search use already acquired local data', (
    tester,
  ) async {
    await _show(tester, collectives: _data(partial: true), hasMore: true);
    // The fourth filter starts outside the narrow viewport. Interact with
    // the actual horizontal strip before tapping its target.
    await tester.drag(
      find.byKey(const Key('me-collectives-filter-scroller')),
      const Offset(-500, 0),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('me-collectives-filter-groups')));
    await tester.pumpAndSettle();
    expect(find.text('Espaces où je peux agir'), findsNothing);
    expect(find.text('Mes groupes'), findsOneWidget);

    await tester.tap(find.byTooltip('Rechercher un collectif'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('me-collectives-search')),
      'introuvable',
    );
    await tester.pumpAndSettle();
    expect(
      find.text('Aucun résultat parmi les collectifs déjà chargés.'),
      findsOneWidget,
    );
    expect(find.textContaining('D’autres collectifs'), findsOneWidget);
  });

  testWidgets('zero is not displayed as an ornamental counter', (tester) async {
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

  testWidgets('Group opens its owner checked depth', (tester) async {
    StructuredDestination? opened;
    await _show(
      tester,
      collectives: _data(),
      onOpen: (destination) {
        opened = destination;
        return true;
      },
    );
    await tester.ensureVisible(
      find.byKey(const Key('me-collective-group-group-1')),
    );
    await tester.tap(find.text('Ouvrir').last);
    expect(opened?.kind, 'group');
    expect(opened?.id, 'group-1');
  });
}
