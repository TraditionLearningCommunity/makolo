import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/platform/location/geo_search_gateway.dart';

import 'dio_testing.dart';

void main() {
  test('blank query returns no suggestions without a network call', () async {
    var calls = 0;
    final gateway = MapTilerGeoSearchGateway(
      apiKey: 'test-only',
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

  test('missing provider configuration is rejected', () {
    expect(() => MapTilerGeoSearchGateway(apiKey: ''), throwsArgumentError);
  });
}
