import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:go_router/go_router.dart';

import '../design/makolo_mark.dart';
import '../design/makolo_theme.dart';

enum MakoloHeaderKind { now, discover, mark, ongoing, me, work, us }

class MakoloPrimaryHeader extends StatelessWidget
    implements PreferredSizeWidget {
  const MakoloPrimaryHeader({
    super.key,
    required this.kind,
    required this.onAvatar,
    this.onBrand,
    this.onConversations,
    this.onNotifications,
    this.onSearch,
    this.onMap,
    this.onCalendar,
    this.hasConversationAttention = false,
    this.hasUnreadNotifications = false,
    this.avatarLetter,
    this.profileUsername,
  });

  final MakoloHeaderKind kind;
  final VoidCallback onAvatar;
  final VoidCallback? onBrand;
  final VoidCallback? onConversations;
  final VoidCallback? onNotifications;
  final VoidCallback? onSearch;
  final VoidCallback? onMap;
  final VoidCallback? onCalendar;
  final bool hasConversationAttention;
  final bool hasUnreadNotifications;
  final String? avatarLetter;
  final String? profileUsername;

  @override
  Size get preferredSize => const Size.fromHeight(64);

  bool get _usesFullBrand =>
      kind == MakoloHeaderKind.now || kind == MakoloHeaderKind.mark;

  String get _profileTitle {
    final value = profileUsername?.trim().replaceFirst(RegExp(r'^@'), '') ?? '';
    return value.isEmpty ? 'Moi' : '@$value';
  }

  String get _title => switch (kind) {
    MakoloHeaderKind.now || MakoloHeaderKind.mark => 'Makolo',
    MakoloHeaderKind.discover => 'Découvrir',
    MakoloHeaderKind.ongoing => 'En cours',
    MakoloHeaderKind.me => _profileTitle,
    MakoloHeaderKind.work => 'Métier',
    MakoloHeaderKind.us => 'Nous',
  };

  List<Widget> _contextActions() => switch (kind) {
    MakoloHeaderKind.now => [
      if (onConversations != null)
        _HeaderAction(
          tooltip: hasConversationAttention
              ? 'Conversations — quelque chose demande votre attention'
              : 'Conversations',
          icon: Icons.forum_outlined,
          onPressed: onConversations,
          attention: hasConversationAttention,
        ),
      if (onNotifications != null)
        _HeaderAction(
          tooltip: hasUnreadNotifications
              ? 'Notifications — nouveaux signaux disponibles'
              : 'Notifications',
          icon: Icons.notifications_none_outlined,
          onPressed: onNotifications,
          attention: hasUnreadNotifications,
        ),
    ],
    MakoloHeaderKind.discover => [
      if (onSearch != null)
        _HeaderAction(
          tooltip: 'Rechercher',
          icon: Icons.search,
          onPressed: onSearch,
        ),
      if (onMap != null)
        _HeaderAction(
          tooltip: 'Carte',
          icon: Icons.map_outlined,
          onPressed: onMap,
        ),
    ],
    MakoloHeaderKind.ongoing => [
      if (onCalendar != null)
        _HeaderAction(
          tooltip: 'Calendrier',
          icon: Icons.calendar_month_outlined,
          onPressed: onCalendar,
        ),
    ],
    MakoloHeaderKind.mark ||
    MakoloHeaderKind.me ||
    MakoloHeaderKind.work ||
    MakoloHeaderKind.us => const [],
  };

  Widget _titleWidget(BuildContext context) {
    final title = _usesFullBrand
        ? SvgPicture.asset(
            Theme.of(context).brightness == Brightness.dark
                ? 'assets/brand/makolo-logo-white.svg'
                : 'assets/brand/makolo-logo-violet.svg',
            height: 38,
            fit: BoxFit.contain,
            semanticsLabel: 'Makolo',
          )
        : Semantics(
            container: true,
            label: _title,
            child: ExcludeSemantics(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const MakoloMark(
                    size: 25,
                    semantics: MakoloMarkSemantics.decorative,
                  ),
                  const SizedBox(width: MakoloSpacing.sm),
                  Flexible(
                    child: Text(
                      _title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.2,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );

    final onTap = onBrand;
    if (onTap == null) return title;
    return Semantics(
      button: true,
      label: 'Revenir à Maintenant',
      child: InkWell(
        borderRadius: BorderRadius.circular(MakoloRadii.control),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xs),
          child: title,
        ),
      ),
    );
  }

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
      title: _titleWidget(context),
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
