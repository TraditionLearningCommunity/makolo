import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/access/access_credential_screen.dart';
import 'package:makolo_mobile/features/access/access_credential_vault.dart';
import 'package:makolo_mobile/features/access/access_repository.dart';
import 'package:makolo_mobile/network/api_error.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';
import 'package:makolo_mobile/sync/sync_engine.dart';

const credentialPath = '/api/v1/me/accesses/access-1/credential/';

class _Vault implements AccessCredentialVault {
  final values = <String, RetainedAccessQr>{};
  String key(String profile, String access) => '$profile:$access';

  @override
  Future<RetainedAccessQr?> read(String profileId, String accessId) async {
    final value = values[key(profileId, accessId)];
    if (value == null || !value.displayableAt(DateTime.now())) return null;
    return value;
  }

  @override
  Future<void> save(String profileId, RetainedAccessQr value) async {
    values[key(profileId, value.accessId)] = value;
  }

  @override
  Future<void> delete(String profileId, String accessId) async {
    values.remove(key(profileId, accessId));
  }

  @override
  Future<void> clearProfile(String profileId) async {
    values.removeWhere((key, value) => key.startsWith('$profileId:'));
  }
}

class _DelayedVault extends _Vault {
  final began = Completer<void>();
  final release = Completer<void>();

  @override
  Future<RetainedAccessQr?> read(String profileId, String accessId) async {
    final observed = await super.read(profileId, accessId);
    if (!began.isCompleted) began.complete();
    await release.future;
    return observed;
  }
}

class _OwnerApi implements MakoloApiClient {
  bool offline = false;
  bool deny = false;
  bool approve = true;
  String relationship = 'beneficiary';
  int requests = 0;
  Completer<ApiResponse>? deferredResponse;
  Completer<void>? deferredStarted;
  @override
  Uri get baseUri => Uri.parse('https://makolo.test/');

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    requests++;
    final deferred = deferredResponse;
    if (deferred != null) {
      deferredResponse = null;
      final started = deferredStarted;
      if (started != null && !started.isCompleted) started.complete();
      return deferred.future;
    }
    if (offline) throw StateError('offline');
    if (deny) {
      throw const MakoloApiError(
        statusCode: 403,
        code: 'permission_denied',
        message: 'Accès refusé.',
      );
    }
    final now = DateTime.now().toUtc();
    final expiry = now.add(const Duration(hours: 6));
    return ApiResponse(
      200,
      jsonEncode({
        'meta': {
          'projection': AccessRepository.credentialProjectionKind,
          'schema_version': 1,
          'generated_at': now.toIso8601String(),
        },
        'data': {
          'access': {'kind': 'access', 'id': 'access-1'},
          'relationship': relationship,
          'representation': {
            'credential_type': 'qr',
            'payload': 'signed-secret-only-in-vault',
            'issued_at': now.toIso8601String(),
          },
          'offline_presentation': {
            'allowed': approve,
            'scope': 'display_only',
            'observed_at': now.toIso8601String(),
            'expires_at': approve ? expiry.toIso8601String() : null,
          },
        },
      }),
      const {'cache-control': 'private, no-store'},
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  test('QR display refuses future, reversed and expired owner windows', () {
    final now = DateTime.now().toUtc();
    RetainedAccessQr qr(DateTime checked, DateTime expiry) => RetainedAccessQr(
      accessId: 'access-1',
      path: credentialPath,
      payload: 'opaque-secret',
      checkedAt: checked,
      expiresAt: expiry,
    );
    expect(
      qr(
        now.add(const Duration(minutes: 1)),
        now.add(const Duration(hours: 2)),
      ).displayableAt(now),
      isFalse,
    );
    expect(
      qr(
        now.subtract(const Duration(hours: 1)),
        now.subtract(const Duration(seconds: 1)),
      ).displayableAt(now),
      isFalse,
    );
    expect(
      qr(
        now.subtract(const Duration(minutes: 1)),
        now.subtract(const Duration(minutes: 2)),
      ).displayableAt(now),
      isFalse,
    );
    expect(
      qr(
        now.subtract(const Duration(minutes: 1)),
        now.add(const Duration(minutes: 1)),
      ).displayableAt(now),
      isTrue,
    );
  });

  test(
    'only the owner-approved QR persists, isolated and expiry bounded',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final vault = _Vault();
      final api = _OwnerApi();
      final repo = AccessRepository(
        database: db,
        store: ProfileStore(db, 'profile-a'),
        profileId: 'profile-a',
        api: api,
        credentialVault: vault,
      );
      final shown = await repo.fetchCredential(
        accessId: 'access-1',
        path: credentialPath,
      );
      expect(shown.locallyRetained, isFalse);
      expect(shown.payload, 'signed-secret-only-in-vault');
      final restored = await repo.readRetainedCredential('access-1');
      expect(restored?.locallyRetained, isTrue);
      expect(restored?.offlineUntil, isNotNull);
      expect(
        await ProfileStore(db, 'profile-a').readProjection(
          AccessRepository.credentialProjectionKind,
          resourceKey: 'access-1',
        ),
        isNull,
      );

      final other = AccessRepository(
        database: db,
        store: ProfileStore(db, 'profile-b'),
        profileId: 'profile-b',
        credentialVault: vault,
      );
      expect(await other.readRetainedCredential('access-1'), isNull);

      api.approve = false;
      await repo.fetchCredential(accessId: 'access-1', path: credentialPath);
      expect(await repo.readRetainedCredential('access-1'), isNull);
      api.approve = true;
      await repo.fetchCredential(accessId: 'access-1', path: credentialPath);
      api.deny = true;
      await expectLater(
        repo.fetchCredential(accessId: 'access-1', path: credentialPath),
        throwsA(isA<MakoloApiError>()),
      );
      expect(await repo.readRetainedCredential('access-1'), isNull);

      await expectLater(
        repo.fetchCredential(
          accessId: 'access-1',
          path: 'https://external.example/accesses/access-1/credential/',
        ),
        throwsFormatException,
      );
    },
  );

  test(
    'late QR response cannot resurrect a 403 from another repository',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final vault = _Vault();
      final owner = _OwnerApi();
      final first = AccessRepository(
        database: db,
        store: ProfileStore(db, 'profile-a'),
        profileId: 'profile-a',
        api: owner,
        credentialVault: vault,
      );
      final second = AccessRepository(
        database: db,
        store: ProfileStore(db, 'profile-a'),
        profileId: 'profile-a',
        api: owner,
        credentialVault: vault,
      );

      // Capture an older success before an owner denial is observed.
      final earlierResponse = await owner.get(credentialPath);
      final delayed = Completer<ApiResponse>();
      owner.deferredResponse = delayed;
      owner.deferredStarted = Completer<void>();
      final inFlight = first.fetchCredential(
        accessId: 'access-1',
        path: credentialPath,
      );
      await owner.deferredStarted!.future;
      owner.deny = true;
      await expectLater(
        second.fetchCredential(accessId: 'access-1', path: credentialPath),
        throwsA(isA<MakoloApiError>()),
      );
      delayed.complete(earlierResponse);
      await expectLater(inFlight, throwsA(isA<StateError>()));
      expect(await first.readRetainedCredential('access-1'), isNull);

      owner.deny = false;
      final reacquired = await first.fetchCredential(
        accessId: 'access-1',
        path: credentialPath,
      );
      expect(reacquired.payload, 'signed-secret-only-in-vault');
      expect(await first.readRetainedCredential('access-1'), isNotNull);
    },
  );

  test(
    'QR vault read cannot disclose a secret after concurrent Access 403',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      final vault = _DelayedVault();
      final owner = _OwnerApi();
      final engine = SyncEngine(
        api: owner,
        database: db,
        store: ProfileStore(db, 'profile-a'),
        profileId: 'profile-a',
      );
      final repo = AccessRepository(
        database: db,
        store: ProfileStore(db, 'profile-a'),
        profileId: 'profile-a',
        api: owner,
        sync: engine,
        credentialVault: vault,
      );
      await repo.fetchCredential(accessId: 'access-1', path: credentialPath);

      final pending = repo.readRetainedCredential('access-1');
      await vault.began.future;
      await engine.revoke(repo.sourceFor('access-1'));
      vault.release.complete();
      expect(await pending, isNull);
    },
  );

  test(
    'Access repository rejects cross-Profile secure credential bindings',
    () async {
      final db = MakoloDatabase.memory();
      addTearDown(db.close);
      expect(
        () => AccessRepository(
          database: db,
          store: ProfileStore(db, 'profile-b'),
          profileId: 'profile-a',
          credentialVault: _Vault(),
        ),
        throwsArgumentError,
      );
    },
  );

  testWidgets('cold offline QR display never claims an accepted AccessUse', (
    tester,
  ) async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    final vault = _Vault();
    final api = _OwnerApi();
    final repo = AccessRepository(
      database: db,
      store: ProfileStore(db, 'profile-a'),
      profileId: 'profile-a',
      api: api,
      credentialVault: vault,
    );
    await repo.fetchCredential(accessId: 'access-1', path: credentialPath);
    api.offline = true;
    await tester.pumpWidget(
      MaterialApp(
        home: AccessCredentialScreen(
          accessId: 'access-1',
          credentialPath: null,
          repository: repo,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Copie protégée reçue'), findsOneWidget);
    expect(find.textContaining('ne prouve pas la validité'), findsOneWidget);
    expect(find.text('signed-secret-only-in-vault'), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(milliseconds: 1));
  });
}
