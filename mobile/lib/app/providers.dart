import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../auth/token_store.dart';
import '../data/local/makolo_database.dart';
import '../data/local/profile_store.dart';
import '../network/makolo_api_client.dart';
import '../repositories/personal_repository.dart';
import '../sync/outbox/outbox_repository.dart';
import '../sync/sync_engine.dart';
import 'environment.dart';

class AppRuntime {
  AppRuntime({
    required this.tokens,
    required this.session,
    this.api,
    this.database,
    this.store,
    this.personal,
    this.outbox,
    this.sync,
  });

  final TokenStore tokens;
  final AuthSession? session;
  final MakoloApiClient? api;
  final MakoloDatabase? database;
  final ProfileStore? store;
  final PersonalRepository? personal;
  final OutboxRepository? outbox;
  final SyncEngine? sync;

  bool get isAuthenticated => session?.profileId != null;
  bool get apiConfigured => api != null;

  Future<void> close() async {
    await database?.close();
  }
}

final tokenStoreProvider = Provider<TokenStore>(
  (ref) => FlutterSecureTokenStore(),
);

final httpClientProvider = Provider<http.Client>((ref) {
  final client = http.Client();
  ref.onDispose(client.close);
  return client;
});

final appRuntimeProvider = FutureProvider<AppRuntime>((ref) async {
  final tokens = ref.watch(tokenStoreProvider);
  final session = await tokens.readSession();
  final baseUri = MakoloEnvironment.apiBaseUri;
  final api = baseUri == null
      ? null
      : MakoloApiClient(
          baseUri: baseUri,
          httpClient: ref.watch(httpClientProvider),
          tokenStore: tokens,
        );

  final profileId = session?.profileId;
  if (profileId == null) {
    return AppRuntime(tokens: tokens, session: session, api: api);
  }

  final database = await MakoloDatabase.openForProfile(profileId);
  ref.onDispose(() {
    unawaited(database.close());
  });
  final store = ProfileStore(database, profileId);
  final personal = PersonalRepository(store);
  final outbox = OutboxRepository(database, profileId);
  final sync = api == null
      ? null
      : SyncEngine(
          api: api,
          store: store,
          database: database,
          profileId: profileId,
        );

  return AppRuntime(
    tokens: tokens,
    session: session,
    api: api,
    database: database,
    store: store,
    personal: personal,
    outbox: outbox,
    sync: sync,
  );
});

