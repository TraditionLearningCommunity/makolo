import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_theme.dart';
import 'space_repository.dart';

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

    return StreamBuilder<StoredProjection?>(
      key: ValueKey(
        '${widget.surface.name}:${actor.space.id}:'
        '${SpaceSyncKeys.perspectiveKey(actor.perspective)}',
      ),
      stream: _stream(repository, actor),
      builder: (context, snapshot) => _SpaceProjectionBody(
        surface: widget.surface,
        projection: snapshot.data,
        fallbackSpaceName: actor.space.slug,
      ),
    );
  }
}

class _SpaceProjectionBody extends StatelessWidget {
  const _SpaceProjectionBody({
    required this.surface,
    required this.projection,
    required this.fallbackSpaceName,
  });

  final SpaceShellSurface surface;
  final StoredProjection? projection;
  final String fallbackSpaceName;

  @override
  Widget build(BuildContext context) {
    final payload = projection?.payload;
    if (payload == null) {
      return _message('Cette vue n’est pas disponible pour le moment.');
    }

    return switch (surface) {
      SpaceShellSurface.now => _attentionBody(
        payload,
        emptyMessage: 'Rien ne demande votre attention pour le moment.',
      ),
      SpaceShellSurface.discover => _attentionBody(
        payload,
        emptyMessage: 'Rien à découvrir pour le moment.',
      ),
      SpaceShellSurface.work => _workBody(context, payload),
      SpaceShellSurface.us => _usBody(payload),
    };
  }

  Widget _attentionBody(
    Map<String, dynamic> payload, {
    required String emptyMessage,
  }) {
    final selection = payload['selection'];
    final state = selection is Map ? selection['state'] : null;
    if (state == 'unavailable') {
      return _message('Cette vue n’est pas disponible pour le moment.');
    }
    final items = payload['items'];
    if (items is! List || items.isEmpty) return _message(emptyMessage);
    return _message(
      '${items.length} élément${items.length > 1 ? 's' : ''} à consulter.',
    );
  }

  Widget _workBody(BuildContext context, Map<String, dynamic> payload) {
    final sections = payload['sections'];
    if (sections is! Map) {
      return _message('Cette vue n’est pas disponible pour le moment.');
    }
    const labels = <String, String>{
      'preparation': 'À préparer',
      'upcoming': 'À venir',
      'active': 'En cours',
      'blocked': 'Bloqués',
      'completed': 'Terminés',
    };
    final rows = <MapEntry<String, int>>[];
    final activeOccurrences = <Map<String, dynamic>>[];
    for (final entry in labels.entries) {
      final section = sections[entry.key];
      final items = section is Map ? section['items'] : null;
      if (items is List && items.isNotEmpty) {
        rows.add(MapEntry(entry.value, items.length));
        if (entry.key == 'active') {
          for (final item in items.whereType<Map>()) {
            final row = Map<String, dynamic>.from(item);
            final capabilities = row['capabilities'];
            final source = row['source'];
            if (source is Map &&
                source['kind'] == 'occurrence' &&
                capabilities is List &&
                capabilities.contains('open_day_of')) {
              activeOccurrences.add(row);
            }
          }
        }
      }
    }
    if (rows.isEmpty) {
      return _message('Aucune activité à afficher pour le moment.');
    }
    return ListView(
      key: const Key('space-work-projection'),
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      children: [
        for (final row in rows)
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(row.key),
            trailing: Text('${row.value}'),
          ),
        if (activeOccurrences.isNotEmpty) ...[
          const Divider(height: MakoloSpacing.xl),
          const Text(
            'Occurrences à opérer maintenant',
            style: TextStyle(fontWeight: FontWeight.w700),
          ),
          for (final item in activeOccurrences)
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(
                item['title'] is String
                    ? item['title'] as String
                    : 'Occurrence',
              ),
              subtitle: const Text('Ouvrir le Jour J Space'),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () {
                final source = item['source'];
                if (source is Map && source['id'] is String) {
                  context.push('/space/occurrences/${source['id']}/day-of');
                }
              },
            ),
        ],
      ],
    );
  }

  Widget _usBody(Map<String, dynamic> payload) {
    final identity = payload['identity'];
    final rawName = identity is Map ? identity['name'] : null;
    final name = rawName is String && rawName.trim().isNotEmpty
        ? rawName.trim()
        : fallbackSpaceName;
    return ListView(
      key: const Key('space-us-projection'),
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      children: [
        Text(name, style: const TextStyle(fontWeight: FontWeight.w700)),
      ],
    );
  }

  Widget _message(String message) => ListView(
    padding: const EdgeInsets.all(MakoloSpacing.lg),
    children: [MakoloEmptyState(title: message)],
  );
}
