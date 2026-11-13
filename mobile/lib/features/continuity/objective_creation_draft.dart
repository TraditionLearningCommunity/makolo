import '../../repositories/draft_repository.dart';

/// Durable, Profile-scoped creation intent. This is not a confirmed
/// Project/Dossier or an outbox command: the Objectives owner alone creates it.
///
/// A request that may have reached Django is held as verification_required.
/// Neither a cold restart nor a network recovery may replay that request.
class ObjectiveCreationDraft {
  ObjectiveCreationDraft({
    required this.repository,
    required this.profileId,
    required this.kind,
    String? spaceId,
  }) : resourceId = '$kind:${spaceId ?? 'personal'}',
       draftId = 'objectives:create:$profileId:$kind:${spaceId ?? 'personal'}' {
    if (profileId.isEmpty ||
        repository.profileId != profileId ||
        (kind != 'project' && kind != 'dossier')) {
      throw ArgumentError('Invalid Objectives draft owner scope');
    }
  }

  static const owner = 'Objectives';
  static const resourceKind = 'objective.creation';

  final DraftRepository repository;
  final String profileId;
  final String kind;
  final String resourceId;
  final String draftId;
  Future<void> _writes = Future<void>.value();

  Future<StoredLocalDraft?> read() async {
    await _writes;
    return repository.read(
      owner: owner,
      resourceKind: resourceKind,
      resourceId: resourceId,
    );
  }

  Future<void> save(
    Map<String, dynamic> values, {
    bool verifiedReopen = false,
  }) {
    // Capture at invocation time: editing autosave cannot overwrite a later
    // verification_required or confirmed snapshot.
    final snapshot = Map<String, dynamic>.from(values);
    final operation = _writes.then(
      (_) => repository.database.transaction(() async {
        // The row is shared by every screen for this Profile and owner scope.
        // A stale screen must never downgrade a potentially sent or confirmed
        // draft, even if it uses another ObjectiveCreationDraft instance.
        final prior = await repository.read(
          owner: owner,
          resourceKind: resourceKind,
          resourceId: resourceId,
        );
        final previousState = prior?.payload['submission_state'];
        final nextState = snapshot['submission_state'];
        if (previousState == 'confirmed' && nextState != 'confirmed') {
          throw StateError('A confirmed creation must be cleared explicitly');
        }
        if (previousState == 'verification_required' &&
            nextState != 'confirmed' &&
            !verifiedReopen) {
          throw StateError('Review is required before resubmitting creation');
        }
        if (previousState == 'confirmed' &&
            nextState == 'confirmed' &&
            prior?.payload['confirmed_id'] != snapshot['confirmed_id']) {
          throw StateError('A confirmed creation cannot change identity');
        }
        await repository.saveLocal(
          draftId: draftId,
          owner: owner,
          resourceKind: resourceKind,
          resourceId: resourceId,
          payload: snapshot,
        );
      }),
    );
    _writes = operation.then<void>(
      (_) {},
      onError: (Object _, StackTrace _) {},
    );
    return operation;
  }

  Future<void> clear() {
    final operation = _writes.then(
      (_) => repository.delete(
        owner: owner,
        resourceKind: resourceKind,
        resourceId: resourceId,
      ),
    );
    _writes = operation.then<void>(
      (_) {},
      onError: (Object _, StackTrace _) {},
    );
    return operation.then<void>((_) {});
  }
}
