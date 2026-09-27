import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:go_router/go_router.dart';

import '../design/makolo_theme.dart';

enum MakoloHeaderKind { now, discover, mark, ongoing, me }

class MakoloPrimaryHeader extends StatelessWidget
    implements PreferredSizeWidget {
  const MakoloPrimaryHeader({
    super.key,
    required this.kind,
    required this.onAvatar,
    this.onConversations,
    this.onNotifications,
    this.onSearch,
    this.onFilters,
    this.onCalendar,
    this.unreadNotifications = 0,
    this.avatarLetter,
  });

  final MakoloHeaderKind kind;
  final VoidCallback onAvatar;
  final VoidCallback? onConversations;
  final VoidCallback? onNotifications;
  final VoidCallback? onSearch;
  final VoidCallback? onFilters;
  final VoidCallback? onCalendar;
  final int unreadNotifications;
  final String? avatarLetter;

  @override
  Size get preferredSize => const Size.fromHeight(64);

  bool get _usesBrand =>
      kind == MakoloHeaderKind.now ||
      kind == MakoloHeaderKind.discover ||
      kind == MakoloHeaderKind.mark;

  String get _title => switch (kind) {
    MakoloHeaderKind.now ||
    MakoloHeaderKind.discover ||
    MakoloHeaderKind.mark => 'Makolo',
    MakoloHeaderKind.ongoing => 'En cours',
    MakoloHeaderKind.me => 'Moi',
  };

  List<Widget> _contextActions() => switch (kind) {
    MakoloHeaderKind.now => [
      _HeaderAction(
        tooltip: 'Conversations',
        icon: Icons.forum_outlined,
        onPressed: onConversations,
      ),
      _HeaderAction(
        tooltip: unreadNotifications > 0
            ? 'Notifications, $unreadNotifications non lues'
            : 'Notifications',
        icon: Icons.notifications_none_outlined,
        onPressed: onNotifications,
        attention: unreadNotifications > 0,
      ),
    ],
    MakoloHeaderKind.discover => [
      _HeaderAction(
        tooltip: 'Rechercher',
        icon: Icons.search,
        onPressed: onSearch,
      ),
      _HeaderAction(tooltip: 'Filtres', icon: Icons.tune, onPressed: onFilters),
    ],
    MakoloHeaderKind.ongoing => [
      _HeaderAction(
        tooltip: 'Calendrier',
        icon: Icons.calendar_month_outlined,
        onPressed: onCalendar,
      ),
    ],
    MakoloHeaderKind.mark || MakoloHeaderKind.me => const [],
  };

  @override
  Widget build(BuildContext context) {
    return AppBar(
      automaticallyImplyLeading: false,
      toolbarHeight: 64,
      elevation: 0,
      scrolledUnderElevation: 0,
      surfaceTintColor: Colors.transparent,
      backgroundColor: Theme.of(context).colorScheme.surface,
      titleSpacing: MakoloSpacing.md,
      title: _usesBrand
          ? SvgPicture.asset(
              'assets/brand/makolo-logo-violet.svg',
              height: 34,
              semanticsLabel: 'Makolo',
            )
          : Text(
              _title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleLarge,
            ),
      actions: [
        ..._contextActions(),
        Semantics(
          button: true,
          label: 'Avatar',
          child: IconButton(
            tooltip: 'Avatar',
            constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
            onPressed: onAvatar,
            icon: Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Theme.of(context).colorScheme.primaryContainer,
              ),
              child: avatarLetter == null
                  ? Icon(
                      Icons.person_outline,
                      size: 20,
                      color: Theme.of(context).colorScheme.onPrimaryContainer,
                    )
                  : Center(
                      child: Text(
                        avatarLetter!,
                        style: TextStyle(
                          color: Theme.of(context)
                              .colorScheme
                              .onPrimaryContainer,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
            ),
          ),
        ),
        const SizedBox(width: MakoloSpacing.xs),
      ],
    );
  }
}

class MakoloSecondaryHeader extends StatelessWidget
    implements PreferredSizeWidget {
  const MakoloSecondaryHeader({
    super.key,
    required this.title,
    this.actions = const [],
    this.onBack,
  });

  final String title;
  final List<Widget> actions;
  final VoidCallback? onBack;

  @override
  Size get preferredSize => const Size.fromHeight(64);

  @override
  Widget build(BuildContext context) {
    return AppBar(
      toolbarHeight: 64,
      elevation: 0,
      scrolledUnderElevation: 0,
      surfaceTintColor: Colors.transparent,
      backgroundColor: Theme.of(context).colorScheme.surface,
      leading: Semantics(
        button: true,
        label: 'Retour',
        child: IconButton(
          tooltip: 'Retour',
          constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
          icon: const Icon(Icons.arrow_back),
          onPressed:
              onBack ??
              () {
                if (context.canPop()) {
                  context.pop();
                } else {
                  context.go('/now');
                }
              },
        ),
      ),
      title: Text(
        title,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: Theme.of(context).textTheme.titleLarge,
      ),
      actions: actions,
    );
  }
}

class _HeaderAction extends StatelessWidget {
  const _HeaderAction({
    required this.tooltip,
    required this.icon,
    required this.onPressed,
    this.attention = false,
  });

  final String tooltip;
  final IconData icon;
  final VoidCallback? onPressed;
  final bool attention;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: tooltip,
      child: IconButton(
        tooltip: tooltip,
        constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
        onPressed: onPressed,
        icon: Stack(
          clipBehavior: Clip.none,
          children: [
            Icon(icon),
            if (attention)
              Positioned(
                right: -1,
                top: -1,
                child: ExcludeSemantics(
                  child: Container(
                    width: 8,
                    height: 8,
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      color: MakoloColors.pulse,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
