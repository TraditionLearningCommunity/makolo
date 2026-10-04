import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/presentation_layout.dart';
import 'package:makolo_mobile/design/surface_states.dart';
import 'package:makolo_mobile/features/me/me_screen.dart';
import 'package:makolo_mobile/features/me/me_selector.dart';
import 'package:makolo_mobile/repositories/personal_repository.dart';
import 'package:makolo_mobile/sync/owner_source_state.dart';
import 'package:makolo_mobile/sync/sync_status.dart';

import 'support/presentation_harness.dart';

StoredProjection _projection(
  Map<String, dynamic> payload, {
  DateTime? freshUntil,
}) {
  return StoredProjection(
    kind: 'personal.me',
    schemaVersion: 1,
    payload: payload,
    receivedAt: DateTime.utc(2026, 10, 3, 12),
    sourceGeneratedAt: DateTime.utc(2026, 10, 3, 12),
    lastVerifiedOnlineAt: DateTime.utc(2026, 10, 3, 12),
    freshUntil: freshUntil,
    freshnessPolicyId: 'personal.me',
  );
}

Map<String, dynamic> _emptyBounded() => {
  'count': 0,
  'items': <Object>[],
  'has_more': false,
};

Map<String, dynamic> _fullPayload({bool supportAvailable = false}) {
  return {
    'identity': {
      'kind': 'profile',
      'id': 'profile-1',
      'display_name': 'Gilbert Bemwiz',
      'profession': 'Ingénieur',
      'bio': 'Construire ce qui facilite la suite.',
      'location': {'city': 'Lubumbashi', 'country': 'RDC'},
    },
    'passport': {
      'available': true,
      'links': {'api': '/api/v1/me/passport/'},
    },
    'considerations': {
      'interests': {
        'count': 1,
        'items': [
          {
            'id': 'interest-1',
            'topic': {'id': 'topic-1', 'code': 'tech', 'label': 'Technologie'},
          },
        ],
        'has_more': false,
      },
      'open_to': _emptyBounded(),
      'watches': _emptyBounded(),
      'bookmarks': _emptyBounded(),
      'followed_spaces': _emptyBounded(),
      'followed_profiles': _emptyBounded(),
    },
    'collectives': {
      'authorized_spaces': {
        'count': 1,
        'items': [
          {
            'kind': 'space',
            'id': 'space-1',
            'name': 'Espace Makolo',
            'relationship': 'authorized_context',
            'can_act': true,
          },
        ],
        'has_more': false,
      },
      'teams': {
        'count': 1,
        'items': [
          {'kind': 'team', 'id': 'team-1', 'name': 'Équipe terrain'},
        ],
        'has_more': false,
      },
      'groups': {
        'count': 1,
        'items': [
          {'kind': 'group', 'id': 'group-1', 'name': 'Groupe local'},
        ],
        'has_more': false,
      },
    },
    'resources': {
      'documents': {
        'count': 1,
        'items': [
          {
            'kind': 'personal_asset',
            'id': 'asset-1',
            'title': 'Passeport.pdf',
            'asset_kind_label': 'Document',
            'sensitivity_label': 'Privé',
          },
        ],
        'has_more': false,
      },
      'proofs': {
        'count': 1,
        'items': [
          {
            'kind': 'proof',
            'id': 'proof-1',
            'proof_type': 'attendance',
            'proof_type_label': 'Participation',
            'status_label': 'Établie',
          },
        ],
        'has_more': false,
      },
      'credentials': {
        'count': 1,
        'items': [
          {
            'kind': 'credential',
            'id': 'credential-1',
            'title': 'CCNA',
            'credential_type_label': 'Certification',
            'status_label': 'Valide',
          },
        ],
        'has_more': false,
      },
    },
    'support': {
      'recognition': {
        'available': supportAvailable,
        'needs_response': supportAvailable,
      },
      'loyalty': {'available': false},
      'partners': {'available': false},
    },
    'links': {
      'self': '/api/v1/me/',
      'passport': '/api/v1/me/passport/',
      'resources': '/api/v1/me/resources/',
    },
  };
}

Map<String, dynamic> _sparsePayload() {
  return {
    'identity': {
      'kind': 'profile',
      'id': 'profile-1',
      'display_name': 'Gilbert Bemwiz',
    },
    'passport': {
      'available': false,
      'links': {'api': '/api/v1/me/passport/'},
    },
    'considerations': {
      'interests': _emptyBounded(),
      'open_to': _emptyBounded(),
      'watches': _emptyBounded(),
      'bookmarks': _emptyBounded(),
      'followed_spaces': _emptyBounded(),
      'followed_profiles': _emptyBounded(),
    },
    'collectives': {
      'authorized_spaces': _emptyBounded(),
      'teams': _emptyBounded(),
      'groups': _emptyBounded(),
    },
    'resources': {
      'documents': _emptyBounded(),
      'proofs': _emptyBounded(),
      'credentials': _emptyBounded(),
    },
    'support': {
      'recognition': {'available': false},
      'loyalty': {'available': false},
      'partners': {'available': false},
    },
    'links': {'self': '/api/v1/me/'},
  };
}

void main() {
  const selector = MeSelector();
  final now = DateTime.utc(2026, 10, 3, 13);

  test('selector adapts the real personal.me shape without mixing owners', () {
    final selection = selector.select(
      projection: _projection(_fullPayload()),
      now: now,
    );

    expect(selection.presentation.identityLabel, 'Gilbert Bemwiz');
    expect(selection.identitySubtitle, 'Ingénieur · Lubumbashi, RDC');
    expect(
      selection.territories.map((territory) => territory.presentation.key),
      ['passport', 'considerations', 'collectives', 'resources'],
    );

    final resources = selection.territories.singleWhere(
      (territory) => territory.presentation.key == 'resources',
    );
    expect(resources.items.map((item) => item.destination.kind), [
      'personal_asset',
      'proof',
      'credential',
    ]);

    final collectives = selection.territories.singleWhere(
      (territory) => territory.presentation.key == 'collectives',
    );
    expect(collectives.items.map((item) => item.subtitle), [
      'Contexte autorisé',
      'Équipe',
      'Groupe',
    ]);
    expect(
      collectives.items
          .where(
            (item) =>
                item.destination.kind == 'team' ||
                item.destination.kind == 'group',
          )
          .map((item) => item.subtitle),
      isNot(contains('Contexte autorisé')),
    );
  });

  test('support is conditional on runtime availability', () {
    final withoutSupport = selector.select(
      projection: _projection(_fullPayload()),
      now: now,
    );
    final withSupport = selector.select(
      projection: _projection(_fullPayload(supportAvailable: true)),
      now: now,
    );

    expect(
      withoutSupport.territories.any(
        (territory) => territory.presentation.key == 'support',
      ),
      isFalse,
    );
    expect(
      withSupport.territories.any(
        (territory) => territory.presentation.key == 'support',
      ),
      isTrue,
    );
  });

  test('sparse remains section-first with local empty territories', () {
    final selection = selector.select(
      projection: _projection(_sparsePayload()),
      now: now,
    );

    expect(selection.presentation.identityLabel, 'Gilbert Bemwiz');
    expect(selection.territories, hasLength(4));
    expect(
      selection.territories.every(
        (territory) =>
            territory.presentation.state.availability ==
            MakoloAvailabilityCue.empty,
      ),
      isTrue,
    );
    expect(selection.state.availability, MakoloAvailabilityCue.content);
  });

  test('nested malformed data degrades only its territory', () {
    final payload = _fullPayload();
    final resources = payload['resources'] as Map<String, dynamic>;
    resources['documents'] = {
      'count': 1,
      'items': 'malformed',
      'has_more': false,
    };

    final selection = selector.select(
      projection: _projection(payload),
      now: now,
    );
    final resourceTerritory = selection.territories.singleWhere(
      (territory) => territory.presentation.key == 'resources',
    );
    final considerations = selection.territories.singleWhere(
      (territory) => territory.presentation.key == 'considerations',
    );

    expect(
      resourceTerritory.presentation.state.failure,
      MakoloFailureCue.blocking,
    );
    expect(considerations.presentation.state.failure, MakoloFailureCue.none);
    expect(selection.state.failure, MakoloFailureCue.none);
  });

  test('freshness remains source metadata driven', () {
    final selection = selector.select(
      projection: _projection(
        _fullPayload(),
        freshUntil: DateTime.utc(2026, 10, 3, 12, 30),
      ),
      now: now,
    );

    expect(selection.state.freshness, MakoloFreshnessCue.unknown);
    expect(
      selection.territories.first.presentation.state.freshness,
      MakoloFreshnessCue.refreshRecommended,
    );
  });

  testWidgets('first availability preserves section grammar', (tester) async {
    final repository = _MeStreamRepository(
      projection: Stream<StoredProjection?>.value(null),
      source: Stream<OwnerSourceState>.value(OwnerSourceState.unknown),
    );

    await PresentationHarness.pump(
      tester,
      child: SyncStatusScope(
        status: const SyncStatus(state: SyncVisualState.syncing),
        child: MeScreen(repository: repository, now: () => now),
      ),
    );

    expect(find.byKey(const Key('me-first-availability')), findsOneWidget);
    expect(find.text('Identité'), findsOneWidget);
    expect(find.text('Passeport Makolo'), findsOneWidget);
    expect(find.text('Ce qui compte pour moi'), findsOneWidget);
    expect(find.text('Mes collectifs'), findsOneWidget);
    expect(find.text('Mes ressources'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);
  });

  testWidgets('sparse renders human local empty copy', (tester) async {
    final selection = selector.select(
      projection: _projection(_sparsePayload()),
      now: now,
    );

    await PresentationHarness.pump(tester, child: MeView(selection: selection));

    expect(
      find.text('Aucun Passeport disponible ici pour le moment.'),
      findsOneWidget,
    );
    expect(find.text('Rien de déclaré pour le moment.'), findsOneWidget);
    expect(find.text('Aucun collectif lié pour le moment.'), findsOneWidget);
    expect(find.text('Aucune ressource disponible ici.'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsNothing);
  });

  testWidgets('800 stays single territory', (tester) async {
    await _pumpFull(
      tester,
      selector: selector,
      now: now,
      viewport: const Size(800, 900),
    );

    expect(find.byKey(const Key('me-territories-compact')), findsOneWidget);
    expect(find.byKey(const Key('me-territories-wide')), findsNothing);
  });

  testWidgets('840 opens stable two-territory composition', (tester) async {
    await _pumpFull(
      tester,
      selector: selector,
      now: now,
      viewport: const Size(840, 900),
    );

    expect(find.byKey(const Key('me-territories-wide')), findsOneWidget);
    expect(find.byKey(const Key('makolo-adaptive-grid')), findsOneWidget);
  });

  testWidgets('900 stays two-territory without dashboard expansion', (
    tester,
  ) async {
    await _pumpFull(
      tester,
      selector: selector,
      now: now,
      viewport: const Size(900, 900),
    );

    expect(find.byKey(const Key('me-territories-wide')), findsOneWidget);

    final grid = tester.widget<MakoloAdaptiveGrid>(
      find.byKey(const Key('me-territories-wide')),
    );
    expect(grid.maxColumns, 2);
  });

  testWidgets('sparse wide does not add cognitive depth for width alone', (
    tester,
  ) async {
    final selection = selector.select(
      projection: _projection(_sparsePayload()),
      now: now,
    );

    await PresentationHarness.pump(
      tester,
      viewport: const Size(900, 900),
      child: MeView(selection: selection),
    );

    expect(find.byKey(const Key('me-territories-compact')), findsOneWidget);
  });

  testWidgets('resource N2 changes focus and back restores Moi', (
    tester,
  ) async {
    final selection = selector.select(
      projection: _projection(_fullPayload()),
      now: now,
    );

    await PresentationHarness.pump(
      tester,
      viewport: const Size(430, 932),
      child: MeView(selection: selection),
    );

    await tester.ensureVisible(find.text('Passeport.pdf'));
    await tester.pump();
    await tester.tap(find.text('Passeport.pdf'));
    await tester.pump();

    expect(find.byKey(const Key('me-depth-scroll')), findsOneWidget);
    expect(
      find.text(
        'Cette ressource est disponible ici. '
        'Son usage dépendra de ce que vous entreprendrez.',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('Requirement'), findsNothing);
    expect(find.textContaining('AccessCredential'), findsNothing);

    await tester.tap(find.widgetWithText(TextButton, 'Moi'));
    await tester.pump();

    expect(find.byKey(const Key('me-depth-scroll')), findsNothing);
    expect(find.byKey(const Key('me-territories-compact')), findsOneWidget);
  });

  testWidgets('refresh keeps existing content visible', (tester) async {
    final selection = selector.select(
      projection: _projection(_fullPayload()),
      now: now,
      refreshing: true,
    );

    await PresentationHarness.pump(tester, child: MeView(selection: selection));

    expect(find.text('Gilbert Bemwiz'), findsOneWidget);
    expect(find.text('Mise à jour…'), findsOneWidget);
  });

  testWidgets('recoverable source failure preserves Moi grammar', (
    tester,
  ) async {
    final selection = selector.select(
      projection: _projection(_fullPayload()),
      now: now,
      reachability: MakoloReachabilityCue.temporarilyUnavailable,
      failure: MakoloFailureCue.recoverable,
    );

    await PresentationHarness.pump(tester, child: MeView(selection: selection));

    expect(find.text('Gilbert Bemwiz'), findsOneWidget);
    expect(find.text('Mes ressources'), findsOneWidget);
    expect(
      find.textContaining('Ce qui est déjà disponible reste visible'),
      findsOneWidget,
    );
  });

  testWidgets('MeScreen consumes shared offline state with local snapshot', (
    tester,
  ) async {
    final database = MakoloDatabase.memory();
    final store = ProfileStore(database, 'profile-1');
    await store.putProjection(
      kind: 'personal.me',
      schemaVersion: 1,
      payload: _fullPayload(),
      receivedAt: DateTime.utc(2026, 10, 3, 12),
    );

    await PresentationHarness.pump(
      tester,
      viewport: const Size(430, 932),
      child: SyncStatusScope(
        status: const SyncStatus(state: SyncVisualState.offline),
        child: MeScreen(repository: PersonalRepository(store), now: () => now),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Gilbert Bemwiz'), findsOneWidget);
    expect(
      find.text('Contenu déjà disponible sur cet appareil.'),
      findsWidgets,
    );

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    await database.close();
  });

  for (final scale in [1.0, 1.3, 1.6]) {
    testWidgets('textScale $scale keeps essential content available', (
      tester,
    ) async {
      final selection = selector.select(
        projection: _projection(_fullPayload()),
        now: now,
      );

      await PresentationHarness.pump(
        tester,
        viewport: const Size(430, 932),
        textScale: scale,
        child: MeView(selection: selection),
      );

      expect(find.text('Gilbert Bemwiz'), findsOneWidget);
      expect(find.text('Passeport Makolo'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
}

Future<void> _pumpFull(
  WidgetTester tester, {
  required MeSelector selector,
  required DateTime now,
  required Size viewport,
}) async {
  final selection = selector.select(
    projection: _projection(_fullPayload()),
    now: now,
  );

  await PresentationHarness.pump(
    tester,
    viewport: viewport,
    child: MeView(selection: selection),
  );
}

class _MeStreamRepository extends PersonalRepository {
  _MeStreamRepository({required this._projection, required this._source})
    : super(_NeverUsedStore());

  final Stream<StoredProjection?> _projection;
  final Stream<OwnerSourceState> _source;

  @override
  Stream<StoredProjection?> watchMe() => _projection;

  @override
  Stream<OwnerSourceState> watchMeSource() => _source;
}

class _NeverUsedStore implements ProfileStore {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
