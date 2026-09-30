import '../data/local/profile_store.dart';
import '../sync/freshness.dart';

class ResourceReference {
  const ResourceReference({
    required this.kind,
    required this.id,
    required this.projectionKind,
    this.label,
  });

  final String kind;
  final String id;
  final String projectionKind;
  final String? label;
}

class DraftReference {
  const DraftReference({
    required this.draftId,
    required this.resourceKind,
    required this.updatedAt,
    this.resourceId,
  });

  final String draftId;
  final String resourceKind;
  final String? resourceId;
  final DateTime updatedAt;
}

class PendingOperationReference {
  const PendingOperationReference({
    required this.operationId,
    required this.operationKind,
    required this.state,
    this.resourceKind,
    this.resourceId,
  });

  final String operationId;
  final String operationKind;
  final String state;
  final String? resourceKind;
  final String? resourceId;
}

class ProjectionPresentationModel {
  const ProjectionPresentationModel({
    required this.available,
    required this.payload,
    required this.freshness,
    required this.resources,
    required this.drafts,
    required this.pendingOperations,
  });

  final bool available;
  final Map<String, dynamic>? payload;
  final FreshnessState? freshness;
  final List<ResourceReference> resources;
  final List<DraftReference> drafts;
  final List<PendingOperationReference> pendingOperations;

  bool get hasPending => pendingOperations.isNotEmpty;
}

class ProjectionSelector {
  const ProjectionSelector();

  ProjectionPresentationModel select({
    required StoredProjection? projection,
    required FreshnessPolicy freshnessPolicy,
    required DateTime now,
    bool forAction = false,
    bool sourceInvalidated = false,
    Iterable<ResourceReference> resources = const [],
    Iterable<DraftReference> drafts = const [],
    Iterable<PendingOperationReference> pendingOperations = const [],
  }) {
    final resourceList = resources.toList(growable: false)
      ..sort((a, b) {
        final kindOrder = a.kind.compareTo(b.kind);
        return kindOrder != 0 ? kindOrder : a.id.compareTo(b.id);
      });
    final draftList = drafts.toList(growable: false)
      ..sort((a, b) {
        final timeOrder = b.updatedAt.compareTo(a.updatedAt);
        return timeOrder != 0 ? timeOrder : a.draftId.compareTo(b.draftId);
      });
    final pendingList = pendingOperations.toList(growable: false)
      ..sort((a, b) => a.operationId.compareTo(b.operationId));

    return ProjectionPresentationModel(
      available: projection != null,
      payload: projection?.payload,
      freshness: projection == null
          ? null
          : freshnessPolicy.evaluate(
              projection,
              now: now,
              forAction: forAction,
              invalidated: sourceInvalidated,
            ),
      resources: List.unmodifiable(resourceList),
      drafts: List.unmodifiable(draftList),
      pendingOperations: List.unmodifiable(pendingList),
    );
  }
}
