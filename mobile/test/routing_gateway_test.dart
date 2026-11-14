import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/environment.dart';
import 'package:makolo_mobile/platform/routing/open_route_service_gateway.dart';
import 'package:makolo_mobile/platform/routing/routing_gateway.dart';
import 'package:makolo_mobile/platform/routing/routing_gateway_factory.dart';

import 'dio_testing.dart';

void main() {
  test('RoutingGateway remains disabled without approved configuration', () {
    expect(createRoutingGateway(enabled: false), isNull);
    expect(
      MakoloRuntimeConfig.fromValues(const {'MAKOLO_ENVIRONMENT': 'dev'})
          .routing
          .enabled,
      isFalse,
    );
  });

  test('enabled gateway requires an explicit provider credential', () {
    expect(() => createRoutingGateway(enabled: true), throwsArgumentError);
    expect(
      () => createRoutingGateway(
        enabled: true,
        provider: 'unknown',
        apiKey: 'test-only',
      ),
      throwsArgumentError,
    );
    expect(
      () => OpenRouteServiceGateway(
        apiKey: 'test-only',
        endpoint: Uri.parse('http://invalid.test/v2/directions'),
      ),
      throwsArgumentError,
    );
  });

  test('HeiGIT route returns verified GeoJSON geometry and summary', () async {
    final gateway = createRoutingGateway(
      enabled: true,
      apiKey: 'test-only',
      dio: MockClient((request) async {
        expect(
          request.url.path,
          '/openrouteservice/v2/directions/foot-walking/geojson',
        );
        expect(request.url.host, 'api.heigit.org');
        expect(request.headers['Authorization'], 'test-only');
        expect((request.data as Map)['coordinates'], [
          [27.48, -11.66],
          [27.50, -11.67],
        ]);
        return MockResponse(
          jsonEncode({
            'type': 'FeatureCollection',
            'features': [
              {
                'type': 'Feature',
                'properties': {
                  'summary': {'distance': 3450.5, 'duration': 2470.0},
                },
                'geometry': {
                  'type': 'LineString',
                  'coordinates': [
                    [27.48, -11.66],
                    [27.49, -11.665],
                    [27.50, -11.67],
                  ],
                },
              },
            ],
          }),
          200,
        );
      }).dio,
    )!;
    final path = await gateway.directions(
      const RoutingPoint(-11.66, 27.48),
      const RoutingPoint(-11.67, 27.50),
    );
    expect(path.mode, RoutingMode.walking);
    expect(path.distanceMeters, 3450.5);
    expect(path.durationSeconds, 2470.0);
    expect(path.points, hasLength(3));
    expect(path.points[1].latitude, -11.665);
    expect(path.points[1].longitude, 27.49);
  });

  test('no route request can be made with invalid coordinates', () async {
    var calls = 0;
    final gateway = OpenRouteServiceGateway(
      apiKey: 'test-only',
      dio: MockClient((request) async {
        calls++;
        return const MockResponse('{}', 200);
      }).dio,
    );
    await expectLater(
      gateway.directions(
        const RoutingPoint(91, 27.48),
        const RoutingPoint(-11.67, 27.50),
      ),
      throwsArgumentError,
    );
    expect(calls, 0);
  });

  test('route provider errors do not leak credentials', () async {
    final gateway = OpenRouteServiceGateway(
      apiKey: 'test-only',
      dio: MockClient((request) async {
        return const MockResponse('{"error":"no route"}', 400);
      }).dio,
    );
    await expectLater(
      gateway.directions(
        const RoutingPoint(-11.66, 27.48),
        const RoutingPoint(-11.67, 27.50),
      ),
      throwsA(
        isA<RoutingUnavailable>().having(
          (error) => error.toString(),
          'safe message',
          isNot(contains('test-only')),
        ),
      ),
    );
  });

  test('malformed provider geometry is rejected, not fabricated', () async {
    final gateway = OpenRouteServiceGateway(
      apiKey: 'test-only',
      dio: MockClient((_) async {
        return const MockResponse(
          '{"features":[{"properties":{"summary":{"distance":3,'
          '"duration":2}},"geometry":{"coordinates":[[999,0],[0,0]]}}]}',
          200,
        );
      }).dio,
    );
    await expectLater(
      gateway.directions(
        const RoutingPoint(-11.66, 27.48),
        const RoutingPoint(-11.67, 27.50),
      ),
      throwsA(isA<RoutingUnavailable>()),
    );
  });
}
