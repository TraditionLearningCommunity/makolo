import '../data/local/makolo_database.dart';
import '../data/local/profile_store.dart';
import '../network/makolo_api_client.dart';
import 'freshness.dart';
import 'projection_contract.dart';

enum SyncSourceCategory { root, keyedDetail, collection, boundedOperational }

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
typedef SyncSourceApplier =
    Future<void> Function(
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
  });

  final String sourceKey;
  final String owner;
  final String path;
  final String projectionKind;
  final String resourceKey;
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
  }) {
    return SyncSourceDefinition(
      sourceKey: sourceKey,
      owner: owner,
      path: path,
      projectionKind: projectionKind,
      resourceKey: resourceKey,
      category: category,
      freshnessPolicy: freshnessPolicy,
      parser: (response) {
        final envelope = ProjectionEnvelope.parse(response.jsonObject());
        if (envelope.projection != projectionKind) {
          throw FormatException(
            'Expected $projectionKind, got ${envelope.projection}',
          );
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
) {
  return context.store.putProjection(
    kind: context.source.projectionKind,
    resourceKey: context.source.resourceKey,
    schemaVersion: projection.schemaVersion,
    payload: projection.payload,
    sourceGeneratedAt: projection.sourceGeneratedAt,
    sourceUpdatedAt: projection.sourceUpdatedAt,
    freshUntil: projection.freshUntil,
    expiresAt: projection.expiresAt,
    freshnessPolicyId: context.source.freshnessPolicy.id,
  );
}
