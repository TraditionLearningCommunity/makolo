import '../platform/maps/map_runtime_config.dart';

export '../platform/maps/map_runtime_config.dart';

enum MakoloRuntimeEnvironment {
  dev,
  beta,
  prod;

  static MakoloRuntimeEnvironment parse(String raw) {
    return switch (raw.trim().toLowerCase()) {
      '' || 'dev' => MakoloRuntimeEnvironment.dev,
      'beta' => MakoloRuntimeEnvironment.beta,
      'prod' => MakoloRuntimeEnvironment.prod,
      _ => throw MakoloConfigurationException(
        'MAKOLO_ENVIRONMENT must be one of: dev, beta, prod.',
      ),
    };
  }
}

class MakoloConfigurationException implements Exception {
  const MakoloConfigurationException(this.message);

  final String message;

  @override
  String toString() => 'MakoloConfigurationException: $message';
}

class MakoloApiConfig {
  const MakoloApiConfig({required this.baseUri});

  final Uri? baseUri;
}

class MakoloGeocodingConfig {
  const MakoloGeocodingConfig({
    required this.enabled,
    required this.apiKey,
    this.provider = 'maptiler',
    this.endpoint,
  });

  final bool enabled;
  final String? apiKey;
  final String provider;
  final Uri? endpoint;
}

/// Routing is opt-in. A free provider still requires an approved, limited
/// credential. Never enable an unrestricted server credential in Flutter.
class MakoloRoutingConfig {
  const MakoloRoutingConfig({
    required this.enabled,
    required this.apiKey,
    this.provider = 'openrouteservice',
    this.endpoint,
  });

  final bool enabled;
  final String? apiKey;
  final String provider;
  final Uri? endpoint;
}

class MakoloFirebaseConfig {
  const MakoloFirebaseConfig({required this.enabled});

  final bool enabled;
}

class MakoloSentryConfig {
  const MakoloSentryConfig({
    required this.enabled,
    required this.dsn,
    required this.release,
  });

  final bool enabled;
  final String? dsn;
  final String? release;
}

class MakoloAppLinksConfig {
  const MakoloAppLinksConfig({
    required this.enabled,
    required this.scheme,
    required this.host,
  });

  final bool enabled;
  final String? scheme;
  final String? host;
}

class MakoloLocationRuntimeConfig {
  const MakoloLocationRuntimeConfig({
    required this.backgroundCapabilityEnabled,
  });

  final bool backgroundCapabilityEnabled;
}

class MakoloRuntimeConfig {
  const MakoloRuntimeConfig({
    required this.environment,
    required this.api,
    required this.maps,
    this.geocoding = const MakoloGeocodingConfig(enabled: false, apiKey: null),
    this.routing = const MakoloRoutingConfig(enabled: false, apiKey: null),
    required this.firebase,
    required this.sentry,
    required this.appLinks,
    required this.location,
  });

  static const _environment = String.fromEnvironment(
    'MAKOLO_ENVIRONMENT',
    defaultValue: 'dev',
  );
  static const _apiBaseUrl = String.fromEnvironment('MAKOLO_API_BASE_URL');
  static const _mapsEnabled = String.fromEnvironment(
    'MAKOLO_MAPS_ENABLED',
    defaultValue: 'false',
  );
  static const _mapStyle = String.fromEnvironment('MAKOLO_MAP_STYLE');
  static const _geocodingEnabled = String.fromEnvironment(
    'MAKOLO_GEOCODING_ENABLED',
    defaultValue: 'false',
  );
  static const _geocodingKey = String.fromEnvironment(
    'MAKOLO_GEOCODING_API_KEY',
  );
  static const _geocodingProvider = String.fromEnvironment(
    'MAKOLO_GEOCODING_PROVIDER',
    defaultValue: 'maptiler',
  );
  static const _geocodingEndpoint = String.fromEnvironment(
    'MAKOLO_GEOCODING_ENDPOINT',
  );
  static const _routingEnabled = String.fromEnvironment(
    'MAKOLO_ROUTING_ENABLED',
    defaultValue: 'false',
  );
  static const _routingKey = String.fromEnvironment('MAKOLO_ROUTING_API_KEY');
  static const _routingProvider = String.fromEnvironment(
    'MAKOLO_ROUTING_PROVIDER',
    defaultValue: 'openrouteservice',
  );
  static const _routingEndpoint = String.fromEnvironment(
    'MAKOLO_ROUTING_ENDPOINT',
  );
  static const _firebaseEnabled = String.fromEnvironment(
    'MAKOLO_FIREBASE_ENABLED',
    defaultValue: 'false',
  );
  static const _sentryEnabled = String.fromEnvironment(
    'MAKOLO_SENTRY_ENABLED',
    defaultValue: 'false',
  );
  static const _sentryDsn = String.fromEnvironment('MAKOLO_SENTRY_DSN');
  static const _release = String.fromEnvironment('MAKOLO_RELEASE');
  static const _appLinksEnabled = String.fromEnvironment(
    'MAKOLO_APP_LINKS_ENABLED',
    defaultValue: 'false',
  );
  static const _appLinksScheme = String.fromEnvironment(
    'MAKOLO_APP_LINKS_SCHEME',
  );
  static const _appLinksHost = String.fromEnvironment('MAKOLO_APP_LINKS_HOST');
  static const _backgroundLocationEnabled = String.fromEnvironment(
    'MAKOLO_BACKGROUND_LOCATION_ENABLED',
    defaultValue: 'false',
  );

  final MakoloRuntimeEnvironment environment;
  final MakoloApiConfig api;
  final MakoloMapsConfig maps;
  final MakoloGeocodingConfig geocoding;
  final MakoloRoutingConfig routing;
  final MakoloFirebaseConfig firebase;
  final MakoloSentryConfig sentry;
  final MakoloAppLinksConfig appLinks;
  final MakoloLocationRuntimeConfig location;

  static MakoloRuntimeConfig fromEnvironment() {
    return fromValues(const {
      'MAKOLO_ENVIRONMENT': _environment,
      'MAKOLO_API_BASE_URL': _apiBaseUrl,
      'MAKOLO_MAPS_ENABLED': _mapsEnabled,
      'MAKOLO_MAP_STYLE': _mapStyle,
      'MAKOLO_GEOCODING_ENABLED': _geocodingEnabled,
      'MAKOLO_GEOCODING_API_KEY': _geocodingKey,
      'MAKOLO_GEOCODING_PROVIDER': _geocodingProvider,
      'MAKOLO_GEOCODING_ENDPOINT': _geocodingEndpoint,
      'MAKOLO_ROUTING_ENABLED': _routingEnabled,
      'MAKOLO_ROUTING_API_KEY': _routingKey,
      'MAKOLO_ROUTING_PROVIDER': _routingProvider,
      'MAKOLO_ROUTING_ENDPOINT': _routingEndpoint,
      'MAKOLO_FIREBASE_ENABLED': _firebaseEnabled,
      'MAKOLO_SENTRY_ENABLED': _sentryEnabled,
      'MAKOLO_SENTRY_DSN': _sentryDsn,
      'MAKOLO_RELEASE': _release,
      'MAKOLO_APP_LINKS_ENABLED': _appLinksEnabled,
      'MAKOLO_APP_LINKS_SCHEME': _appLinksScheme,
      'MAKOLO_APP_LINKS_HOST': _appLinksHost,
      'MAKOLO_BACKGROUND_LOCATION_ENABLED': _backgroundLocationEnabled,
    });
  }

  static MakoloRuntimeConfig fromValues(Map<String, String> values) {
    final environment = MakoloRuntimeEnvironment.parse(
      values['MAKOLO_ENVIRONMENT'] ?? 'dev',
    );
    final apiBaseUri = _optionalHttpUri(
      values['MAKOLO_API_BASE_URL'],
      name: 'MAKOLO_API_BASE_URL',
      trailingSlash: true,
    );

    final mapsEnabled = _bool(
      values['MAKOLO_MAPS_ENABLED'],
      name: 'MAKOLO_MAPS_ENABLED',
    );
    final mapStyle = _optional(values['MAKOLO_MAP_STYLE']);
    if (mapsEnabled && mapStyle == null) {
      throw const MakoloConfigurationException(
        'MAKOLO_MAPS_ENABLED=true requires MAKOLO_MAP_STYLE.',
      );
    }

    final geocodingEnabled = _bool(
      values['MAKOLO_GEOCODING_ENABLED'],
      name: 'MAKOLO_GEOCODING_ENABLED',
    );
    final geocodingKey = _optional(values['MAKOLO_GEOCODING_API_KEY']);
    final geocodingProvider =
        (_optional(values['MAKOLO_GEOCODING_PROVIDER']) ?? 'maptiler')
            .toLowerCase();
    if (!const {'maptiler', 'google_maps'}.contains(geocodingProvider)) {
      throw const MakoloConfigurationException(
        'MAKOLO_GEOCODING_PROVIDER must be maptiler or google_maps.',
      );
    }
    final geocodingEndpoint = _optionalHttpUri(
      values['MAKOLO_GEOCODING_ENDPOINT'],
      name: 'MAKOLO_GEOCODING_ENDPOINT',
    );
    if (geocodingEndpoint != null && geocodingEndpoint.scheme != 'https') {
      throw const MakoloConfigurationException(
        'MAKOLO_GEOCODING_ENDPOINT must use https.',
      );
    }
    if (geocodingEnabled && geocodingEndpoint == null) {
      throw const MakoloConfigurationException(
        'MAKOLO_GEOCODING_ENABLED=true requires MAKOLO_GEOCODING_ENDPOINT.',
      );
    }
    if (geocodingEnabled && geocodingKey == null) {
      throw const MakoloConfigurationException(
        'MAKOLO_GEOCODING_ENABLED=true requires MAKOLO_GEOCODING_API_KEY.',
      );
    }

    // No routing service is silently enabled, even in DEV.
    final routingEnabled = _bool(
      values['MAKOLO_ROUTING_ENABLED'],
      name: 'MAKOLO_ROUTING_ENABLED',
    );
    final routingKey = _optional(values['MAKOLO_ROUTING_API_KEY']);
    final routingProvider =
        (_optional(values['MAKOLO_ROUTING_PROVIDER']) ?? 'openrouteservice')
            .toLowerCase();
    final routingEndpoint = _optionalHttpUri(
      values['MAKOLO_ROUTING_ENDPOINT'],
      name: 'MAKOLO_ROUTING_ENDPOINT',
    );
    if (routingEnabled && routingProvider != 'openrouteservice') {
      throw const MakoloConfigurationException(
        'MAKOLO_ROUTING_PROVIDER must be openrouteservice.',
      );
    }
    if (routingEndpoint != null && routingEndpoint.scheme != 'https') {
      throw const MakoloConfigurationException(
        'MAKOLO_ROUTING_ENDPOINT must use https.',
      );
    }
    if (routingEnabled && routingKey == null) {
      throw const MakoloConfigurationException(
        'MAKOLO_ROUTING_ENABLED=true requires MAKOLO_ROUTING_API_KEY.',
      );
    }
    if (routingEnabled && environment != MakoloRuntimeEnvironment.dev) {
      throw const MakoloConfigurationException(
        'Routing requires reviewed credentials before BETA or PROD activation.',
      );
    }

    final firebaseEnabled = _bool(
      values['MAKOLO_FIREBASE_ENABLED'],
      name: 'MAKOLO_FIREBASE_ENABLED',
    );

    final sentryEnabled = _bool(
      values['MAKOLO_SENTRY_ENABLED'],
      name: 'MAKOLO_SENTRY_ENABLED',
    );
    final sentryDsn = _optional(values['MAKOLO_SENTRY_DSN']);
    final release = _optional(values['MAKOLO_RELEASE']);
    if (sentryEnabled && sentryDsn == null) {
      throw const MakoloConfigurationException(
        'MAKOLO_SENTRY_ENABLED=true requires MAKOLO_SENTRY_DSN.',
      );
    }

    final appLinksEnabled = _bool(
      values['MAKOLO_APP_LINKS_ENABLED'],
      name: 'MAKOLO_APP_LINKS_ENABLED',
    );
    final appLinksScheme = _optional(values['MAKOLO_APP_LINKS_SCHEME']);
    final appLinksHost = _optional(values['MAKOLO_APP_LINKS_HOST']);
    if (appLinksEnabled) {
      if (appLinksScheme == null || appLinksHost == null) {
        throw const MakoloConfigurationException(
          'MAKOLO_APP_LINKS_ENABLED=true requires '
          'MAKOLO_APP_LINKS_SCHEME and MAKOLO_APP_LINKS_HOST.',
        );
      }
      if (appLinksScheme != 'https' && appLinksScheme != 'http') {
        throw const MakoloConfigurationException(
          'MAKOLO_APP_LINKS_SCHEME must be http or https.',
        );
      }
      if (appLinksHost.contains('/') || appLinksHost.contains('://')) {
        throw const MakoloConfigurationException(
          'MAKOLO_APP_LINKS_HOST must be a host name, not a URL.',
        );
      }
    }

    final backgroundLocationEnabled = _bool(
      values['MAKOLO_BACKGROUND_LOCATION_ENABLED'],
      name: 'MAKOLO_BACKGROUND_LOCATION_ENABLED',
    );

    if (environment == MakoloRuntimeEnvironment.prod && apiBaseUri == null) {
      throw const MakoloConfigurationException(
        'PROD requires MAKOLO_API_BASE_URL; no production URL is inferred.',
      );
    }
    if (environment == MakoloRuntimeEnvironment.beta && apiBaseUri == null) {
      throw const MakoloConfigurationException(
        'BETA requires MAKOLO_API_BASE_URL; no beta URL is inferred.',
      );
    }
    if (environment == MakoloRuntimeEnvironment.prod &&
        apiBaseUri != null &&
        apiBaseUri.scheme != 'https') {
      throw const MakoloConfigurationException(
        'PROD requires an https MAKOLO_API_BASE_URL.',
      );
    }

    return MakoloRuntimeConfig(
      environment: environment,
      api: MakoloApiConfig(baseUri: apiBaseUri),
      maps: MakoloMapsConfig(enabled: mapsEnabled, style: mapStyle),
      geocoding: MakoloGeocodingConfig(
        enabled: geocodingEnabled,
        apiKey: geocodingKey,
        provider: geocodingProvider,
        endpoint: geocodingEndpoint,
      ),
      routing: MakoloRoutingConfig(
        enabled: routingEnabled,
        apiKey: routingKey,
        provider: routingProvider,
        endpoint: routingEndpoint,
      ),
      firebase: MakoloFirebaseConfig(enabled: firebaseEnabled),
      sentry: MakoloSentryConfig(
        enabled: sentryEnabled,
        dsn: sentryDsn,
        release: release,
      ),
      appLinks: MakoloAppLinksConfig(
        enabled: appLinksEnabled,
        scheme: appLinksScheme,
        host: appLinksHost,
      ),
      location: MakoloLocationRuntimeConfig(
        backgroundCapabilityEnabled: backgroundLocationEnabled,
      ),
    );
  }

  static bool _bool(String? raw, {required String name}) {
    final value = (raw ?? 'false').trim().toLowerCase();
    return switch (value) {
      '' || 'false' => false,
      'true' => true,
      _ => throw MakoloConfigurationException('$name must be true or false.'),
    };
  }

  static String? _optional(String? raw) {
    final value = raw?.trim() ?? '';
    return value.isEmpty ? null : value;
  }

  static Uri? _optionalHttpUri(
    String? raw, {
    required String name,
    bool trailingSlash = false,
  }) {
    final value = _optional(raw);
    if (value == null) return null;
    final uri = Uri.tryParse(value);
    if (uri == null ||
        !uri.hasScheme ||
        (uri.scheme != 'http' && uri.scheme != 'https') ||
        uri.host.isEmpty) {
      throw MakoloConfigurationException(
        '$name must be an absolute http(s) URL.',
      );
    }
    if (!trailingSlash || uri.path.endsWith('/')) return uri;
    return uri.replace(path: '${uri.path}/');
  }
}

class MakoloEnvironment {
  const MakoloEnvironment._();

  static MakoloRuntimeConfig get current {
    return MakoloRuntimeConfig.fromEnvironment();
  }

  static Uri? get apiBaseUri => current.api.baseUri;
}
