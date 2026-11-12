import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';
import '../../design/behavior_primitives.dart';

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
import 'space_us_resources_screen.dart';
import 'space_us_authority_facts.dart';
import '../now/now_screen.dart';
import '../now/now_selector.dart';
import '../discovery/discovery_repository.dart';
import '../discovery/discovery_screens.dart';

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
    // Discover shares the canonical Discovery acquisition, not the old
    // Space-only attention snapshot. It refreshes through DiscoveryScreen.
    if (widget.surface == SpaceShellSurface.discover) return;
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
          const ActorPerspective.all(),
        ),
        SpaceShellSurface.discover => repository.refreshDiscover(actor.space),
        SpaceShellSurface.work => repository.refreshWork(
          actor.space,
          const ActorPerspective.all(),
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
      const ActorPerspective.all(),
    ),
    SpaceShellSurface.discover => repository.watchDiscover(actor.space),
    SpaceShellSurface.work => repository.watchWork(
      actor.space,
      const ActorPerspective.all(),
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

    if (widget.surface == SpaceShellSurface.discover) {
      final discovery = widget.runtime.discovery;
      if (discovery == null) {
        return const MakoloEmptyState(
          title: 'Découvrir n’est pas disponible pour le moment.',
        );
      }
      final query = DiscoveryQuery(
        spaceSlug: actor.space.slug,
        spaceId: actor.space.id,
      );
      return DiscoveryScreen(
        key: ValueKey('space-discovery:${actor.space.id}'),
        initialQuery: query,
        repository: discovery,
        onOpenActivity: (id) => context.push(
          Uri(
            path: '/discover/items/activity/${Uri.encodeComponent(id)}',
            queryParameters: {'context': 'space', 'space': actor.space.slug},
          ).toString(),
        ),
        onOpenItem: (family, id) => context.push(
          Uri(
            path:
                '/discover/items/${Uri.encodeComponent(family)}/'
                '${Uri.encodeComponent(id)}',
            queryParameters: {'context': 'space', 'space': actor.space.slug},
          ).toString(),
        ),
      );
    }

    final source = switch (widget.surface) {
      SpaceShellSurface.now => repository.nowSource(
        actor.space,
        const ActorPerspective.all(),
      ),
      SpaceShellSurface.discover => repository.discoverSource(actor.space),
      SpaceShellSurface.work => repository.workSource(
        actor.space,
        const ActorPerspective.all(),
      ),
      SpaceShellSurface.us => repository.usSource(actor.space),
    };
    return StreamBuilder<OwnerSourceState>(
      key: ValueKey(source.sourceKey),
      stream: repository.watchSource(source),
      builder: (context, status) {
        if (status.data?.invalidated == true) {
          return const MakoloEmptyState(
            title: 'Impossible d’accéder à cet Espace actuellement.',
            icon: Icons.lock_outline,
          );
        }
        return StreamBuilder<StoredProjection?>(
          key: ValueKey(
            '${widget.surface.name}:${actor.space.id}:'
            'all',
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
            // Stale locally acquired facts remain readable. Freshness is a
            // presentation cue, not evidence of withdrawn permission.
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Nous presents the retained owner snapshot without an extra
                // refresh banner. The shell already carries the transport cue.
                // Revoked access remains enforced by source.invalidated above.
                if (widget.surface != SpaceShellSurface.us)
                  MakoloFreshnessNotice(
                    freshness: const ProjectionSurfaceAdapter().freshnessCue(
                      freshness,
                    ),
                  ),
                Expanded(
                  child: _SpaceProjectionBody(
                    surface: widget.surface,
                    projection: snapshot.data,
                    fallbackSpaceName: actor.space.slug,
                    spaceId: actor.space.id,
                    onRefresh: _refresh,
                    mediaBaseUri: widget.runtime.api?.baseUri,
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
    required this.spaceId,
    required this.onRefresh,
    this.mediaBaseUri,
  });

  final SpaceShellSurface surface;
  final StoredProjection? projection;
  final String fallbackSpaceName;
  final String spaceId;
  final Future<void> Function() onRefresh;
  final Uri? mediaBaseUri;

  @override
  Widget build(BuildContext context) {
    final payload = projection?.payload;
    if (payload == null) {
      return _initialStructure(context);
    }

    return switch (surface) {
      SpaceShellSurface.now => _spaceNowBody(context),
      SpaceShellSurface.discover => _attentionBody(
        payload,
        emptyMessage: 'Rien à découvrir pour le moment.',
      ),
      SpaceShellSurface.work => SpaceWorkSurface(
        payload: payload,
        mediaBaseUri: mediaBaseUri,
      ),
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
            title: 'Rien à afficher pour le moment.',
            body:
                'Vous pouvez actualiser pour voir les dernières informations.',
            icon: Icons.info_outline_rounded,
          ),
          MakoloActionButton(
            label: 'Actualiser',
            onPressed: onRefresh,
            appearance: MakoloActionAppearance.quiet,
            icon: Icons.refresh_rounded,
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
            child: MakoloActionButton(
              label: 'Poursuivre dans Métier',
              onPressed: () => context.go('/space/work'),
              appearance: MakoloActionAppearance.quiet,
              icon: Icons.arrow_forward_rounded,
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
        onOpen: (route) async {
          await context.push(route);
          if (context.mounted) await onRefresh();
        },
      );

  Map<String, dynamic>? _map(Object? value) => value is Map
      ? value.map((key, value) => MapEntry(key.toString(), value))
      : null;

  String? _text(Object? value) {
    if (value is! String || value.trim().isEmpty) return null;
    return value.trim();
  }

  Widget _initialStructure(BuildContext context) {
    // The screen's composition is known even when the owner has never
    // provided this Space's content. Do not invent rows, counts or authority.
    final sections = switch (surface) {
      SpaceShellSurface.now => const ['Now'],
      SpaceShellSurface.discover => const ['Découvrir'],
      SpaceShellSurface.work => const ['Métier'],
      SpaceShellSurface.us => const [
        'Notre Passeport',
        'Nos démarches',
        'Notre espace',
      ],
    };
    return ListView(
      key: Key('space-initial-structure-${surface.name}'),
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      children: [
        for (final title in sections) ...[
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: MakoloSpacing.sm),
          const MakoloCard(child: MakoloSkeleton(lines: 3)),
          const SizedBox(height: MakoloSpacing.md),
        ],
      ],
    );
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
  Map<String, dynamic>? _authorityFacts;
  bool _authorityLoading = false;
  String? _authorityError;
  int _authorityRequestVersion = 0;

  @override
  void initState() {
    super.initState();
    if (widget.depth != 'resources') {
      widget.runtime.actorContext?.addListener(_onActorChanged);
      _resolveSpace();
    }
  }

  void _onActorChanged() {
    if (!mounted) return;
    // N3 authority is never retained across actor or perspective transitions.
    _authorityRequestVersion++;
    setState(() {
      _fullTeam = null;
      _teamUnavailable = false;
      _authorityFacts = null;
      _authorityLoading = false;
      _authorityError = null;
    });
    final current = widget.runtime.actorContext?.value;
    if (current is SpaceActorContext &&
        _space != null &&
        current.space.id == _space!.id) {
      final repository = widget.runtime.space;
      if (repository != null && repository.sync != null) {
        unawaited(repository.refreshUs(_space!).catchError((Object _) {}));
      }
      if (widget.depth == 'team' && widget.runtime.api != null) {
        unawaited(_loadTeam(_space!));
      }
      if (widget.depth == 'authority') {
        unawaited(_loadAuthority(_space!));
      }
    }
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    super.dispose();
  }

  Future<void> _resolveSpace() async {
    final repository = widget.runtime.space;
    if (repository == null) {
      if (mounted) {
        setState(() {
          _denied = true;
          _loading = false;
        });
      }
      return;
    }
    final actorBeforeLookup = widget.runtime.actorContext?.value;
    final inventory = await repository.readInventory();
    if (!mounted) return;
    // Never replace a user-initiated actor change that happened while the
    // inventory was loading for an old deep link.
    if (widget.runtime.actorContext?.value != actorBeforeLookup) {
      setState(() {
        _denied = true;
        _loading = false;
      });
      return;
    }
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
    if (widget.depth == 'authority') {
      await _loadAuthority(summary.identity);
    }
  }

  Future<void> _loadAuthority(SpaceActorIdentity space) async {
    final version = ++_authorityRequestVersion;
    final current = widget.runtime.actorContext?.value;
    final api = widget.runtime.api;
    if (current is! SpaceActorContext ||
        current.space.id != space.id ||
        api == null) {
      if (mounted) {
        setState(() {
          _authorityFacts = null;
          _authorityLoading = false;
          _authorityError = 'Connexion nécessaire pour consulter vos droits.';
        });
      }
      return;
    }
    setState(() {
      _authorityFacts = null;
      _authorityLoading = true;
      _authorityError = null;
    });
    try {
      final response = await api.get(
        'api/v1/organizations/workspaces/${Uri.encodeComponent(space.slug)}/us/authority/',
      );
      final payload = response.jsonObject();
      if (payload['space_id']?.toString() != space.id ||
          payload['mandates'] is! List) {
        throw const FormatException('Invalid N3 authority');
      }
      final active = widget.runtime.actorContext?.value;
      if (!mounted ||
          version != _authorityRequestVersion ||
          active is! SpaceActorContext ||
          active.space.id != space.id) {
        return;
      }
      setState(() {
        _authorityFacts = payload;
        _authorityLoading = false;
      });
    } on MakoloApiError catch (error) {
      final active = widget.runtime.actorContext?.value;
      if (!mounted ||
          version != _authorityRequestVersion ||
          active is! SpaceActorContext ||
          active.space.id != space.id) {
        return;
      }
      setState(() {
        _authorityFacts = null;
        _authorityLoading = false;
        if (error.statusCode == 401 ||
            error.statusCode == 403 ||
            error.statusCode == 404) {
          _denied = true;
        } else {
          _authorityError = 'Impossible de consulter vos autorisations.';
        }
      });
    } on Object {
      final active = widget.runtime.actorContext?.value;
      if (!mounted ||
          version != _authorityRequestVersion ||
          active is! SpaceActorContext ||
          active.space.id != space.id) {
        return;
      }
      setState(() {
        _authorityFacts = null;
        _authorityLoading = false;
        _authorityError = 'Impossible de consulter vos autorisations.';
      });
    }
  }

  Future<void> _loadTeam(SpaceActorIdentity space) async {
    final api = widget.runtime.api;
    if (api == null) return; // Offline preview remains usable until expiry.
    try {
      final response = await api.get(
        'api/v1/organizations/workspaces/${Uri.encodeComponent(space.slug)}/team/',
      );
      final decoded = jsonDecode(response.body);
      if (decoded is! List) throw const FormatException('Expected team list');
      final rows = <Map<String, dynamic>>[
        for (final item in decoded)
          if (item is Map)
            {
              for (final entry in item.entries)
                if (entry.key is String) entry.key as String: entry.value,
            },
      ];
      final actor = widget.runtime.actorContext?.value;
      if (!mounted ||
          actor is! SpaceActorContext ||
          actor.space.id != space.id) {
        return;
      }
      setState(() {
        _fullTeam = rows;
        _teamUnavailable = false;
      });
    } on MakoloApiError catch (error) {
      final active = widget.runtime.actorContext?.value;
      if (!mounted ||
          active is! SpaceActorContext ||
          active.space.id != space.id) {
        return;
      }
      if (error.statusCode == 401 ||
          error.statusCode == 403 ||
          error.statusCode == 404) {
        setState(() {
          _denied = true;
          _fullTeam = null;
        });
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

  Future<void> _mutateTeam(
    Future<void> Function() operation, {
    String successMessage = 'Équipe actualisée.',
    String? subscriptionHandoff,
  }) async {
    final current = widget.runtime.actorContext?.value;
    if (_teamMutating ||
        current is! SpaceActorContext ||
        _space == null ||
        current.space.id != _space!.id) {
      return;
    }
    final spaceId = current.space.id;
    setState(() => _teamMutating = true);
    try {
      await operation();
      if (!mounted ||
          widget.runtime.actorContext?.value is! SpaceActorContext) {
        return;
      }
      final currentActor =
          widget.runtime.actorContext!.value as SpaceActorContext;
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
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(successMessage)));
      }
    } on MakoloApiError catch (error) {
      final currentActor = widget.runtime.actorContext?.value;
      if (!mounted ||
          currentActor is! SpaceActorContext ||
          currentActor.space.id != spaceId ||
          currentActor.space.slug != widget.slug) {
        return; // Late response from a different actor; never show stale data.
      }
      if (error.statusCode == 401 ||
          error.statusCode == 403 ||
          error.statusCode == 404) {
        setState(() {
          _denied = true;
          _fullTeam = null;
        });
      } else {
        // A Subscription quota is different from a transport error or a
        // Mandate refusal. Only a server-declared owner denial can hand off.
        final isSubscriptionDenial =
            error.statusCode == 400 && error.fields.containsKey('subscription');
        final handoff = '/space/${widget.slug}/subscription';
        final actor = widget.runtime.actorContext?.value;
        final mayInspect =
            isSubscriptionDenial &&
            subscriptionHandoff == handoff &&
            actor is SpaceActorContext &&
            actor.space.id == spaceId &&
            actor.space.slug == widget.slug;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(error.message),
            duration: const Duration(seconds: 7),
            action: mayInspect
                ? SnackBarAction(
                    label: 'Comprendre',
                    onPressed: () {
                      final current = widget.runtime.actorContext?.value;
                      if (!mounted ||
                          current is! SpaceActorContext ||
                          current.space.id != spaceId ||
                          current.space.slug != widget.slug) {
                        return;
                      }
                      context.push('$handoff?from=team');
                    },
                  )
                : null,
          ),
        );
      }
    } on Object {
      final currentActor = widget.runtime.actorContext?.value;
      if (mounted &&
          currentActor is SpaceActorContext &&
          currentActor.space.id == spaceId &&
          currentActor.space.slug == widget.slug) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Cette modification n’a pas été enregistrée.'),
          ),
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
    String? selected;
    try {
      final result = await showDialog<Map<String, String>>(
        context: context,
        builder: (context) => StatefulBuilder(
          builder: (context, update) => AlertDialog(
            title: const Text('Ajouter un collaborateur'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'Cette personne doit déjà avoir un compte Makolo. '
                  'Le rôle attribué détermine les droits d’action dans cet Espace.',
                ),
                TextField(
                  controller: email,
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(
                    labelText: 'E-mail du Profil',
                  ),
                ),
                DropdownButtonFormField<String>(
                  initialValue: selected,
                  isExpanded: true,
                  hint: const Text('Choisir un rôle'),
                  decoration: const InputDecoration(labelText: 'Rôle'),
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
              MakoloActionButton(
                label: 'Annuler',
                onPressed: () => Navigator.pop(context),
                appearance: MakoloActionAppearance.quiet,
              ),
              MakoloActionButton(
                label: 'Confirmer l’ajout',
                onPressed: () {
                  if (email.text.trim().isEmpty || selected == null) return;
                  Navigator.pop(context, {
                    'email': email.text.trim(),
                    'role': selected!,
                  });
                },
                appearance: MakoloActionAppearance.primary,
              ),
            ],
          ),
        ),
      );
      if (result == null || !mounted) return;
      final links = payload['handoffs'];
      final subscriptionHandoff = links is Map
          ? links['subscription']?.toString()
          : null;
      await _mutateTeam(() async {
        await api.post(
          'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.slug)}/team/',
          body: result,
        );
      }, subscriptionHandoff: subscriptionHandoff);
    } finally {
      email.dispose();
    }
  }

  Future<void> _changeTeamRole(
    Map<String, dynamic> row,
    Map<String, dynamic> payload,
  ) async {
    final api = widget.runtime.api;
    final roles = _teamRoleOptions(payload);
    final id = _text(row['id']);
    if (api == null || roles.isEmpty || id == null) return;
    String? selected;
    final chosen = await showDialog<String>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Ajouter un rôle'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_depthRowLabel(row)),
              const Text(
                'Ce rôle s’ajoute aux mandats existants. Les autorisations déjà accordées restent actives.',
              ),
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
            MakoloActionButton(
              label: 'Annuler',
              onPressed: () => Navigator.pop(context),
              appearance: MakoloActionAppearance.quiet,
            ),
            MakoloActionButton(
              label: 'Ajouter ce rôle',
              onPressed: selected == null
                  ? null
                  : () => Navigator.pop(context, selected),
              appearance: MakoloActionAppearance.primary,
            ),
          ],
        ),
      ),
    );
    if (chosen == null || !mounted) return;
    await _mutateTeam(() async {
      await api.patch(
        'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.slug)}/team/${Uri.encodeComponent(id)}/',
        body: {'role': chosen},
      );
    });
  }

  Future<void> _transferOwnership(Map<String, dynamic> payload) async {
    final capabilities = _map(payload['capabilities']);
    final api = widget.runtime.api;
    if (api == null ||
        _fullTeam == null ||
        capabilities?['manage_team'] != true ||
        capabilities?['manage_ownership'] != true) {
      return;
    }
    final candidates = _fullTeam!
        .where(
          (row) =>
              _text(row['id']) != null &&
              row['responsibility'] != 'space_owner',
        )
        .toList();
    if (candidates.isEmpty) return;
    String? chosenId;
    var relinquish = false;
    final selection = await showDialog<Map<String, Object>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Transférer la propriété de l’Espace'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Choisissez un collaborateur actif. '
                'Votre droit de transférer la propriété sera vérifié.',
              ),
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
                onChanged: (value) => update(() => relinquish = value == true),
              ),
            ],
          ),
          actions: [
            MakoloActionButton(
              label: 'Annuler',
              onPressed: () => Navigator.pop(context),
              appearance: MakoloActionAppearance.quiet,
            ),
            MakoloActionButton(
              label: 'Confirmer le transfert',
              onPressed: chosenId == null
                  ? null
                  : () => Navigator.pop(context, <String, Object>{
                      'target_membership_id': chosenId!,
                      'relinquish_current_owner': relinquish,
                    }),
              appearance: MakoloActionAppearance.primary,
            ),
          ],
        ),
      ),
    );
    if (selection == null || !mounted) return;
    await _mutateTeam(() async {
      await api.post(
        'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.slug)}/ownership/transfer/',
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
        content: Text(
          'Retirer ${_depthRowLabel(row)} peut également lui retirer '
          'ses responsabilités dans cet Espace.',
        ),
        actions: [
          MakoloActionButton(
            label: 'Annuler',
            onPressed: () => Navigator.pop(context, false),
            appearance: MakoloActionAppearance.quiet,
          ),
          MakoloActionButton(
            label: 'Confirmer le retrait',
            onPressed: () => Navigator.pop(context, true),
            appearance: MakoloActionAppearance.danger,
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    await _mutateTeam(() async {
      await api.delete(
        'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.slug)}/team/${Uri.encodeComponent(id)}/',
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    if (widget.depth == 'resources') {
      return SpaceUsResourcesScreen(runtime: widget.runtime, slug: widget.slug);
    }
    if (_loading) {
      return const MakoloSecondaryScreen(
        title: 'Nous',
        message: 'Vérification de votre accès à cet Espace…',
      );
    }
    if (_denied || _space == null) {
      return const MakoloSecondaryScreen(
        title: 'Nous',
        message:
            'Vous ne pouvez pas accéder à cet Espace avec votre compte actuel.',
      );
    }
    final current = widget.runtime.actorContext?.value;
    if (current is! SpaceActorContext || current.space.id != _space!.id) {
      return const MakoloSecondaryScreen(
        title: 'Nous',
        message: 'Vous avez changé d’Espace. Revenez à Nous pour continuer.',
      );
    }
    final repository = widget.runtime.space!;
    final source = repository.usSource(_space!);
    return StreamBuilder<OwnerSourceState>(
      stream: repository.watchSource(source),
      initialData: OwnerSourceState.unknown,
      builder: (context, sourceSnapshot) {
        final state = sourceSnapshot.data ?? OwnerSourceState.unknown;
        if (state.invalidated) {
          return MakoloSecondaryScreen(
            title: _depthTitle(widget.depth),
            message:
                'Cette rubrique n’est plus accessible avec vos droits actuels.',
          );
        }
        return StreamBuilder<StoredProjection?>(
          stream: repository.watchUs(_space!),
          builder: (context, snapshot) {
            final payload = snapshot.data?.payload;
            if (payload == null) {
              return MakoloErrorState(
                message: 'Cette profondeur ne peut pas être actualisée pour le moment.',
                onRetry: _retryDepth,
              );
            }
            final handoffs = payload['handoffs'];
            final link = handoffs is Map ? handoffs[widget.depth] : null;
            final allowed = link == '/space/${widget.slug}/us/${widget.depth}';
            if (!allowed) {
              return MakoloSecondaryScreen(
                title: _depthTitle(widget.depth),
                message: 'Cette rubrique n’est pas accessible avec vos droits actuels.',
              );
            }
            final freshness = WorkspaceContextRepository.surfaceFreshness
                .evaluate(snapshot.data!, now: DateTime.now());
            if (freshness == FreshnessState.expired) {
              return MakoloErrorState(
                message: 'Ces informations doivent être actualisées.',
                onRetry: _retryDepth,
              );
            }
            return _depthBody(
              context,
              payload,
              observationOnly:
                  state.lastErrorCode != null || state.lastSuccessAt == null,
            );
          },
        );
      },
    );
  }

  Future<void> _retryDepth() async {
    final active = widget.runtime.actorContext?.value;
    final repository = widget.runtime.space;
    if (active is! SpaceActorContext ||
        _space == null ||
        active.space.id != _space!.id ||
        repository == null ||
        repository.sync == null) {
      return;
    }
    try {
      await repository.refreshUs(_space!);
      if (widget.depth == 'team') await _loadTeam(_space!);
      if (widget.depth == 'authority') await _loadAuthority(_space!);
    } on MakoloApiError catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401 ||
          error.statusCode == 403 ||
          error.statusCode == 404) {
        setState(() {
          _denied = true;
          _fullTeam = null;
        });
      }
    } on Object {
      // Keep the last non-expired observation; owner-source state reports
      // the failure and no offline action can be submitted from it.
    }
  }

  Widget _depthBody(
    BuildContext context,
    Map<String, dynamic> payload, {
    bool observationOnly = false,
  }) {
    if (widget.depth == 'authority') {
      return Scaffold(
        appBar: AppBar(title: const Text('Mes autorisations')),
        body: _authorityLoading
            ? const Center(child: CircularProgressIndicator())
            : _authorityFacts == null || observationOnly
            ? ListView(
                padding: const EdgeInsets.all(MakoloSpacing.lg),
                children: [
                  Text(
                    observationOnly
                        ? 'Actualisez vos autorisations avant de les consulter.'
                        : _authorityError ?? 'Autorisations indisponibles.',
                  ),
                  if (widget.runtime.api != null &&
                      widget.runtime.space?.sync != null)
                    MakoloActionButton(
                      label: 'Réessayer',
                      onPressed: _retryDepth,
                      appearance: MakoloActionAppearance.quiet,
                      icon: Icons.refresh_rounded,
                    ),
                ],
              )
            : ListView(
                padding: const EdgeInsets.all(MakoloSpacing.lg),
                children: [
                  Text(
                    'Mes autorisations',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                  const Text(
                    'Vos rôles actifs dans cet Espace et leurs droits. '
                    'Chaque action est vérifiée au moment de son exécution.',
                  ),
                  const SizedBox(height: MakoloSpacing.lg),
                  SpaceUsAuthorityFacts(payload: _authorityFacts!),
                ],
              ),
      );
    }
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
        ? allRows
              .where(
                (row) =>
                    widget.depth != 'responsibilities' ||
                    _map(row)?['combined'] != true,
              )
              .toList()
        : const <dynamic>[];
    final canManageTeam =
        !observationOnly &&
        widget.depth == 'team' &&
        _map(payload['capabilities'])?['manage_team'] == true &&
        _teamRoleOptions(payload).isNotEmpty;
    final canTransferOwnership =
        !observationOnly &&
        widget.depth == 'ownership' &&
        _map(payload['capabilities'])?['manage_team'] == true &&
        _map(payload['capabilities'])?['manage_ownership'] == true;
    final intro = switch (widget.depth) {
      'team' => 'Les collaborateurs actuellement visibles dans cette équipe.',
      'responsibilities' => 'Les rôles présentés ici sont distincts des tâches confiées aux collaborateurs.',
      'ownership' =>
        'Les personnes qui détiennent actuellement la propriété de cet Espace.',
      'trust' => 'Les faits de vérification établis dans ce contexte.',
      _ => 'Cette rubrique dépend de vos droits dans l’Espace actif.',
    };
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: ListView(
        padding: const EdgeInsets.all(MakoloSpacing.lg),
        children: [
          Text(title, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: MakoloSpacing.sm),
          Text(intro, style: Theme.of(context).textTheme.bodyMedium),
          if (widget.depth == 'team' &&
              _map(payload['handoffs'])?['relationships'] ==
                  '/space/${widget.slug}/us/relationships') ...[
            const SizedBox(height: MakoloSpacing.md),
            MakoloActionButton(
              label: 'Voir les relations de cet Espace',
              onPressed: () =>
                  context.push('/space/${widget.slug}/us/relationships'),
              appearance: MakoloActionAppearance.quiet,
              icon: Icons.hub_outlined,
            ),
          ],
          if (widget.depth == 'responsibilities' &&
              _map(payload['handoffs'])?['authority'] ==
                  '/space/${widget.slug}/us/authority') ...[
            const SizedBox(height: MakoloSpacing.md),
            MakoloActionButton(
              label: 'Voir mes autorisations',
              onPressed: observationOnly
                  ? null
                  : () => context.push('/space/${widget.slug}/us/authority'),
              appearance: MakoloActionAppearance.secondary,
              icon: Icons.shield_outlined,
            ),
          ],
          if (observationOnly) ...[
            const SizedBox(height: MakoloSpacing.md),
            const MakoloStatus(
              label: 'Consultation uniquement pour le moment.',
              tone: MakoloStatusTone.info,
              icon: Icons.cloud_off_outlined,
            ),
          ],
          const SizedBox(height: MakoloSpacing.lg),
          if (canManageTeam) ...[
            MakoloActionButton(
              label: 'Ajouter un collaborateur',
              onPressed: _teamMutating ? null : () => _addTeamMember(payload),
              appearance: MakoloActionAppearance.primary,
              icon: Icons.person_add_alt_1_outlined,
            ),
            const SizedBox(height: MakoloSpacing.md),
          ],
          if (canTransferOwnership) ...[
            if (_fullTeam == null)
              MakoloActionButton(
                label: 'Choisir un nouveau propriétaire',
                onPressed: _teamMutating ? null : () => _loadTeam(_space!),
                appearance: MakoloActionAppearance.secondary,
                icon: Icons.group_add_outlined,
              )
            else if (_fullTeam!.any(
              (row) =>
                  _text(row['id']) != null &&
                  row['responsibility'] != 'space_owner',
            ))
              MakoloActionButton(
                label: 'Transférer la propriété',
                onPressed: _teamMutating
                    ? null
                    : () => _transferOwnership(payload),
                appearance: MakoloActionAppearance.primary,
                icon: Icons.verified_user_outlined,
              )
            else
              const Text('Aucun collaborateur éligible à ce transfert.'),
            if (_teamUnavailable)
              MakoloActionButton(
                label: 'Réessayer de charger les collaborateurs',
                onPressed: () => _loadTeam(_space!),
                appearance: MakoloActionAppearance.quiet,
              ),
            const SizedBox(height: MakoloSpacing.md),
          ],
          if (_teamMutating) const LinearProgressIndicator(),
          if (widget.depth == 'trust') ...[
            if (_map(payload['trust'])?['claims'] case final List claims)
              if (claims.isNotEmpty)
                for (final claim in claims)
                  if (_map(claim) case final fact?)
                    Padding(
                      padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                      child: MakoloCard(
                        padding: const EdgeInsets.all(MakoloSpacing.md),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _text(fact['claim_type']) ??
                                  'Fait de vérification',
                              style: Theme.of(context).textTheme.titleSmall,
                            ),
                            if (_text(fact['status']) case final status?)
                              Text('État : $status'),
                            if (fact['valid_until'] != null)
                              Text(
                                'Validité annoncée : ${fact['valid_until']}',
                              ),
                          ],
                        ),
                      ),
                    )
                  else
                    const MakoloEmptyState(
                      title: 'Aucun fait public de vérification actif.',
                    )
              else
                const MakoloEmptyState(title: 'Vérifications indisponibles.'),
            const Text(
              'Ces faits ne constituent pas un score global de confiance.',
            ),
          ] else if (rows.isEmpty)
            const MakoloEmptyState(title: 'Aucun élément visible ici.')
          else
            for (final row in rows)
              Padding(
                padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                child: MakoloCard(
                  padding: const EdgeInsets.all(MakoloSpacing.md),
                  child: Row(
                    children: [
                      Icon(
                        widget.depth == 'team'
                            ? Icons.person_outline
                            : widget.depth == 'ownership'
                            ? Icons.verified_user_outlined
                            : Icons.assignment_ind_outlined,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(width: MakoloSpacing.md),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _depthRowLabel(row),
                              style: Theme.of(context).textTheme.titleSmall,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              _depthRowDetail(row),
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                            if (canManageTeam &&
                                _fullTeam != null &&
                                _map(row) != null &&
                                (_map(row)?['responsibility'] !=
                                        'space_owner' ||
                                    _map(
                                          payload['capabilities'],
                                        )?['manage_ownership'] ==
                                        true)) ...[
                              const SizedBox(height: MakoloSpacing.sm),
                              Wrap(
                                spacing: MakoloSpacing.sm,
                                children: [
                                  MakoloActionButton(
                                    label: 'Ajouter un rôle',
                                    onPressed: _teamMutating
                                        ? null
                                        : () => _changeTeamRole(
                                            _map(row)!,
                                            payload,
                                          ),
                                    appearance: MakoloActionAppearance.quiet,
                                  ),
                                  MakoloActionButton(
                                    label: 'Retirer',
                                    onPressed: _teamMutating
                                        ? null
                                        : () => _removeTeamMember(_map(row)!),
                                    appearance: MakoloActionAppearance.danger,
                                  ),
                                ],
                              ),
                            ],
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          if (widget.depth == 'team' &&
              _fullTeam == null &&
              section?['has_more'] == true)
            const Text(
              'Aperçu partiel : tous les membres ne sont pas chargés.',
            ),
          if (widget.depth == 'team' && _teamUnavailable)
            MakoloActionButton(
              label: 'Réessayer de charger l’équipe',
              onPressed: () => _loadTeam(_space!),
              appearance: MakoloActionAppearance.quiet,
              icon: Icons.refresh_rounded,
            ),
          if (widget.depth == 'ownership' && section?['has_more'] == true)
            const Text('Aperçu partiel de la gouvernance institutionnelle.'),
        ],
      ),
    );
  }

  String _depthTitle(String depth) => switch (depth) {
    'team' => 'Équipe',
    'responsibilities' => 'Mes rôles',
    'authority' => 'Mes autorisations',
    'relationships' => 'Personnes & relations',
    'ownership' => 'Gouvernance',
    'resources' => 'Nos ressources',
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
    if (widget.depth == 'team') {
      final rawRoles = row?['roles'];
      if (rawRoles is List) {
        final labels = rawRoles
            .map((item) => _text(_map(item)?['label']))
            .whereType<String>()
            .toList(growable: false);
        if (labels.isNotEmpty) return labels.join(' · ');
      }
    }
    final responsibility = _map(row?['responsibility']);
    final activity = _map(row?['activity']);
    return _text(responsibility?['label']) ??
        _text(activity?['title']) ??
        (widget.depth == 'team'
            ? 'Membre de l’équipe'
            : widget.depth == 'ownership'
            ? 'Mandat de propriétaire'
            : 'Portée collective');
  }

  Map<String, dynamic>? _map(Object? value) => value is Map
      ? value.map((key, value) => MapEntry(key.toString(), value))
      : null;

  String? _text(Object? value) =>
      value is String && value.trim().isNotEmpty ? value.trim() : null;
}
