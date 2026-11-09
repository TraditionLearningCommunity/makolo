import 'package:flutter/material.dart';

import 'makolo_theme.dart';

/// Presentation only: the Profile or Space owner supplies every fact and action.
class MakoloIdentityPortrait extends StatelessWidget {
  const MakoloIdentityPortrait({
    super.key,
    required this.name,
    required this.leading,
    this.eyebrow,
    this.subtitle,
    this.subtitleMaxLines,
    this.detail,
    this.trailing,
    this.padding = const EdgeInsets.symmetric(vertical: MakoloSpacing.compact),
  });

  final String name;
  final Widget leading;
  final String? eyebrow;
  final String? subtitle;

  /// Limit long institutional summaries without changing owner data.
  /// Omitted for personal identity to preserve its existing presentation.
  final int? subtitleMaxLines;
  final String? detail;
  final Widget? trailing;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      container: true,
      label: name,
      child: Padding(
        padding: padding,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            leading,
            const SizedBox(width: MakoloSpacing.compact),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (eyebrow != null && eyebrow!.isNotEmpty) ...[
                    Text(
                      eyebrow!,
                      style: theme.textTheme.labelMedium?.copyWith(
                        color: theme.colorScheme.primary,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: MakoloSpacing.xs),
                  ],
                  Text(
                    name,
                    style: theme.textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (subtitle != null && subtitle!.isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.xs),
                    Text(
                      subtitle!,
                      maxLines: subtitleMaxLines,
                      overflow: subtitleMaxLines == null
                          ? null
                          : TextOverflow.ellipsis,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                  if (detail != null && detail!.isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.xs),
                    Text(
                      detail!,
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodyMedium,
                    ),
                  ],
                ],
              ),
            ),
            ?trailing,
          ],
        ),
      ),
    );
  }
}

/// A common Passport recognition card; Sharing still owns all Passport actions.
class MakoloPassportGateway extends StatelessWidget {
  const MakoloPassportGateway({
    super.key,
    required this.title,
    required this.subtitle,
    required this.onOpen,
    this.semanticLabel,
  });

  final String title;
  final String subtitle;
  final VoidCallback? onOpen;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Semantics(
      button: onOpen != null,
      label: semanticLabel ?? title,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(MakoloRadii.card),
        clipBehavior: Clip.antiAlias,
        child: Ink(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              colors: [MakoloColors.indigo, MakoloColors.deep],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.all(Radius.circular(MakoloRadii.card)),
          ),
          child: InkWell(
            onTap: onOpen,
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: MakoloSpacing.md,
                vertical: MakoloSpacing.md,
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.badge_outlined,
                    color: Colors.white,
                    size: 32,
                  ),
                  const SizedBox(width: MakoloSpacing.compact),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          style: text.titleMedium?.copyWith(
                            color: Colors.white,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: MakoloSpacing.xs),
                        Text(
                          subtitle,
                          style: text.bodySmall?.copyWith(
                            color: Colors.white.withValues(alpha: .9),
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (onOpen != null) ...[
                    const SizedBox(width: MakoloSpacing.sm),
                    const Icon(
                      Icons.arrow_forward_rounded,
                      color: Colors.white,
                      size: 24,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Shared visual entry point. Never resolves or grants a domain capability.
class MakoloPrimaryShortcut extends StatelessWidget {
  const MakoloPrimaryShortcut({
    super.key,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onOpen,
    this.tapKey,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback? onOpen;
  final Key? tapKey;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surface,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        key: tapKey,
        borderRadius: BorderRadius.circular(18),
        onTap: onOpen,
        child: Container(
          constraints: const BoxConstraints(minHeight: 94),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: scheme.primary.withValues(alpha: .25)),
          ),
          child: Row(
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: scheme.primary.withValues(alpha: .085),
                  borderRadius: BorderRadius.circular(13),
                ),
                child: Icon(icon, color: scheme.primary, size: 28),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      title,
                      style: Theme.of(context).textTheme.titleMedium
                          ?.copyWith(fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      subtitle,
                      style: Theme.of(context).textTheme.bodySmall
                          ?.copyWith(color: scheme.onSurfaceVariant),
                    ),
                  ],
                ),
              ),
              Icon(Icons.arrow_forward_rounded, color: scheme.primary),
            ],
          ),
        ),
      ),
    );
  }
}

enum MakoloTerritoryLayout { list, grid }

/// Only switches how already-authorized entries are presented.
class MakoloTerritoryViewToggle extends StatelessWidget {
  const MakoloTerritoryViewToggle({
    super.key,
    required this.value,
    required this.onChanged,
    this.toggleKey,
  });

  final MakoloTerritoryLayout value;
  final ValueChanged<MakoloTerritoryLayout> onChanged;
  final Key? toggleKey;

  @override
  Widget build(BuildContext context) => SegmentedButton<MakoloTerritoryLayout>(
    key: toggleKey,
    showSelectedIcon: false,
    segments: const [
      ButtonSegment(
        value: MakoloTerritoryLayout.list,
        icon: Icon(Icons.view_list_outlined, size: 18),
        tooltip: 'Liste',
      ),
      ButtonSegment(
        value: MakoloTerritoryLayout.grid,
        icon: Icon(Icons.grid_view_rounded, size: 18),
        tooltip: 'Grille',
      ),
    ],
    selected: {value},
    onSelectionChanged: (values) => onChanged(values.first),
  );
}

class MakoloTerritoryPreview {
  const MakoloTerritoryPreview({required this.title, this.onOpen});

  final String title;
  final VoidCallback? onOpen;
}

/// Preview rows are deliberately bounded by the caller's owner-backed data.
class MakoloTerritoryListCard extends StatelessWidget {
  const MakoloTerritoryListCard({
    super.key,
    required this.title,
    required this.subtitle,
    required this.symbol,
    this.count,
    this.tapKey,
    this.onOpen,
    this.previews = const [],
    this.bottomSpacing = 8,
    this.headerVerticalPadding = 14,
    this.previewVerticalPadding = 7,
  });

  final String title;
  final String subtitle;
  final Widget symbol;
  final int? count;
  final Key? tapKey;
  final VoidCallback? onOpen;
  final List<MakoloTerritoryPreview> previews;
  final double bottomSpacing;
  final double headerVerticalPadding;
  final double previewVerticalPadding;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: EdgeInsets.only(bottom: bottomSpacing),
      child: Material(
        color: scheme.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: scheme.outlineVariant),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          children: [
            InkWell(
              key: tapKey,
              onTap: onOpen,
              child: Padding(
                padding: EdgeInsets.symmetric(
                  horizontal: 13,
                  vertical: headerVerticalPadding,
                ),
                child: Row(
                  children: [
                    symbol,
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            title,
                            style: Theme.of(context).textTheme.titleSmall
                                ?.copyWith(fontWeight: FontWeight.w800),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            subtitle,
                            style: Theme.of(context).textTheme.bodySmall
                                ?.copyWith(color: scheme.onSurfaceVariant),
                          ),
                        ],
                      ),
                    ),
                    if (count != null && count! > 0) ...[
                      Text(
                        count.toString(),
                        style: Theme.of(context).textTheme.labelMedium
                            ?.copyWith(color: scheme.onSurfaceVariant),
                      ),
                      const SizedBox(width: 6),
                    ],
                    if (onOpen != null)
                      Icon(
                        Icons.chevron_right_rounded,
                        color: scheme.onSurfaceVariant,
                      ),
                  ],
                ),
              ),
            ),
            if (previews.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(48, 0, 12, 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    for (final item in previews.take(3))
                      InkWell(
                        onTap: item.onOpen,
                        child: Padding(
                          padding: EdgeInsets.symmetric(
                            vertical: previewVerticalPadding,
                          ),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  item.title,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                              ),
                              if (item.onOpen != null)
                                Icon(
                                  Icons.arrow_outward_rounded,
                                  size: 16,
                                  color: scheme.onSurfaceVariant,
                                ),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class MakoloTerritoryGridCard extends StatelessWidget {
  const MakoloTerritoryGridCard({
    super.key,
    required this.title,
    required this.subtitle,
    required this.symbol,
    this.countDescription,
    this.tapKey,
    this.onOpen,
  });

  final String title;
  final String subtitle;
  final Widget symbol;
  final String? countDescription;
  final Key? tapKey;
  final VoidCallback? onOpen;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: scheme.outlineVariant),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        key: tapKey,
        onTap: onOpen,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 150),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 15),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Center(child: symbol),
                const SizedBox(height: 11),
                Text(
                  title,
                  textAlign: TextAlign.center,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 6),
                Text(
                  subtitle,
                  textAlign: TextAlign.center,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall
                      ?.copyWith(color: scheme.onSurfaceVariant),
                ),
                if (countDescription != null) ...[
                  const SizedBox(height: 8),
                  Text(
                    countDescription!,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.labelSmall
                        ?.copyWith(color: scheme.primary),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
