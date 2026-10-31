import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../network/api_error.dart';
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
        if (projection?.payload['has_more'] == true)
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: MakoloSpacing.md,
              vertical: MakoloSpacing.sm,
            ),
            child: TextButton.icon(
              onPressed: () => context.go('/space/work'),
              icon: const Icon(Icons.arrow_forward_rounded),
              label: const Text('Poursuivre dans Métier'),
            ),
          ),
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
  List<Map<String, dynamic>>? _fullTeam;
  bool _teamUnavailable = false;
  bool _teamMutating = false;

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_onActorChanged);
    _resolveSpace();
  }

  void _onActorChanged() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    super.dispose();
  }

  Future<void> _resolveSpace() async {
    final repository = widget.runtime.space;
    if (repository == null) {
      if (mounted) setState(() { _denied = true; _loading = false; });
      return;
    }
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
    if (widget.depth == 'team') {
      await _loadTeam(summary.identity);
    }
  }

  Future<void> _loadTeam(SpaceActorIdentity space) async {
    final api = widget.runtime.api;
    if (api == null) return; // Offline preview remains usable until expiry.
    try {
      final response = await api.get(
        'api/v1/organizations/workspaces/' +
        Uri.encodeComponent(space.slug) + '/team/',
      );
      final decoded = jsonDecode(response.body);
      if (decoded is! List) throw const FormatException('Expected team list');
      final rows = <Map<String, dynamic>>[
        for (final item in decoded)
          if (item is Map)
            {for (final entry in item.entries)
              if (entry.key is String) entry.key as String: entry.value},
      ];
      final actor = widget.runtime.actorContext?.value;
      if (!mounted || actor is! SpaceActorContext ||
          actor.space.id != space.id) return;
      setState(() { _fullTeam = rows; _teamUnavailable = false; });
    } on MakoloApiError catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401 || error.statusCode == 403 ||
          error.statusCode == 404) {
        setState(() { _denied = true; _fullTeam = null; });
      } else {
        setState(() => _teamUnavailable = true);
      }
    } on Object {
      if (mounted) setState(() => _teamUnavailable = true);
    }
  }

  List<Map<String, String>> _teamRoleOptions(Map<String, dynamic> payload) {
    final options = _map(payload['team'])?['role_options'];
    if (options is! List) return const [];
    return [
      for (final entry in options)
        if (_map(entry) case final role?)
          if (_text(role['code']) != null)
            {
              'code': _text(role['code'])!,
              'label': _text(role['label']) ?? _text(role['code'])!,
            },
    ];
  }

  Future<void> _mutateTeam(Future<void> Function() operation, {
    String successMessage = 'Équipe actualisée.',
  }) async {
    final current = widget.runtime.actorContext?.value;
    if (_teamMutating || current is! SpaceActorContext ||
        _space == null || current.space.id != _space!.id) return;
    final spaceId = current.space.id;
    setState(() => _teamMutating = true);
    try {
      await operation();
      if (!mounted || widget.runtime.actorContext?.value
          is! SpaceActorContext) return;
      final currentActor = widget.runtime.actorContext!.value as SpaceActorContext;
      if (currentActor.space.id != spaceId) return;
      await _loadTeam(_space!);
      final repository = widget.runtime.space;
      if (repository != null) {
        try {
          await repository.refreshUs(_space!);
          await repository.refreshRelationships(_space!);
        } on Object {
          // Server mutation succeeded, but local projections may be older.
        }
      }
      if (mounted && !_denied) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(successMessage)),
        );
      }
    } on MakoloApiError catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401 || error.statusCode == 403 ||
          error.statusCode == 404) {
        setState(() { _denied = true; _fullTeam = null; });
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text(
            'Action indisponible. Le serveur n’a pas confirmé la modification.',
          )),
        );
      }
    } finally {
      if (mounted) setState(() => _teamMutating = false);
    }
  }

  Future<void> _addTeamMember(Map<String, dynamic> payload) async {
    final api = widget.runtime.api;
    final roles = _teamRoleOptions(payload);
    if (api == null || roles.isEmpty) return;
    final email = TextEditingController();
    var selected = roles.first['code']!;
    try {
      final result = await showDialog<Map<String, String>>(
        context: context,
        builder: (context) => StatefulBuilder(
          builder: (context, update) => AlertDialog(
            title: const Text('Ajouter un collaborateur'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('La personne doit déjà posséder un Profil Makolo. '
                  'Le rôle choisi crée une autorité explicite et sera vérifié '
                  'par le serveur.'),
                TextField(
                  controller: email,
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(labelText: 'E-mail du Profil'),
                ),
                DropdownButtonFormField<String>(
                  initialValue: selected,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Responsabilité'),
                  items: [
                    for (final role in roles)
                      DropdownMenuItem(
                        value: role['code']!,
                        child: Text(role['label']!),
                      ),
                  ],
                  onChanged: (value) {
                    if (value != null) update(() => selected = value);
                  },
                ),
              ],
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context),
                child: const Text('Annuler')),
              FilledButton(
                onPressed: () {
                  if (email.text.trim().isEmpty) return;
                  Navigator.pop(context, {
                    'email': email.text.trim(),
                    'role': selected,
                  });
                },
                child: const Text('Ajouter'),
              ),
            ],
          ),
        ),
      );
      if (result == null || !mounted) return;
      await _mutateTeam(() async {
        await api.post(
          'api/v1/organizations/workspaces/' +
            Uri.encodeComponent(widget.slug) + '/team/',
          body: result,
        );
      });
    } finally {
      email.dispose();
    }
  }

  Future<void> _changeTeamRole(
    Map<String, dynamic> row, Map<String, dynamic> payload,
  ) async {
    final api = widget.runtime.api;
    final roles = _teamRoleOptions(payload);
    final id = _text(row['id']);
    if (api == null || roles.isEmpty || id == null) return;
    final currentRole = _text(row['responsibility']);
    String? selected = roles.any((role) => role['code'] == currentRole)
        ? currentRole : null;
    final chosen = await showDialog<String>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Changer la responsabilité'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_depthRowLabel(row)),
              const Text('Ce changement peut modifier l’autorité du membre.'),
              DropdownButtonFormField<String>(
                initialValue: selected,
                isExpanded: true,
                hint: const Text('Choisir un rôle'),
                items: [
                  for (final role in roles)
                    DropdownMenuItem(
                      value: role['code']!,
                      child: Text(role['label']!),
                    ),
                ],
                onChanged: (value) {
                  if (value != null) update(() => selected = value);
                },
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context),
              child: const Text('Annuler')),
            FilledButton(
              onPressed: selected == null ? null : () => Navigator.pop(context, selected),
              child: const Text('Confirmer le changement'),
            ),
          ],
        ),
      ),
    );
    if (chosen == null || !mounted) return;
    await _mutateTeam(() async {
      await api.patch(
        'api/v1/organizations/workspaces/' +
          Uri.encodeComponent(widget.slug) + '/team/' +
          Uri.encodeComponent(id) + '/',
        body: {'role': chosen},
      );
    });
  }

  Future<void> _transferOwnership(Map<String, dynamic> payload) async {
    final capabilities = _map(payload['capabilities']);
    final api = widget.runtime.api;
    if (api == null || _fullTeam == null ||
        capabilities?['manage_team'] != true ||
        capabilities?['manage_ownership'] != true) return;
    final candidates = _fullTeam!.where((row) =>
      _text(row['id']) != null && row['responsibility'] != 'space_owner'
    ).toList();
    if (candidates.isEmpty) return;
    String? chosenId;
    var relinquish = false;
    final selection = await showDialog<Map<String, Object>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Transférer la propriété du Space'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Choisissez un collaborateur actif. '
                'Le serveur validera sa présence et votre autorité.'),
              DropdownButtonFormField<String>(
                isExpanded: true,
                initialValue: chosenId,
                hint: const Text('Nouveau propriétaire'),
                items: [
                  for (final row in candidates)
                    DropdownMenuItem(
                      value: _text(row['id'])!,
                      child: Text(_depthRowLabel(row)),
                    ),
                ],
                onChanged: (value) => update(() => chosenId = value),
              ),
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Renoncer aussi à mon rôle de propriétaire'),
                subtitle: const Text('Décoché : je reste propriétaire.'),
                value: relinquish,
                onChanged: (value) =>
                  update(() => relinquish = value == true),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Annuler'),
            ),
            FilledButton(
              onPressed: chosenId == null ? null : () =>
                Navigator.pop(context, <String, Object>{
                  'target_membership_id': chosenId!,
                  'relinquish_current_owner': relinquish,
                }),
              child: const Text('Confirmer le transfert'),
            ),
          ],
        ),
      ),
    );
    if (selection == null || !mounted) return;
    await _mutateTeam(() async {
      await api.post(
        'api/v1/organizations/workspaces/' +
          Uri.encodeComponent(widget.slug) + '/ownership/transfer/',
        body: selection,
      );
    }, successMessage: 'Gouvernance actualisée.');
  }

  Future<void> _removeTeamMember(Map<String, dynamic> row) async {
    final api = widget.runtime.api;
    final id = _text(row['id']);
    if (api == null || id == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Retirer ce collaborateur ?'),
        content: Text('Retirer ' + _depthRowLabel(row) +
          ' peut révoquer ses Mandates. Le serveur protège '
          'les contraintes de propriété du Space.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false),
            child: const Text('Annuler')),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Confirmer le retrait'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    await _mutateTeam(() async {
      await api.delete(
        'api/v1/organizations/workspaces/' +
          Uri.encodeComponent(widget.slug) + '/team/' +
          Uri.encodeComponent(id) + '/',
      );
    });
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
    final current = widget.runtime.actorContext?.value;
    if (current is! SpaceActorContext || current.space.id != _space!.id) {
      return const MakoloSecondaryScreen(
        title: 'Nous',
        message: 'Ce Space n’est plus le contexte actif. Revenez à Nous pour continuer.',
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
            final allowed = link == '/space/${widget.slug}/us/${widget.depth}';
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
    final allRows = widget.depth == 'team' && _fullTeam != null
        ? _fullTeam!
        : section?['items'];
    final rows = allRows is List
        ? allRows.where((row) =>
            widget.depth != 'responsibilities' ||
            _map(row)?['combined'] != true).toList()
        : const <dynamic>[];
    final canManageTeam = widget.depth == 'team' &&
        _map(payload['capabilities'])?['manage_team'] == true &&
        _teamRoleOptions(payload).isNotEmpty;
    final canTransferOwnership = widget.depth == 'ownership' &&
        _map(payload['capabilities'])?['manage_team'] == true &&
        _map(payload['capabilities'])?['manage_ownership'] == true;
    final intro = switch (widget.depth) {
      'team' => 'Les collaborateurs actuellement visibles dans cette équipe.',
      'responsibilities' =>
        'Ce que nous portons, sans déduire une autorité de cette responsabilité.',
      'ownership' =>
        'Les Mandates de propriétaire actifs, indépendants des appartenances.',
      'trust' => 'Les faits de vérification établis dans ce contexte.',
      _ => 'Cette profondeur dépend de vos droits sur le Space actif.',
    };
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: ListView(
        padding: const EdgeInsets.all(MakoloSpacing.lg),
        children: [
          Text(title, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: MakoloSpacing.sm),
          Text(intro, style: Theme.of(context).textTheme.bodyMedium),
          const SizedBox(height: MakoloSpacing.lg),
          if (canManageTeam) ...[
            FilledButton.icon(
              onPressed: _teamMutating ? null : () => _addTeamMember(payload),
              icon: const Icon(Icons.person_add_alt_1_outlined),
              label: const Text('Ajouter un collaborateur'),
            ),
            const SizedBox(height: MakoloSpacing.md),
          ],
          if (canTransferOwnership) ...[
            if (_fullTeam == null)
              OutlinedButton.icon(
                onPressed: _teamMutating
                  ? null : () => _loadTeam(_space!),
                icon: const Icon(Icons.group_add_outlined),
                label: const Text('Choisir un nouveau propriétaire'),
              )
            else if (_fullTeam!.any((row) =>
                _text(row['id']) != null &&
                row['responsibility'] != 'space_owner'))
              FilledButton.icon(
                onPressed: _teamMutating
                  ? null : () => _transferOwnership(payload),
                icon: const Icon(Icons.verified_user_outlined),
                label: const Text('Transférer la propriété'),
              )
            else
              const Text('Aucun collaborateur éligible à ce transfert.'),
            if (_teamUnavailable)
              TextButton(
                onPressed: () => _loadTeam(_space!),
                child: const Text('Réessayer de charger les collaborateurs'),
              ),
            const SizedBox(height: MakoloSpacing.md),
          ],
          if (_teamMutating) const LinearProgressIndicator(),
          if (widget.depth == 'trust')
            Text(
              _map(payload['trust'])?['verified'] == true
                  ? 'Des faits publics de vérification sont établis.'
                  : 'Aucun fait public de vérification établi.',
            )
          else if (rows.isEmpty)
            const MakoloEmptyState(title: 'Aucun élément visible ici.')
          else
            for (final row in rows)
              Padding(
                padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                child: MakoloCard(
                  padding: const EdgeInsets.all(MakoloSpacing.md),
                  child: Row(children: [
                    Icon(
                      widget.depth == 'team'
                          ? Icons.person_outline
                          : widget.depth == 'ownership'
                              ? Icons.verified_user_outlined
                              : Icons.assignment_ind_outlined,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(width: MakoloSpacing.md),
                    Expanded(child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(_depthRowLabel(row),
                          style: Theme.of(context).textTheme.titleSmall),
                        const SizedBox(height: 4),
                        Text(_depthRowDetail(row),
                          style: Theme.of(context).textTheme.bodySmall),
                        if (canManageTeam && _fullTeam != null &&
                            _map(row) != null &&
                            (_map(row)?['responsibility'] != 'space_owner' ||
                             _map(payload['capabilities'])?['manage_ownership'] == true)) ...[
                          const SizedBox(height: MakoloSpacing.sm),
                          Wrap(
                            spacing: MakoloSpacing.sm,
                            children: [
                              TextButton(
                                onPressed: _teamMutating
                                    ? null : () => _changeTeamRole(
                                        _map(row)!, payload),
                                child: const Text('Responsabilité'),
                              ),
                              TextButton(
                                onPressed: _teamMutating
                                    ? null : () => _removeTeamMember(_map(row)!),
                                child: const Text('Retirer'),
                              ),
                            ],
                          ),
                        ],
                      ],
                    )),
                  ]),
                ),
              ),
          if (widget.depth == 'team' && _fullTeam == null &&
              section?['has_more'] == true)
            const Text('Aperçu partiel : tous les membres ne sont pas chargés.'),
          if (widget.depth == 'team' && _teamUnavailable)
            TextButton.icon(
              onPressed: () => _loadTeam(_space!),
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Réessayer de charger l’équipe'),
            ),
          if (widget.depth == 'ownership' && section?['has_more'] == true)
            const Text('Aperçu partiel de la gouvernance institutionnelle.'),
        ],
      ),
    );
  }

  String _depthTitle(String depth) => switch (depth) {
    'team' => 'Équipe',
    'responsibilities' => 'Responsabilités',
    'relationships' => 'Personnes & relations',
    'ownership' => 'Gouvernance',
    'trust' => 'Confiance',
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
        (widget.depth == 'team' ? 'Membre de l’équipe' :
          widget.depth == 'ownership' ? 'Mandate de propriétaire' :
          'Portée collective');
  }

  Map<String, dynamic>? _map(Object? value) => value is Map
      ? value.map((key, value) => MapEntry(key.toString(), value))
      : null;

  String? _text(Object? value) =>
      value is String && value.trim().isNotEmpty ? value.trim() : null;
}
