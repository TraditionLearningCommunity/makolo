import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_theme.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import 'space_attention_presentation.dart';
import 'space_repository.dart';

class SpaceDiscoverScreen extends StatefulWidget {
  const SpaceDiscoverScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  State<SpaceDiscoverScreen> createState() => _SpaceDiscoverScreenState();
}

class _SpaceDiscoverScreenState extends State<SpaceDiscoverScreen> {
  static const _loadingDelay = Duration(milliseconds: 150);

  Timer? _loadingTimer;
  String? _spaceId;
  bool _showLoading = false;
  final Set<String> _refreshingSources = <String>{};

  SpaceActorContext? get _actor {
    final actor = widget.runtime.actorContext?.value;
    return actor is SpaceActorContext ? actor : null;
  }

  String? get _currentSpaceId => _actor?.space.id;

  @override
  void initState() {
    super.initState();
    _spaceId = _currentSpaceId;
    widget.runtime.actorContext?.addListener(_onActorContextChanged);
    _armLoading();
    WidgetsBinding.instance.addPostFrameCallback((_) => unawaited(_acquire()));
  }

  @override
  void didUpdateWidget(covariant SpaceDiscoverScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(_onActorContextChanged);
      widget.runtime.actorContext?.addListener(_onActorContextChanged);
      _onActorContextChanged();
    }
  }

  void _onActorContextChanged() {
    final nextSpaceId = _currentSpaceId;
    if (nextSpaceId == _spaceId) return;
    _spaceId = nextSpaceId;
    _loadingTimer?.cancel();
    if (mounted) {
      setState(() => _showLoading = false);
    }
    _armLoading();
    unawaited(_acquire());
  }

  void _armLoading() {
    _loadingTimer?.cancel();
    final armedSpaceId = _currentSpaceId;
    if (armedSpaceId == null) return;
    _loadingTimer = Timer(_loadingDelay, () {
      if (!mounted || _currentSpaceId != armedSpaceId) return;
      setState(() => _showLoading = true);
    });
  }

  bool _isCurrent(SpaceActorContext actor) =>
      _actor?.space.id == actor.space.id;

  Future<void> _acquire() async {
    final repository = widget.runtime.space;
    final actor = _actor;
    if (repository == null || repository.sync == null || actor == null) return;

    final source = repository.discoverSource(actor.space);
    final local = await repository.readDiscover(actor.space);
    final sourceState = await repository.readSource(source);
    if (!_isCurrent(actor)) return;

    final freshness = local == null
        ? null
        : WorkspaceContextRepository.surfaceFreshness.evaluate(
            local,
            now: DateTime.now(),
            invalidated: sourceState.invalidated,
          );
    if (local == null ||
        sourceState.invalidated ||
        sourceState.lastErrorCode != null ||
        freshness != FreshnessState.fresh) {
      await _refresh(actor);
    }
  }

  Future<void> _refresh([SpaceActorContext? requestedActor]) async {
    final repository = widget.runtime.space;
    final actor = requestedActor ?? _actor;
    if (repository == null || repository.sync == null || actor == null) return;
    final source = repository.discoverSource(actor.space);
    if (!_refreshingSources.add(source.sourceKey)) return;
    try {
      await repository.refreshDiscover(actor.space);
    } finally {
      _refreshingSources.remove(source.sourceKey);
    }
  }

  @override
  Widget build(BuildContext context) {
    final repository = widget.runtime.space;
    final actor = _actor;
    if (repository == null || actor == null) {
      return const SizedBox.shrink();
    }

    final source = repository.discoverSource(actor.space);
    return StreamBuilder<StoredProjection?>(
      stream: repository.watchDiscover(actor.space),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<OwnerSourceState>(
          stream: repository.watchSource(source),
          initialData: OwnerSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final presentation = SpaceAttentionPresentation.resolve(
              projection: projectionSnapshot.data,
              source: sourceSnapshot.data ?? OwnerSourceState.unknown,
              now: DateTime.now(),
            );
            return SpaceDiscoverView(
              spaceId: actor.space.id,
              presentation: presentation,
              showLoading: _showLoading,
              onRefresh: _refresh,
            );
          },
        );
      },
    );
  }

  @override
  void dispose() {
    _loadingTimer?.cancel();
    widget.runtime.actorContext?.removeListener(_onActorContextChanged);
    super.dispose();
  }
}

class SpaceDiscoverView extends StatelessWidget {
  const SpaceDiscoverView({
    super.key,
    required this.spaceId,
    required this.presentation,
    required this.showLoading,
    required this.onRefresh,
  });

  final String spaceId;
  final SpaceAttentionPresentation presentation;
  final bool showLoading;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: onRefresh,
      child: ListView(
        key: Key('space-discover:$spaceId'),
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(
          MakoloSpacing.lg,
          MakoloSpacing.lg,
          MakoloSpacing.lg,
          MakoloSpacing.xl,
        ),
        children: [
          Semantics(
            header: true,
            child: Text(
              'Qu’est-ce qui pourrait nous aider à avancer ?',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
          ),
          const SizedBox(height: MakoloSpacing.xl),
          _state(),
          if (presentation.hasRefreshFailure ||
              presentation.needsFreshnessCaution) ...[
            const SizedBox(height: MakoloSpacing.lg),
            const InlineMessage(
              message:
                  'Cette vue n’a pas pu être actualisée. '
                  'La dernière connaissance disponible est conservée.',
            ),
          ],
        ],
      ),
    );
  }

  Widget _state() {
    return switch (presentation.state) {
      SpaceAttentionState.initial =>
        showLoading
            ? const SizedBox(
                height: 180,
                child: MakoloLoadingState(label: 'Mise à jour…'),
              )
            : const SizedBox(height: 180),
      SpaceAttentionState.unavailable => const MakoloEmptyState(
        title: 'Aucune possibilité n’est présentée pour le moment.',
        body:
            'Makolo ne dispose pas d’une sélection suffisamment établie '
            'pour vous proposer des pistes ici.',
        icon: Icons.hourglass_empty_rounded,
      ),
      SpaceAttentionState.failure => MakoloErrorState(
        message: 'Impossible de mettre cette vue à jour pour le moment.',
        onRetry: () => unawaited(onRefresh()),
      ),
    };
  }
}
