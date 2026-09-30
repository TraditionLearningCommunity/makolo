import 'package:flutter/material.dart';

import 'makolo_components.dart';
import 'makolo_theme.dart';

class MakoloStateTransition extends StatelessWidget {
  const MakoloStateTransition({
    super.key,
    required this.child,
    this.duration = MakoloMotion.short,
  });

  final Widget child;
  final Duration duration;

  @override
  Widget build(BuildContext context) {
    return AnimatedSwitcher(
      duration: MakoloMotion.effective(context, duration),
      switchInCurve: Curves.easeOutCubic,
      switchOutCurve: Curves.easeInCubic,
      transitionBuilder: (child, animation) =>
          FadeTransition(opacity: animation, child: child),
      child: child,
    );
  }
}

class MakoloStatusMetadataAction extends StatelessWidget {
  const MakoloStatusMetadataAction({
    super.key,
    required this.title,
    this.subtitle,
    this.status,
    this.metadata = const [],
    this.action,
    this.leading,
  });

  final String title;
  final String? subtitle;
  final MakoloStatus? status;
  final List<MakoloMetadataItem> metadata;
  final Widget? action;
  final Widget? leading;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (leading != null) ...[
          leading!,
          const SizedBox(width: MakoloSpacing.compact),
        ],
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleLarge),
              if (subtitle != null) ...[
                const SizedBox(height: MakoloSpacing.xs),
                Text(
                  subtitle!,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
              if (status != null) ...[
                const SizedBox(height: MakoloSpacing.sm),
                status!,
              ],
              if (metadata.isNotEmpty) ...[
                const SizedBox(height: MakoloSpacing.sm),
                MakoloMetadata(items: metadata),
              ],
            ],
          ),
        ),
        if (action != null) ...[
          const SizedBox(width: MakoloSpacing.sm),
          action!,
        ],
      ],
    );
  }
}

class MakoloAttentionBlock extends StatelessWidget {
  const MakoloAttentionBlock({
    super.key,
    required this.title,
    required this.body,
    this.action,
    this.icon = Icons.priority_high_rounded,
  });

  final String title;
  final String body;
  final Widget? action;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: 'Attention. $title. $body',
      excludeSemantics: action == null,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: context.makoloSurfaces.warning.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(MakoloRadii.card),
          border: Border.all(
            color: context.makoloSurfaces.warning.withValues(alpha: 0.24),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.md),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: context.makoloSurfaces.warning, size: 22),
              const SizedBox(width: MakoloSpacing.compact),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: MakoloSpacing.xs),
                    Text(body),
                    if (action != null) ...[
                      const SizedBox(height: MakoloSpacing.md),
                      action!,
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class MakoloTimelineItem {
  const MakoloTimelineItem({
    required this.title,
    this.body,
    this.trailing,
    this.completed = false,
    this.current = false,
  });

  final String title;
  final String? body;
  final Widget? trailing;
  final bool completed;
  final bool current;
}

class MakoloTimeline extends StatelessWidget {
  const MakoloTimeline({super.key, required this.items});

  final List<MakoloTimelineItem> items;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      explicitChildNodes: true,
      child: Column(
        children: [
          for (var index = 0; index < items.length; index++)
            _TimelineRow(
              item: items[index],
              showConnector: index < items.length - 1,
            ),
        ],
      ),
    );
  }
}

class _TimelineRow extends StatelessWidget {
  const _TimelineRow({required this.item, required this.showConnector});

  final MakoloTimelineItem item;
  final bool showConnector;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final marker = item.completed
        ? scheme.primary
        : item.current
        ? scheme.tertiary
        : scheme.outlineVariant;
    final stateLabel = item.completed
        ? 'Terminé'
        : item.current
        ? 'En cours'
        : 'À venir';
    final semanticLabel = item.body == null
        ? '$stateLabel. \${item.title}'
        : '$stateLabel. \${item.title}. \${item.body}';

    return Semantics(
      container: true,
      label: semanticLabel,
      excludeSemantics: item.trailing == null,
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              width: 28,
              child: Column(
                children: [
                  Container(
                    width: 12,
                    height: 12,
                    margin: const EdgeInsets.only(top: 5),
                    decoration: BoxDecoration(
                      color: item.completed || item.current
                          ? marker
                          : Colors.transparent,
                      shape: BoxShape.circle,
                      border: Border.all(color: marker, width: 2),
                    ),
                  ),
                  if (showConnector)
                    Expanded(
                      child: Container(
                        width: 1,
                        margin: const EdgeInsets.symmetric(
                          vertical: MakoloSpacing.xs,
                        ),
                        color: scheme.outlineVariant,
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(width: MakoloSpacing.sm),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.only(bottom: MakoloSpacing.inner),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            item.title,
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          if (item.body != null) ...[
                            const SizedBox(height: MakoloSpacing.xs),
                            Text(
                              item.body!,
                              style: Theme.of(context).textTheme.bodyMedium,
                            ),
                          ],
                        ],
                      ),
                    ),
                    if (item.trailing != null) ...[
                      const SizedBox(width: MakoloSpacing.sm),
                      item.trailing!,
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class MakoloDetailHeader extends StatelessWidget {
  const MakoloDetailHeader({
    super.key,
    required this.title,
    this.eyebrow,
    this.subtitle,
    this.status,
    this.metadata = const [],
    this.leading,
    this.trailing,
  });

  final String title;
  final String? eyebrow;
  final String? subtitle;
  final MakoloStatus? status;
  final List<MakoloMetadataItem> metadata;
  final Widget? leading;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(MakoloSpacing.inner),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (leading != null) ...[
            leading!,
            const SizedBox(height: MakoloSpacing.md),
          ],
          if (eyebrow != null) ...[
            Text(
              eyebrow!,
              style: Theme.of(context).textTheme.labelLarge
                  ?.copyWith(color: Theme.of(context).colorScheme.primary),
            ),
            const SizedBox(height: MakoloSpacing.xs),
          ],
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
              ),
              if (trailing != null) ...[
                const SizedBox(width: MakoloSpacing.sm),
                trailing!,
              ],
            ],
          ),
          if (subtitle != null) ...[
            const SizedBox(height: MakoloSpacing.sm),
            Text(
              subtitle!,
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          if (status != null) ...[
            const SizedBox(height: MakoloSpacing.md),
            status!,
          ],
          if (metadata.isNotEmpty) ...[
            const SizedBox(height: MakoloSpacing.md),
            MakoloMetadata(items: metadata),
          ],
        ],
      ),
    );
  }
}
