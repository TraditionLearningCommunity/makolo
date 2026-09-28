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
import '../sync/sync_status.dart';
import 'providers.dart';
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

  @override
  void initState() {
    super.initState();
    _meStream = widget.runtime.personal?.watchMe();
    unawaited(_loadUnreadNotifications());
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

  MakoloHeaderKind get _headerKind =>
      switch (widget.navigationShell.currentIndex) {
        0 => MakoloHeaderKind.now,
        1 => MakoloHeaderKind.discover,
        2 => MakoloHeaderKind.ongoing,
        3 => MakoloHeaderKind.me,
        _ => MakoloHeaderKind.now,
      };

  void _goBranch(int index) {
    if (index == widget.navigationShell.currentIndex) return;
    widget.navigationShell.goBranch(index);
  }

  void _openAvatar() {
    showMakoloAvatarSheet(
      context,
      runtime: widget.runtime,
      onConnections: () => context.push('/connections'),
      onSwitchAccount: widget.onSwitchAccount,
      onLogout: widget.onLogout,
    );
  }

  Widget _content(SyncStatus? syncStatus) {
    return SafeArea(
      top: false,
      child: Column(
        children: [
          if (syncStatus != null && syncStatus.state != SyncVisualState.synced)
            Padding(
              padding: const EdgeInsets.fromLTRB(
                MakoloSpacing.md,
                MakoloSpacing.sm,
                MakoloSpacing.md,
                0,
              ),
              child: NetworkStateIndicator(status: syncStatus),
            ),
          Expanded(child: widget.navigationShell),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    widget.recovery.rememberLocation(
      MakoloDestination.values[widget.navigationShell.currentIndex].path,
    );
    final syncStatus = SyncStatusScope.maybeOf(context);
    final useRail = MakoloLayout.useNavigationRail(MediaQuery.sizeOf(context));

    return StreamBuilder<StoredProjection?>(
      stream: _meStream,
      builder: (context, snapshot) {
        final identity = snapshot.data?.payload['identity'];
        final displayName = identity is Map ? identity['display_name'] : null;
        final avatarLetter =
            displayName is String && displayName.trim().isNotEmpty
            ? displayName.trim().substring(0, 1).toUpperCase()
            : null;
        final content = _content(syncStatus);

        return Scaffold(
          appBar: MakoloPrimaryHeader(
            kind: _headerKind,
            avatarLetter: avatarLetter,
            unreadNotifications: _unreadNotifications,
            onConversations: () => context.push('/conversations'),
            onNotifications: () => context.push('/notifications'),
            onSearch: () => context.push('/discover/search'),
            onFilters: () => context.push('/discover/filters'),
            onCalendar: () => context.push('/ongoing/calendar'),
            onAvatar: _openAvatar,
          ),
          body: useRail
              ? Row(
                  children: [
                    _MakoloNavigationRail(
                      selectedIndex: widget.navigationShell.currentIndex,
                      onDestination: _goBranch,
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
                  selectedIndex: widget.navigationShell.currentIndex,
                  onDestination: _goBranch,
                  onMark: () => context.push('/mark'),
                ),
        );
      },
    );
  }
}

class _MakoloBottomNavigation extends StatelessWidget {
  const _MakoloBottomNavigation({
    required this.selectedIndex,
    required this.onDestination,
    required this.onMark,
  });

  final int selectedIndex;
  final ValueChanged<int> onDestination;
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
                destination: MakoloDestination.now,
                icon: Icons.schedule_outlined,
                selected: selectedIndex == 0,
                onTap: () => onDestination(0),
              ),
              _NavButton(
                destination: MakoloDestination.discover,
                icon: Icons.explore_outlined,
                selected: selectedIndex == 1,
                onTap: () => onDestination(1),
              ),
              Expanded(child: _MarkButton(onTap: onMark)),
              _NavButton(
                destination: MakoloDestination.ongoing,
                icon: Icons.route_outlined,
                selected: selectedIndex == 2,
                onTap: () => onDestination(2),
              ),
              _NavButton(
                destination: MakoloDestination.me,
                icon: Icons.person_outline,
                selected: selectedIndex == 3,
                onTap: () => onDestination(3),
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
    required this.selectedIndex,
    required this.onDestination,
    required this.onMark,
  });

  final int selectedIndex;
  final ValueChanged<int> onDestination;
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
                destination: MakoloDestination.now,
                icon: Icons.schedule_outlined,
                selected: selectedIndex == 0,
                onTap: () => onDestination(0),
              ),
              _RailButton(
                destination: MakoloDestination.discover,
                icon: Icons.explore_outlined,
                selected: selectedIndex == 1,
                onTap: () => onDestination(1),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.sm),
                child: _MarkButton(onTap: onMark),
              ),
              _RailButton(
                destination: MakoloDestination.ongoing,
                icon: Icons.route_outlined,
                selected: selectedIndex == 2,
                onTap: () => onDestination(2),
              ),
              _RailButton(
                destination: MakoloDestination.me,
                icon: Icons.person_outline,
                selected: selectedIndex == 3,
                onTap: () => onDestination(3),
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
                  size: 38,
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
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final MakoloDestination destination;
  final IconData icon;
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
                  Icon(icon, color: color),
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
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final MakoloDestination destination;
  final IconData icon;
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
                Icon(icon, color: color),
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
