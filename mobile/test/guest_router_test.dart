import 'dart:async';
import 'dart:convert' as convert;

import 'package:flutter/material.dart';
import 'package:makolo_mobile/platform/location/geo_search_gateway.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/providers.dart';
import 'package:makolo_mobile/app/resumable_interaction_store.dart';
import 'package:makolo_mobile/app/router.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/features/auth/login_screen.dart';
import 'package:makolo_mobile/features/auth/signup_screen.dart';
import 'package:makolo_mobile/features/discovery/discovery_event_tickets_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';
import 'fakes.dart';

class _MemoryLaunchPreferences implements LaunchPreferencesStore {
  LaunchPreferencesSnapshot snapshot = const LaunchPreferencesSnapshot();

  @override
  Future<LaunchPreferencesSnapshot> read() async => snapshot;

  @override
  Future<void> setLastBrandMomentAt(DateTime value) async {
    snapshot = snapshot.copyWith(lastBrandMomentAt: value);
  }

  @override
  Future<void> setOnboardingCompleted() async {
    snapshot = snapshot.copyWith(hasCompletedOnboarding: true);
  }
}

AppRuntime _guestRuntime(
  SessionRecoveryController recovery, {
  MockClient? client,
  GeoSearchGateway? geoSearch,
  ResumableInteractionAccess? interactions,
}) {
  final tokens = MemoryTokenStore();
  return AppRuntime(
    tokens: tokens,
    session: null,
    recovery: recovery,
    launchPreferences: _MemoryLaunchPreferences(),
    interactions: interactions ?? ResumableInteractionStore.memory(),
    geoSearch: geoSearch,
    api: client == null
        ? null
        : MakoloApiClient(
            baseUri: Uri.parse('https://makolo.invalid/'),
            dio: client.dio,
            tokenStore: tokens,
          ),
  );
}

GoRouter _router(AppRuntime runtime) {
  return createMakoloRouter(runtime, onAuthenticationChanged: () {});
}

Future<void> _pump(WidgetTester tester, GoRouter router) async {
  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp.router(
        theme: buildMakoloTheme(),
        routerConfig: router,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Map<String, dynamic> _item(String title, String id) => {
  'identity': {
    'family': 'activity',
    'candidate_key': 'activity:$id',
    'resource': {'kind': 'activity', 'id': id},
  },
  'representation': {
    'title': title,
    'summary': 'Description publique.',
    'eyebrow': 'Voyager',
  },
  'capabilities': ['view'],
  'links': {'detail': '/api/v1/discovery/items/activity/$id/'},
};

/// Legacy screen fixtures are framed as the actual B1 public wire.
/// Contract rejection cases are tested directly in discovery_wire_test.dart.
String _mockResponseJson(Object? value) {
  if (value is! Map || value['data'] is! Map) {
    return convert.jsonEncode(value);
  }
  final data = Map<String, dynamic>.from(value['data'] as Map);
  final results = data['results'];
  final detail = data['item'];
  if (results is! List && detail is! Map) {
    return convert.jsonEncode(value);
  }
  if (detail is Map) {
    if (detail['identity'] is! Map) {
      return convert.jsonEncode(value);
    }
    return convert.jsonEncode({
      ...value,
      'meta': {
        'projection': 'discovery.item',
        'schema_version': 1,
        'scope': 'public',
        'generated_at': '2026-10-17T12:00:00+00:00',
      },
    });
  }
  if (results!.isNotEmpty &&
      results.first is Map &&
      (results.first as Map)['identity'] is! Map) {
    return convert.jsonEncode(value);
  }
  final count = data['count'];
  final emptyField = count == 0;
  final hasNext = data['has_next'] == true;
  data.addAll({
    'surface': 'discover_public',
    'actor': null,
    'viewer': null,
    'items': results,
    'selection': {
      'state': emptyField ? 'empty' : 'ready',
      'reason': emptyField ? 'no_current_proposal' : null,
    },
    'terminal': {
      'state': emptyField
          ? 'empty'
          : results.isEmpty
          ? 'end_of_field'
          : 'ok',
      'message': null,
    },
    'continuation': {
      'state': hasNext ? 'more' : 'end',
      'token': hasNext ? 'fixture-opaque-next-page' : null,
    },
    'exploration': {'raw_text': '', 'constraints': <Object>[]},
    'freshness': {'state': 'fresh', 'fact_freshness': 'not_asserted'},
  });
  return convert.jsonEncode({
    ...value,
    'meta': {
      'projection': 'discovery.items',
      'schema_version': 1,
      'scope': 'public',
      'generated_at': '2026-10-17T12:00:00+00:00',
    },
    'data': data,
  });
}

class _FaultyInteractions implements ResumableInteractionAccess {
  _FaultyInteractions({this.failRead = false, this.failSave = false});

  final bool failRead;
  final bool failSave;

  @override
  Future<Map<String, dynamic>> read(String interactionId) async {
    if (failRead) throw const FormatException('corrupt local interaction');
    return <String, dynamic>{};
  }

  @override
  Future<void> save(String interactionId, Map<String, dynamic> values) async {
    if (failSave) throw const FormatException('local storage unavailable');
  }

  @override
  Future<void> clear(String interactionId) async {}
}

void main() {
  testWidgets('public Discover paints server results when count is 188', (
    tester,
  ) async {
    final client = MockClient(
      (request) async => MockResponse(
        _mockResponseJson({
          'data': {
            'count': 188,
            'page': 1,
            'page_size': 12,
            'has_next': true,
            'results': [
              _item(
                'Possibilité visible malgré un total de 188',
                '11111111-1111-4111-8111-111111111111',
              ),
            ],
          },
        }),
        200,
      ),
    );
    final router = _router(
      _guestRuntime(SessionRecoveryController(), client: client),
    );
    await _pump(tester, router);
    router.go('/discover');
    await tester.pumpAndSettle();

    expect(find.text('188 résultats'), findsOneWidget);
    expect(
      find.text('Possibilité visible malgré un total de 188'),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('public Discovery loads after local restore failure', (
    tester,
  ) async {
    final client = MockClient(
      (request) async => MockResponse(
        _mockResponseJson({
          'data': {
            'count': 1,
            'page': 1,
            'page_size': 12,
            'has_next': false,
            'results': [
              _item(
                'Possibilité après erreur locale',
                '11111111-1111-4111-8111-111111111111',
              ),
            ],
          },
        }),
        200,
      ),
    );
    final router = _router(
      _guestRuntime(
        SessionRecoveryController(),
        client: client,
        interactions: _FaultyInteractions(failRead: true),
      ),
    );
    await _pump(tester, router);
    router.go('/discover');
    await tester.pumpAndSettle();

    expect(find.text('Possibilité après erreur locale'), findsOneWidget);
    expect(
      find.byKey(const Key('guest-discover-local-warning')),
      findsOneWidget,
    );
    expect(find.byType(CircularProgressIndicator), findsNothing);
  });

  testWidgets('public Discovery does not wait for a failing local save', (
    tester,
  ) async {
    final client = MockClient(
      (request) async => MockResponse(
        _mockResponseJson({
          'data': {
            'count': 1,
            'page': 1,
            'page_size': 12,
            'has_next': false,
            'results': [
              _item(
                'Possibilité malgré écriture locale',
                '11111111-1111-4111-8111-111111111111',
              ),
            ],
          },
        }),
        200,
      ),
    );
    final router = _router(
      _guestRuntime(
        SessionRecoveryController(),
        client: client,
        interactions: _FaultyInteractions(failSave: true),
      ),
    );
    await _pump(tester, router);
    router.go('/discover');
    await tester.pumpAndSettle();

    expect(find.text('Possibilité malgré écriture locale'), findsOneWidget);
    expect(
      find.byKey(const Key('guest-discover-local-warning')),
      findsOneWidget,
    );
    expect(find.byType(CircularProgressIndicator), findsNothing);
  });

  testWidgets(
    'public Discovery exposes a malformed HTTP 200 as contract error',
    (tester) async {
      final client = MockClient(
        (request) async => MockResponse(
          convert.jsonEncode({
            'meta': {
              'projection': 'discovery.items',
              'schema_version': 1,
              'scope': 'public',
              'generated_at': '2026-10-19T12:00:00Z',
            },
            'data': {
              'surface': 'discover_public',
              'actor': null,
              'viewer': null,
              'count': 1,
              'page': 1,
              'page_size': 12,
              'has_next': true,
              'results': [
                _item(
                  'Réponse incomplète',
                  '11111111-1111-4111-8111-111111111111',
                ),
              ],
            },
          }),
          200,
        ),
      );
      final router = _router(
        _guestRuntime(SessionRecoveryController(), client: client),
      );
      await _pump(tester, router);
      router.go('/discover');
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('guest-discover-load-error')),
        findsOneWidget,
      );
      expect(
        find.textContaining('Contrat Discovery incompatible'),
        findsOneWidget,
      );
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(find.text('Réessayer'), findsOneWidget);
    },
  );
  testWidgets('guest enters public home with no Profile or Space shell', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(360, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final router = _router(_guestRuntime(SessionRecoveryController()));

    await _pump(tester, router);

    expect(tester.takeException(), isNull);
    expect(find.byKey(const Key('guest-public-home')), findsOneWidget);
    expect(find.text('Ça vous intéresserait'), findsOneWidget);
    expect(find.byKey(const Key('guest-home-search-submit')), findsOneWidget);
    expect(find.byKey(const Key('guest-home-quick-choices')), findsOneWidget);
    expect(find.byKey(const Key('guest-home-action-journey')), findsOneWidget);
    expect(find.text('Accueil'), findsOneWidget);
    expect(find.text('Espaces'), findsWidgets);
    expect(find.text('En cours'), findsNothing);
    expect(find.text('Moi'), findsNothing);
    expect(find.byTooltip('Avatar'), findsNothing);
    expect(find.byTooltip('Compte'), findsNothing);
    expect(find.byKey(const Key('guest-login-action')), findsOneWidget);
    expect(find.byKey(const Key('guest-register-action')), findsOneWidget);
    expect(find.byType(LoginScreen), findsNothing);

    await tester.tap(find.byKey(const Key('guest-login-action')));
    await tester.pumpAndSettle();
    expect(find.byType(LoginScreen), findsOneWidget);
  });

  testWidgets('guest welcome search submits to native Discover', (
    tester,
  ) async {
    final seenQueries = <String>[];
    final client = MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      expect(request.url.path, '/api/v1/discovery/items/');
      seenQueries.add(request.url.queryParameters['q'] ?? '');
      return MockResponse(
        _mockResponseJson({
          'data': {
            'count': 0,
            'page': 1,
            'page_size': 12,
            'has_next': false,
            'results': <Object>[],
          },
        }),
        200,
      );
    });
    final router = _router(
      _guestRuntime(SessionRecoveryController(), client: client),
    );
    await _pump(tester, router);

    await tester.enterText(
      find.byKey(const Key('guest-home-query')),
      'Voyager à Kolwezi',
    );
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(router.routeInformationProvider.value.uri.path, '/discover');
    expect(
      router.routeInformationProvider.value.uri.queryParameters['q'],
      'Voyager à Kolwezi',
    );
    expect(seenQueries, contains('Voyager à Kolwezi'));
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets('guest welcome quick filter navigates natively', (tester) async {
    final router = _router(_guestRuntime(SessionRecoveryController()));
    await _pump(tester, router);

    await tester.tap(find.text('Participer'));
    await tester.pumpAndSettle();

    expect(router.routeInformationProvider.value.uri.path, '/discover');
    expect(
      router.routeInformationProvider.value.uri.queryParameters['vertical'],
      'event',
    );
    expect(
      router.routeInformationProvider.value.uri.queryParameters['q'],
      isNull,
    );
  });

  for (final choice in const [
    ('Voyager', 'transport'),
    ('Être accompagné', 'service'),
    ('Tout explorer', ''),
  ]) {
    testWidgets('guest $choice opens the existing Discover field', (
      tester,
    ) async {
      final router = _router(_guestRuntime(SessionRecoveryController()));
      await _pump(tester, router);

      await tester.tap(find.text(choice.$1));
      await tester.pumpAndSettle();

      expect(router.routeInformationProvider.value.uri.path, '/discover');
      expect(
        router.routeInformationProvider.value.uri.queryParameters['vertical'],
        choice.$2.isEmpty ? isNull : choice.$2,
      );
      expect(find.byType(LoginScreen), findsNothing);
    });
  }

  testWidgets('guest welcome links to public Spaces', (tester) async {
    final router = _router(_guestRuntime(SessionRecoveryController()));
    await _pump(tester, router);

    await tester.scrollUntilVisible(
      find.byKey(const Key('guest-home-spaces')),
      160,
      scrollable: find
          .descendant(
            of: find.byKey(const Key('guest-public-home')),
            matching: find.byType(Scrollable),
          )
          .first,
    );
    await Scrollable.ensureVisible(
      tester.element(find.byKey(const Key('guest-home-spaces'))),
      alignment: 0.3,
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('guest-home-spaces')));
    await tester.pumpAndSettle();

    expect(router.routeInformationProvider.value.uri.path, '/spaces');
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets(
    'public Discover actually searches the server, not loaded items',
    (tester) async {
      final seenQueries = <String>[];
      final client = MockClient((request) async {
        expect(request.headers.containsKey('Authorization'), isFalse);
        expect(request.url.path, '/api/v1/discovery/items/');
        seenQueries.add(request.url.queryParameters['q'] ?? '');
        final filtered = request.url.queryParameters['q'] == '023';
        return MockResponse(
          _mockResponseJson({
            'data': {
              'count': filtered ? 1 : 2,
              'page': 1,
              'page_size': 12,
              'has_next': false,
              'results': filtered
                  ? [
                      _item(
                        'Accompagnement bourses Accra — 023',
                        '11111111-1111-4111-8111-111111111111',
                      ),
                    ]
                  : [
                      _item(
                        'Accompagnement bourses Accra — 023',
                        '11111111-1111-4111-8111-111111111111',
                      ),
                      _item(
                        'Atelier numérique Lubumbashi',
                        '22222222-2222-4222-8222-222222222222',
                      ),
                    ],
            },
          }),
          200,
        );
      });
      final router = _router(
        _guestRuntime(SessionRecoveryController(), client: client),
      );
      await _pump(tester, router);
      router.go('/discover');
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Atelier numérique Lubumbashi'),
        180,
        scrollable: find
            .descendant(
              of: find.byKey(const Key('guest-public-landing')),
              matching: find.byType(Scrollable),
            )
            .first,
      );
      expect(find.text('Atelier numérique Lubumbashi'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.byKey(const Key('guest-search-query')),
        -180,
        scrollable: find
            .descendant(
              of: find.byKey(const Key('guest-public-landing')),
              matching: find.byType(Scrollable),
            )
            .first,
      );
      await Scrollable.ensureVisible(
        tester.element(find.byKey(const Key('guest-search-query'))),
        alignment: 0.2,
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('guest-search-query')),
        '023',
      );
      await tester.pump(const Duration(milliseconds: 400));
      expect(
        find.byKey(const Key('guest-discover-search-clear')),
        findsOneWidget,
      );
      await tester.testTextInput.receiveAction(TextInputAction.search);
      await tester.pumpAndSettle();

      expect(seenQueries, contains('023'));
      expect(find.text('Accompagnement bourses Accra — 023'), findsOneWidget);
      expect(find.text('Atelier numérique Lubumbashi'), findsNothing);
    },
  );

  testWidgets(
    'public Discover text searches progressively without submission',
    (tester) async {
      final queries = <Uri>[];
      final client = MockClient((request) async {
        queries.add(request.url);
        return MockResponse(
          _mockResponseJson({
            'data': {
              'count': 0,
              'page': 1,
              'page_size': 12,
              'has_next': false,
              'results': <Object>[],
            },
          }),
          200,
        );
      });
      final router = _router(
        _guestRuntime(SessionRecoveryController(), client: client),
      );
      await _pump(tester, router);
      router.go('/discover');
      await tester.pumpAndSettle();
      final input = find.byKey(const Key('guest-search-query'));
      await tester.enterText(input, 'zam');
      await tester.pump(const Duration(milliseconds: 200));
      await tester.enterText(input, 'zamof');
      await tester.pump(const Duration(milliseconds: 360));
      await tester.pumpAndSettle();
      expect(queries.last.queryParameters['q'], 'zamof');
      expect(queries.last.queryParameters['page'], '1');
      await tester.enterText(input, '');
      await tester.pump(const Duration(milliseconds: 360));
      await tester.pumpAndSettle();
      expect(queries.last.queryParameters.containsKey('q'), isFalse);
    },
  );

  testWidgets('public Discover filters preserve supported server criteria', (
    tester,
  ) async {
    final requests = <Uri>[];
    final client = MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      expect(request.url.path, '/api/v1/discovery/items/');
      requests.add(request.url);
      return MockResponse(
        _mockResponseJson({
          'data': {
            'count': 0,
            'page': 1,
            'page_size': 12,
            'has_next': false,
            'results': <Object>[],
          },
        }),
        200,
      );
    });
    final router = _router(
      _guestRuntime(SessionRecoveryController(), client: client),
    );
    await _pump(tester, router);
    router.go('/discover');
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('guest-discover-categories')), findsOneWidget);
    await tester.tap(find.byKey(const Key('guest-filter-toggle')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('guest-filter-place')),
      'Kolwezi',
    );
    tester.testTextInput.hide();
    await tester.pumpAndSettle();
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();

    expect(requests.last.queryParameters['place'], 'Kolwezi');
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets(
    'guest chooses a real city and sends the supported place criterion',
    (tester) async {
      final requests = <Uri>[];
      final client = MockClient((request) async {
        requests.add(request.url);
        return MockResponse(
          _mockResponseJson({
            'data': {
              'count': 0,
              'page': 1,
              'page_size': 12,
              'has_next': false,
              'results': <Object>[],
            },
          }),
          200,
        );
      });
      final gateway = MapTilerGeoSearchGateway(
        apiKey: 'test-only',
        dio: MockClient(
          (request) async => MockResponse(
            _mockResponseJson({
              'features': [
                {
                  'id': 'place.kolwezi',
                  'place_name': 'Kolwezi, Lualaba, RD Congo',
                  'center': [25.47, -10.72],
                  'place_type': ['place'],
                },
              ],
            }),
            200,
          ),
        ).dio,
      );
      final router = _router(
        _guestRuntime(
          SessionRecoveryController(),
          client: client,
          geoSearch: gateway,
        ),
      );
      await _pump(tester, router);
      router.go('/discover');
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('guest-filter-toggle')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('guest-filter-place')),
        'Kol',
      );
      await tester.pump(const Duration(milliseconds: 360));
      await tester.pumpAndSettle();
      expect(find.text('Kolwezi, Lualaba, RD Congo'), findsOneWidget);
      await tester.tap(find.text('Kolwezi, Lualaba, RD Congo'));
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();
      expect(requests.last.queryParameters['place'], 'Kolwezi');
      expect(find.byType(LoginScreen), findsNothing);
    },
  );

  testWidgets(
    'guest selects a custom calendar date using the existing date API',
    (tester) async {
      final requests = <Uri>[];
      final client = MockClient((request) async {
        requests.add(request.url);
        return MockResponse(
          _mockResponseJson({
            'data': {
              'count': 0,
              'page': 1,
              'page_size': 12,
              'has_next': false,
              'results': <Object>[],
            },
          }),
          200,
        );
      });
      final router = _router(
        _guestRuntime(SessionRecoveryController(), client: client),
      );
      await _pump(tester, router);
      router.go('/discover');
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('guest-filter-toggle')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('guest-filter-when')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Choisir une date…').last);
      await tester.pumpAndSettle();
      expect(find.byType(DatePickerDialog), findsOneWidget);
      await tester.tap(find.text('Valider'));
      await tester.pumpAndSettle();
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();
      expect(requests.last.queryParameters['date'], isNotEmpty);
      expect(requests.last.queryParameters.containsKey('when'), isFalse);
    },
  );

  testWidgets('older public search response never replaces newer results', (
    tester,
  ) async {
    final previous = Completer<MockResponse>();
    final client = MockClient((request) async {
      final q = request.url.queryParameters['q'];
      if (q == 'ancien') return previous.future;
      return MockResponse(
        _mockResponseJson({
          'data': {
            'count': q == 'nouveau' ? 1 : 0,
            'page': 1,
            'page_size': 12,
            'has_next': false,
            'results': q == 'nouveau'
                ? [
                    _item(
                      'Nouvelle possibilité',
                      '11111111-1111-4111-8111-111111111111',
                    ),
                  ]
                : <Object>[],
          },
        }),
        200,
      );
    });
    final router = _router(
      _guestRuntime(SessionRecoveryController(), client: client),
    );
    await _pump(tester, router);
    router.go('/discover');
    await tester.pumpAndSettle();

    final input = find.byKey(const Key('guest-search-query'));
    await tester.enterText(input, 'ancien');
    await tester.pump(const Duration(milliseconds: 360));
    await tester.enterText(input, 'nouveau');
    await tester.pump(const Duration(milliseconds: 360));
    await tester.pumpAndSettle();
    expect(find.text('Nouvelle possibilité'), findsOneWidget);

    previous.complete(
      MockResponse(
        _mockResponseJson({
          'data': {
            'count': 1,
            'page': 1,
            'page_size': 12,
            'has_next': false,
            'results': [
              _item(
                'Ancienne possibilité',
                '22222222-2222-4222-8222-222222222222',
              ),
            ],
          },
        }),
        200,
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Nouvelle possibilité'), findsOneWidget);
    expect(find.text('Ancienne possibilité'), findsNothing);
  });

  testWidgets('public Discovery paginates on the server', (tester) async {
    final seenPages = <String>[];
    final client = MockClient((request) async {
      seenPages.add(request.url.queryParameters['page'] ?? '');
      final page = int.parse(request.url.queryParameters['page'] ?? '1');
      return MockResponse(
        _mockResponseJson({
          'data': {
            'count': 24,
            'page': page,
            'page_size': 12,
            'has_next': page == 1,
            'results': [
              _item(
                'Page $page',
                page == 1
                    ? '11111111-1111-4111-8111-111111111111'
                    : '22222222-2222-4222-8222-222222222222',
              ),
            ],
          },
        }),
        200,
      );
    });
    final router = _router(
      _guestRuntime(SessionRecoveryController(), client: client),
    );
    await _pump(tester, router);
    router.go('/discover');
    await tester.pumpAndSettle();

    expect(find.text('Page 1'), findsWidgets);
    expect(find.text('Suivant'), findsNothing);
    await tester.drag(
      find.byKey(const Key('guest-public-landing')),
      const Offset(0, -800),
    );
    await tester.pumpAndSettle();

    expect(seenPages, contains('2'));
    expect(find.text('Page 1'), findsWidgets);
    expect(find.text('Page 2'), findsWidgets);
  });

  testWidgets('guest opens public possibility detail without authentication', (
    tester,
  ) async {
    final client = MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      expect(
        request.url.path,
        '/api/v1/discovery/items/activity/11111111-1111-4111-8111-111111111111/',
      );
      return MockResponse(
        _mockResponseJson({
          'data': {
            'item': {
              ..._item(
                'Voyage Lubumbashi–Kolwezi',
                '11111111-1111-4111-8111-111111111111',
              ),
              'detail': {'description': 'Voyage public confirmé.'},
              'engagement': {
                'presentation': {
                  'enabled': true,
                  'label': 'Voir l’événement',
                  'web': '/activities/11111111-1111-4111-8111-111111111111/',
                },
              },
              'links': {
                'web': '/activities/11111111-1111-4111-8111-111111111111/',
              },
            },
          },
        }),
        200,
      );
    });
    final router = _router(
      _guestRuntime(SessionRecoveryController(), client: client),
    );
    await _pump(tester, router);
    router.go('/discover/items/activity/11111111-1111-4111-8111-111111111111');
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('guest-possibility-detail')), findsOneWidget);
    expect(find.text('Voyage Lubumbashi–Kolwezi'), findsOneWidget);
    expect(find.textContaining('Voyage public confirmé.'), findsOneWidget);
    expect(find.text('Voir l’événement'), findsNothing);
    expect(find.text('Voir la page publique'), findsNothing);
    expect(find.byKey(const Key('discover-save-n2')), findsOneWidget);
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets('guest N2 opens publicly browsable ticket offers before login', (
    tester,
  ) async {
    const id = '11111111-1111-4111-8111-111111111111';
    final recovery = SessionRecoveryController();
    final client = MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      if (request.url.path != '/api/v1/discovery/items/activity/$id/') {
        return const MockResponse('{"detail":"Unavailable"}', 404);
      }
      return MockResponse(
        _mockResponseJson({
          'data': {
            'item': {
              ..._item('Concert public', id),
              'engagement': {
                'owner': 'events',
                'state': 'owner_api',
                'resource': {'kind': 'event', 'id': id},
                'capabilities': ['inspect_offers'],
                'links': {'native': '/events/$id/tickets'},
                'primary_action': {
                  'code': 'inspect_offers',
                  'label': 'Voir les billets',
                  'destination': {
                    'kind': 'native',
                    'path': '/events/$id/tickets',
                  },
                },
              },
            },
          },
        }),
        200,
      );
    });
    final router = _router(_guestRuntime(recovery, client: client));
    await _pump(tester, router);
    router.go('/discover/items/activity/$id');
    await tester.pumpAndSettle();

    final action = find.byKey(const Key('discover-primary-n2'));
    expect(action, findsOneWidget);
    await tester.ensureVisible(action);
    await tester.tap(action);
    await tester.pumpAndSettle();

    expect(find.byType(DiscoveryEventTicketsScreen), findsOneWidget);
    expect(find.byType(LoginScreen), findsNothing);
    expect(recovery.awaitingAuthentication, isFalse);
  });

  testWidgets('guest N2 keeps a protected Service start after login', (
    tester,
  ) async {
    const id = '11111111-1111-4111-8111-111111111111';
    final recovery = SessionRecoveryController();
    final client = MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      expect(request.url.path, '/api/v1/discovery/items/service_activity/$id/');
      return MockResponse(
        _mockResponseJson({
          'data': {
            'item': {
              ..._item('Service public', id),
              'identity': {
                'family': 'service_activity',
                'candidate_key': 'service_activity:$id',
                'resource': {'kind': 'activity', 'id': id},
              },
              'engagement': {
                'owner': 'services',
                'state': 'owner_api',
                'resource': {'kind': 'service', 'id': id},
                'capabilities': ['start_after_auth'],
                'presentation': {
                  'capability': 'start',
                  'enabled': false,
                  'requires_auth': true,
                },
                'primary_action': {
                  'code': 'start',
                  'label': 'Commencer',
                  'destination': {
                    'kind': 'native',
                    'path': '/services/$id/start',
                  },
                },
              },
            },
          },
        }),
        200,
      );
    });
    final router = _router(_guestRuntime(recovery, client: client));
    await _pump(tester, router);
    router.go('/discover/items/service_activity/$id');
    await tester.pumpAndSettle();
    final action = find.byKey(const Key('discover-primary-n2'));
    expect(action, findsOneWidget);
    await tester.ensureVisible(action);
    await tester.tap(action);
    await tester.pumpAndSettle();

    expect(recovery.lastUsefulLocation, '/services/$id/start');
    expect(recovery.awaitingAuthentication, isTrue);
    expect(find.byType(LoginScreen), findsOneWidget);
  });

  testWidgets('public Space directory and details stay anonymous', (
    tester,
  ) async {
    final client = MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      if (request.url.path.endsWith('/public-spaces/')) {
        return MockResponse(
          _mockResponseJson({
            'data': {
              'count': 1,
              'page': 1,
              'has_next': false,
              'results': [
                {
                  'name': 'Association Visible',
                  'slug': 'association-visible',
                  'city': 'Lubumbashi',
                  'country': 'RDC',
                },
              ],
            },
          }),
          200,
        );
      }
      expect(
        request.url.path,
        '/api/v1/organizations/public-spaces/association-visible/',
      );
      return MockResponse(
        _mockResponseJson({
          'data': {
            'space': {
              'name': 'Association Visible',
              'slug': 'association-visible',
              'description': 'Une association publique.',
              'archetype': 'generic',
              'city': 'Lubumbashi',
              'country': 'RDC',
            },
            'possibilities': {
              'count': 0,
              'page': 1,
              'has_next': false,
              'results': <Object>[],
            },
          },
        }),
        200,
      );
    });
    final router = _router(
      _guestRuntime(SessionRecoveryController(), client: client),
    );
    await _pump(tester, router);
    router.go('/spaces');
    await tester.pumpAndSettle();
    expect(find.text('Association Visible'), findsOneWidget);

    router.go('/spaces/association-visible');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('guest-public-space-detail')), findsOneWidget);
    expect(find.text('Une association publique.'), findsOneWidget);
    expect(find.text('Espace générique'), findsOneWidget);
    expect(find.text('generic'), findsNothing);
    expect(find.text('Lubumbashi · RDC'), findsOneWidget);
    expect(find.text('À propos'), findsOneWidget);
    expect(find.text('Site officiel'), findsNothing);
    expect(find.text('Ce que propose cet Espace'), findsOneWidget);
    expect(
      find.text('Cet Espace ne propose pas encore de possibilité publique.'),
      findsOneWidget,
    );
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets(
    'public Space keeps its identity separate from opportunity place',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(360, 800));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      const id = '11111111-1111-4111-8111-111111111111';
      const title = 'Clinique CV & candidature Kinshasa — 069';
      final client = MockClient((request) async {
        if (request.url.path.endsWith('/public-spaces/agri/')) {
          return MockResponse(
            _mockResponseJson({
              'data': {
                'space': {
                  'name': 'AgriFuture Cooperative',
                  'slug': 'agri',
                  'archetype': 'generic',
                  'city': 'Yaoundé',
                  'country': 'CM',
                },
                'possibilities': {
                  'count': 2,
                  'page': 1,
                  'page_size': 12,
                  'has_next': false,
                  'results': [
                    {
                      ..._item(title, id),
                      'place': {'name': 'Kinshasa', 'locality': 'Kinshasa'},
                    },
                    _item(
                      'Clinique CV & candidature Kinshasa — 189',
                      '22222222-2222-4222-8222-222222222222',
                    ),
                  ],
                },
              },
            }),
            200,
          );
        }
        expect(request.url.path, '/api/v1/discovery/items/activity/$id/');
        return MockResponse(
          _mockResponseJson({
            'data': {
              'item': {
                ..._item(title, id),
                'detail': {'description': 'Détail public.'},
              },
            },
          }),
          200,
        );
      });
      final router = _router(
        _guestRuntime(SessionRecoveryController(), client: client),
      );
      await _pump(tester, router);
      router.go('/spaces/agri');
      await tester.pumpAndSettle();

      expect(find.text('Espace générique'), findsOneWidget);
      expect(find.text('Yaoundé · CM'), findsOneWidget);
      expect(find.text('Kinshasa'), findsOneWidget);
      expect(find.text(title), findsOneWidget);
      expect(find.text('2 possibilités'), findsOneWidget);
      expect(find.text('À propos'), findsNothing);
      expect(find.text('Site officiel'), findsNothing);
      await tester.ensureVisible(find.text(title));
      await tester.tap(find.text(title));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('guest-possibility-detail')), findsOneWidget);
      expect(find.text(title), findsOneWidget);
      expect(find.byType(LoginScreen), findsNothing);
    },
  );

  testWidgets('public Spaces search uses its field action and server query', (
    tester,
  ) async {
    final seenQueries = <Uri>[];
    final client = MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      expect(request.url.path, '/api/v1/organizations/public-spaces/');
      seenQueries.add(request.url);
      return MockResponse(
        _mockResponseJson({
          'data': {
            'count': 0,
            'page': 1,
            'has_next': false,
            'categories': [
              {'value': 'community', 'label': 'Association / communauté'},
              {'value': 'creative', 'label': 'Artiste / création'},
            ],
            'results': <Object>[],
          },
        }),
        200,
      );
    });
    final router = _router(
      _guestRuntime(SessionRecoveryController(), client: client),
    );
    await _pump(tester, router);
    router.go('/spaces');
    await tester.pumpAndSettle();

    expect(find.text('Les Espaces sur Makolo'), findsOneWidget);
    expect(
      find.textContaining('Chaque Espace présente une organisation'),
      findsOneWidget,
    );
    await tester.enterText(
      find.byKey(const Key('guest-space-query')),
      'Association Visible',
    );
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('guest-space-search-clear')), findsOneWidget);

    expect(
      seenQueries.any(
        (url) => url.queryParameters['q'] == 'Association Visible',
      ),
      isTrue,
    );
    await tester.tap(find.byKey(const Key('guest-spaces-filter-toggle')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('guest-spaces-city')),
      'Lubumbashi',
    );
    tester.testTextInput.hide();
    await tester.tap(find.byKey(const Key('guest-spaces-category')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Association / communauté').last);
    await tester.pumpAndSettle();
    await tester.pump(const Duration(milliseconds: 600));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('guest-spaces-filter-apply')), findsNothing);
    expect(seenQueries.last.queryParameters['q'], 'Association Visible');
    expect(seenQueries.last.queryParameters['city'], 'Lubumbashi');
    expect(seenQueries.last.queryParameters['category'], 'community');
    await tester.tap(find.byKey(const Key('guest-spaces-reset')));
    await tester.pumpAndSettle();
    expect(seenQueries.last.queryParameters['q'], isNull);
    expect(seenQueries.last.queryParameters['city'], isNull);
    expect(seenQueries.last.queryParameters['category'], isNull);
    expect(find.text('Toutes les catégories'), findsOneWidget);
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets('public Spaces name progressively updates directory', (
    tester,
  ) async {
    final queries = <Uri>[];
    final client = MockClient((request) async {
      queries.add(request.url);
      return MockResponse(
        _mockResponseJson({
          'data': {
            'count': 0,
            'page': 1,
            'has_next': false,
            'categories': <Object>[],
            'results': <Object>[],
          },
        }),
        200,
      );
    });
    final router = _router(
      _guestRuntime(SessionRecoveryController(), client: client),
    );
    await _pump(tester, router);
    router.go('/spaces');
    await tester.pumpAndSettle();
    final input = find.byKey(const Key('guest-space-query'));
    await tester.enterText(input, 'al');
    await tester.pump(const Duration(milliseconds: 100));
    await tester.enterText(input, 'alm');
    await tester.pump(const Duration(milliseconds: 360));
    await tester.pumpAndSettle();
    expect(queries.last.queryParameters['q'], 'alm');
    expect(queries.last.queryParameters['page'], '1');
    await tester.tap(find.byKey(const Key('guest-space-search-clear')));
    await tester.pumpAndSettle();
    expect(queries.last.queryParameters.containsKey('q'), isFalse);
    await tester.enterText(input, 'alm');
    await tester.pump(const Duration(milliseconds: 360));
    await tester.pumpAndSettle();
    await tester.enterText(input, '');
    await tester.pump(const Duration(milliseconds: 360));
    await tester.pumpAndSettle();
    expect(queries.last.queryParameters.containsKey('q'), isFalse);
  });

  testWidgets('directory page failure stops auto-retry and retains page one', (
    tester,
  ) async {
    var pageTwoRequests = 0;
    final client = MockClient((request) async {
      expect(request.url.path, '/api/v1/organizations/public-spaces/');
      final page = request.url.queryParameters['page'] ?? '1';
      if (page == '2') {
        pageTwoRequests++;
        if (pageTwoRequests == 1) {
          return const MockResponse('{"detail":"Unavailable"}', 503);
        }
      }
      return MockResponse(
        _mockResponseJson({
          'data': {
            'count': 22,
            'page': int.parse(page),
            'page_size': 20,
            'has_next': page == '1',
            'categories': <Object>[],
            'results': [
              for (
                var i = page == '1' ? 0 : 20;
                i < (page == '1' ? 20 : 22);
                i++
              )
                {
                  'name': 'Espace $i',
                  'slug': 'space-$i',
                  'city': 'Kolwezi',
                  'country': 'CD',
                },
            ],
          },
        }),
        200,
      );
    });
    final router = _router(
      _guestRuntime(SessionRecoveryController(), client: client),
    );
    await _pump(tester, router);
    router.go('/spaces');
    await tester.pumpAndSettle();
    await tester.drag(
      find.byKey(const Key('guest-public-spaces')),
      const Offset(0, -2400),
    );
    await tester.pumpAndSettle();
    expect(pageTwoRequests, 1);
    await tester.scrollUntilVisible(
      find.byKey(const Key('guest-spaces-page-retry')),
      200,
      scrollable: find
          .descendant(
            of: find.byKey(const Key('guest-public-spaces')),
            matching: find.byType(Scrollable),
          )
          .first,
    );
    await tester.pumpAndSettle();
    expect(
      find.text('Impossible d’actualiser les Espaces publics.'),
      findsOneWidget,
    );
    await tester.drag(
      find.byKey(const Key('guest-public-spaces')),
      const Offset(0, -200),
    );
    await tester.pumpAndSettle();
    expect(pageTwoRequests, 1);

    // The transient refresh SnackBar overlays the bottom of the directory.
    // Dismiss it so the persistent inline retry is genuinely hit-testable.
    ScaffoldMessenger.of(
      tester.element(find.byKey(const Key('guest-spaces-page-retry'))),
    ).removeCurrentSnackBar();
    await tester.pumpAndSettle();
    await tester.ensureVisible(
      find.byKey(const Key('guest-spaces-page-retry')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('guest-spaces-page-retry')));
    await tester.pumpAndSettle();
    expect(pageTwoRequests, 2);
    expect(
      find.text('Impossible d’actualiser les Espaces publics.'),
      findsNothing,
    );
  });

  testWidgets('empty public contract stays calm without invented cards', (
    tester,
  ) async {
    final client = MockClient(
      (request) async => MockResponse(
        _mockResponseJson({
          'data': {
            'count': 0,
            'page': 1,
            'page_size': 12,
            'has_next': false,
            'results': <Object>[],
          },
        }),
        200,
      ),
    );
    final router = _router(
      _guestRuntime(SessionRecoveryController(), client: client),
    );
    await _pump(tester, router);
    router.go('/discover');
    await tester.pumpAndSettle();

    expect(
      find.text('Aucune possibilité publique à afficher pour cette recherche.'),
      findsOneWidget,
    );
  });

  testWidgets(
    'personal guest destination asks for auth without personal shell',
    (tester) async {
      final recovery = SessionRecoveryController();
      final router = _router(_guestRuntime(recovery));
      await _pump(tester, router);

      router.go('/ongoing');
      await tester.pumpAndSettle();

      expect(find.byType(LoginScreen), findsOneWidget);
      expect(
        find.text('Connectez-vous pour poursuivre votre action.'),
        findsOneWidget,
      );
      expect(find.text('Now'), findsNothing);
      expect(find.text('En cours'), findsNothing);
      expect(find.byTooltip('Avatar'), findsNothing);
      expect(recovery.lastUsefulLocation, '/ongoing');
    },
  );

  testWidgets('login and create-account remain explicit public destinations', (
    tester,
  ) async {
    final router = _router(_guestRuntime(SessionRecoveryController()));
    await _pump(tester, router);

    router.go('/login');
    await tester.pumpAndSettle();
    expect(find.byType(LoginScreen), findsOneWidget);

    router.go('/create-account');
    await tester.pumpAndSettle();
    expect(find.byType(SignupScreen), findsOneWidget);
  });

  testWidgets('protected deep destination is preserved for post-auth resume', (
    tester,
  ) async {
    final recovery = SessionRecoveryController();
    final router = _router(_guestRuntime(recovery));
    await _pump(tester, router);

    router.go('/journeys/journey-1');
    await tester.pumpAndSettle();

    expect(find.byType(LoginScreen), findsOneWidget);
    expect(
      find.text('Connectez-vous pour poursuivre votre action.'),
      findsOneWidget,
    );
    expect(find.text('Now'), findsNothing);
    expect(find.text('En cours'), findsNothing);
    expect(find.byTooltip('Avatar'), findsNothing);
    expect(recovery.lastUsefulLocation, '/journeys/journey-1');
    expect(recovery.awaitingAuthentication, isTrue);
  });
}
