import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../navigation/secondary_screen.dart';
import '../../sync/owner_source_state.dart';
import '../../design/surface_states.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../sync/freshness.dart';
import 'space_repository.dart';
import 'space_work_surface.dart';
import 'space_us_surface.dart';
import '../now/now_screen.dart';
import '../now/now_selector.dart';

enum SpaceShellSurface { now, discover, work, us }

StatefulShellBranch spaceNowBranch(AppRuntime runtime) => _spaceBranch(
  runtime: runtime,
  path: '/space/now',
  surface: SpaceShellSurface.now,
);

StatefulShellBranch spaceDiscoveryBranch(AppRuntime runtime) => _spaceBranch(
  runtime: runtime,
  path: '/space/discover',
  surface: SpaceShellSurface.discover,
);

StatefulShellBranch spaceWorkBranch(AppRuntime runtime) => _spaceBranch(
  runtime: runtime,
  path: '/space/work',
  surface: SpaceShellSurface.work,
);

StatefulShellBranch spaceUsBranch(AppRuntime runtime) => _spaceBranch(
  runtime: runtime,
  path: '/space/us',
  surface: SpaceShellSurface.us,
);

StatefulShellBranch _spaceBranch({
  required AppRuntime runtime,
  required String path,
  required SpaceShellSurface surface,
}) => StatefulShellBranch(
  routes: [
    GoRoute(
      path: path,
      builder: (context, state) =>
          SpaceShellRootScreen(runtime: runtime, surface: surface),
    ),
  ],
);

class SpaceShellRootScreen extends StatefulWidget {
  const SpaceShellRootScreen({
    super.key,
    required this.runtime,
    required this.surface,
  });

  final AppRuntime runtime;
  final SpaceShellSurface surface;

  @override
  State<SpaceShellRootScreen> createState() => _SpaceShellRootScreenState();
}

class _SpaceShellRootScreenState extends State<SpaceShellRootScreen> {
  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_onActorContextChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => unawaited(_refresh()));
  }

  @override
  void didUpdateWidget(covariant SpaceShellRootScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(_onActorContextChanged);
      widget.runtime.actorContext?.addListener(_onActorContextChanged);
    }
  }

  void _onActorContextChanged() {
    if (!mounted) return;
    setState(() {});
    unawaited(_refresh());
  }

  Future<void> _refresh() async {
    final repository = widget.runtime.space;
    final actor = widget.runtime.actorContext?.value;
    if (repository == null ||
        repository.sync == null ||
        actor is! SpaceActorContext) {
      return;
    }
    try {
      await switch (widget.surface) {
        SpaceShellSurface.now => repository.refreshNow(
          actor.space,
          actor.perspective,
        ),
        SpaceShellSurface.discover => repository.refreshDiscover(actor.space),
        SpaceShellSurface.work => repository.refreshWork(
          actor.space,
          actor.perspective,
        ),
        SpaceShellSurface.us => repository.refreshUs(actor.space),
      };
    } on Object {
      // Existing local projections stay visible when refresh is unavailable.
    }
  }

  Stream<StoredProjection?>? _stream(
    WorkspaceContextRepository repository,
    SpaceActorContext actor,
  ) => switch (widget.surface) {
    SpaceShellSurface.now => repository.watchNow(
      actor.space,
      actor.perspective,
    ),
    SpaceShellSurface.discover => repository.watchDiscover(actor.space),
    SpaceShellSurface.work => repository.watchWork(
      actor.space,
      actor.perspective,
    ),
    SpaceShellSurface.us => repository.watchUs(actor.space),
  };

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_onActorContextChanged);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final repository = widget.runtime.space;
    final actor = widget.runtime.actorContext?.value;
    if (repository == null || actor is! SpaceActorContext) {
      return const SizedBox.shrink();
    }

    final source = switch (widget.surface) {
      SpaceShellSurface.now => repository.nowSource(
        actor.space,
        actor.perspective,
      ),
      SpaceShellSurface.discover => repository.discoverSource(actor.space),
      SpaceShellSurface.work => repository.workSource(
        actor.space,
        actor.perspective,
      ),
      SpaceShellSurface.us => repository.usSource(actor.space),
    };
    return StreamBuilder<OwnerSourceState>(
      key: ValueKey(source.sourceKey),
      stream: repository.watchSource(source),
      builder: (context, status) {
        if (status.data?.invalidated == true) {
          return const MakoloEmptyState(
            title: 'Autorité Space révoquée ou indisponible.',
            icon: Icons.lock_outline,
          );
        }
        return StreamBuilder<StoredProjection?>(
          key: ValueKey(
            '${widget.surface.name}:${actor.space.id}:'
            '${SpaceSyncKeys.perspectiveKey(actor.perspective)}',
          ),
          stream: _stream(repository, actor),
          builder: (context, snapshot) {
            final projection = snapshot.data;
            final freshness = projection == null
                ? null
                : WorkspaceContextRepository.surfaceFreshness.evaluate(
                    projection,
                    now: DateTime.now(),
                  );
            if (freshness == FreshnessState.expired) {
              return MakoloErrorState(
                message: 'Cette observation a expiré.',
                onRetry: _refresh,
              );
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                MakoloFreshnessNotice(
                  freshness: const ProjectionSurfaceAdapter().freshnessCue(
                    freshness,
                  ),
                ),
                if (status.data?.lastErrorCode != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(
                            projection == null
                                ? 'Actualisation indisponible.'
                                : 'Actualisation indisponible. Observation conservée du ${projection.receivedAt.toLocal()}',
                          ),
                        ),
                        TextButton(
                          onPressed: _refresh,
                          child: const Text('Réessayer'),
                        ),
                      ],
                    ),
                  ),
                Expanded(
                  child: _SpaceProjectionBody(
                    surface: widget.surface,
                    projection: snapshot.data,
                    fallbackSpaceName: actor.space.slug,
                    onRefresh: _refresh,
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }
}

class _SpaceProjectionBody extends StatelessWidget {
  const _SpaceProjectionBody({
    required this.surface,
    required this.projection,
    required this.fallbackSpaceName,
    required this.onRefresh,
  });

  final SpaceShellSurface surface;
  final StoredProjection? projection;
  final String fallbackSpaceName;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    final payload = projection?.payload;
    if (payload == null) {
      return _message('Cette vue n’est pas disponible pour le moment.');
    }

    return switch (surface) {
      SpaceShellSurface.now => _spaceNowBody(context),
      SpaceShellSurface.discover => _attentionBody(
        payload,
        emptyMessage: 'Rien à découvrir pour le moment.',
      ),
      SpaceShellSurface.work => SpaceWorkSurface(payload: payload),
      SpaceShellSurface.us => _usBody(context, payload),
    };
  }

  Widget _spaceNowBody(BuildContext context) {
    final selection = const NowSelector().select(
      projection: projection,
      now: DateTime.now(),
    );
    if (selection.situations.isEmpty &&
        _map(projection?.payload['selection'])?['state'] == 'partial') {
      return Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const MakoloEmptyState(
            title: 'Aucune situation établie dans cette perspective.',
            body: 'La couverture actuelle reste partielle. Makolo ne peut pas '
                'encore conclure que tout est en ordre pour cet Espace.',
            icon: Icons.info_outline_rounded,
          ),
          TextButton.icon(
            onPressed: onRefresh,
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('Actualiser'),
          ),
        ],
      );
    }
    final space = _map(projection?.payload['space']);
    final nowView = NowView(
      key: ValueKey(
        'space-now:${_text(space?['id'])}:${_text(projection?.payload['responsibility'])}',
      ),
      selection: selection,
      onRetry: onRefresh,
      onOpenOwner: (destination) async {
        final path = NowScreen.ownerPathFor(destination);
        if (path == null) return;
        await context.push(path);
        if (context.mounted) await onRefresh();
      },
    );
    if (_map(projection?.payload['selection'])?['state'] != 'partial') {
      return nowView;
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: MakoloSpacing.md),
          child: MakoloStatus(
            label: 'Certaines situations restent hors de cette sélection.',
            tone: MakoloStatusTone.info,
            icon: Icons.info_outline_rounded,
          ),
        ),
        Expanded(child: nowView),
      ],
    );
  }

  Widget _attentionBody(
    Map<String, dynamic> payload, {
    required String emptyMessage,
  }) {
    final selection = payload['selection'];
    final state = selection is Map ? selection['state'] : null;
    if (state != 'established' && state != 'available' && state != 'partial') {
      return _message('Cette vue n’est pas disponible pour le moment.');
    }
    final items = payload['items'];
    if (items is! List || items.isEmpty) {
      return _message(
        state == 'established' || state == 'available' ? emptyMessage : 'La sélection est partielle. Aucun élément connu dans cet aperçu.',
      );
    }
    return _message(
      '${items.length} élément${items.length > 1 ? 's' : ''} à consulter.',
    );
  }

  Widget _usBody(BuildContext context, Map<String, dynamic> payload) =>
      SpaceUsSurface(
        payload: payload,
        fallbackSpaceName: fallbackSpaceName,
      );

  Map<String, dynamic>? _map(Object? value) => value is Map
      ? value.map((key, value) => MapEntry(key.toString(), value))
      : null;

  String? _text(Object? value) {
    if (value is! String || value.trim().isEmpty) return null;
    return value.trim();
  }

  Widget _message(String message) => ListView(
    padding: const EdgeInsets.all(MakoloSpacing.lg),
    children: [MakoloEmptyState(title: message)],
  );
}

class SpaceNousDepthScreen extends StatefulWidget {
  const SpaceNousDepthScreen({
    super.key,
    required this.runtime,
    required this.slug,
    required this.depth,
  });

  final AppRuntime runtime;
  final String slug;
  final String depth;

  @override
  State<SpaceNousDepthScreen> createState() => _SpaceNousDepthScreenState();
}

class _SpaceNousDepthScreenState extends State<SpaceNousDepthScreen> {
  SpaceActorIdentity? _space;
  bool _denied = false;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _resolveSpace();
  }

  Future<void> _resolveSpace() async {
    final repository = widget.runtime.space;
    if (repository == null) return;
    final inventory = await repository.readInventory();
    SpaceSummary? summary;
    for (final candidate in inventory) {
      if (candidate.identity.slug == widget.slug) {
        summary = candidate;
        break;
      }
    }
    if (!mounted) return;
    if (summary == null) {
      setState(() {
        _denied = true;
        _loading = false;
      });
      return;
    }
    final actor = widget.runtime.actorContext?.value;
    if (actor is! SpaceActorContext || actor.space.id != summary.identity.id) {
      await widget.runtime.actorContext?.selectSpace(summary.identity);
    }
    if (!mounted) return;
    setState(() {
      _space = summary!.identity;
      _loading = false;
    });
    try {
      await repository.refreshUs(summary.identity);
    } on Object {
      // The source state below turns a revoked or unavailable depth into a
      // safe local message; it never promotes cached authority.
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const MakoloSecondaryScreen(
        title: 'Nous',
        message: 'Vérification du contexte Space…',
      );
    }
    if (_denied || _space == null) {
      return const MakoloSecondaryScreen(
        title: 'Nous',
        message: 'Ce contexte Space n’est pas disponible pour votre Profil.',
      );
    }
    final repository = widget.runtime.space!;
    final source = repository.usSource(_space!);
    return StreamBuilder<OwnerSourceState>(
      stream: repository.watchSource(source),
      initialData: OwnerSourceState.unknown,
      builder: (context, sourceSnapshot) {
        final state = sourceSnapshot.data ?? OwnerSourceState.unknown;
        if (state.invalidated || state.lastErrorCode != null) {
          return MakoloSecondaryScreen(
            title: _depthTitle(widget.depth),
            message: 'Cette profondeur n’est plus disponible avec l’autorité actuelle. Le contexte public de l’Espace reste protégé.',
          );
        }
        return StreamBuilder<StoredProjection?>(
          stream: repository.watchUs(_space!),
          builder: (context, snapshot) {
            final payload = snapshot.data?.payload;
            if (payload == null) {
              return MakoloSecondaryScreen(
                title: _depthTitle(widget.depth),
                message: 'Cette profondeur ne peut pas être actualisée pour le moment.',
              );
            }
            final handoffs = payload['handoffs'];
            final link = handoffs is Map ? handoffs[widget.depth] : null;
            final allowed = link is String;
            if (!allowed) {
              return MakoloSecondaryScreen(
                title: _depthTitle(widget.depth),
                message:
                    'Cette profondeur n’est pas autorisée dans ce contexte.',
              );
            }
            return _depthBody(context, payload);
          },
        );
      },
    );
  }

  Widget _depthBody(BuildContext context, Map<String, dynamic> payload) {
    final title = _depthTitle(widget.depth);
    final section = widget.depth == 'team'
        ? _map(payload['team'])
        : widget.depth == 'responsibilities'
        ? _map(payload['responsibilities'])
        : widget.depth == 'ownership'
        ? _map(payload['ownership'])
        : null;
    final rows = section?['items'];
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: ListView(
        padding: const EdgeInsets.all(MakoloSpacing.lg),
        children: [
          Text('Nous', style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: MakoloSpacing.sm),
          Text(
            'Cette profondeur reste attachée au Space actif et à son autorité serveur.',
          ),
          const SizedBox(height: MakoloSpacing.lg),
          if (widget.depth == 'trust')
            Text(
              _map(payload['trust'])?['verified'] == true
                  ? 'Identité de l’Espace vérifiée dans un périmètre connu.'
                  : 'Aucun fait public de vérification actif n’est projeté.',
            )
          else if (rows is List && rows.isNotEmpty)
            for (final row in rows)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(_depthRowLabel(row)),
                subtitle: Text(_depthRowDetail(row)),
              )
          else
            const Text('Aucun élément visible dans ce contexte.'),
        ],
      ),
    );
  }

  String _depthTitle(String depth) => switch (depth) {
    'team' => 'Équipe',
    'responsibilities' => 'Responsabilités',
    'relationships' => 'Personnes & relations',
    'ownership' => 'Ownership',
    'trust' => 'Trust',
    'pilot' => 'Piloter',
    'settings' => 'Paramètres institutionnels',
    _ => 'Nous',
  };

  String _depthRowLabel(Object? value) {
    final row = _map(value);
    final profile = _map(row?['profile']);
    return _text(profile?['name']) ??
        _text(row?['label']) ??
        _text(row?['name']) ??
        'Élément';
  }

  String _depthRowDetail(Object? value) {
    final row = _map(value);
    final responsibility = _map(row?['responsibility']);
    final activity = _map(row?['activity']);
    return _text(responsibility?['label']) ??
        _text(activity?['title']) ??
        'Fait projeté par le serveur';
  }

  Map<String, dynamic>? _map(Object? value) => value is Map
      ? value.map((key, value) => MapEntry(key.toString(), value))
      : null;

  String? _text(Object? value) =>
      value is String && value.trim().isNotEmpty ? value.trim() : null;
}
