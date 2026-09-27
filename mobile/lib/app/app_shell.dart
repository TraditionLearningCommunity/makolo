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
import 'sync_lifecycle.dart';

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

  MakoloHeaderKind get _headerKind => switch (
    widget.navigationShell.currentIndex
  ) {
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
      onSwitchAccount: widget.onSwitchAccount,
      onLogout: widget.onLogout,
    );
  }

  @override
  Widget build(BuildContext context) {
    widget.recovery.rememberLocation(
      MakoloDestination.values[widget.navigationShell.currentIndex].path,
    );
    final syncStatus = SyncStatusScope.maybeOf(context);

    return StreamBuilder<StoredProjection?>(
      stream: _meStream,
      builder: (context, snapshot) {
        final identity = snapshot.data?.payload['identity'];
        final displayName = identity is Map ? identity['display_name'] : null;
        final avatarLetter = displayName is String && displayName.trim().isNotEmpty
            ? displayName.trim().substring(0, 1).toUpperCase()
            : null;

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
          body: SafeArea(
            top: false,
            child: Column(
              children: [
                if (syncStatus != null &&
                    syncStatus.state != SyncVisualState.synced)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(
                      MakoloSpacing.md,
                      MakoloSpacing.sm,
                      MakoloSpacing.md,
                      0,
                    ),
                    child: NetworkStateIndicator(status: syncStatus),
                  ),
                Expanded(
                  child: RefreshIndicator(
                    onRefresh: () async {
                      final refresh = SyncRefreshScope.maybeOf(context);
                      if (refresh != null) await refresh.refresh();
                    },
                    child: widget.navigationShell,
                  ),
                ),
              ],
            ),
          ),
          bottomNavigationBar: _MakoloBottomNavigation(
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
        color: Theme.of(context).colorScheme.surface,
        elevation: 8,
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
              Expanded(
                child: Semantics(
                  button: true,
                  label: 'Makolo Mark',
                  child: Tooltip(
                    message: 'Makolo Mark',
                    child: InkResponse(
                      onTap: onMark,
                      radius: 28,
                      containedInkWell: true,
                      child: const SizedBox(
                        height: 64,
                        child: Center(
                          child: SizedBox(
                            width: 48,
                            height: 48,
                            child: Center(child: MakoloMark(size: 32)),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
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
                    style: TextStyle(
                      color: color,
                      fontSize: 11,
                      fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
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
