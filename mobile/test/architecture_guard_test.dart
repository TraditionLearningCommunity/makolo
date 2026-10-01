import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

const _forbiddenInfrastructurePackages = <String>{
  'camera',
  'connectivity_plus',
  'dio',
  'drift',
  'drift_flutter',
  'file_picker',
  'firebase_core',
  'firebase_messaging',
  'flutter_local_notifications',
  'flutter_secure_storage',
  'geolocator',
  'home_widget',
  'image_picker',
  'local_auth',
  'maplibre_gl',
  'mobile_scanner',
  'path_provider',
  'permission_handler',
  'sentry_flutter',
  'share_plus',
  'url_launcher',
  'workmanager',
};

final _packageImport = RegExp(
  r'''^\s*import\s+['"]package:([^/'"]+)''',
  multiLine: true,
);
final _relativeImport = RegExp(
  r'''^\s*import\s+['"]([^'"]+)['"]\s*;''',
  multiLine: true,
);
final _hardcodedHttpUrl = RegExp(r'''['"]https?://[^'"]+['"]''');

Iterable<File> _featureDartFiles() sync* {
  final root = Directory('lib/features');
  for (final entry in root.listSync(recursive: true, followLinks: false)) {
    if (entry is File && entry.path.endsWith('.dart')) yield entry;
  }
}

bool _isUiBoundary(String path) =>
    path.endsWith('_screen.dart') ||
    path.endsWith('_routes.dart') ||
    path.contains('/presentation/') ||
    path.contains('/widgets/');

bool _isRepositoryStorageImport(String path, String package) =>
    path.endsWith('_repository.dart') &&
    (package == 'drift' || package == 'drift_flutter');

void main() {
  test('features respect Makolo infrastructure and app boundaries', () {
    final violations = <String>[];

    for (final file in _featureDartFiles()) {
      final path = file.path.replaceAll('\\', '/');
      final source = file.readAsStringSync();

      for (final match in _packageImport.allMatches(source)) {
        final package = match.group(1)!;
        if (_forbiddenInfrastructurePackages.contains(package) &&
            !_isRepositoryStorageImport(path, package)) {
          violations.add(
            '$path imports package:$package directly; use the Makolo '
            'repository/platform/runtime boundary instead.',
          );
        }
      }

      for (final match in _relativeImport.allMatches(source)) {
        final imported = match.group(1)!;
        if (imported.endsWith('/app/router.dart') ||
            imported.endsWith('/app/app_shell.dart')) {
          violations.add(
            '$path imports $imported; app composes feature routes, never '
            'the reverse.',
          );
        }
        if (imported.endsWith('/app/environment.dart') ||
            imported.contains('/config/')) {
          violations.add(
            '$path imports runtime configuration directly; consume an '
            'injected repository/service boundary instead.',
          );
        }
        if (_isUiBoundary(path) &&
            (imported.endsWith('/data/local/makolo_database.dart') ||
                imported.contains('/data/local/tables') ||
                imported.contains('/data/local/dao'))) {
          violations.add(
            '$path accesses the local database from UI/navigation code; '
            'use a repository.',
          );
        }
      }

      if (source.contains('String.fromEnvironment') ||
          source.contains('MakoloRuntimeConfig.fromEnvironment')) {
        violations.add(
          '$path reads runtime configuration directly; configuration is '
          'app/runtime-owned.',
        );
      }

      final withoutLineComments = source
          .split('\n')
          .where((line) => !line.trimLeft().startsWith('//'))
          .join('\n');
      if (_hardcodedHttpUrl.hasMatch(withoutLineComments)) {
        violations.add(
          '$path contains a hardcoded HTTP(S) URL in production feature '
          'code; provider/API URLs belong to owner/runtime configuration.',
        );
      }
    }

    final violationDetails = violations.map((value) => ' - $value').join('\n');
    expect(
      violations,
      isEmpty,
      reason: violations.isEmpty
          ? null
          : 'PAR-1D architecture guard violations:\n$violationDetails',
    );
  });
}
