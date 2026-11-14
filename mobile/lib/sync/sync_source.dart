import '../data/local/makolo_database.dart';
import '../data/local/profile_store.dart';
import '../network/makolo_api_client.dart';
import 'freshness.dart';
import 'projection_contract.dart';

enum SyncSourceCategory { root, keyedDetail, collection, boundedOperational }

enum SyncActorScopeKind { personal, space }

final class SyncActorScope {
  const SyncActorScope.personal()
    : kind = SyncActorScopeKind.personal,
      spaceId = null,
      perspectiveKey = null;

  const SyncActorScope._space({
    required this.spaceId,
    required this.perspectiveKey,
  }) : kind = SyncActorScopeKind.space;

  factory SyncActorScope.space({
    required String spaceId,
    String? perspectiveKey,
  }) {
    final normalizedSpaceId = spaceId.trim();
    if (normalizedSpaceId.isEmpty) {
      throw ArgumentError.value(spaceId, 'spaceId', 'must not be empty');
    }

    final normalizedPerspective = perspectiveKey?.trim();
    if (perspectiveKey != null && normalizedPerspective!.isEmpty) {
      throw ArgumentError.value(
        perspectiveKey,
        'perspectiveKey',
        'must not be empty',
      );
    }

    return SyncActorScope._space(
      spaceId: normalizedSpaceId,
      perspectiveKey: normalizedPerspective,
    );
  }

  final SyncActorScopeKind kind;
  final String? spaceId;
  final String? perspectiveKey;

  bool get isPersonal => kind == SyncActorScopeKind.personal;
  bool get isSpace => kind == SyncActorScopeKind.space;

  String get stableKey {
    if (isPersonal) return 'personal';
    final perspective = perspectiveKey;
    if (perspective == null) return 'space:$spaceId';
    return 'space:$spaceId:perspective:$perspective';
  }

  @override
  bool operator ==(Object other) =>
      other is SyncActorScope &&
      other.kind == kind &&
      other.spaceId == spaceId &&
      other.perspectiveKey == perspectiveKey;

  @override
  int get hashCode => Object.hash(kind, spaceId, perspectiveKey);
}

class AcquiredProjection {
  const AcquiredProjection({
    required this.schemaVersion,
    required this.payload,
    this.sourceGeneratedAt,
    this.sourceUpdatedAt,
    this.freshUntil,
    this.expiresAt,
  });

  final int schemaVersion;
  final Map<String, dynamic> payload;
  final DateTime? sourceGeneratedAt;
  final DateTime? sourceUpdatedAt;
  final DateTime? freshUntil;
  final DateTime? expiresAt;
}

class SourceMembership {
  const SourceMembership({
    required this.sourceKey,
    required this.projectionKind,
    required this.resourceKey,
  });

  final String sourceKey;
  final String projectionKind;
  final String resourceKey;
}

class SyncApplyContext {
  const SyncApplyContext({
    required this.database,
    required this.store,
    required this.profileId,
    required this.source,
  });

  final MakoloDatabase database;
  final ProfileStore store;
  final String profileId;
  final SyncSourceDefinition source;
}

typedef SyncSourceParser = AcquiredProjection Function(ApiResponse response);
typedef SyncSourceApplier = Future<void> Function(
  SyncApplyContext context,
  AcquiredProjection projection,
);

class SyncSourceDefinition {
  const SyncSourceDefinition({
    required this.sourceKey,
    required this.owner,
    required this.path,
    required this.projectionKind,
    required this.category,
    required this.freshnessPolicy,
    required this.parser,
    required this.applier,
    this.resourceKey = '',
    this.actorScope = const SyncActorScope.personal(),
    this.indexedResourceKind,
  });

  final String sourceKey;
  final String owner;
  final String path;
  final String projectionKind;
  final String resourceKey;
  final SyncActorScope actorScope;

  /// Opt-in pointer for a keyed, owner-confirmed resource detail.
  final String? indexedResourceKind;
  final SyncSourceCategory category;
  final FreshnessPolicy freshnessPolicy;
  final SyncSourceParser parser;
  final SyncSourceApplier applier;

  SourceMembership get membership => SourceMembership(
    sourceKey: sourceKey,
    projectionKind: projectionKind,
    resourceKey: resourceKey,
  );

  factory SyncSourceDefinition.projectionEnvelope({
    required String sourceKey,
    required String owner,
    required String path,
    required String projectionKind,
    String resourceKey = '',
    SyncSourceCategory category = SyncSourceCategory.root,
    FreshnessPolicy freshnessPolicy = const FreshnessPolicy(id: 'contextual'),
    SyncActorScope actorScope = const SyncActorScope.personal(),
    String? indexedResourceKind,
    String? expectedOccurrenceId,
    String? expectedActorSpaceId,
    String? expectedViewerProfileId,
    String? expectedSurface,
  }) {
    return SyncSourceDefinition(
      sourceKey: sourceKey,
      owner: owner,
      path: path,
      projectionKind: projectionKind,
      resourceKey: resourceKey,
      actorScope: actorScope,
      indexedResourceKind: indexedResourceKind,
      category: category,
      freshnessPolicy: freshnessPolicy,
      parser: (response) {
        final envelope = ProjectionEnvelope.parse(response.jsonObject());
        if (envelope.projection != projectionKind) {
          throw FormatException(
            'Expected $projectionKind, got ${envelope.projection}',
          );
        }
        if (expectedOccurrenceId != null) {
          final identity = envelope.data['identity'];
          final context = envelope.data['context'];
          if (identity is! Map ||
              identity['kind'] != 'occurrence' ||
              identity['id']?.toString() != expectedOccurrenceId ||
              context is! Map ||
              (context['occurrence'] is! Map ||
                  (context['occurrence'] as Map)['id']?.toString() !=
                      expectedOccurrenceId) ||
              context['actor_space_id']?.toString() != expectedActorSpaceId ||
              (expectedViewerProfileId != null &&
                  context['viewer_profile_id']?.toString() !=
                      expectedViewerProfileId) ||
              (expectedSurface != null &&
                  envelope.data['surface'] != expectedSurface)) {
            throw const FormatException(
              'Occurrence projection has a mismatched actor, identity or surface',
            );
          }
        }
        return AcquiredProjection(
          schemaVersion: envelope.schemaVersion,
          payload: envelope.data,
          sourceGeneratedAt: envelope.generatedAt,
        );
      },
      applier: applyProjectionSnapshot,
    );
  }
}

Future<void> applyProjectionSnapshot(
  SyncApplyContext context,
  AcquiredProjection projection,
) async {
  final source = context.source;
  final resourceKind = source.indexedResourceKind;
  if (resourceKind != null) {
    if (!source.actorScope.isPersonal ||
        source.category != SyncSourceCategory.keyedDetail ||
        source.resourceKey.isEmpty) {
      throw const FormatException(
        'Only personal keyed owner details are indexed',
      );
    }
    // Reject a mismatched identity before storing any data or index pointer.
    final observedId = projection.payload['id'];
    if (observedId != null && observedId.toString() != source.resourceKey) {
      throw const FormatException('Owner resource identity mismatch');
    }
  }
  await context.store.putProjection(
    kind: source.projectionKind,
    resourceKey: source.resourceKey,
    schemaVersion: projection.schemaVersion,
    payload: projection.payload,
    sourceGeneratedAt: projection.sourceGeneratedAt,
    sourceUpdatedAt: projection.sourceUpdatedAt,
    freshUntil: projection.freshUntil,
    expiresAt: projection.expiresAt,
    freshnessPolicyId: source.freshnessPolicy.id,
  );
  if (resourceKind != null) {
    final title = projection.payload['title'];
    await context.store.putResourceReference(
      resourceKind: resourceKind,
      resourceId: source.resourceKey,
      projectionKind: source.projectionKind,
      label: title is String ? title : null,
    );
  }
}
