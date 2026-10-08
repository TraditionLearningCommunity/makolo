import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/local/profile_store.dart';
import '../design/behavior_primitives.dart';
import '../design/makolo_mark.dart';
import '../design/makolo_theme.dart';
import '../navigation/avatar_sheet.dart';
import '../navigation/destination.dart';
import '../navigation/shell_header.dart';
import '../navigation/space_context_bar.dart';
import '../sync/sync_status.dart';
import 'launch_preferences.dart';
import 'providers.dart';
import 'runtime/actor_context.dart';
import 'runtime/actor_context_controller.dart';
import 'session_recovery.dart';

class AppShell extends StatefulWidget {
  const AppShell({
    super.key,
    required this.navigationShell,
    required this.recovery,
    required this.runtime,
    this.onSwitchAccount,
    this.onLogout,
  });

  final StatefulNavigationShell navigationShell;
  final SessionRecoveryController recovery;
  final AppRuntime runtime;
  final VoidCallback? onSwitchAccount;
  final VoidCallback? onLogout;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _unreadNotifications = 0;
  Stream<StoredProjection?>? _meStream;
  ActorContextController? _actorController;
  String? _rememberedPath;

  @override
  void initState() {
    super.initState();
    _meStream = widget.runtime.personal?.watchMe();
    _bindActorContext();
    unawaited(_loadUnreadNotifications());
  }

  void _bindActorContext() {
    _actorController?.removeListener(_onActorContextChanged);
    _actorController = widget.runtime.actorContext;
    _actorController?.addListener(_onActorContextChanged);
  }

  @override
  void didUpdateWidget(covariant AppShell oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.personal != widget.runtime.personal) {
      _meStream = widget.runtime.personal?.watchMe();
    }
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      _bindActorContext();
    }
  }

  ActorContext get _actor =>
      widget.runtime.actorContext?.value ?? const PersonalActorContext();

  MakoloDestination get _currentDestination {
    final branch = MakoloDestination.forBranchIndex(
      widget.navigationShell.currentIndex,
    );
    return MakoloDestination.forActor(_actor, branch.door);
  }

  MakoloHeaderKind get _headerKind => switch (_currentDestination) {
    MakoloDestination.personalNow ||
    MakoloDestination.spaceNow => MakoloHeaderKind.now,
    MakoloDestination.personalDiscover ||
    MakoloDestination.spaceDiscover => MakoloHeaderKind.discover,
    MakoloDestination.personalContinuity => MakoloHeaderKind.ongoing,
    MakoloDestination.personalIdentity => MakoloHeaderKind.me,
    MakoloDestination.spaceContinuity => MakoloHeaderKind.work,
    MakoloDestination.spaceIdentity => MakoloHeaderKind.us,
  };

  void _onActorContextChanged() {
    if (!mounted) return;
    setState(() {});
    final current = MakoloDestination.forBranchIndex(
      widget.navigationShell.currentIndex,
    );
    final target = MakoloDestination.forActor(_actor, current.door);
    if (target.branchIndex == widget.navigationShell.currentIndex) {
      _rememberDestination(target);
      return;
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      widget.navigationShell.goBranch(
        target.branchIndex,
        initialLocation: true,
      );
      _rememberDestination(target);
    });
  }

  Future<void> _loadUnreadNotifications() async {
    final api = widget.runtime.api;
    if (api == null) return;
    try {
      final response = await api.get('api/v1/notifications/unread-count/');
      final value = response.jsonObject()['unread_count'];
      if (!mounted || value is! num) return;
      setState(() => _unreadNotifications = value.toInt());
    } on Object {
      // A badge is supplemental shell information. Local content remains usable
      // when its dedicated endpoint is unavailable.
    }
  }

  void _rememberDestination(MakoloDestination destination) {
    if (_rememberedPath == destination.path) return;
    _rememberedPath = destination.path;
    widget.recovery.rememberLocation(destination.path);
    final profileId =
        widget.runtime.actorContext?.profileId ??
        widget.runtime.session?.profileId;
    final preferences = widget.runtime.launchPreferences;
    if (profileId != null && preferences is FileLaunchPreferencesStore) {
      unawaited(preferences.writeShellLocation(profileId, destination.path));
    }
  }

  void _goDestination(MakoloDestination destination) {
    if (destination.branchIndex == widget.navigationShell.currentIndex) return;
    widget.navigationShell.goBranch(destination.branchIndex);
    _rememberDestination(destination);
  }

  void _goDoor(MakoloPrimaryDoor door) {
    _goDestination(MakoloDestination.forActor(_actor, door));
  }

  void _openAvatar() {
    showMakoloAvatarSheet(
      context,
      runtime: widget.runtime,
      onConnections: () => context.push('/connections'),
      onBilling: () => context.push('/billing'),
      onSettings: () => context.push('/settings'),
      onSwitchAccount: widget.onSwitchAccount,
      onLogout: widget.onLogout,
    );
  }

  Widget _content(SyncStatus? syncStatus, ActorContext actor) {
    return SafeArea(
      top: false,
      child: Column(
        children: [
          if (actor is SpaceActorContext)
            MakoloSpaceContextBar(runtime: widget.runtime, actor: actor),
          if (syncStatus != null) ...[
            NetworkStateCue(status: syncStatus),
            if (syncStatus.state == SyncVisualState.pending ||
                syncStatus.state == SyncVisualState.conflict)
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  MakoloSpacing.md,
                  MakoloSpacing.sm,
                  MakoloSpacing.md,
                  0,
                ),
                child: NetworkStateIndicator(status: syncStatus),
              ),
          ],
          Expanded(child: widget.navigationShell),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final actor = _actor;
    final destination = _currentDestination;
    _rememberDestination(destination);
    final syncStatus = SyncStatusScope.maybeOf(context);
    final useRail = MakoloLayout.useNavigationRail(MediaQuery.sizeOf(context));
    final destinations = MakoloDestination.primaryForActor(actor);

    return StreamBuilder<StoredProjection?>(
      stream: _meStream,
      builder: (context, snapshot) {
        final identity = snapshot.data?.payload['identity'];
        final displayName = identity is Map ? identity['display_name'] : null;
        final profileUsername = identity is Map ? identity['username'] : null;
        final avatarLetter =
            displayName is String && displayName.trim().isNotEmpty
            ? displayName.trim().substring(0, 1).toUpperCase()
            : null;
        final content = _content(syncStatus, actor);

        return Scaffold(
          appBar: MakoloPrimaryHeader(
            kind: _headerKind,
            avatarLetter: avatarLetter,
            profileUsername: profileUsername is String ? profileUsername : null,
            unreadNotifications: _unreadNotifications,
            onBrand: () => _goDoor(MakoloPrimaryDoor.now),
            onConversations: actor is PersonalActorContext
                ? () => context.push('/conversations')
                : null,
            onNotifications: actor is PersonalActorContext
                ? () => context.push('/notifications')
                : null,
            onSearch: actor is PersonalActorContext
                ? () => context.push('/discover/search')
                : null,
            onMap: actor is PersonalActorContext
                ? () => context.push('/discover/map')
                : null,
            onCalendar: actor is PersonalActorContext
                ? () => context.push('/ongoing/calendar')
                : null,
            onAvatar: _openAvatar,
          ),
          body: useRail
              ? Row(
                  children: [
                    _MakoloNavigationRail(
                      destinations: destinations,
                      selectedDoor: destination.door,
                      onDestination: _goDestination,
                      onMark: () => context.push('/mark'),
                    ),
                    VerticalDivider(
                      width: 1,
                      color: context.makoloSurfaces.border,
                    ),
                    Expanded(child: content),
                  ],
                )
              : content,
          bottomNavigationBar: useRail
              ? null
              : _MakoloBottomNavigation(
                  destinations: destinations,
                  selectedDoor: destination.door,
                  onDestination: _goDestination,
                  onMark: () => context.push('/mark'),
                ),
        );
      },
    );
  }

  @override
  void dispose() {
    _actorController?.removeListener(_onActorContextChanged);
    super.dispose();
  }
}

class _MakoloBottomNavigation extends StatelessWidget {
  const _MakoloBottomNavigation({
    required this.destinations,
    required this.selectedDoor,
    required this.onDestination,
    required this.onMark,
  });

  final List<MakoloDestination> destinations;
  final MakoloPrimaryDoor selectedDoor;
  final ValueChanged<MakoloDestination> onDestination;
  final VoidCallback onMark;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Material(
        key: const Key('makolo-bottom-navigation'),
        color: context.makoloSurfaces.surface,
        elevation: MakoloElevation.level1,
        child: SizedBox(
          height: 72,
          child: Row(
            children: [
              _NavButton(
                destination: destinations[0],
                selected: selectedDoor == destinations[0].door,
                onTap: () => onDestination(destinations[0]),
              ),
              _NavButton(
                destination: destinations[1],
                selected: selectedDoor == destinations[1].door,
                onTap: () => onDestination(destinations[1]),
              ),
              Expanded(child: _MarkButton(onTap: onMark)),
              _NavButton(
                destination: destinations[2],
                selected: selectedDoor == destinations[2].door,
                onTap: () => onDestination(destinations[2]),
              ),
              _NavButton(
                destination: destinations[3],
                selected: selectedDoor == destinations[3].door,
                onTap: () => onDestination(destinations[3]),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MakoloNavigationRail extends StatelessWidget {
  const _MakoloNavigationRail({
    required this.destinations,
    required this.selectedDoor,
    required this.onDestination,
    required this.onMark,
  });

  final List<MakoloDestination> destinations;
  final MakoloPrimaryDoor selectedDoor;
  final ValueChanged<MakoloDestination> onDestination;
  final VoidCallback onMark;

  @override
  Widget build(BuildContext context) {
    return Material(
      key: const Key('makolo-navigation-rail'),
      color: context.makoloSurfaces.surface,
      elevation: MakoloElevation.level1,
      child: SafeArea(
        right: false,
        child: SizedBox(
          width: MakoloLayout.navigationRailWidth,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _RailButton(
                destination: destinations[0],
                selected: selectedDoor == destinations[0].door,
                onTap: () => onDestination(destinations[0]),
              ),
              _RailButton(
                destination: destinations[1],
                selected: selectedDoor == destinations[1].door,
                onTap: () => onDestination(destinations[1]),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.sm),
                child: _MarkButton(onTap: onMark),
              ),
              _RailButton(
                destination: destinations[2],
                selected: selectedDoor == destinations[2].door,
                onTap: () => onDestination(destinations[2]),
              ),
              _RailButton(
                destination: destinations[3],
                selected: selectedDoor == destinations[3].door,
                onTap: () => onDestination(destinations[3]),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MarkButton extends StatelessWidget {
  const _MarkButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'Makolo Mark',
      child: Tooltip(
        message: 'Makolo Mark',
        child: Material(
          color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.06),
          shape: CircleBorder(
            side: BorderSide(
              color: Theme.of(context).colorScheme.primary,
              width: 1.5,
            ),
          ),
          child: InkWell(
            customBorder: const CircleBorder(),
            onTap: () {
              MakoloHaptics.selection();
              onTap();
            },
            child: const SizedBox(
              width: 56,
              height: 56,
              child: Center(
                child: MakoloMark(
                  size: 32,
                  semantics: MakoloMarkSemantics.decorative,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({
    required this.destination,
    required this.selected,
    required this.onTap,
  });

  final MakoloDestination destination;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected
        ? Theme.of(context).colorScheme.primary
        : Theme.of(context).colorScheme.onSurfaceVariant;
    return Expanded(
      child: Semantics(
        button: true,
        selected: selected,
        label: destination.label,
        child: InkWell(
          onTap: onTap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 48),
            child: SizedBox(
              height: 64,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(_destinationIcon(destination), color: color),
                  const SizedBox(height: 3),
                  Text(
                    destination.label,
                    maxLines: 1,
                    overflow: TextOverflow.fade,
                    softWrap: false,
                    style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      color: color,
                      fontWeight: selected ? FontWeight.w700 : FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _RailButton extends StatelessWidget {
  const _RailButton({
    required this.destination,
    required this.selected,
    required this.onTap,
  });

  final MakoloDestination destination;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected
        ? Theme.of(context).colorScheme.primary
        : Theme.of(context).colorScheme.onSurfaceVariant;
    return Semantics(
      button: true,
      selected: selected,
      label: destination.label,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(MakoloRadii.control),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minWidth: 72, minHeight: 56),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.sm),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(_destinationIcon(destination), color: color),
                const SizedBox(height: MakoloSpacing.xs),
                Text(
                  destination.label,
                  maxLines: 1,
                  overflow: TextOverflow.fade,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: color,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

IconData _destinationIcon(MakoloDestination destination) =>
    switch (destination) {
      MakoloDestination.personalNow ||
      MakoloDestination.spaceNow => Icons.adjust,
      MakoloDestination.personalDiscover ||
      MakoloDestination.spaceDiscover => Icons.explore_outlined,
      MakoloDestination.personalContinuity => Icons.route_outlined,
      MakoloDestination.personalIdentity => Icons.person_outline,
      MakoloDestination.spaceContinuity => Icons.business_center_outlined,
      MakoloDestination.spaceIdentity => Icons.groups_outlined,
    };
