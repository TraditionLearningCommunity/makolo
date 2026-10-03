import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/design/surface_states.dart';
import 'package:makolo_mobile/features/me/me_screen.dart';
import 'package:makolo_mobile/features/me/me_selector.dart';

import 'support/presentation_harness.dart';

StoredProjection _projection(
  Map<String, dynamic> payload, {
  DateTime? freshUntil,
  DateTime? expiresAt,
}) {
  return StoredProjection(
    kind: 'personal.me',
    schemaVersion: 1,
    payload: payload,
    receivedAt: DateTime.utc(2026, 10, 3, 12),
    sourceGeneratedAt: DateTime.utc(2026, 10, 3, 12),
    lastVerifiedOnlineAt: DateTime.utc(2026, 10, 3, 12),
    freshUntil: freshUntil,
    expiresAt: expiresAt,
    freshnessPolicyId: 'personal.me',
  );
}

Map<String, dynamic> _fullPayload() => {
  'identity': {
    'kind': 'profile',
    'id': 'profile-1',
    'display_name': 'Gilbra',
    'profession': 'Ingénieur',
    'bio': 'Construire ce qui facilite la suite.',
    'location': {'city': 'Kinshasa', 'country': 'RDC'},
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
    'open_to': {'count': 0, 'items': [], 'has_more': false},
    'watches': {'count': 0, 'items': [], 'has_more': false},
    'bookmarks': {'count': 0, 'items': [], 'has_more': false},
    'followed_spaces': {'count': 0, 'items': [], 'has_more': false},
    'followed_profiles': {'count': 0, 'items': [], 'has_more': false},
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
    'recognition': {'available': false},
    'loyalty': {'available': false},
    'partners': {'available': false},
  },
  'links': {},
};

void main() {
  const selector = MeSelector();
  final now = DateTime.utc(2026, 10, 3, 13);

  test('selector adapts the real personal.me root shape', () {
    final selection = selector.select(
      projection: _projection(_fullPayload()),
      now: now,
    );

    expect(selection.presentation.identityLabel, 'Gilbra');
    expect(selection.identitySubtitle, 'Ingénieur · Kinshasa, RDC');
    expect(selection.territories.map((item) => item.presentation.key), [
      'passport',
      'considerations',
      'collectives',
      'resources',
    ]);

    final resources = selection.territories.singleWhere(
      (item) => item.presentation.key == 'resources',
    );
    expect(resources.items.map((item) => item.destination.kind), [
      'personal_asset',
      'proof',
      'credential',
    ]);

    final collectives = selection.territories.singleWhere(
      (item) => item.presentation.key == 'collectives',
    );
    expect(
      collectives.items.first.subtitle,
      'Contexte autorisé par le serveur',
    );
    expect(collectives.items[1].subtitle, 'Membre');
  });

  test('sparse payload keeps identity and local empty territories', () {
    final selection = selector.select(
      projection: _projection({
        'identity': {
          'kind': 'profile',
          'id': 'profile-1',
          'display_name': 'Gilbra',
        },
        'passport': {'available': false},
      }),
      now: now,
    );

    expect(selection.presentation.identityLabel, 'Gilbra');
    expect(selection.territories, hasLength(4));
    expect(
      selection.territories
          .where(
            (item) =>
                item.presentation.state.availability ==
                MakoloAvailabilityCue.empty,
          )
          .length,
      greaterThanOrEqualTo(4),
    );
  });

  test('projection freshness is reflected without inventing a TTL', () {
    final selection = selector.select(
      projection: _projection(
        _fullPayload(),
        freshUntil: DateTime.utc(2026, 10, 3, 12, 30),
      ),
      now: now,
    );

    expect(
      selection.state.freshness,
      MakoloFreshnessCue.refreshRecommended,
    );
    expect(
      selection.territories.first.presentation.state.freshness,
      MakoloFreshnessCue.refreshRecommended,
    );
  });

  test('section empty and section error stay local', () {
    final payload = _fullPayload();
    payload['considerations'] = {
      'interests': {'count': 0, 'items': [], 'has_more': false},
      'open_to': {'count': 0, 'items': [], 'has_more': false},
      'watches': {'count': 0, 'items': [], 'has_more': false},
      'bookmarks': {'count': 0, 'items': [], 'has_more': false},
      'followed_spaces': {'count': 0, 'items': [], 'has_more': false},
      'followed_profiles': {'count': 0, 'items': [], 'has_more': false},
    };
    payload['collectives'] = 'malformed';

    final selection = selector.select(
      projection: _projection(payload),
      now: now,
    );

    final considerations = selection.territories.singleWhere(
      (item) => item.presentation.key == 'considerations',
    );
    final collectives = selection.territories.singleWhere(
      (item) => item.presentation.key == 'collectives',
    );

    expect(
      considerations.presentation.state.availability,
      MakoloAvailabilityCue.empty,
    );
    expect(
      collectives.presentation.state.failure,
      MakoloFailureCue.blocking,
    );
    expect(selection.presentation.identityLabel, 'Gilbra');
    expect(selection.state.availability, MakoloAvailabilityCue.content);
  });

  test('content can remain available while offline', () {
    final selection = selector.select(
      projection: _projection(_fullPayload()),
      now: now,
      reachability: MakoloReachabilityCue.temporarilyUnavailable,
    );

    expect(selection.state.availability, MakoloAvailabilityCue.content);
    expect(
      selection.state.reachability,
      MakoloReachabilityCue.temporarilyUnavailable,
    );
    expect(
      selection.territories.first.presentation.state.reachability,
      MakoloReachabilityCue.temporarilyUnavailable,
    );
  });

  testWidgets('G08 compact remains section-first and vertical', (tester) async {
    final selection = selector.select(
      projection: _projection(_fullPayload()),
      now: now,
    );

    await PresentationHarness.pump(
      tester,
      viewport: const Size(360, 800),
      child: MeView(selection: selection),
    );

    expect(find.byKey(const Key('me-territories-compact')), findsOneWidget);
    expect(find.byKey(const Key('me-territories-wide')), findsNothing);
    expect(find.text('Déjà en place'), findsOneWidget);
    expect(find.text('Passeport Makolo'), findsOneWidget);
  });

  testWidgets('G09 wide uses at most two adaptive territories', (tester) async {
    final selection = selector.select(
      projection: _projection(_fullPayload()),
      now: now,
    );

    await PresentationHarness.pump(
      tester,
      viewport: const Size(1000, 900),
      child: MeView(selection: selection),
    );

    expect(find.byKey(const Key('me-territories-wide')), findsOneWidget);
    expect(find.byKey(const Key('makolo-adaptive-grid')), findsOneWidget);
  });

  testWidgets('resource opens a local N2 depth and back restores Moi', (
    tester,
  ) async {
    final selection = selector.select(
      projection: _projection(_fullPayload()),
      now: now,
    );

    await PresentationHarness.pump(
      tester,
      viewport: const Size(430, 900),
      child: MeView(selection: selection),
    );

    await tester.scrollUntilVisible(
      find.text('Passeport.pdf'),
      250,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.text('Passeport.pdf'));
    await tester.pump();

    expect(
      find.text(
        'Posséder cette ressource ne signifie pas qu’un Requirement est satisfait.',
      ),
      findsOneWidget,
    );

    await tester.tap(find.widgetWithText(TextButton, 'Moi'));
    await tester.pump();
    expect(find.text('Déjà en place'), findsOneWidget);
  });

  testWidgets(
    'offline-known remains usable and textScale critical does not break',
    (tester) async {
      final selection = selector.select(
      projection: _projection(_fullPayload()),
      now: now,
      reachability: MakoloReachabilityCue.temporarilyUnavailable,
      );

      await PresentationHarness.pump(
        tester,
        viewport: const Size(430, 932),
        textScale: 1.6,
        child: MeView(selection: selection),
      );

      expect(
        find.text(
          'La source distante est momentanément indisponible. Le contenu déjà disponible reste utilisable.',
        ),
        findsOneWidget,
      );
      expect(find.text('Gilbra'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}
