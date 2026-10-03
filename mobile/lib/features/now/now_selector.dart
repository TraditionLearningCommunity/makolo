import '../../data/local/profile_store.dart';
import '../../design/surface_states.dart';
import '../../navigation/destination.dart';
import '../../presentation/contracts/now_presentation.dart';
import '../../sync/freshness.dart';

class NowSelection {
  const NowSelection({
    required this.situations,
    required this.state,
  });

  final List<NowSituationPresentation> situations;
  final MakoloSurfacePresentation state;

  bool get isCalm =>
      state.availability == MakoloAvailabilityCue.empty && situations.isEmpty;
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

    return NowSelection(
      situations: List.unmodifiable(situations),
      state: MakoloSurfacePresentation(
        availability: situations.isEmpty
            ? MakoloAvailabilityCue.empty
            : MakoloAvailabilityCue.content,
        freshness: _freshnessCue(
          _freshnessPolicy.evaluate(projection, now: now),
        ),
        reachability: reachability,
        commit: commit,
        failure: failure,
        refreshing: refreshing,
      ),
    );
  }

  NowSituationPresentation? _situation(Object? raw, {required int index}) {
    if (raw is! Map) return null;

    final sourceRaw = raw['source'];
    if (sourceRaw is! Map) return null;

    final kind = _string(sourceRaw['kind']);
    final id = _string(sourceRaw['id']);
    final title = _string(raw['title']);
    final summary = _string(raw['summary']);
    if (kind == null || id == null || title == null) return null;

    final capabilities = _strings(raw['capabilities']);
    final links = raw['links'] is Map ? raw['links'] as Map : const {};
    final detailLink = _string(links['detail']);
    final hasOpenCapability = capabilities.contains('open_detail');

    final timing = raw['timing'];
    final metadata = <String>[];
    String? whyNow;
    if (timing is Map) {
      whyNow = _string(timing['label']) ?? _string(timing['why_now']);
      for (final key in const ['due_at', 'starts_at', 'deadline']) {
        final value = _string(timing[key]);
        if (value != null) metadata.add(value);
      }
    }

    final reference = StructuredDestination(
      kind: kind,
      id: id,
      link: detailLink,
    );

    return NowSituationPresentation(
      reference: reference,
      humanContext: title,
      meaning: summary ?? title,
      whyNow: whyNow,
      emphasis: index == 0
          ? NowPresentationEmphasis.primary
          : NowPresentationEmphasis.secondary,
      responseLabel: hasOpenCapability ? 'Ouvrir' : null,
      responseCapability: hasOpenCapability ? 'open_detail' : null,
      metadata: List.unmodifiable(metadata),
      freshness: MakoloFreshnessCue.unknown,
      ownerDestination: reference,
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
