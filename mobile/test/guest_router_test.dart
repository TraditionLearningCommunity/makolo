import 'dart:convert';

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
}) {
  final tokens = MemoryTokenStore();
  return AppRuntime(
    tokens: tokens,
    session: null,
    recovery: recovery,
    launchPreferences: _MemoryLaunchPreferences(),
    interactions: ResumableInteractionStore.memory(),
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
    'resource': {'id': id},
  },
  'representation': {
    'title': title,
    'summary': 'Description publique.',
    'eyebrow': 'Voyager',
  },
  'capabilities': ['view'],
  'links': {'detail': '/api/v1/discovery/items/activity/$id/'},
};

void main() {
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
        jsonEncode({
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
          jsonEncode({
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
      tester.testTextInput.hide();
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('guest-discover-search-submit')),
        findsOneWidget,
      );
      await tester.tap(find.byKey(const Key('guest-discover-search-submit')));
      await tester.pumpAndSettle();

      expect(seenQueries, contains('023'));
      expect(find.text('Accompagnement bourses Accra — 023'), findsOneWidget);
      expect(find.text('Atelier numérique Lubumbashi'), findsNothing);
    },
  );

  testWidgets('public Discover text searches progressively without submission', (
    tester,
  ) async {
    final queries = <Uri>[];
    final client = MockClient((request) async {
      queries.add(request.url);
      return MockResponse(
        jsonEncode({
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
  });

  testWidgets('public Discover filters preserve supported server criteria', (
    tester,
  ) async {
    final requests = <Uri>[];
    final client = MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      expect(request.url.path, '/api/v1/discovery/items/');
      requests.add(request.url);
      return MockResponse(
        jsonEncode({
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
          jsonEncode({
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
            jsonEncode({
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
          jsonEncode({
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

  testWidgets('public Discovery paginates on the server', (tester) async {
    final seenPages = <String>[];
    final client = MockClient((request) async {
      seenPages.add(request.url.queryParameters['page'] ?? '');
      final page = int.parse(request.url.queryParameters['page'] ?? '1');
      return MockResponse(
        jsonEncode({
          'data': {
            'count': 24,
            'page': page,
            'page_size': 12,
            'has_next': page == 1,
            'results': [
              _item('Page $page', '11111111-1111-4111-8111-111111111111'),
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
    await tester.scrollUntilVisible(
      find.text('Suivant'),
      200,
      scrollable: find
          .descendant(
            of: find.byKey(const Key('guest-public-landing')),
            matching: find.byType(Scrollable),
          )
          .first,
    );
    await tester.tap(find.text('Suivant'));
    await tester.pumpAndSettle();

    expect(seenPages, contains('2'));
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
        jsonEncode({
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
    expect(find.text('Voyage public confirmé.'), findsOneWidget);
    expect(find.text('Voir l’événement'), findsNothing);
    expect(find.text('Voir la page publique'), findsNothing);
    expect(find.byKey(const Key('guest-save-signin')), findsOneWidget);
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets('public Space directory and details stay anonymous', (
    tester,
  ) async {
    final client = MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      if (request.url.path.endsWith('/public-spaces/')) {
        return MockResponse(
          jsonEncode({
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
        jsonEncode({
          'data': {
            'space': {
              'name': 'Association Visible',
              'slug': 'association-visible',
              'description': 'Une association publique.',
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
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets('public Spaces search uses its field action and server query', (
    tester,
  ) async {
    final seenQueries = <Uri>[];
    final client = MockClient((request) async {
      expect(request.headers.containsKey('Authorization'), isFalse);
      expect(request.url.path, '/api/v1/organizations/public-spaces/');
      seenQueries.add(request.url);
      return MockResponse(
        jsonEncode({
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
    await tester.tap(find.byKey(const Key('guest-space-search-submit')));
    await tester.pumpAndSettle();

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
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets('public Spaces name progressively updates directory', (
    tester,
  ) async {
    final queries = <Uri>[];
    final client = MockClient((request) async {
      queries.add(request.url);
      return MockResponse(
        jsonEncode({
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
    await tester.enterText(input, '');
    await tester.pump(const Duration(milliseconds: 360));
    await tester.pumpAndSettle();
    expect(queries.last.queryParameters.containsKey('q'), isFalse);
  });

  testWidgets('empty public contract stays calm without invented cards', (
    tester,
  ) async {
    final client = MockClient(
      (request) async => MockResponse(
        jsonEncode({
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
