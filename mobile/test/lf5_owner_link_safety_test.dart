import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/resources/resource_repository.dart';
import 'package:makolo_mobile/features/access/access_repository.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

class _NeverNetworkApi implements MakoloApiClient {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  const version = '12345678-1234-1234-1234-123456789abc';

  test('resource bytes and reuse only accept same-origin owner actions', () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final repo = ResourceRepository(
      database: db,
      store: ProfileStore(db, 'profile-a'),
      profileId: 'profile-a',
      api: _NeverNetworkApi(),
    );
    for (final path in [
      'https://external.invalid/api/v1/me/resources/versions/$version/download/',
      'https:/api/v1/me/resources/versions/$version/download/',
      '//external.invalid/api/v1/me/resources/versions/$version/download/',
      '/api/v1/me/resources/versions/$version/download/?redirect=1',
      '/api/v1/me/resources/versions/$version/reuse/',
    ]) {
      await expectLater(
        repo.downloadVersion(
          path: path,
          destinationPath: '/unused/never-created',
        ),
        throwsFormatException,
      );
    }
    await expectLater(
      repo.reuseVersion(
        path: '/api/v1/me/resources/versions/$version/download/',
        journeyId: 'journey-known',
      ),
      throwsFormatException,
    );
  });

  test('credential links reject a forged URL with a scheme', () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final repo = AccessRepository(
      database: db,
      store: ProfileStore(db, 'profile-a'),
      profileId: 'profile-a',
      api: _NeverNetworkApi(),
    );
    await expectLater(
      repo.fetchCredential(
        accessId: 'access-1',
        path: 'https:/api/v1/me/accesses/access-1/credential/',
      ),
      throwsFormatException,
    );
  });
}
