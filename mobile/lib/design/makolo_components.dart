import 'package:flutter/material.dart';

import 'makolo_theme.dart';

enum MakoloStatusTone { neutral, info, success, warning, error }

class MakoloStatus extends StatelessWidget {
  const MakoloStatus({
    super.key,
    required this.label,
    this.tone = MakoloStatusTone.neutral,
    this.icon,
  });

  final String label;
  final MakoloStatusTone tone;
  final IconData? icon;

  Color _accent(BuildContext context) {
    return switch (tone) {
      MakoloStatusTone.neutral => Theme.of(
        context,
      ).colorScheme.onSurfaceVariant,
      MakoloStatusTone.info => context.makoloSurfaces.info,
      MakoloStatusTone.success => context.makoloSurfaces.success,
      MakoloStatusTone.warning => context.makoloSurfaces.warning,
      MakoloStatusTone.error => Theme.of(context).colorScheme.error,
    };
  }

  @override
  Widget build(BuildContext context) {
    final accent = _accent(context);
    return Semantics(
      label: 'Statut : $label',
      child: ExcludeSemantics(
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: accent.withValues(alpha: 0.10),
            borderRadius: BorderRadius.circular(MakoloRadii.pill),
            border: Border.all(color: accent.withValues(alpha: 0.24)),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: MakoloSpacing.compact,
              vertical: MakoloSpacing.xs,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (icon != null) ...[
                  Icon(icon, size: 14, color: accent),
                  const SizedBox(width: MakoloSpacing.xs),
                ],
                Flexible(
                  child: Text(
                    label,
                    style: Theme.of(context).textTheme.bodySmall
                        ?.copyWith(color: accent, fontWeight: FontWeight.w700),
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

@immutable
class MakoloMetadataItem {
  const MakoloMetadataItem(this.label, {this.icon});

  final String label;
  final IconData? icon;
}

class MakoloMetadata extends StatelessWidget {
  const MakoloMetadata({
    super.key,
    required this.items,
    this.spacing = MakoloSpacing.compact,
  });

  final List<MakoloMetadataItem> items;
  final double spacing;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: spacing,
      runSpacing: MakoloSpacing.sm,
      children: [
        for (final item in items)
          Semantics(
            label: item.label,
            child: ExcludeSemantics(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (item.icon != null) ...[
                    Icon(
                      item.icon,
                      size: 16,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                    const SizedBox(width: MakoloSpacing.xs),
                  ],
                  Text(
                    item.label,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

class MakoloSection extends StatelessWidget {
  const MakoloSection({
    super.key,
    required this.title,
    required this.child,
    this.description,
    this.action,
    this.padding = const EdgeInsets.symmetric(horizontal: MakoloSpacing.inner),
  });

  final String title;
  final String? description;
  final Widget? action;
  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: padding,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: Theme.of(context).textTheme.titleLarge),
                    if (description != null) ...[
                      const SizedBox(height: MakoloSpacing.xs),
                      Text(
                        description!,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (action != null) ...[
                const SizedBox(width: MakoloSpacing.sm),
                action!,
              ],
            ],
          ),
          const SizedBox(height: MakoloSpacing.md),
          child,
        ],
      ),
    );
  }
}

class MakoloCard extends StatelessWidget {
  const MakoloCard({
    super.key,
    required this.child,
    this.onTap,
    this.semanticLabel,
    this.padding = const EdgeInsets.all(MakoloSpacing.md),
  });

  final Widget child;
  final VoidCallback? onTap;
  final String? semanticLabel;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final card = Card(
      clipBehavior: Clip.antiAlias,
      child: onTap == null
          ? Padding(padding: padding, child: child)
          : InkWell(
              onTap: onTap,
              child: Padding(padding: padding, child: child),
            ),
    );
    if (semanticLabel == null) return card;
    return Semantics(
      container: true,
      button: onTap != null,
      label: semanticLabel,
      child: card,
    );
  }
}
