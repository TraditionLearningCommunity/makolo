import 'dart:convert';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/actor_context_controller.dart';
import '../../data/local/makolo_database.dart';
import '../../data/local/profile_store.dart';
import '../../network/api_error.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_engine.dart';
import '../../sync/sync_source.dart';

enum SpaceProjectionKind {
  workspace('space.workspace'),
  now('space.now'),
  discover('space.discover'),
  work('space.work'),
  us('space.us'),
  relationships('space.relationships'),
  pilot('space.pilot');

  const SpaceProjectionKind(this.wireValue);
  final String wireValue;
}

final class SpaceSummary {
  const SpaceSummary({
    required this.identity,
    required this.name,
    required this.archetype,
    required this.lifecycle,
    required this.limitedToActivities,
  });

  final SpaceActorIdentity identity;
  final String name;
  final String archetype;
  final String lifecycle;
  final bool limitedToActivities;

  factory SpaceSummary.fromJson(Map<String, dynamic> json) {
    return SpaceSummary(
      identity: SpaceActorIdentity(
        id: _requiredString(json, 'id'),
        slug: _requiredString(json, 'slug'),
      ),
      name: _requiredString(json, 'name'),
      archetype: _requiredString(json, 'archetype'),
      lifecycle: _requiredString(json, 'lifecycle'),
      limitedToActivities: _requiredBool(json, 'limited_to_activities'),
    );
  }
}

final class SpaceResponsibilitySummary {
  const SpaceResponsibilitySummary({
    required this.key,
    required this.label,
    required this.scope,
    required this.combined,
  });

  final String key;
  final String label;
  final String scope;
  final bool combined;

  factory SpaceResponsibilitySummary.fromJson(Map<String, dynamic> json) {
    return SpaceResponsibilitySummary(
      key: _requiredString(json, 'key'),
      label: _requiredString(json, 'label'),
      scope: _requiredString(json, 'scope'),
      combined: _requiredBool(json, 'combined'),
    );
  }
}

final class SpaceBootstrap {
  const SpaceBootstrap({
    required this.identity,
    required this.responsibilities,
    required this.payload,
  });

  final SpaceActorIdentity identity;
  final List<SpaceResponsibilitySummary> responsibilities;
  final Map<String, dynamic> payload;

  bool supportsPerspective(ActorPerspective perspective) {
    final key = SpaceSyncKeys.perspectiveKey(perspective);
    return responsibilities.any((item) => item.key == key);
  }

  factory SpaceBootstrap.fromPayload(Map<String, dynamic> payload) {
    final space = _requiredMap(payload, 'space');
    final responsibilityRows = _requiredList(payload, 'responsibilities');
    final responsibilities = responsibilityRows
        .map(
          (row) => SpaceResponsibilitySummary.fromJson(
            _mapValue(row, 'responsibility'),
          ),
        )
        .toList(growable: false);
    if (!responsibilities.any((item) => item.key == 'all')) {
      throw const FormatException(
        'Workspace bootstrap must expose the all responsibility perspective.',
      );
    }
    return SpaceBootstrap(
      identity: SpaceActorIdentity(
        id: _requiredString(space, 'id'),
        slug: _requiredString(space, 'slug'),
      ),
      responsibilities: responsibilities,
      payload: payload,
    );
  }
}

final class SpaceSyncKeys {
  const SpaceSyncKeys._();

  static const inventoryProjectionKind = 'space.inventory';
  static const inventorySourceKey = 'space.inventory';
  static const documentsProjectionKind = 'space.documents';
  static const resourcesProjectionKind = 'space.resources';

  static String resourcesResourceKey(String spaceId) =>
      Uri.encodeComponent(spaceId);

  static String resourcesSourceKey(String spaceId) =>
      'space:${Uri.encodeComponent(spaceId)}:resources';

  static String documentsResourceKey(
    String spaceId, {
    required String query,
    required int offset,
  }) =>
      '${Uri.encodeComponent(spaceId)}|'
      '${Uri.encodeComponent(query.trim())}|$offset';

  static String documentsSourceKey(
    String spaceId, {
    required String query,
    required int offset,
  }) =>
      'space:${Uri.encodeComponent(spaceId)}:documents:'
      '${Uri.encodeComponent(query.trim())}:$offset';

  static String perspectiveKey(ActorPerspective perspective) =>
      perspective.isAll ? 'all' : perspective.id!;

  static String resourceKey(String spaceId, {ActorPerspective? perspective}) {
    final encodedSpace = Uri.encodeComponent(spaceId);
    if (perspective == null) return encodedSpace;
    return '$encodedSpace|${Uri.encodeComponent(perspectiveKey(perspective))}';
  }

  static String sourceKey(
    String spaceId,
    SpaceProjectionKind kind, {
    ActorPerspective? perspective,
  }) {
    final encodedSpace = Uri.encodeComponent(spaceId);
    final suffix = perspective == null
        ? ''
        : ':${Uri.encodeComponent(perspectiveKey(perspective))}';
    return 'space:$encodedSpace:${kind.name}$suffix';
  }
}

final class WorkspaceContextRepository {
  WorkspaceContextRepository({
    required this.database,
    required this.store,
    required this.profileId,
    required this.actorContext,
    this.sync,
  });

  static const inventoryFreshness = FreshnessPolicy(id: 'contextual');
  static const contextFreshness = FreshnessPolicy(id: 'contextual');
  static const surfaceFreshness = FreshnessPolicy(
    id: 'swr',
    refreshRecommendedAfter: Duration(minutes: 10),
    usableButOldAfter: Duration(hours: 6),
  );

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final ActorContextController actorContext;
  final SyncEngine? sync;

  SyncSourceDefinition inventorySource() {
    return SyncSourceDefinition(
      sourceKey: SpaceSyncKeys.inventorySourceKey,
      owner: 'Organizations',
      path: 'api/v1/organizations/workspaces/',
      projectionKind: SpaceSyncKeys.inventoryProjectionKind,
      category: SyncSourceCategory.collection,
      freshnessPolicy: inventoryFreshness,
      parser: _parseInventory,
      applier: applyProjectionSnapshot,
    );
  }

  SyncSourceDefinition workspaceSource(SpaceActorIdentity space) {
    return SyncSourceDefinition(
      sourceKey: SpaceSyncKeys.sourceKey(
        space.id,
        SpaceProjectionKind.workspace,
      ),
      owner: 'Organizations',
      actorScope: SyncActorScope.space(spaceId: space.id),
      path: _spacePath(space.slug),
      projectionKind: SpaceProjectionKind.workspace.wireValue,
      resourceKey: SpaceSyncKeys.resourceKey(space.id),
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: contextFreshness,
      parser: (response) =>
          _parseWorkspace(response, expectedSpaceId: space.id),
      applier: applyProjectionSnapshot,
    );
  }

  SyncSourceDefinition nowSource(
    SpaceActorIdentity space,
    ActorPerspective perspective,
  ) {
    return _perspectiveSource(
      space: space,
      perspective: perspective,
      kind: SpaceProjectionKind.now,
      owner: 'Organizations',
      segment: 'now',
      parser: (response) => _parseAttention(
        response,
        expectedSpaceId: space.id,
        expectedResponsibility: SpaceSyncKeys.perspectiveKey(perspective),
      ),
    );
  }

  SyncSourceDefinition discoverSource(SpaceActorIdentity space) {
    return _spaceSource(
      space: space,
      kind: SpaceProjectionKind.discover,
      owner: 'Organizations',
      segment: 'discover',
      parser: (response) => _parseDiscover(response, expectedSpaceId: space.id),
    );
  }

  SyncSourceDefinition workSource(
    SpaceActorIdentity space,
    ActorPerspective perspective,
  ) {
    return _perspectiveSource(
      space: space,
      perspective: perspective,
      kind: SpaceProjectionKind.work,
      owner: 'Organizations',
      segment: 'work',
      parser: (response) => _parseWork(
        response,
        expectedSpaceId: space.id,
        expectedResponsibility: SpaceSyncKeys.perspectiveKey(perspective),
      ),
    );
  }

  SyncSourceDefinition usSource(SpaceActorIdentity space) {
    return _spaceSource(
      space: space,
      kind: SpaceProjectionKind.us,
      owner: 'Organizations',
      segment: 'us',
      parser: (response) => _parseUs(response, expectedSpaceId: space.id),
    );
  }

  SyncSourceDefinition resourcesSource(SpaceActorIdentity space) {
    return SyncSourceDefinition(
      sourceKey: SpaceSyncKeys.resourcesSourceKey(space.id),
      owner: 'SpaceResources',
      actorScope: SyncActorScope.space(spaceId: space.id),
      path: _spaceSegmentPath(
        space.slug,
        'us/resources',
        queryParameters: const {'kind': 'document', 'offset': '0'},
      ),
      projectionKind: SpaceSyncKeys.resourcesProjectionKind,
      resourceKey: SpaceSyncKeys.resourcesResourceKey(space.id),
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: surfaceFreshness,
      parser: (response) =>
          _parseResources(response, expectedSpaceId: space.id),
      applier: applyProjectionSnapshot,
    );
  }

  SyncSourceDefinition documentsSource(
    SpaceActorIdentity space, {
    String query = '',
    int offset = 0,
  }) {
    final normalizedQuery = query.trim();
    final path = _spaceSegmentPath(
      space.slug,
      'documents',
      queryParameters: {
        if (normalizedQuery.isNotEmpty) 'q': normalizedQuery,
        'offset': '$offset',
      },
    );
    return SyncSourceDefinition(
      sourceKey: SpaceSyncKeys.documentsSourceKey(
        space.id,
        query: normalizedQuery,
        offset: offset,
      ),
      owner: 'SpaceDocument',
      actorScope: SyncActorScope.space(spaceId: space.id),
      path: path,
      projectionKind: SpaceSyncKeys.documentsProjectionKind,
      resourceKey: SpaceSyncKeys.documentsResourceKey(
        space.id,
        query: normalizedQuery,
        offset: offset,
      ),
      category: SyncSourceCategory.collection,
      freshnessPolicy: surfaceFreshness,
      parser: (response) => _parseDocuments(
        response,
        expectedSpaceId: space.id,
        query: normalizedQuery,
        offset: offset,
      ),
      applier: applyProjectionSnapshot,
    );
  }

  SyncSourceDefinition relationshipsSource(SpaceActorIdentity space) {
    return _spaceSource(
      space: space,
      kind: SpaceProjectionKind.relationships,
      owner: 'Organizations',
      segment: 'relationships',
      parser: (response) => _parseLinkedProjection(
        response,
        expectedWorkspacePath: _spacePath(space.slug),
        requiredCollectionKey: 'sections',
      ),
    );
  }

  SyncSourceDefinition pilotSource(SpaceActorIdentity space) {
    return _spaceSource(
      space: space,
      kind: SpaceProjectionKind.pilot,
      owner: 'Analytics',
      segment: 'pilot',
      parser: (response) => _parseLinkedProjection(
        response,
        expectedWorkspacePath: _spacePath(space.slug),
        requiredCollectionKey: 'sections',
      ),
    );
  }

  Stream<List<SpaceSummary>> watchInventory() {
    return store
        .watchProjection(SpaceSyncKeys.inventoryProjectionKind)
        .map(_inventoryFromSnapshot);
  }

  Future<List<SpaceSummary>> readInventory() async {
    return _inventoryFromSnapshot(
      await store.readProjection(SpaceSyncKeys.inventoryProjectionKind),
    );
  }

  Stream<StoredProjection?> watchWorkspace(SpaceActorIdentity space) {
    return store.watchProjection(
      SpaceProjectionKind.workspace.wireValue,
      resourceKey: SpaceSyncKeys.resourceKey(space.id),
    );
  }

  Future<SpaceBootstrap?> readWorkspace(SpaceActorIdentity space) async {
    final projection = await store.readProjection(
      SpaceProjectionKind.workspace.wireValue,
      resourceKey: SpaceSyncKeys.resourceKey(space.id),
    );
    if (projection == null) return null;
    return SpaceBootstrap.fromPayload(projection.payload);
  }

  Stream<StoredProjection?> watchNow(
    SpaceActorIdentity space,
    ActorPerspective perspective,
  ) => _watchPerspective(SpaceProjectionKind.now, space, perspective);

  Stream<StoredProjection?> watchDiscover(SpaceActorIdentity space) =>
      _watchSpace(SpaceProjectionKind.discover, space);

  Stream<StoredProjection?> watchWork(
    SpaceActorIdentity space,
    ActorPerspective perspective,
  ) => _watchPerspective(SpaceProjectionKind.work, space, perspective);

  Stream<StoredProjection?> watchUs(SpaceActorIdentity space) =>
      _watchSpace(SpaceProjectionKind.us, space);

  Stream<StoredProjection?> watchResources(SpaceActorIdentity space) =>
      store.watchProjection(
        SpaceSyncKeys.resourcesProjectionKind,
        resourceKey: SpaceSyncKeys.resourcesResourceKey(space.id),
      );

  Future<StoredProjection?> readResources(SpaceActorIdentity space) =>
      store.readProjection(
        SpaceSyncKeys.resourcesProjectionKind,
        resourceKey: SpaceSyncKeys.resourcesResourceKey(space.id),
      );

  Stream<List<StoredProjection>> watchDocumentPages(
    SpaceActorIdentity space, {
    String query = '',
  }) {
    final normalizedQuery = query.trim();
    return store.watchProjections(SpaceSyncKeys.documentsProjectionKind).map((
      pages,
    ) {
      final selected =
          pages.where((page) {
            final payload = page.payload;
            return payload['space_id']?.toString() == space.id &&
                (payload['_query']?.toString() ?? '') == normalizedQuery;
          }).toList()..sort((a, b) {
            final left = a.payload['_offset'];
            final right = b.payload['_offset'];
            final leftOffset = left is num ? left.toInt() : 0;
            final rightOffset = right is num ? right.toInt() : 0;
            return leftOffset.compareTo(rightOffset);
          });
      return selected;
    });
  }

  Future<StoredProjection?> readDocumentPage(
    SpaceActorIdentity space, {
    String query = '',
    int offset = 0,
  }) => store.readProjection(
    SpaceSyncKeys.documentsProjectionKind,
    resourceKey: SpaceSyncKeys.documentsResourceKey(
      space.id,
      query: query.trim(),
      offset: offset,
    ),
  );

  Stream<StoredProjection?> watchRelationships(SpaceActorIdentity space) =>
      _watchSpace(SpaceProjectionKind.relationships, space);

  Stream<StoredProjection?> watchPilot(SpaceActorIdentity space) =>
      _watchSpace(SpaceProjectionKind.pilot, space);

  /// A Space listed in an authorized local inventory can be selected as a
  /// *presentation context* even before its first workspace snapshot.
  /// This never grants permissions or certifies an owner action. This does not grant any
  /// authority: each owner still validates permissions for its own actions.
  ///
  /// A source explicitly invalidated by its owner, a denied/missing Space,
  /// an unrecognized Profile, or a mismatched cached identity is never used.
  Future<bool> hasAcquiredSpaceContext(SpaceActorIdentity space) async {
    final inventoryState = await readSource(inventorySource());
    if (!_usableForLocalContext(inventoryState)) return false;
    final known = (await readInventory()).any((item) => item.identity == space);
    if (!known) return false;

    final workspaceState = await readSource(workspaceSource(space));
    if (workspaceState.invalidated) return false;
    if (workspaceState.lastSuccessAt == null) {
      // An authorized inventory is enough to choose a reading perspective
      // before the first workspace download. It grants no owner action.
      // A previous explicit denial still forbids that transition.
      return workspaceState.lastErrorCode == null ||
          const {
            'timeout',
            'makolo_unreachable',
            'secure_connection_failed',
            'transport_error',
            'server_unavailable',
          }.contains(workspaceState.lastErrorCode);
    }
    if (!_usableForLocalContext(workspaceState)) return false;
    try {
      final workspace = await readWorkspace(space);
      return workspace != null && workspace.identity == space;
    } on FormatException {
      return false;
    }
  }

  static bool _usableForLocalContext(OwnerSourceState source) {
    if (source.invalidated || source.lastSuccessAt == null) return false;
    // Only known transport failures preserve a previously acquired view.
    // Unknown errors are not evidence of retained authority.
    return source.lastErrorCode == null ||
        const {
          'timeout',
          'makolo_unreachable',
          'secure_connection_failed',
          'transport_error',
          'server_unavailable',
        }.contains(source.lastErrorCode);
  }

  Future<void> refreshInventory() async {
    final engine = _requireSync();
    final previous = await readInventory();
    try {
      await engine.pullSource(inventorySource());
    } on MakoloApiError catch (error) {
      if (engine.isActive &&
          (error.statusCode == 403 || error.statusCode == 404)) {
        // A denied inventory cannot validate the selected Space actor.
        // Transport outages do not reset a valid local preference.
        await actorContext.selectPersonal();
      }
      rethrow;
    }
    if (!engine.isActive) return; // Superseded Profile runtime.
    final state = await readSource(inventorySource());
    if (state.invalidated || state.lastErrorCode != null) return;
    final current = await readInventory();
    final ids = current.map((item) => item.identity.id).toSet();
    // An inventory removal is an owner-confirmed withdrawal for that Space,
    // not a reason to erase other Spaces or device-owned drafts.
    for (final former in previous) {
      if (!ids.contains(former.identity.id)) {
        await engine.revoke(
          workspaceSource(former.identity),
          code: 'not_found',
        );
      }
    }
    await _reconcileActorContextFromInventory();
  }

  /// Creation belongs to Organizations; this does not grant actor authority.
  Future<SpaceActorIdentity> createSpace({
    required String name,
    required bool publicProfile,
  }) async {
    final engine = _requireSync();
    final response = await engine.api.post(
      'api/v1/organizations/workspaces/',
      body: {'name': name.trim(), 'public_profile': publicProfile},
    );
    final space = _requiredMap(response.jsonObject(), 'space');
    return SpaceActorIdentity(
      id: _requiredString(space, 'id'),
      slug: _requiredString(space, 'slug'),
    );
  }

  Future<void> refreshWorkspace(SpaceActorIdentity space) async {
    final engine = _requireSync();
    try {
      await engine.pullSource(workspaceSource(space));
    } on MakoloApiError catch (error) {
      if (engine.isActive &&
          (error.statusCode == 403 || error.statusCode == 404)) {
        final selected = actorContext.value;
        if (selected is SpaceActorContext && selected.space.id == space.id) {
          await actorContext.selectPersonal();
        }
      }
      rethrow;
    }
    if (!engine.isActive) return;
    await _reconcilePerspective(space);
  }

  Future<void> refreshNow(
    SpaceActorIdentity space,
    ActorPerspective perspective,
  ) => _refresh(nowSource(space, perspective));

  Future<void> refreshDiscover(SpaceActorIdentity space) =>
      _refresh(discoverSource(space));

  Future<void> refreshWork(
    SpaceActorIdentity space,
    ActorPerspective perspective,
  ) => _refresh(workSource(space, perspective));

  Future<void> refreshUs(SpaceActorIdentity space) => _refresh(usSource(space));

  Future<bool> shouldRefreshResources(
    SpaceActorIdentity space, {
    DateTime? now,
  }) async {
    final source = resourcesSource(space);
    final state = await readSource(source);
    if (state.invalidated &&
        const {
          'permission_denied',
          'not_found',
        }.contains(state.lastErrorCode)) {
      return false;
    }
    final projection = await readResources(space);
    if (projection == null ||
        state.lastSuccessAt == null ||
        state.lastErrorCode != null ||
        state.invalidated) {
      return true;
    }
    return surfaceFreshness.evaluate(
          projection,
          now: (now ?? DateTime.now()).toUtc(),
        ) !=
        FreshnessState.fresh;
  }

  Future<void> ensureResources(SpaceActorIdentity space) async {
    if (await shouldRefreshResources(space)) {
      await refreshResources(space);
    }
  }

  Future<void> refreshResources(SpaceActorIdentity space) =>
      _refresh(resourcesSource(space));

  Future<bool> shouldRefreshDocumentPage(
    SpaceActorIdentity space, {
    String query = '',
    int offset = 0,
    DateTime? now,
  }) async {
    final source = documentsSource(space, query: query, offset: offset);
    final state = await readSource(source);
    if (state.invalidated &&
        const {
          'permission_denied',
          'not_found',
        }.contains(state.lastErrorCode)) {
      return false;
    }
    final projection = await readDocumentPage(
      space,
      query: query,
      offset: offset,
    );
    if (projection == null ||
        state.lastSuccessAt == null ||
        state.lastErrorCode != null ||
        state.invalidated) {
      return true;
    }
    return surfaceFreshness.evaluate(
          projection,
          now: (now ?? DateTime.now()).toUtc(),
        ) !=
        FreshnessState.fresh;
  }

  Future<void> ensureDocumentPage(
    SpaceActorIdentity space, {
    String query = '',
    int offset = 0,
  }) async {
    if (!await shouldRefreshDocumentPage(space, query: query, offset: offset)) {
      return;
    }
    await refreshDocumentPage(space, query: query, offset: offset);
  }

  Future<void> refreshDocumentPage(
    SpaceActorIdentity space, {
    String query = '',
    int offset = 0,
  }) => _refresh(documentsSource(space, query: query, offset: offset));

  Future<void> refreshRelationships(SpaceActorIdentity space) =>
      _refresh(relationshipsSource(space));

  Future<void> refreshPilot(SpaceActorIdentity space) =>
      _refresh(pilotSource(space));

  Stream<OwnerSourceState> watchSource(SyncSourceDefinition source) {
    return watchOwnerSourceState(
      database: database,
      profileId: profileId,
      sourceKey: source.sourceKey,
    );
  }

  Future<OwnerSourceState> readSource(SyncSourceDefinition source) {
    return readOwnerSourceState(
      database: database,
      profileId: profileId,
      sourceKey: source.sourceKey,
    );
  }

  Future<void> _reconcileActorContextFromInventory() async {
    final current = actorContext.value;
    if (current is! SpaceActorContext) return;

    final inventory = await readInventory();
    SpaceSummary? matched;
    for (final item in inventory) {
      if (item.identity.id == current.space.id) {
        matched = item;
        break;
      }
    }

    if (matched == null) {
      await actorContext.selectPersonal();
      return;
    }

    if (matched.identity.slug != current.space.slug) {
      await actorContext.selectSpace(
        matched.identity,
        perspective: current.perspective,
      );
    }
  }

  Future<void> _reconcilePerspective(SpaceActorIdentity space) async {
    final current = actorContext.value;
    if (current is! SpaceActorContext || current.space.id != space.id) return;

    final bootstrap = await readWorkspace(space);
    if (bootstrap == null) return;

    if (!current.perspective.isAll &&
        !bootstrap.supportsPerspective(current.perspective)) {
      await actorContext.selectPerspective(const ActorPerspective.all());
    }
  }

  Future<void> _refresh(SyncSourceDefinition source) async {
    final engine = _requireSync();
    await engine.refreshSource(source);
  }

  SyncEngine _requireSync() {
    final engine = sync;
    if (engine == null) {
      throw StateError('Remote Space owner is not configured.');
    }
    return engine;
  }

  Stream<StoredProjection?> _watchSpace(
    SpaceProjectionKind kind,
    SpaceActorIdentity space,
  ) {
    return store.watchProjection(
      kind.wireValue,
      resourceKey: SpaceSyncKeys.resourceKey(space.id),
    );
  }

  Stream<StoredProjection?> _watchPerspective(
    SpaceProjectionKind kind,
    SpaceActorIdentity space,
    ActorPerspective perspective,
  ) {
    return store.watchProjection(
      kind.wireValue,
      resourceKey: SpaceSyncKeys.resourceKey(
        space.id,
        perspective: perspective,
      ),
    );
  }

  SyncSourceDefinition _spaceSource({
    required SpaceActorIdentity space,
    required SpaceProjectionKind kind,
    required String owner,
    required String segment,
    required SyncSourceParser parser,
  }) {
    return SyncSourceDefinition(
      sourceKey: SpaceSyncKeys.sourceKey(space.id, kind),
      owner: owner,
      actorScope: SyncActorScope.space(spaceId: space.id),
      path: _spaceSegmentPath(space.slug, segment),
      projectionKind: kind.wireValue,
      resourceKey: SpaceSyncKeys.resourceKey(space.id),
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: surfaceFreshness,
      parser: parser,
      applier: applyProjectionSnapshot,
    );
  }

  SyncSourceDefinition _perspectiveSource({
    required SpaceActorIdentity space,
    required ActorPerspective perspective,
    required SpaceProjectionKind kind,
    required String owner,
    required String segment,
    required SyncSourceParser parser,
  }) {
    final perspectiveKey = SpaceSyncKeys.perspectiveKey(perspective);
    final path = _spaceSegmentPath(
      space.slug,
      segment,
      queryParameters: perspective.isAll
          ? const {}
          : {'responsibility': perspectiveKey},
    );
    return SyncSourceDefinition(
      sourceKey: SpaceSyncKeys.sourceKey(
        space.id,
        kind,
        perspective: perspective,
      ),
      owner: owner,
      actorScope: SyncActorScope.space(
        spaceId: space.id,
        perspectiveKey: perspective.isAll ? null : perspectiveKey,
      ),
      path: path,
      projectionKind: kind.wireValue,
      resourceKey: SpaceSyncKeys.resourceKey(
        space.id,
        perspective: perspective,
      ),
      category: SyncSourceCategory.keyedDetail,
      freshnessPolicy: surfaceFreshness,
      parser: parser,
      applier: applyProjectionSnapshot,
    );
  }

  static String _spacePath(String slug) =>
      'api/v1/organizations/workspaces/${Uri.encodeComponent(slug)}/';

  static String _spaceSegmentPath(
    String slug,
    String segment, {
    Map<String, String> queryParameters = const {},
  }) {
    final uri = Uri(
      path:
          'api/v1/organizations/workspaces/'
          '${Uri.encodeComponent(slug)}/$segment/',
      queryParameters: queryParameters.isEmpty ? null : queryParameters,
    );
    return uri.toString();
  }

  static AcquiredProjection _parseInventory(ApiResponse response) {
    final decoded = jsonDecode(response.body);
    if (decoded is! List) {
      throw const FormatException('Expected Workspace inventory collection.');
    }
    final rows = <Map<String, dynamic>>[];
    final seen = <String>{};
    for (final item in decoded) {
      final row = _mapValue(item, 'workspace inventory item');
      final summary = SpaceSummary.fromJson(row);
      if (!seen.add(summary.identity.id)) {
        throw const FormatException(
          'Workspace inventory contains duplicate ids.',
        );
      }
      final links = _requiredMap(row, 'links');
      _requiredString(links, 'workspace');
      rows.add(row);
    }
    return AcquiredProjection(schemaVersion: 1, payload: {'items': rows});
  }

  static AcquiredProjection _parseWorkspace(
    ApiResponse response, {
    required String expectedSpaceId,
  }) {
    final payload = response.jsonObject();
    final bootstrap = SpaceBootstrap.fromPayload(payload);
    if (bootstrap.identity.id != expectedSpaceId) {
      throw const FormatException(
        'Workspace response does not match Space id.',
      );
    }
    _requiredMap(payload, 'authority');
    _requiredMap(payload, 'capabilities');
    _requiredMap(payload, 'operating_preset');
    _requiredMap(payload, 'links');
    _requiredList(payload, 'modules');
    return AcquiredProjection(schemaVersion: 1, payload: payload);
  }

  static AcquiredProjection _parseAttention(
    ApiResponse response, {
    required String expectedSpaceId,
    required String expectedResponsibility,
  }) {
    final payload = response.jsonObject();
    _validateSpaceContext(
      payload,
      expectedSpaceId: expectedSpaceId,
      expectedResponsibility: expectedResponsibility,
    );
    final selection = _requiredMap(payload, 'selection');
    _requiredString(selection, 'state');
    _requiredList(payload, 'items');
    _requiredBool(payload, 'has_more');
    return AcquiredProjection(schemaVersion: 1, payload: payload);
  }

  static AcquiredProjection _parseDiscover(
    ApiResponse response, {
    required String expectedSpaceId,
  }) {
    final payload = response.jsonObject();
    _validateSpaceContext(
      payload,
      expectedSpaceId: expectedSpaceId,
      expectedResponsibility: 'all',
    );
    final selection = _requiredMap(payload, 'selection');
    _requiredString(selection, 'state');
    _requiredList(payload, 'items');
    _requiredBool(payload, 'has_more');
    return AcquiredProjection(schemaVersion: 1, payload: payload);
  }

  static AcquiredProjection _parseWork(
    ApiResponse response, {
    required String expectedSpaceId,
    required String expectedResponsibility,
  }) {
    final payload = response.jsonObject();
    _validateSpaceContext(
      payload,
      expectedSpaceId: expectedSpaceId,
      expectedResponsibility: expectedResponsibility,
    );
    _requiredString(payload, 'primary_business_label');
    final presentation = _requiredMap(payload, 'presentation');
    _requiredString(presentation, 'empty_message');
    final sections = _requiredMap(payload, 'sections');
    for (final key in const [
      'preparation',
      'upcoming',
      'active',
      'blocked',
      'completed',
    ]) {
      _requiredMap(sections, key);
    }
    for (final entry in sections.entries) {
      final section = _mapValue(entry.value, 'work section');
      _requiredString(section, 'representation');
      _requiredString(section, 'role');
      _requiredString(section, 'empty_message');
      _requiredList(section, 'items');
      _requiredBool(section, 'has_more');
    }
    return AcquiredProjection(schemaVersion: 1, payload: payload);
  }

  static AcquiredProjection _parseResources(
    ApiResponse response, {
    required String expectedSpaceId,
  }) {
    final payload = response.jsonObject();
    if (payload['space_id']?.toString() != expectedSpaceId) {
      throw const FormatException(
        'Space resources response does not match Space id.',
      );
    }
    if (payload['counts'] is! Map ||
        payload['items'] is! List ||
        payload['total_count'] is! num ||
        payload['count'] is! num ||
        payload['has_more'] is! bool ||
        payload['next_offset'] is! num ||
        payload['kind'] != 'document') {
      throw const FormatException('Space resources response is incomplete.');
    }
    return AcquiredProjection(schemaVersion: 1, payload: payload);
  }

  static AcquiredProjection _parseDocuments(
    ApiResponse response, {
    required String expectedSpaceId,
    required String query,
    required int offset,
  }) {
    final payload = response.jsonObject();
    if (payload['space_id']?.toString() != expectedSpaceId) {
      throw const FormatException(
        'Space documents response does not match Space id.',
      );
    }
    if (payload['items'] is! List ||
        payload['has_more'] is! bool ||
        payload['can_manage'] is! bool ||
        payload['count'] is! num ||
        payload['next_offset'] is! num) {
      throw const FormatException('Space documents response is incomplete.');
    }
    return AcquiredProjection(
      schemaVersion: 1,
      payload: {...payload, '_query': query, '_offset': offset},
    );
  }

  static AcquiredProjection _parseUs(
    ApiResponse response, {
    required String expectedSpaceId,
  }) {
    final payload = response.jsonObject();
    final identity = _requiredMap(payload, 'identity');
    if (_requiredString(identity, 'id') != expectedSpaceId) {
      throw const FormatException('Us projection does not match Space id.');
    }
    _requiredString(identity, 'slug');
    _requiredMap(payload, 'authority');
    _requiredMap(payload, 'responsibilities');
    _requiredMap(payload, 'links');
    return AcquiredProjection(schemaVersion: 1, payload: payload);
  }

  static AcquiredProjection _parseLinkedProjection(
    ApiResponse response, {
    required String expectedWorkspacePath,
    required String requiredCollectionKey,
  }) {
    final payload = response.jsonObject();
    final links = _requiredMap(payload, 'links');
    if (_requiredString(links, 'workspace') != '/$expectedWorkspacePath') {
      throw const FormatException('Projection workspace link does not match.');
    }
    _requiredMap(payload, 'authority');
    _requiredMap(payload, requiredCollectionKey);
    return AcquiredProjection(schemaVersion: 1, payload: payload);
  }

  static void _validateSpaceContext(
    Map<String, dynamic> payload, {
    required String expectedSpaceId,
    required String expectedResponsibility,
  }) {
    final space = _requiredMap(payload, 'space');
    if (_requiredString(space, 'id') != expectedSpaceId) {
      throw const FormatException('Projection does not match Space id.');
    }
    _requiredString(space, 'slug');
    if (_requiredString(payload, 'responsibility') != expectedResponsibility) {
      throw const FormatException('Projection responsibility does not match.');
    }
    _requiredMap(payload, 'authority');
  }

  static List<SpaceSummary> _inventoryFromSnapshot(StoredProjection? snapshot) {
    if (snapshot == null) return const [];
    final rows = _requiredList(snapshot.payload, 'items');
    return rows
        .map((row) => SpaceSummary.fromJson(_mapValue(row, 'workspace')))
        .toList(growable: false);
  }
}

Map<String, dynamic> _mapValue(Object? value, String label) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    final mapped = <String, dynamic>{};
    for (final entry in value.entries) {
      if (entry.key is! String) {
        throw FormatException('$label contains a non-string key.');
      }
      mapped[entry.key as String] = entry.value;
    }
    return mapped;
  }
  throw FormatException('Expected $label object.');
}

Map<String, dynamic> _requiredMap(Map<String, dynamic> json, String key) =>
    _mapValue(json[key], key);

List<dynamic> _requiredList(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is List) return value;
  throw FormatException('Expected $key list.');
}

String _requiredString(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('Expected non-empty $key string.');
  }
  return value.trim();
}

bool _requiredBool(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is bool) return value;
  throw FormatException('Expected $key boolean.');
}
