import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/space/space_us_surface.dart';

Map<String, dynamic> _projection({bool limited = false}) => {
  'identity': {
    'slug': 'atelier',
    'name': 'Atelier collectif',
    'description': 'Création, formation et transmission.',
    if (!limited) 'location': {'city': 'Lubumbashi', 'country': 'CD'},
  },
  'authority': {'scope': limited ? 'activity_limited' : 'space'},
  'team': {
    'visibility': limited ? 'restricted' : 'visible',
    'items': limited ? [] : [
      {'profile': {'name': 'Amina'}},
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
    'items': limited ? [] : [
      {'profile': {'name': 'Kasa'}, 'responsibility': {'label': 'Propriétaire'}},
    ],
  },
  'relationships': {
    'label': 'Personnes & relations',
    'sections': limited ? {} : {
      'partners': {
        'items': [{'name': 'Partenaire Alpha'}],
        'has_more': false,
      },
    },
  },
  'trust': {'verified': false},
  'handoffs': {
    'responsibilities': '/space/atelier/us/responsibilities',
    if (!limited) ...{
      'team': '/space/atelier/us/team',
      'relationships': '/space/atelier/us/relationships',
      'ownership': '/space/atelier/us/ownership',
    },
    'settings': '/space/atelier/us/settings',
    'pilot': '/space/atelier/us/pilot',
    'trust': '/space/atelier/us/trust',
  },
};

void main() {
  for (final width in [360.0, 834.0, 1440.0]) {
    testWidgets('Nous is readable at width ' + width.toString(), (tester) async {
      tester.view.physicalSize = Size(width, 1100);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final routes = <String>[];
      await tester.pumpWidget(MaterialApp(
        theme: buildMakoloTheme(),
        home: Scaffold(body: SpaceUsSurface(
          payload: _projection(),
          fallbackSpaceName: 'Fallback',
          onOpen: routes.add,
        )),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Atelier collectif'), findsOneWidget);
      expect(find.text('Coordination'), findsOneWidget);
      expect(find.text('Toutes'), findsNothing);
      expect(find.text('Amina'), findsOneWidget);
      expect(find.text('Partenaires'), findsOneWidget);
      expect(find.text('Paramètres institutionnels'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.ensureVisible(find.text('Explorer les relations'));
      await tester.tap(find.text('Explorer les relations'));
      expect(routes, ['/space/atelier/us/relationships']);
      await tester.ensureVisible(find.text('Consulter les faits de confiance'));
      await tester.tap(find.text('Consulter les faits de confiance'));
      expect(routes.last, '/space/atelier/us/trust');
      await tester.ensureVisible(find.text('Modifier les informations collectives'));
      await tester.tap(find.text('Modifier les informations collectives'));
      expect(routes.last, '/space/atelier/us/settings');
      await tester.ensureVisible(find.text('Comprendre notre activité'));
      await tester.tap(find.text('Comprendre notre activité'));
      expect(routes.last, '/space/atelier/us/pilot');
    });
  }

  testWidgets('activity-only projection never shows institution data', (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: buildMakoloTheme(),
      home: Scaffold(body: SpaceUsSurface(
        payload: _projection(limited: true),
        fallbackSpaceName: 'Fallback',
        onOpen: (_) {},
      )),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Coordination'), findsOneWidget);
    expect(find.text('Amina'), findsNothing);
    expect(find.text('Kasa'), findsNothing);
    expect(find.text('Partenaires'), findsNothing);
    expect(find.text('Ouvrir l’équipe'), findsNothing);
    expect(find.text('Explorer les relations'), findsNothing);
    expect(find.text('Modifier les informations collectives'), findsNothing);
    expect(find.text('Comprendre notre activité'), findsNothing);
    expect(find.textContaining('Contexte limité'), findsOneWidget);
  });

  testWidgets('forged cross-Space link is not presented', (tester) async {
    final projection = _projection();
    (projection['handoffs'] as Map<String, dynamic>)['relationships'] =
        '/space/autre/us/relationships';
    await tester.pumpWidget(MaterialApp(
      theme: buildMakoloTheme(),
      home: Scaffold(body: SpaceUsSurface(
        payload: projection, fallbackSpaceName: 'Fallback',
        onOpen: (_) => fail('Cross-Space route should not open'),
      )),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Explorer les relations'), findsNothing);
  });
}
