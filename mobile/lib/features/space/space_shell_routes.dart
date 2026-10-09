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
import 'space_repository.dart';
import 'space_work_surface.dart';

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
      return _message('Cette vue nÔÇÖest pas disponible pour le moment.');
    }

    return switch (surface) {
      SpaceShellSurface.now => _attentionBody(
        payload,
        emptyMessage: 'Rien ne demande votre attention pour le moment.',
      ),
      SpaceShellSurface.discover => _attentionBody(
        payload,
        emptyMessage: 'Rien ├á d├®couvrir pour le moment.',
      ),
      SpaceShellSurface.work => SpaceWorkSurface(payload: payload),
      SpaceShellSurface.us => _usBody(context, payload),
    };
  }

  Widget _attentionBody(
    Map<String, dynamic> payload, {
    required String emptyMessage,
  }) {
    final selection = payload['selection'];
    final state = selection is Map ? selection['state'] : null;
    if (state == 'unavailable') {
      return _message('Cette vue nÔÇÖest pas disponible pour le moment.');
    }
    final items = payload['items'];
    if (items is! List || items.isEmpty) return _message(emptyMessage);
    return _message(
      '${items.length} ├®l├®ment${items.length > 1 ? 's' : ''} ├á consulter.',
    );
  }

  Widget _usBody(BuildContext context, Map<String, dynamic> payload) {
    final identity = _map(payload['identity']);
    final name = _text(identity?['name']) ?? fallbackSpaceName;
    final authority = _map(payload['authority']);
    final limited =
        authority?['scope'] == 'activity_limited' ||
        authority?['limited_to_activities'] == true;
    final team = _map(payload['team']);
    final responsibilities = _map(payload['responsibilities']);
    final ownership = _map(payload['ownership']);
    final trust = _map(payload['trust']);
    final capabilities = _map(payload['capabilities']);
    final handoffs = _map(payload['handoffs']);
    final teamItems = team?['items'] is List
        ? team!['items'] as List
        : const [];
    final responsibilityItems = responsibilities?['items'] is List
        ? responsibilities!['items'] as List
        : const [];
    final ownershipItems = ownership?['items'] is List
        ? ownership!['items'] as List
        : const [];
    return ListView(
      key: const Key('space-us-projection'),
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      children: [
        Semantics(
          header: true,
          child: Text(
            'Nous',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
        ),
        const SizedBox(height: MakoloSpacing.xs),
        Text(name, style: Theme.of(context).textTheme.titleLarge),
        if (_text(identity?['description']) case final description?) ...[
          const SizedBox(height: MakoloSpacing.xs),
          Text(description),
        ],
        if (limited) ...[
          const SizedBox(height: MakoloSpacing.md),
          const MakoloStatus(
            label: 'Contexte limit├® ├á certaines activit├®s',
            tone: MakoloStatusTone.info,
            icon: Icons.lock_outline,
          ),
        ],
        const SizedBox(height: MakoloSpacing.xl),
        _usSection(
          context,
          title: '├ëquipe',
          description: limited
              ? 'La composition globale nÔÇÖest pas visible dans ce contexte.'
              : 'Les personnes qui font vivre cet Espace.',
          child: limited
              ? const Text('D├®tails r├®serv├®s ├á une autorit├® Space.')
              : _usRows(
                  teamItems,
                  empty: 'Aucun membre visible pour le moment.',
                ),
        ),
        if (handoffs?['team'] is String)
          _usHandoff(context, handoffs!['team'] as String, 'Voir lÔÇÖ├®quipe'),
        if (handoffs?['responsibilities'] is String)
          _usHandoff(
            context,
            handoffs!['responsibilities'] as String,
            'Approfondir les responsabilit├®s',
          ),
        if (handoffs?['relationships'] is String)
          _usHandoff(
            context,
            handoffs!['relationships'] as String,
            'Personnes & relations',
          ),
        _usSection(
          context,
          title: 'Responsabilit├®s',
          description:
              'Qui porte quoi, sans confondre responsabilit├® et autorit├®.',
          child: _usRows(
            responsibilityItems,
            empty: 'Aucune responsabilit├® visible dans ce contexte.',
            label: (item) => _text(_map(item)?['label']) ?? 'Responsabilit├®',
            detail: (item) {
              final row = _map(item);
              final activity = _map(row?['activity']);
              return _text(activity?['title']) ?? 'Port├®e de lÔÇÖEspace';
            },
          ),
        ),
        if (!limited && ownershipItems.isNotEmpty)
          _usSection(
            context,
            title: 'Ownership',
            description: 'Une responsabilit├® institutionnelle distincte de lÔÇÖ├®quipe.',
            child: _usRows(ownershipItems, empty: ''),
          ),
        if (!limited && handoffs?['ownership'] is String)
          _usHandoff(
            context,
            handoffs!['ownership'] as String,
            'Ouvrir Ownership',
          ),
        _usSection(
          context,
          title: 'Confiance',
          description: 'Des faits contextualis├®s, jamais un score global.',
          child: Text(
            trust?['verified'] == true
                ? 'Identit├® de lÔÇÖEspace v├®rifi├®e dans un p├®rim├¿tre connu.'
                : 'Aucun fait public de v├®rification actif nÔÇÖest projet├®.',
          ),
        ),
        if (handoffs?['trust'] is String)
          _usHandoff(context, handoffs!['trust'] as String, 'Ouvrir Trust'),
        if (!limited && handoffs?['pilot'] is String)
          _usHandoff(context, handoffs!['pilot'] as String, 'Piloter'),
        if (!limited && capabilities?['update_space'] == true) ...[
          const SizedBox(height: MakoloSpacing.lg),
          Text(
            'Param├¿tres de lÔÇÖEspace restent une profondeur institutionnelle.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          if (handoffs?['settings'] is String)
            _usHandoff(
              context,
              handoffs!['settings'] as String,
              'Param├¿tres institutionnels',
            ),
        ],
      ],
    );
  }

  Widget _usHandoff(BuildContext context, String route, String label) => Align(
    alignment: Alignment.centerLeft,
    child: TextButton.icon(
      onPressed: () => context.push(route),
      icon: const Icon(Icons.arrow_forward_rounded),
      label: Text(label),
    ),
  );

  Widget _usSection(
    BuildContext context, {
    required String title,
    required String description,
    required Widget child,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
    child: MakoloSection(title: title, description: description, child: child),
  );

  Widget _usRows(
    List items, {
    required String empty,
    String Function(Object item)? label,
    String Function(Object item)? detail,
  }) {
    if (items.isEmpty) return Text(empty);
    return Column(
      children: [
        for (final item in items)
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(label?.call(item) ?? _rowLabel(item)),
            subtitle: Text(detail?.call(item) ?? _rowDetail(item)),
          ),
      ],
    );
  }

  String _rowLabel(Object item) {
    final row = _map(item);
    final profile = _map(row?['profile']);
    return _text(profile?['name']) ??
        _text(row?['name']) ??
        '├ël├®ment collectif';
  }

  String _rowDetail(Object item) {
    final row = _map(item);
    final responsibility = _map(row?['responsibility']);
    return _text(responsibility?['label']) ?? 'Fait collectif connu';
  }

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
        message: 'V├®rification du contexte SpaceÔÇª',
      );
    }
    if (_denied || _space == null) {
      return const MakoloSecondaryScreen(
        title: 'Nous',
        message: 'Ce contexte Space nÔÇÖest pas disponible pour votre Profil.',
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
            message: 'Cette profondeur nÔÇÖest plus disponible avec lÔÇÖautorit├® actuelle. Le contexte public de lÔÇÖEspace reste prot├®g├®.',
          );
        }
        return StreamBuilder<StoredProjection?>(
          stream: repository.watchUs(_space!),
          builder: (context, snapshot) {
            final payload = snapshot.data?.payload;
            if (payload == null) {
              return MakoloSecondaryScreen(
                title: _depthTitle(widget.depth),
                message: 'Cette profondeur ne peut pas ├¬tre actualis├®e pour le moment.',
              );
            }
            final handoffs = payload['handoffs'];
            final link = handoffs is Map ? handoffs[widget.depth] : null;
            final allowed = link is String;
            if (!allowed) {
              return MakoloSecondaryScreen(
                title: _depthTitle(widget.depth),
                message:
                    'Cette profondeur nÔÇÖest pas autoris├®e dans ce contexte.',
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
            'Cette profondeur reste attach├®e au Space actif et ├á son autorit├® serveur.',
          ),
          const SizedBox(height: MakoloSpacing.lg),
          if (widget.depth == 'trust')
            Text(
              _map(payload['trust'])?['verified'] == true
                  ? 'Identit├® de lÔÇÖEspace v├®rifi├®e dans un p├®rim├¿tre connu.'
                  : 'Aucun fait public de v├®rification actif nÔÇÖest projet├®.',
            )
          else if (rows is List && rows.isNotEmpty)
            for (final row in rows)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(_depthRowLabel(row)),
                subtitle: Text(_depthRowDetail(row)),
              )
          else
            const Text('Aucun ├®l├®ment visible dans ce contexte.'),
        ],
      ),
    );
  }

  String _depthTitle(String depth) => switch (depth) {
    'team' => '├ëquipe',
    'responsibilities' => 'Responsabilit├®s',
    'relationships' => 'Personnes & relations',
    'ownership' => 'Ownership',
    'trust' => 'Trust',
    'pilot' => 'Piloter',
    'settings' => 'Param├¿tres institutionnels',
    _ => 'Nous',
  };

  String _depthRowLabel(Object? value) {
    final row = _map(value);
    final profile = _map(row?['profile']);
    return _text(profile?['name']) ??
        _text(row?['label']) ??
        _text(row?['name']) ??
        '├ël├®ment';
  }

  String _depthRowDetail(Object? value) {
    final row = _map(value);
    final responsibility = _map(row?['responsibility']);
    final activity = _map(row?['activity']);
    return _text(responsibility?['label']) ??
        _text(activity?['title']) ??
        'Fait projet├® par le serveur';
  }

  Map<String, dynamic>? _map(Object? value) => value is Map
      ? value.map((key, value) => MapEntry(key.toString(), value))
      : null;

  String? _text(Object? value) =>
      value is String && value.trim().isNotEmpty ? value.trim() : null;
}
