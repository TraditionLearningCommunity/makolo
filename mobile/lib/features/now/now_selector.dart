import '../../data/local/profile_store.dart';
import '../../design/surface_states.dart';
import '../../navigation/destination.dart';
import '../../presentation/contracts/now_presentation.dart';
import '../../sync/freshness.dart';

class NowSelection {
  const NowSelection({
    required this.situations,
    required this.state,
    this.selectionState,
    this.actorAttentionState,
    this.serverFreshnessState,
    this.continuation = const NowContinuationPresentation(
      state: NowContinuationState.unknown,
    ),
    this.calmIsCurrent = true,
  });

  final List<NowSituationPresentation> situations;
  final MakoloSurfacePresentation state;
  final String? selectionState;
  final String? actorAttentionState;
  final String? serverFreshnessState;
  final NowContinuationPresentation continuation;
  final bool calmIsCurrent;

  bool get isCalm =>
      selectionState == 'empty' &&
      actorAttentionState == 'calm' &&
      calmIsCurrent &&
      state.availability == MakoloAvailabilityCue.empty &&
      state.failure == MakoloFailureCue.none &&
      situations.isEmpty;
}

class NowSelector {
  const NowSelector();

  static const FreshnessPolicy _freshnessPolicy = FreshnessPolicy(
    id: 'personal.now',
    revalidateAfterFreshUntil: true,
  );

  NowSelection select({
    required StoredProjection? projection,
    required DateTime now,
    MakoloReachabilityCue reachability = MakoloReachabilityCue.unknown,
    MakoloCommitCue commit = MakoloCommitCue.none,
    MakoloFailureCue failure = MakoloFailureCue.none,
    bool refreshing = false,
    bool sourceInvalidated = false,
  }) {
    if (projection == null) {
      return NowSelection(
        situations: const [],
        state: MakoloSurfacePresentation(
          availability: MakoloAvailabilityCue.initial,
          reachability: reachability,
          commit: commit,
          failure: failure,
          refreshing: refreshing,
        ),
      );
    }

    final items = projection.payload['items'];
    if (items is! List) {
      return NowSelection(
        situations: const [],
        state: MakoloSurfacePresentation(
          availability: MakoloAvailabilityCue.empty,
          failure: MakoloFailureCue.blocking,
          freshness: _freshnessCue(
            _freshnessPolicy.evaluate(projection, now: now),
          ),
          reachability: reachability,
          commit: commit,
          refreshing: refreshing,
        ),
      );
    }

    final situations = <NowSituationPresentation>[];
    for (var index = 0; index < items.length; index++) {
      final situation = _situation(items[index], index: index);
      if (situation != null) situations.add(situation);
    }

    final malformedOnly = items.isNotEmpty && situations.isEmpty;
    final isC0 = _string(projection.payload['surface']) == 'now_me';
    final selectionState =
        _nestedString(projection.payload, 'selection', 'state') ??
        (!isC0 ? (items.isEmpty ? 'empty' : 'ready') : null);
    final serverFreshnessState = _nestedString(
      projection.payload,
      'freshness',
      'state',
    );
    final terminalState =
        _nestedString(projection.payload, 'terminal', 'state') ??
        (!isC0 && items.isEmpty ? 'empty' : null);
    final actorAttentionState =
        _string(projection.payload['actor_attention_state']) ??
        (!isC0 && items.isEmpty ? 'calm' : null);
    final freshness = _freshnessPolicy.evaluate(
      projection,
      now: now,
      invalidated: sourceInvalidated,
    );
    final calmIsCurrent =
        selectionState == 'empty' &&
        terminalState == 'empty' &&
        situations.isEmpty &&
        freshness != FreshnessState.revalidationRequired &&
        freshness != FreshnessState.expired;
    var contractFailure = failure;
    if (malformedOnly) {
      contractFailure = MakoloFailureCue.blocking;
    } else if (selectionState == 'unavailable' ||
        serverFreshnessState == 'unavailable') {
      contractFailure = situations.isEmpty
          ? MakoloFailureCue.blocking
          : MakoloFailureCue.recoverable;
    } else if ((selectionState == 'partial' ||
            serverFreshnessState == 'partial') &&
        failure == MakoloFailureCue.none) {
      contractFailure = MakoloFailureCue.recoverable;
    }

    return NowSelection(
      situations: List.unmodifiable(situations),
      selectionState: selectionState,
      actorAttentionState: actorAttentionState,
      serverFreshnessState: serverFreshnessState,
      continuation: _continuation(projection.payload['continuation']),
      calmIsCurrent: calmIsCurrent,
      state: MakoloSurfacePresentation(
        availability: situations.isEmpty
            ? MakoloAvailabilityCue.empty
            : MakoloAvailabilityCue.content,
        freshness: _freshnessCue(freshness),
        reachability: reachability,
        commit: commit,
        failure: contractFailure,
        refreshing: refreshing,
      ),
    );
  }

  NowSituationPresentation? _situation(Object? raw, {required int index}) {
    if (raw is! Map) return null;

    final c0Identity = _string(raw['id']);
    final identity = c0Identity ?? _string(raw['key']);
    final sourceRaw = raw['source'];
    final legacySource = sourceRaw is Map ? sourceRaw : const {};
    final handoff = _ownerHandoff(raw['handoffs']);
    final kind = _string(handoff?['target']) ?? _string(legacySource['kind']);
    final id = _string(handoff?['id']) ?? _string(legacySource['id']);
    final title = _string(raw['title']);
    final summary = _string(raw['summary']);
    final humanContext = _string(raw['human_context']) ?? title;
    final serverState = _semanticString(raw['state'], 'value');
    final meaning = c0Identity != null
        ? _string(raw['state_meaning']) ?? summary ?? serverState ?? title
        : summary ?? title;
    if (identity == null || humanContext == null || meaning == null) {
      return null;
    }

    final capabilities = _strings(raw['capabilities']);
    final links = raw['links'] is Map ? raw['links'] as Map : const {};
    final detailLink = _string(handoff?['link']) ?? _string(links['detail']);

    final timing = raw['timing'];
    final metadata = <String>[];
    final whyNowRaw = raw['why_now'];
    final whyNowReason = _semanticString(whyNowRaw, 'reason');
    String? whyNow = _semanticString(whyNowRaw, 'meaning');
    if (timing is Map) {
      whyNow ??= _string(timing['label']) ?? _string(timing['why_now']);
      for (final key in const [
        'deadline_at',
        'due_at',
        'starts_at',
        'deadline',
      ]) {
        final value = _string(timing[key]);
        if (value != null) metadata.add(value);
      }
    }

    final reference = StructuredDestination(kind: 'now', id: identity);
    final ownerDestination = kind == null || id == null
        ? null
        : StructuredDestination(kind: kind, id: id, link: detailLink);
    final response = raw['response'] is Map ? raw['response'] as Map : const {};
    final responseType = _string(response['type']);
    final responseLabel = _string(response['label']);
    final businessActions = raw['business_actions'];
    String? businessCapability;
    if (businessActions is List) {
      for (final action in businessActions) {
        if (action is! Map) continue;
        businessCapability = _string(action['capability']);
        if (businessCapability != null) break;
      }
    }
    final legacyCanOpen = capabilities.contains('open_detail');

    return NowSituationPresentation(
      identity: identity,
      reference: reference,
      humanContext: humanContext,
      meaning: meaning,
      whyNow: whyNow,
      whyNowReason: whyNowReason,
      serverState: serverState,
      consequence: _semanticString(raw['consequence'], 'effect'),
      consequenceState: _semanticString(raw['consequence'], 'state'),
      turn: _semanticString(raw['turn'], 'type'),
      responseType: responseType,
      emphasis: index == 0
          ? NowPresentationEmphasis.primary
          : NowPresentationEmphasis.secondary,
      responseLabel: responseLabel ?? (legacyCanOpen ? 'Ouvrir' : null),
      responseCapability:
          businessCapability ?? (legacyCanOpen ? 'open_detail' : null),
      metadata: List.unmodifiable(metadata),
      freshness: MakoloFreshnessCue.unknown,
      ownerDestination: ownerDestination,
    );
  }

  Map? _ownerHandoff(Object? value) {
    if (value is! List) return null;
    for (final item in value) {
      if (item is Map && _string(item['type']) == 'owner') return item;
    }
    return null;
  }

  String? _nestedString(Map payload, String parent, String child) {
    final value = payload[parent];
    return value is Map ? _string(value[child]) : null;
  }

  String? _semanticString(Object? value, String field) {
    if (value is Map) return _string(value[field]);
    return _string(value);
  }

  NowContinuationPresentation _continuation(Object? raw) {
    if (raw == null) {
      return const NowContinuationPresentation(state: NowContinuationState.end);
    }
    if (raw is! Map) {
      return const NowContinuationPresentation(
        state: NowContinuationState.unknown,
      );
    }
    final state = switch (_string(raw['state'])?.toLowerCase()) {
      'more' => NowContinuationState.more,
      'end' => NowContinuationState.end,
      _ => NowContinuationState.unknown,
    };
    return NowContinuationPresentation(
      state: state,
      token: state == NowContinuationState.more ? _string(raw['token']) : null,
    );
  }

  String? _string(Object? value) {
    if (value is! String) return null;
    final trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }

  List<String> _strings(Object? value) {
    if (value is! List) return const [];
    return value
        .whereType<String>()
        .map((item) => item.trim())
        .where((item) => item.isNotEmpty)
        .toList(growable: false);
  }

  MakoloFreshnessCue _freshnessCue(FreshnessState state) {
    return switch (state) {
      FreshnessState.fresh => MakoloFreshnessCue.current,
      FreshnessState.usableButOld => MakoloFreshnessCue.oldObservation,
      FreshnessState.refreshRecommended =>
        MakoloFreshnessCue.refreshRecommended,
      FreshnessState.revalidationRequired =>
        MakoloFreshnessCue.revalidationRequired,
      FreshnessState.expired => MakoloFreshnessCue.expired,
    };
  }
}
