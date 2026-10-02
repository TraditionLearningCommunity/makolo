import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/space/space_attention_presentation.dart';
import 'package:makolo_mobile/features/space/space_discover_screen.dart';
import 'package:makolo_mobile/features/space/space_now_screen.dart';
import 'package:makolo_mobile/sync/owner_source_state.dart';

StoredProjection _unavailableProjection() {
  return StoredProjection(
    kind: 'space.now',
    schemaVersion: 1,
    payload: {
      'selection': {
        'state': 'unavailable',
        'reason': 'no_safe_selection_contract',
      },
      'items': <Object>[],
      'has_more': false,
    },
    receivedAt: DateTime.utc(2026, 10, 2, 12),
  );
}

SpaceAttentionPresentation _unavailable({
  OwnerSourceState source = OwnerSourceState.unknown,
}) {
  return SpaceAttentionPresentation.resolve(
    projection: _unavailableProjection(),
    source: source,
    now: DateTime.utc(2026, 10, 2, 12),
  );
}

Future<void> _pump(
  WidgetTester tester,
  Widget child, {
  bool dark = false,
  double textScale = 1,
}) {
  return tester.pumpWidget(
    MaterialApp(
      theme: dark ? buildMakoloDarkTheme() : buildMakoloLightTheme(),
      home: Scaffold(
        body: Builder(
          builder: (context) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(textScaler: TextScaler.linear(textScale)),
            child: child,
          ),
        ),
      ),
    ),
  );
}

void main() {
  testWidgets('Space Now unavailable stays distinct from calm empty', (
    tester,
  ) async {
    var refreshes = 0;
    await _pump(
      tester,
      SpaceNowView(
        scopeKey: 'space-x:all',
        presentation: _unavailable(),
        showLoading: false,
        onRefresh: () async {
          refreshes += 1;
        },
      ),
    );

    expect(
      find.text('Qu’est-ce qui mérite notre attention maintenant ?'),
      findsOneWidget,
    );
    expect(
      find.text('Aucune priorité n’est présentée pour le moment.'),
      findsOneWidget,
    );
    expect(find.text('Tout est en ordre. ✓'), findsNothing);
    expect(find.text('no_safe_selection_contract'), findsNothing);
    expect(tester.takeException(), isNull);
    expect(refreshes, 0);
  });

  testWidgets('Space Discover unavailable never fabricates possibilities', (
    tester,
  ) async {
    await _pump(
      tester,
      SpaceDiscoverView(
        spaceId: 'space-x',
        presentation: _unavailable(),
        showLoading: false,
        onRefresh: () async {},
      ),
    );

    expect(
      find.text('Qu’est-ce qui pourrait nous aider à avancer ?'),
      findsOneWidget,
    );
    expect(
      find.text('Aucune possibilité n’est présentée pour le moment.'),
      findsOneWidget,
    );
    expect(find.text('Trending'), findsNothing);
    expect(find.text('Popular'), findsNothing);
    expect(find.text('no_safe_selection_contract'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('offline with snapshot keeps the last unavailable knowledge', (
    tester,
  ) async {
    await _pump(
      tester,
      SpaceNowView(
        scopeKey: 'space-x:all',
        presentation: _unavailable(
          source: const OwnerSourceState(lastErrorCode: 'transport_error'),
        ),
        showLoading: false,
        onRefresh: () async {},
      ),
    );

    expect(
      find.text('Aucune priorité n’est présentée pour le moment.'),
      findsOneWidget,
    );
    expect(
      find.textContaining('dernière connaissance disponible'),
      findsOneWidget,
    );
    expect(find.text('Tout est en ordre. ✓'), findsNothing);
  });

  testWidgets('failure without snapshot offers a recoverable retry', (
    tester,
  ) async {
    var refreshes = 0;
    const failure = SpaceAttentionPresentation(
      state: SpaceAttentionState.failure,
      source: OwnerSourceState(lastErrorCode: 'transport_error'),
    );
    await _pump(
      tester,
      SpaceDiscoverView(
        spaceId: 'space-x',
        presentation: failure,
        showLoading: false,
        onRefresh: () async {
          refreshes += 1;
        },
      ),
    );

    expect(
      find.text('Impossible de mettre cette vue à jour pour le moment.'),
      findsOneWidget,
    );
    expect(
      find.text('Aucune possibilité n’est présentée pour le moment.'),
      findsNothing,
    );

    await tester.tap(find.text('Réessayer'));
    await tester.pump();
    expect(refreshes, 1);
  });

  testWidgets('Now and Discover remain readable at 2x text on a small phone', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(320, 568));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await _pump(
      tester,
      SpaceNowView(
        scopeKey: 'space-x:all',
        presentation: _unavailable(),
        showLoading: false,
        onRefresh: () async {},
      ),
      textScale: 2,
    );
    expect(tester.takeException(), isNull);

    await _pump(
      tester,
      SpaceDiscoverView(
        spaceId: 'space-x',
        presentation: _unavailable(),
        showLoading: false,
        onRefresh: () async {},
      ),
      dark: true,
      textScale: 2,
    );
    expect(tester.takeException(), isNull);
  });
}
