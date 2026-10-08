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
  const MarkRepository(this.runtime);

  final AppRuntime runtime;

  String _draftId(ActorContext actor) => switch (actor) {
    PersonalActorContext() => 'mark:personal',
    SpaceActorContext(:final space) => 'mark:space:' + space.slug,
  };

  String _owner(ActorContext actor) => switch (actor) {
    PersonalActorContext() => 'profile',
    SpaceActorContext(:final space) => 'space:' + space.slug,
  };

  Future<void> saveDraft({
    required ActorContext actor,
    required String input,
    required String inputKind,
    Map<String, String>? selected,
    List<Map<String, dynamic>> attachments = const [],
  }) async {
    final drafts = runtime.drafts;
    if (drafts == null) return;
    await drafts.saveLocal(
      draftId: _draftId(actor),
      owner: _owner(actor),
      resourceKind: 'mark_intake',
      resourceId: _draftId(actor),
      payload: {
        'version': 1,
        'actor_context': ActorContextCodec.encode(actor),
        'input': input,
        'input_kind': inputKind,
        'selected': selected,
        'attachments': attachments,
      },
    );
  }

  Future<Map<String, dynamic>?> readDraft(ActorContext actor) async {
    final drafts = runtime.drafts;
    if (drafts == null) return null;
    final draft = await drafts.read(
      owner: _owner(actor),
      resourceKind: 'mark_intake',
      resourceId: _draftId(actor),
    );
    return draft?.payload;
  }

  Future<void> clearDraft(ActorContext actor) async {
    final drafts = runtime.drafts;
    if (drafts == null) return;
    await drafts.delete(
      owner: _owner(actor),
      resourceKind: 'mark_intake',
      resourceId: _draftId(actor),
    );
  }

  Future<MarkResult> submit({
    required ActorContext actor,
    required String input,
    String inputKind = 'text',
    Map<String, String>? selected,
    List<Map<String, dynamic>> attachments = const [],
  }) async {
    await saveDraft(
      actor: actor,
      input: input,
      inputKind: inputKind,
      selected: selected,
      attachments: attachments,
    );

    final api = runtime.api;
    if (api == null) {
      return const MarkResult(
        state: 'offline_draft',
        message: 'Enregistré sur cet appareil. L’action sera possible lorsque Makolo pourra revalider le contexte.',
        offline: true,
      );
    }

    final context = <String, dynamic>{
      if (selected != null) 'selected': selected,
    };

    try {
      final response = switch (actor) {
        PersonalActorContext() => await api.post(
          'api/v1/me/mark/',
          body: {
            'input': {'kind': inputKind, 'value': input},
            'context': context,
          },
        ),
        SpaceActorContext(:final space, :final perspective) => await api.post(
          'api/v1/organizations/workspaces/' + space.slug + '/mark/',
          body: {
            'input': {'kind': inputKind, 'value': input},
            'context': {
              ...context,
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
      if (result.state == 'completed') await clearDraft(actor);
      return result;
    } on MakoloTransportError {
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
