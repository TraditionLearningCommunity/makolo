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

class MakoloMapsConfig {
  const MakoloMapsConfig({required this.enabled, required this.style});

  final bool enabled;
  final String? style;
}

class MakoloFirebaseConfig {
  const MakoloFirebaseConfig({required this.enabled});

  final bool enabled;
}

class MakoloSentryConfig {
  const MakoloSentryConfig({required this.enabled, required this.dsn});

  final bool enabled;
  final String? dsn;
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
  static const _firebaseEnabled = String.fromEnvironment(
    'MAKOLO_FIREBASE_ENABLED',
    defaultValue: 'false',
  );
  static const _sentryEnabled = String.fromEnvironment(
    'MAKOLO_SENTRY_ENABLED',
    defaultValue: 'false',
  );
  static const _sentryDsn = String.fromEnvironment('MAKOLO_SENTRY_DSN');
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
      'MAKOLO_FIREBASE_ENABLED': _firebaseEnabled,
      'MAKOLO_SENTRY_ENABLED': _sentryEnabled,
      'MAKOLO_SENTRY_DSN': _sentryDsn,
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

    final firebaseEnabled = _bool(
      values['MAKOLO_FIREBASE_ENABLED'],
      name: 'MAKOLO_FIREBASE_ENABLED',
    );

    final sentryEnabled = _bool(
      values['MAKOLO_SENTRY_ENABLED'],
      name: 'MAKOLO_SENTRY_ENABLED',
    );
    final sentryDsn = _optional(values['MAKOLO_SENTRY_DSN']);
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

    return MakoloRuntimeConfig(
      environment: environment,
      api: MakoloApiConfig(baseUri: apiBaseUri),
      maps: MakoloMapsConfig(enabled: mapsEnabled, style: mapStyle),
      firebase: MakoloFirebaseConfig(enabled: firebaseEnabled),
      sentry: MakoloSentryConfig(enabled: sentryEnabled, dsn: sentryDsn),
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
