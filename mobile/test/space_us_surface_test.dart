import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/space/space_us_surface.dart';

Map<String, dynamic> _projection({bool limited = false}) => {
  'identity': {
    'slug': 'atelier',
    'name': 'Atelier collectif',
    'archetype': 'generic',
    'description': 'Création, formation et transmission.',
    if (!limited) 'location': {'city': 'Lubumbashi', 'country': 'CD'},
  },
  'authority': {'scope': limited ? 'activity_limited' : 'space'},
  'primary_role': limited
      ? null
      : {'code': 'space-admin', 'label': 'Coordination'},
  'team': {
    'visibility': limited ? 'restricted' : 'visible',
    'items': limited
        ? []
        : [
            {
              'profile': {'id': 'a', 'name': 'Amina Mbala'},
            },
          ],
  },
  'responsibilities': {
    'items': [
      {'combined': true, 'label': 'Toutes'},
      {'combined': false, 'label': 'Coordination'},
    ],
  },
  'ownership': {
    'visibility': limited ? 'restricted' : 'visible',
    'items': limited
        ? []
        : [
            {
              'profile': {'name': 'Kasa'},
              'responsibility': {'label': 'Propriétaire'},
            },
          ],
  },
  'relationships': {
    'label': 'Personnes & relations',
    'visibility': limited ? 'restricted' : 'visible',
    'sections': limited
        ? {}
        : {
            'partners': {
              'items': [
                {'name': 'Partenaire Alpha'},
              ],
              'has_more': false,
            },
          },
  },
  'trust': {'verified': false},
  'resources': {
    'visibility': limited ? 'restricted' : 'visible',
    'count': limited ? null : 1,
    'items': limited
        ? []
        : [
            {
              'kind': 'passport',
              'title': 'Passeport Makolo · PM-S-20261103-A1B2C3D4',
              'detail': 'Document institutionnel émis',
            },
          ],
  },
  'handoffs': {
    'responsibilities': '/space/atelier/us/responsibilities',
    if (!limited) ...{
      'team': '/space/atelier/us/team',
      'relationships': '/space/atelier/us/relationships',
      'ownership': '/space/atelier/us/ownership',
      'resources': '/space/atelier/us/resources',
    },
    'settings': '/space/atelier/us/settings',
    if (!limited) 'passport': '/space/atelier/us/passport',
    'pilot': '/space/atelier/us/pilot',
    'trust': '/space/atelier/us/trust',
  },
};

void main() {
  for (final width in [360.0, 834.0, 1440.0]) {
    testWidgets('Nous is readable at width $width', (tester) async {
      tester.view.physicalSize = Size(width, 1100);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final routes = <String>[];
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: Scaffold(
            body: SpaceUsSurface(
              payload: _projection(),
              fallbackSpaceName: 'Fallback',
              onOpen: routes.add,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Atelier collectif'), findsOneWidget);
      expect(find.text('Espace générique'), findsOneWidget);
      expect(
        tester.getTopLeft(find.text('Espace générique')).dy,
        greaterThan(tester.getTopLeft(find.text('Atelier collectif')).dy),
      );
      expect(find.text('Coordination'), findsOneWidget);
      expect(find.text('Toutes'), findsNothing);
      expect(find.text('AM'), findsOneWidget);
      expect(find.byKey(const Key('space-us-members-strip')), findsOneWidget);
      expect(find.byKey(const Key('space-us-entry-team')), findsNothing);
      expect(find.text('Nos relations'), findsNothing);
      expect(find.text('Paramètres institutionnels'), findsNothing);
      expect(tester.takeException(), isNull);
      expect(find.text('Passeport Makolo'), findsNothing);
      expect(find.text('Notre Passeport'), findsOneWidget);
      expect(find.text('Nous'), findsNothing);
      expect(find.text('Nos démarches'), findsOneWidget);
      expect(find.text('Abonnement de cet Espace'), findsNothing);
      expect(find.text('Gérer les connexions de cet Espace'), findsNothing);

      expect(find.text('Lubumbashi, Congo-Kinshasa'), findsOneWidget);
      expect(
        find.byKey(const Key('space-us-territories-list')),
        findsOneWidget,
      );
      expect(find.text('Notre espace'), findsOneWidget);
      await tester.ensureVisible(find.text('Notre Passeport'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Notre Passeport'));
      expect(routes, ['/space/atelier/us/passport']);
      await tester.ensureVisible(find.text('Nos démarches'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Nos démarches'));
      expect(routes.last, '/space/atelier/objectives');

      expect(
        find.byKey(const Key('space-us-entry-relationships')),
        findsNothing,
      );
      await tester.tap(find.byKey(const Key('space-us-primary-role')));
      expect(routes.last, '/space/atelier/us/responsibilities');
      await tester.scrollUntilVisible(
        find.byKey(const Key('space-us-entry-resources')),
        250,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('space-us-entry-resources')));
      expect(routes.last, '/space/atelier/us/resources');
      await tester.scrollUntilVisible(
        find.byKey(const Key('space-us-entry-trust')),
        250,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('space-us-entry-trust')));
      expect(routes.last, '/space/atelier/us/trust');
      await tester.ensureVisible(
        find.byKey(const Key('space-us-edit-passport')),
      );
      await tester.tap(find.byKey(const Key('space-us-edit-passport')));
      expect(routes.last, '/space/atelier/us/settings');
      await tester.scrollUntilVisible(
        find.text('Comprendre notre activité'),
        250,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Comprendre notre activité'));
      expect(routes.last, '/space/atelier/us/pilot');
    });
  }

  for (final width in [320.0, 360.0, 393.0]) {
    testWidgets('Nous compact grid stays two-up at width $width', (
      tester,
    ) async {
      tester.view.physicalSize = Size(width, 940);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final routes = <String>[];
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: Scaffold(
            body: SpaceUsSurface(
              payload: _projection(),
              fallbackSpaceName: 'Fallback',
              onOpen: routes.add,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(
        find.byKey(const Key('space-us-layout-toggle')),
      );
      await tester.tap(find.byIcon(Icons.grid_view_rounded));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('space-us-territories-grid')),
        findsOneWidget,
      );

      final first = find.byKey(const Key('space-us-grid-resources'));
      final second = find.byKey(const Key('space-us-grid-ownership'));
      expect(first, findsOneWidget);
      expect(second, findsOneWidget);
      await tester.ensureVisible(first);
      await tester.pumpAndSettle();
      final firstPosition = tester.getTopLeft(first);
      final secondPosition = tester.getTopLeft(second);
      expect(secondPosition.dx, greaterThan(firstPosition.dx));
      expect((secondPosition.dy - firstPosition.dy).abs(), lessThan(2.0));
      expect(tester.getSize(first).width, lessThan(width / 2));
      expect(tester.takeException(), isNull);

      await tester.tap(second);
      expect(routes.last, '/space/atelier/us/ownership');
    });
  }

  testWidgets(
    'Nous identity truncates presentation visually, not owner facts',
    (tester) async {
      tester.view.physicalSize = const Size(360, 940);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final projection = _projection();
      final description = List.filled(
        12,
        'Notre Espace accompagne des rencontres et des activités collectives.',
      ).join(' ');
      (projection['identity'] as Map<String, dynamic>)['description'] =
          description;
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: Scaffold(
            body: SpaceUsSurface(
              payload: projection,
              fallbackSpaceName: 'Fallback',
              onOpen: (_) {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text(description), findsOneWidget);
      expect(
        tester.getSize(find.byKey(const Key('space-us-identity-card'))).height,
        lessThan(200),
      );
      expect(find.text('Lubumbashi, Congo-Kinshasa'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Nous management uses shared cards and real Space handoffs', (
    tester,
  ) async {
    final opened = <String>[];
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: _projection(),
            fallbackSpaceName: 'Fallback',
            onOpen: opened.add,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final settings = find.byKey(const Key('space-us-edit-passport'));
    await tester.scrollUntilVisible(
      settings,
      250,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(settings);
    expect(opened.single, '/space/atelier/us/settings');
    expect(find.text('Informations et gestion'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('scanner cannot edit Space Passport without update permission', (
    tester,
  ) async {
    final projection = _projection();
    (projection['handoffs'] as Map<String, dynamic>).remove('settings');
    (projection['handoffs'] as Map<String, dynamic>).remove('passport');
    (projection['primary_role'] as Map<String, dynamic>)['label'] = 'Scanneur';
    final opened = <String>[];
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: projection,
            fallbackSpaceName: 'Fallback',
            onOpen: opened.add,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Scanneur'), findsOneWidget);
    expect(find.byKey(const Key('space-us-edit-passport')), findsNothing);
    expect(find.text('Modifier les informations collectives'), findsNothing);
    await tester.tap(find.byKey(const Key('space-us-primary-role')));
    expect(opened.single, '/space/atelier/us/responsibilities');
  });

  testWidgets('empty authorized team has a compact link, not a false count', (
    tester,
  ) async {
    final projection = _projection();
    (projection['team'] as Map<String, dynamic>)['items'] = [];
    (projection['team'] as Map<String, dynamic>).remove('active_members');
    final opened = <String>[];
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: projection,
            fallbackSpaceName: 'Fallback',
            onOpen: opened.add,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('space-us-team-link-empty')), findsOneWidget);
    expect(find.textContaining('membres'), findsNothing);
    await tester.tap(find.byKey(const Key('space-us-team-link-empty')));
    expect(opened.single, '/space/atelier/us/team');
  });

  testWidgets('activity-only projection never shows institution data', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: _projection(limited: true),
            fallbackSpaceName: 'Fallback',
            onOpen: (_) {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Coordination'), findsOneWidget);
    expect(find.text('Amina'), findsNothing);
    expect(find.text('Kasa'), findsNothing);
    expect(find.text('Partenaires'), findsNothing);
    expect(find.text('Notre équipe'), findsNothing);
    expect(find.text('Nos relations'), findsNothing);
    expect(find.text('Modifier les informations collectives'), findsNothing);
    expect(find.text('Notre Passeport'), findsNothing);
    expect(find.text('Nos démarches'), findsNothing);
    expect(find.text('Nos ressources'), findsNothing);
    expect(find.text('Comprendre notre activité'), findsNothing);
    expect(find.textContaining('Contexte limité'), findsOneWidget);
  });

  testWidgets(
    'archived Space identity is explained without hiding the portrait',
    (tester) async {
      final projection = _projection();
      (projection['identity'] as Map<String, dynamic>)['lifecycle'] =
          'archived';
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: Scaffold(
            body: SpaceUsSurface(
              payload: projection,
              fallbackSpaceName: 'Fallback',
              onOpen: (_) {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Atelier collectif'), findsOneWidget);
      expect(find.text('Cet Espace est archivé.'), findsOneWidget);
    },
  );

  testWidgets('Nous keeps secondary administration routes out of the hub', (
    tester,
  ) async {
    final projection = _projection();
    (projection['handoffs'] as Map<String, dynamic>).addAll({
      'subscription': '/space/atelier/subscription',
      'connections': '/space/atelier/connections',
    });
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: projection,
            fallbackSpaceName: 'Fallback',
            onOpen: (_) {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Nos démarches'), findsOneWidget);
    expect(find.text('Informations et gestion'), findsOneWidget);
    expect(find.text('Abonnement de cet Espace'), findsNothing);
    expect(find.text('Gérer les connexions de cet Espace'), findsNothing);
    expect(
      find.text('Les fonctions institutionnelles autorisées.'),
      findsNothing,
    );
  });

  testWidgets('authorized Space team shows people rather than generic symbol', (
    tester,
  ) async {
    final projection = _projection();
    (projection['team'] as Map<String, dynamic>)['items'] = [
      {
        'profile': {'id': 'a', 'name': 'Amina Mbala'},
      },
      {
        'profile': {'id': 'b', 'name': 'Patrick Kasa'},
      },
      {
        'profile': {'id': 'c', 'name': 'Chantal Lunda'},
      },
    ];
    (projection['team'] as Map<String, dynamic>)['active_members'] = 5;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: projection,
            fallbackSpaceName: 'Fallback',
            onOpen: (_) {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('space-us-entry-team')), findsNothing);
    expect(find.byKey(const Key('space-us-members-strip')), findsOneWidget);
    expect(find.text('AM'), findsOneWidget);
    expect(find.text('PK'), findsOneWidget);
    expect(find.text('CL'), findsOneWidget);
    expect(find.text('+2'), findsOneWidget);
    expect(find.text('5 membres'), findsOneWidget);
    expect(find.text('Notre équipe'), findsNothing);
  });

  testWidgets('member avatars open existing Profile; count opens team', (
    tester,
  ) async {
    final routes = <String>[];
    final projection = _projection();
    (projection['team'] as Map<String, dynamic>)['active_members'] = 5;
    (projection['team'] as Map<String, dynamic>)['items'] = [
      for (final person in [
        'Amina Mbala',
        'Esther Sow',
        'Grace Mutombo',
        'Naomi Traore',
      ])
        {
          'profile': {
            'id': person.split(' ').first.toLowerCase(),
            'name': person,
          },
        },
    ];
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: projection,
            fallbackSpaceName: 'Espace',
            onOpen: routes.add,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('5 membres'), findsOneWidget);
    expect(find.text('+1'), findsOneWidget);
    expect(find.byKey(const Key('space-us-member-avatar-3')), findsOneWidget);
    expect(find.byKey(const Key('space-us-member-avatar-4')), findsNothing);
    expect(find.byKey(const Key('space-us-entry-team')), findsNothing);
    await tester.tap(find.byKey(const Key('space-us-member-avatar-0')));
    expect(routes.last, '/people/amina');
    await tester.tap(find.byKey(const Key('space-us-members-link')));
    expect(routes.last, '/space/atelier/us/team');
  });

  testWidgets('team preview does not invent a member count', (tester) async {
    final projection = _projection();
    (projection['team'] as Map<String, dynamic>).remove('active_members');
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: projection,
            fallbackSpaceName: 'Espace',
            onOpen: (_) {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('space-us-members-strip')), findsOneWidget);
    expect(find.textContaining('membres'), findsNothing);
    expect(find.text('AM'), findsOneWidget);
  });

  testWidgets('restricted Team section never exposes cached member rows', (
    tester,
  ) async {
    final projection = _projection();
    final team = projection['team'] as Map<String, dynamic>;
    team['visibility'] = 'restricted';
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: projection,
            fallbackSpaceName: 'Fallback',
            onOpen: (_) => fail('Restricted Team link cannot open'),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Atelier collectif'), findsOneWidget);
    expect(find.text('Amina'), findsNothing);
    expect(find.text('Notre équipe'), findsNothing);
    expect(find.byKey(const Key('space-us-members-strip')), findsNothing);
  });

  testWidgets('unknown Space visibility never leaks cached institution rows', (
    tester,
  ) async {
    final projection = _projection();
    (projection['team'] as Map<String, dynamic>)['visibility'] = 'unavailable';
    (projection['ownership'] as Map<String, dynamic>)['visibility'] = 'unknown';
    (projection['relationships'] as Map<String, dynamic>)['visibility'] =
        'restricted';
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: projection,
            fallbackSpaceName: 'Fallback',
            onOpen: (_) =>
                fail('No restricted institution destination may open'),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Coordination'), findsOneWidget);
    expect(find.text('Amina'), findsNothing);
    expect(find.text('Kasa'), findsNothing);
    expect(find.text('Partenaires'), findsNothing);
    expect(find.byKey(const Key('space-us-entry-team')), findsNothing);
    expect(find.byKey(const Key('space-us-entry-ownership')), findsNothing);
    expect(find.byKey(const Key('space-us-entry-relationships')), findsNothing);
  });

  testWidgets('sparse relations avoid empty preview rows', (tester) async {
    final projection = _projection();
    (projection['relationships'] as Map<String, dynamic>)['sections'] = {
      'team': {
        'items': [
          {'name': 'Amina'},
        ],
        'has_more': false,
      },
      'partners': {'items': [], 'has_more': false},
    };
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: projection,
            fallbackSpaceName: 'Fallback',
            onOpen: (_) {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('AM'), findsOneWidget);
    expect(find.text('Partenaires'), findsNothing);
    expect(find.text('Nos relations'), findsNothing);
  });

  testWidgets('Nous presents institutional documents without private data', (
    tester,
  ) async {
    final projection = _projection();
    (projection['resources'] as Map<String, dynamic>)['items'] = [
      {
        'kind': 'document',
        'id': 'f3f928b9-113a-43ed-a66d-67de43de521a',
        'title': 'Statuts de l’Espace',
        'detail': 'Document de l’Espace · Confidentiel',
      },
    ];
    final opened = <String>[];
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: projection,
            fallbackSpaceName: 'Espace',
            onOpen: opened.add,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Statuts de l’Espace'), findsOneWidget);
    expect(find.textContaining('private_media'), findsNothing);
    await tester.ensureVisible(
      find.byKey(const Key('space-us-entry-resources')),
    );
    await tester.tap(find.byKey(const Key('space-us-entry-resources')));
    expect(opened.single, '/space/atelier/us/resources');
  });

  testWidgets('Resources never open a forged cross-Space destination', (
    tester,
  ) async {
    final projection = _projection();
    (projection['handoffs'] as Map<String, dynamic>)['resources'] =
        '/space/other/us/resources';
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: projection,
            fallbackSpaceName: 'Fallback',
            onOpen: (_) => fail('Foreign Resources link cannot open'),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Nos ressources'), findsNothing);
  });

  testWidgets('forged cross-Space link is not presented', (tester) async {
    final projection = _projection();
    (projection['handoffs'] as Map<String, dynamic>)['relationships'] =
        '/space/autre/us/relationships';
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: projection,
            fallbackSpaceName: 'Fallback',
            onOpen: (_) => fail('Cross-Space route should not open'),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('space-us-entry-relationships')), findsNothing);
    expect(find.byKey(const Key('space-us-edit-passport')), findsOneWidget);
  });
  testWidgets('Nous switches to the shared grid and keeps owner handoffs', (
    tester,
  ) async {
    final opened = <String>[];
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(
          body: SpaceUsSurface(
            payload: _projection(),
            fallbackSpaceName: 'Fallback',
            onOpen: opened.add,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('space-us-layout-toggle')));
    await tester.tap(find.byIcon(Icons.grid_view_rounded));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('space-us-territories-grid')), findsOneWidget);
    expect(find.byKey(const Key('space-us-territories-list')), findsNothing);
    expect(find.byKey(const Key('space-us-grid-team')), findsNothing);
    expect(find.byKey(const Key('space-us-members-strip')), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('space-us-members-link')));
    await tester.tap(find.byKey(const Key('space-us-members-link')));
    expect(opened.single, '/space/atelier/us/team');
    await tester.ensureVisible(find.byKey(const Key('space-us-layout-toggle')));
    await tester.tap(find.byIcon(Icons.view_list_outlined));
    await tester.pumpAndSettle();
    expect(find.text('AM'), findsOneWidget);
  });

  testWidgets('switching Spaces clears the previous presentation and routes', (
    tester,
  ) async {
    final opened = <String>[];
    final payload = _projection();
    Widget surface(Map<String, dynamic> value) => MaterialApp(
      theme: buildMakoloTheme(),
      home: Scaffold(
        body: SpaceUsSurface(
          payload: value,
          fallbackSpaceName: 'Fallback',
          onOpen: opened.add,
        ),
      ),
    );
    await tester.pumpWidget(surface(payload));
    await tester.pumpAndSettle();
    await tester.tap(find.byIcon(Icons.grid_view_rounded));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('space-us-territories-grid')), findsOneWidget);
    final next = _projection();
    (next['identity'] as Map<String, dynamic>)['slug'] = 'different-space';
    (next['identity'] as Map<String, dynamic>)['name'] = 'Autre collectif';
    await tester.pumpWidget(surface(next));
    await tester.pumpAndSettle();
    expect(find.text('Autre collectif'), findsOneWidget);
    expect(find.byKey(const Key('space-us-territories-list')), findsOneWidget);
    // Old projection handoffs are rejected when they point at another Space.
    expect(find.byKey(const Key('space-us-entry-resources')), findsNothing);
    expect(opened, isEmpty);
  });

  testWidgets('revoked institutional visibility removes team and resources', (
    tester,
  ) async {
    final visible = _projection();
    final hidden = _projection();
    (hidden['team'] as Map<String, dynamic>)['visibility'] = 'restricted';
    (hidden['resources'] as Map<String, dynamic>)['visibility'] = 'restricted';
    Widget surface(Map<String, dynamic> value) => MaterialApp(
      theme: buildMakoloTheme(),
      home: Scaffold(
        body: SpaceUsSurface(
          payload: value,
          fallbackSpaceName: 'Fallback',
          onOpen: (_) {},
        ),
      ),
    );
    await tester.pumpWidget(surface(visible));
    await tester.pumpAndSettle();
    // The previous test may have stored a Grid preference on this device.
    await tester.ensureVisible(find.byKey(const Key('space-us-layout-toggle')));
    await tester.tap(find.byIcon(Icons.view_list_outlined));
    await tester.pumpAndSettle();
    expect(find.text('AM'), findsOneWidget);
    await tester.pumpWidget(surface(hidden));
    await tester.pumpAndSettle();
    expect(find.text('AM'), findsNothing);
    expect(find.byKey(const Key('space-us-members-strip')), findsNothing);
    expect(find.byKey(const Key('space-us-entry-team')), findsNothing);
    expect(find.byKey(const Key('space-us-entry-resources')), findsNothing);
  });
  testWidgets(
    'Nous switching respects reduced motion on small text-scaled view',
    (tester) async {
      tester.view.physicalSize = const Size(280, 860);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          theme: buildMakoloTheme(),
          home: MediaQuery(
            data: const MediaQueryData(
              disableAnimations: true,
              textScaler: TextScaler.linear(1.6),
            ),
            child: Scaffold(
              body: SpaceUsSurface(
                payload: _projection(),
                fallbackSpaceName: 'Espace',
                onOpen: (_) {},
              ),
            ),
          ),
        ),
      );
      await tester.pump();
      final switcher = tester.widget<AnimatedSwitcher>(
        find.byKey(const ValueKey<String>('space-us-switcher-atelier')),
      );
      expect(switcher.duration, Duration.zero);
      await tester.ensureVisible(
        find.byKey(const Key('space-us-layout-toggle')),
      );
      if (find.byIcon(Icons.grid_view_rounded).evaluate().isNotEmpty) {
        await tester.tap(find.byIcon(Icons.grid_view_rounded).first);
      }
      await tester.pump();
      expect(
        find.byKey(const Key('space-us-territories-grid')),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('old Space team is not shown even during outgoing animation', (
    tester,
  ) async {
    Widget screen(Map<String, dynamic> projection) => MaterialApp(
      theme: buildMakoloTheme(),
      home: Scaffold(
        body: SpaceUsSurface(
          payload: projection,
          fallbackSpaceName: 'Espace',
          onOpen: (_) {},
        ),
      ),
    );
    await tester.pumpWidget(screen(_projection()));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('space-us-layout-toggle')));
    if (find.byIcon(Icons.grid_view_rounded).evaluate().isNotEmpty) {
      await tester.tap(find.byIcon(Icons.grid_view_rounded).first);
      await tester.pumpAndSettle();
    }

    final next = _projection();
    (next['identity'] as Map<String, dynamic>)['slug'] = 'different-space';
    (next['identity'] as Map<String, dynamic>)['name'] = 'Nouveau collectif';
    (next['team'] as Map<String, dynamic>)['visibility'] = 'restricted';
    (next['handoffs'] as Map<String, dynamic>).clear();
    await tester.pumpWidget(screen(next));
    await tester.pump();
    expect(find.text('Nouveau collectif'), findsOneWidget);
    expect(find.text('AM'), findsNothing);
    expect(find.byKey(const Key('space-us-members-strip')), findsNothing);
  });
}
