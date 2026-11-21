import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/location/geo_search_gateway.dart';
import 'package:makolo_mobile/platform/location/geo_search_gateway_factory.dart';

import 'dio_testing.dart';

void main() {
  test('blank query returns no suggestions without a network call', () async {
    var calls = 0;
    final gateway = MapTilerGeoSearchGateway(
      apiKey: 'test-only',
      endpoint: Uri.parse('https://geo.example.test/geocoding/'),
      dio: MockClient((_) async {
        calls++;
        return const MockResponse('{}', 200);
      }).dio,
    );
    expect(await gateway.suggest('   '), isEmpty);
    expect(calls, 0);
  });

  test('MapTiler adapter parses valid suggestions and sends no GPS', () async {
    final gateway = MapTilerGeoSearchGateway(
      apiKey: 'test-only',
      endpoint: Uri.parse('https://geo.example.test/geocoding/'),
      dio: MockClient((request) async {
        expect(request.url.scheme, 'https');
        expect(request.url.path, '/geocoding/Ko.json');
        expect(request.url.queryParameters['autocomplete'], 'true');
        expect(request.url.queryParameters['language'], 'fr');
        expect(request.url.queryParameters['limit'], '5');
        expect(request.url.queryParameters.containsKey('proximity'), false);
        return MockResponse(
          jsonEncode({
            'features': [
              {
                'id': 'place.1',
                'place_name': 'Kolwezi, Lualaba, RD Congo',
                'center': [25.47, -10.72],
                'place_type': ['place'],
              },
              {
                'id': 'invalid',
                'place_name': 'Missing coordinates',
                'center': [],
              },
            ],
          }),
          200,
        );
      }).dio,
    );
    final results = await gateway.suggest('Ko');
    expect(results, hasLength(1));
    expect(results.single.label, 'Kolwezi, Lualaba, RD Congo');
    expect(results.single.source, 'maptiler');
    expect(results.single.latitude, -10.72);
    expect(results.single.longitude, 25.47);
  });

  test(
    'malformed payload is surfaced instead of inventing locations',
    () async {
      final gateway = MapTilerGeoSearchGateway(
        apiKey: 'test-only',
        endpoint: Uri.parse('https://geo.example.test/geocoding/'),
        dio: MockClient((_) async => const MockResponse('{"bad":[]}', 200)).dio,
      );
      await expectLater(
        gateway.suggest('Kol'),
        throwsA(isA<GeoSearchException>()),
      );
    },
  );

  test('request cancellation is preserved for the caller', () async {
    final requestStarted = Completer<void>();
    final release = Completer<MockResponse>();
    final gateway = MapTilerGeoSearchGateway(
      apiKey: 'test-only',
      endpoint: Uri.parse('https://geo.example.test/geocoding/'),
      dio: MockClient((_) {
        requestStarted.complete();
        return release.future;
      }).dio,
    );
    final cancellation = GeoSearchCancellation();
    final future = gateway.suggest('Kol', cancelToken: cancellation);
    await requestStarted.future;
    cancellation.cancel();
    await expectLater(future, throwsA(isA<DioException>()));
    release.complete(const MockResponse('{"features":[]}', 200));
  });

  test('Google Maps adapter parses geocoding results', () async {
    final gateway = GoogleMapsGeoSearchGateway(
      apiKey: 'test-only',
      endpoint: Uri.parse('https://geo.example.test/maps/api/geocode/json'),
      dio: MockClient((request) async {
        expect(request.url.scheme, 'https');
        expect(request.url.path, '/maps/api/geocode/json');
        expect(request.url.queryParameters['address'], 'Kinshasa');
        expect(request.url.queryParameters['language'], 'fr');
        expect(request.url.queryParameters['key'], 'test-only');
        return MockResponse(
          jsonEncode({
            'status': 'OK',
            'results': [
              {
                'place_id': 'google-place-1',
                'formatted_address': 'Kinshasa, RDC',
                'geometry': {
                  'location': {'lat': -4.32, 'lng': 15.31},
                },
                'types': ['locality'],
              },
            ],
          }),
          200,
        );
      }).dio,
    );
    final results = await gateway.suggest('Kinshasa');
    expect(results, hasLength(1));
    expect(results.single.source, 'google_maps');
    expect(results.single.latitude, -4.32);
    expect(results.single.longitude, 15.31);
  });

  test('Google Maps ZERO_RESULTS is an empty result, not an error', () async {
    final gateway = GoogleMapsGeoSearchGateway(
      apiKey: 'test-only',
      endpoint: Uri.parse('https://geo.example.test/maps/api/geocode/json'),
      dio: MockClient(
        (_) async =>
            const MockResponse('{"status":"ZERO_RESULTS","results":[]}', 200),
      ).dio,
    );
    expect(await gateway.suggest('unknown place'), isEmpty);
  });

  test('provider factory selects the configured adapter', () {
    final mapTiler = createGeoSearchGateway(
      enabled: true,
      provider: 'maptiler',
      apiKey: 'test-only',
      endpoint: Uri.parse('https://geo.example.test/geocoding/'),
    );
    final google = createGeoSearchGateway(
      enabled: true,
      provider: 'google_maps',
      apiKey: 'test-only',
      endpoint: Uri.parse('https://geo.example.test/maps/api/geocode/json'),
    );
    expect(mapTiler, isA<MapTilerGeoSearchGateway>());
    expect(google, isA<GoogleMapsGeoSearchGateway>());
    expect(
      createGeoSearchGateway(
        enabled: false,
        provider: 'unsupported',
        apiKey: null,
      ),
      isNull,
    );
  });

  test('missing provider configuration is rejected', () {
    expect(
      () => MapTilerGeoSearchGateway(
        apiKey: '',
        endpoint: Uri.parse('https://geo.example.test/geocoding/'),
      ),
      throwsArgumentError,
    );
  });
}
