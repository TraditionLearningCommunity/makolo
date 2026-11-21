import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../network/api_error.dart';

class MarkResult {
  const MarkResult({
    required this.state,
    this.message,
    this.question,
    this.action,
    this.handoff,
    this.links = const {},
    this.raw = const {},
    this.offline = false,
  });

  final String state;
  final String? message;
  final Map<String, dynamic>? question;
  final Map<String, dynamic>? action;
  final Map<String, dynamic>? handoff;
  final Map<String, dynamic> links;
  final Map<String, dynamic> raw;
  final bool offline;

  bool get needsInput => state == 'needs_clarification';
}

class MarkRepository {
  MarkRepository(this.runtime);

  final AppRuntime runtime;
  final Map<String, Future<void>> _draftWrites = {};

  String _draftId(ActorContext actor) => switch (actor) {
    PersonalActorContext() => 'mark:personal',
    SpaceActorContext(:final space) => 'mark:space:${space.slug}',
  };

  String _owner(ActorContext actor) => switch (actor) {
    PersonalActorContext() => 'profile',
    SpaceActorContext(:final space) => 'space:${space.slug}',
  };

  Future<void> saveDraft({
    required ActorContext actor,
    required String input,
    required String inputKind,
    Map<String, String>? selected,
    List<Map<String, dynamic>> attachments = const [],
    List<String> links = const [],
    Map<String, String>? teamMember,
    String? pendingConfirmationCode,
    String? pendingConfirmationKey,
  }) {
    final drafts = runtime.drafts;
    if (drafts == null) return Future<void>.value();
    final id = _draftId(actor);
    final payload = <String, dynamic>{
      'version': 1,
      'actor_context': ActorContextCodec.encode(actor),
      'input': input,
      'input_kind': inputKind,
      'selected': selected == null ? null : Map<String, String>.of(selected),
      'attachments': [
        for (final item in attachments) Map<String, dynamic>.of(item),
      ],
      'links': List<String>.of(links),
      if (teamMember != null) 'team_member': Map<String, String>.of(teamMember),
      'pending_confirmation_code': ?pendingConfirmationCode,
      'pending_confirmation_key': ?pendingConfirmationKey,
    };
    // Autosave, share ingress, confirmation and deletion can interleave.
    // Serialize by actor and snapshot each payload before it is enqueued.
    final previous = _draftWrites[id] ?? Future<void>.value();
    final write = previous
        .catchError((Object _) {})
        .then(
          (_) => drafts.saveLocal(
            draftId: id,
            owner: _owner(actor),
            resourceKind: 'mark_intake',
            resourceId: id,
            payload: payload,
          ),
        );
    _draftWrites[id] = write;
    return write;
  }

  Future<Map<String, dynamic>?> readDraft(ActorContext actor) async {
    final drafts = runtime.drafts;
    if (drafts == null) return null;
    final id = _draftId(actor);
    final pending = _draftWrites[id];
    if (pending != null) {
      await pending.catchError((Object _) {});
    }
    final draft = await drafts.read(
      owner: _owner(actor),
      resourceKind: 'mark_intake',
      resourceId: id,
    );
    return draft?.payload;
  }

  Future<void> clearDraft(ActorContext actor) async {
    final drafts = runtime.drafts;
    if (drafts == null) return;
    final id = _draftId(actor);
    final pending = _draftWrites[id];
    if (pending != null) {
      await pending.catchError((Object _) {});
    }
    await drafts.delete(
      owner: _owner(actor),
      resourceKind: 'mark_intake',
      resourceId: id,
    );
  }

  Future<MarkResult> submit({
    required ActorContext actor,
    required String input,
    String inputKind = 'text',
    Map<String, String>? selected,
    List<Map<String, dynamic>> attachments = const [],
    List<String> links = const [],
    Map<String, String>? teamMember,
    bool allowTextOnly = false,
    Map<String, dynamic>? confirmation,
    String? idempotencyKey,
  }) async {
    await saveDraft(
      actor: actor,
      input: input,
      inputKind: inputKind,
      selected: selected,
      attachments: attachments,
      links: links,
      teamMember: teamMember,
      pendingConfirmationCode: confirmation?['code']?.toString(),
      pendingConfirmationKey: idempotencyKey,
    );

    // FileRecords are local references. Neither Mark owner API accepts media
    // yet: never silently claim to have submitted these attachments.
    if ((attachments.isNotEmpty || links.isNotEmpty) &&
        (!allowTextOnly || input.trim().isEmpty)) {
      if (attachments.isNotEmpty) {
        return const MarkResult(
          state: 'local_attachments_only',
          message: 'Pièces conservées sur cet appareil. Aucun fichier n’a été transmis à Makolo.',
        );
      }
      return const MarkResult(
        state: 'local_references_only',
        message: 'Liens conservés dans le brouillon. Ils ne sont pas interprétés ni transmis automatiquement.',
      );
    }

    final api = runtime.api;
    if (api == null) {
      return const MarkResult(
        state: 'offline_draft',
        message: 'Enregistré sur cet appareil. L’action sera possible lorsque Makolo pourra revalider le contexte.',
        offline: true,
      );
    }

    final context = <String, dynamic>{
      ...?selected == null ? null : {'selected': selected},
      'confirmation': ?confirmation,
      'idempotency_key': ?idempotencyKey,
    };

    try {
      final response = switch (actor) {
        PersonalActorContext() => await api.post(
          'api/v1/me/mark/',
          body: {
            'input': {
              'kind': allowTextOnly ? 'text' : inputKind,
              'value': input,
            },
            'context': context,
          },
        ),
        SpaceActorContext(:final space, :final perspective) => await api.post(
          'api/v1/organizations/workspaces/${space.slug}/mark/',
          body: {
            'input': {
              'kind': allowTextOnly ? 'text' : inputKind,
              'value': input,
            },
            'context': {
              ...context,
              'team_member': ?teamMember,
              if (!perspective.isAll) 'responsibility': perspective.id,
            },
          },
        ),
      };

      final envelope = response.jsonObject();
      final data = envelope['data'] is Map<String, dynamic>
          ? envelope['data'] as Map<String, dynamic>
          : envelope;
      final result = MarkResult(
        state: data['state']?.toString() ?? 'unknown',
        message: data['message']?.toString(),
        question: _map(data['question']),
        action: _map(data['action']),
        handoff: _map(data['handoff']),
        links: _map(data['links']) ?? const {},
        raw: data,
      );
      // A completed text-only action does not dispose of unsent local media.
      if (result.state == 'completed' && attachments.isEmpty && links.isEmpty) {
        await clearDraft(actor);
      }
      return result;
    } on MakoloTransportError {
      if (confirmation != null) {
        // The owner may have committed the mutation before transport failed.
        // Do not label it a draft or retry it blindly.
        return const MarkResult(
          state: 'confirmation_unknown',
          message:
              'Le résultat n’a pas pu être vérifié. Consultez le propriétaire '
              'avant de renouveler cette action.',
          offline: true,
        );
      }
      return const MarkResult(
        state: 'offline_draft',
        message: 'Enregistré sur cet appareil. Makolo n’a pas pu revalider le contexte à distance.',
        offline: true,
      );
    } on MakoloApiError catch (error) {
      return MarkResult(
        state: error.statusCode == 403 ? 'forbidden' : 'failed',
        message: error.message,
      );
    }
  }

  static Map<String, dynamic>? _map(Object? value) {
    if (value is! Map) return null;
    return {
      for (final entry in value.entries)
        if (entry.key is String) entry.key as String: entry.value,
    };
  }
}
