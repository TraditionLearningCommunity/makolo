import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/presentation/mps/mps_models.dart';
import 'package:makolo_mobile/presentation/mps/mps_repository.dart';

void main() {
  test('separate cached template and theme build one MPS package', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-1');
    final repository = MpsPresentationRepository(
      store: store,
      profileId: 'profile-1',
    );

    await store.putProjection(
      kind: mpsArtifactProjectionKind,
      resourceKey: repository.accessArtifactKey('access-1'),
      schemaVersion: 1,
      payload: const {
        'identity': {
          'kind': 'mps_artifact',
          'resource_key': 'access:access-1:access_pass',
        },
        'purpose': 'access_pass',
        'renderer': {
          'contract': 'mps.native.v1',
          'schema_version': 1,
          'minimum_renderer_version': 1,
        },
        'template': {'resource_key': '12', 'builtin': false},
        'theme': {'resource_key': '7', 'builtin': false},
        'context': {
          'activity': {'display_title': 'Activity'},
        },
        'capabilities': <String>[],
        'links': <String, String>{},
      },
    );
    await store.putProjection(
      kind: mpsTemplateProjectionKind,
      resourceKey: '12',
      schemaVersion: 1,
      payload: const {
        'manifest': {
          'schema_version': 1,
          'layout': {
            'component': 'Heading',
            'props': {
              'value': {'binding': 'activity.display_title'},
            },
          },
        },
      },
    );
    await store.putProjection(
      kind: mpsThemeProjectionKind,
      resourceKey: '7',
      schemaVersion: 1,
      payload: const {
        'tokens': {'accent': '#5232DB'},
      },
    );

    final value = await repository.readAccessPackage('access-1');
    expect(value, isNotNull);
    expect(value!.usedFallback, isFalse);
    expect(value.themeTokens['accent'], '#5232DB');
  });

  test('missing custom definitions degrade locally without losing artifact context', () async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-1');
    final repository = MpsPresentationRepository(
      store: store,
      profileId: 'profile-1',
    );

    await store.putProjection(
      kind: mpsArtifactProjectionKind,
      resourceKey: repository.activityArtifactKey('activity-1', 'invitation'),
      schemaVersion: 1,
      payload: const {
        'identity': {
          'kind': 'mps_artifact',
          'resource_key': 'activity:activity-1:invitation',
        },
        'purpose': 'invitation',
        'renderer': {
          'contract': 'mps.native.v1',
          'schema_version': 1,
          'minimum_renderer_version': 1,
        },
        'template': {'resource_key': '99', 'builtin': false},
        'theme': {'resource_key': '88', 'builtin': false},
        'context': {
          'activity': {'display_title': 'Offline Activity'},
        },
        'capabilities': <String>[],
        'links': <String, String>{},
      },
    );

    final value = await repository.readActivityPackage(
      'activity-1',
      'invitation',
    );
    expect(value, isNotNull);
    expect(value!.usedFallback, isTrue);
    expect(value.artifact.context['activity'], isNotNull);
    expect(value.manifest, mpsEssentialManifest);
  });
}
