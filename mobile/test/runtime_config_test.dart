import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/environment.dart';

void main() {
  group('MakoloRuntimeConfig', () {
    test('defaults to a disabled DEV configuration', () {
      final config = MakoloRuntimeConfig.fromValues(const {});

      expect(config.environment, MakoloRuntimeEnvironment.dev);
      expect(config.api.baseUri, isNull);
      expect(config.maps.enabled, isFalse);
      expect(config.firebase.enabled, isFalse);
      expect(config.sentry.enabled, isFalse);
      expect(config.appLinks.enabled, isFalse);
      expect(config.location.backgroundCapabilityEnabled, isFalse);
    });

    test('normalizes an API base URL', () {
      final config = MakoloRuntimeConfig.fromValues(const {
        'MAKOLO_API_BASE_URL': 'https://example.test/api',
      });

      expect(config.api.baseUri, Uri.parse('https://example.test/api/'));
    });

    test('rejects a non-http API URL', () {
      expect(
        () => MakoloRuntimeConfig.fromValues(const {
          'MAKOLO_API_BASE_URL': 'file:///tmp/makolo',
        }),
        throwsA(isA<MakoloConfigurationException>()),
      );
    });

    test('requires a map style when maps are enabled', () {
      expect(
        () => MakoloRuntimeConfig.fromValues(const {
          'MAKOLO_MAPS_ENABLED': 'true',
        }),
        throwsA(
          isA<MakoloConfigurationException>().having(
            (error) => error.message,
            'message',
            contains('MAKOLO_MAP_STYLE'),
          ),
        ),
      );
    });

    test('requires a DSN when Sentry is enabled', () {
      expect(
        () => MakoloRuntimeConfig.fromValues(const {
          'MAKOLO_SENTRY_ENABLED': 'true',
        }),
        throwsA(
          isA<MakoloConfigurationException>().having(
            (error) => error.message,
            'message',
            contains('MAKOLO_SENTRY_DSN'),
          ),
        ),
      );
    });

    test('requires App Links scheme and host when enabled', () {
      expect(
        () => MakoloRuntimeConfig.fromValues(const {
          'MAKOLO_APP_LINKS_ENABLED': 'true',
        }),
        throwsA(isA<MakoloConfigurationException>()),
      );
    });

    test('does not invent a production API', () {
      expect(
        () => MakoloRuntimeConfig.fromValues(const {
          'MAKOLO_ENVIRONMENT': 'prod',
        }),
        throwsA(
          isA<MakoloConfigurationException>().having(
            (error) => error.message,
            'message',
            contains('no production URL is inferred'),
          ),
        ),
      );
    });

    test('beta also requires an explicit API base URL', () {
      expect(
        () => MakoloRuntimeConfig.fromValues(const {
          'MAKOLO_ENVIRONMENT': 'beta',
        }),
        throwsA(isA<MakoloConfigurationException>()),
      );
    });

    test('prod requires https API base URL', () {
      expect(
        () => MakoloRuntimeConfig.fromValues(const {
          'MAKOLO_ENVIRONMENT': 'prod',
          'MAKOLO_API_BASE_URL': 'http://prod.example.test',
        }),
        throwsA(isA<MakoloConfigurationException>()),
      );
    });

    test('accepts explicit independent capabilities', () {
      final config = MakoloRuntimeConfig.fromValues(const {
        'MAKOLO_ENVIRONMENT': 'beta',
        'MAKOLO_API_BASE_URL': 'https://beta.example.test',
        'MAKOLO_RELEASE': '0.1.0+42',
        'MAKOLO_MAPS_ENABLED': 'true',
        'MAKOLO_MAP_STYLE': 'asset://map-style.json',
        'MAKOLO_FIREBASE_ENABLED': 'true',
        'MAKOLO_SENTRY_ENABLED': 'true',
        'MAKOLO_SENTRY_DSN': 'https://public@example.test/1',
        'MAKOLO_APP_LINKS_ENABLED': 'true',
        'MAKOLO_APP_LINKS_SCHEME': 'https',
        'MAKOLO_APP_LINKS_HOST': 'links.example.test',
        'MAKOLO_BACKGROUND_LOCATION_ENABLED': 'true',
      });

      expect(config.environment, MakoloRuntimeEnvironment.beta);
      expect(config.maps.style, 'asset://map-style.json');
      expect(config.firebase.enabled, isTrue);
      expect(config.sentry.dsn, 'https://public@example.test/1');
      expect(config.sentry.release, '0.1.0+42');
      expect(config.appLinks.host, 'links.example.test');
      expect(config.location.backgroundCapabilityEnabled, isTrue);
    });
  });
}
