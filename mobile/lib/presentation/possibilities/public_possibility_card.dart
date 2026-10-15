import 'package:flutter/material.dart';

import '../../design/makolo_theme.dart';
import '../../features/discovery/discovery_selector.dart';

/// One public Discovery presentation, two densities; no domain ownership.
class PublicPossibilityCard extends StatelessWidget {
  const PublicPossibilityCard({
    super.key,
    required this.item,
    required this.onTap,
    this.compact = false,
  });

  final DiscoveryItemPresentation item;
  final VoidCallback onTap;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final uri = item.imageUrl == null ? null : Uri.tryParse(item.imageUrl!);
    final hasImage =
        uri != null &&
        (uri.scheme == 'https' || uri.scheme == 'http') &&
        uri.host.isNotEmpty;
    return Padding(
      padding: EdgeInsets.only(
        bottom: compact ? MakoloSpacing.sm : MakoloSpacing.md,
      ),
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (hasImage && !compact)
                AspectRatio(
                  aspectRatio: 4 / 3,
                  child: Image.network(
                    item.imageUrl!,
                    fit: BoxFit.cover,
                    errorBuilder: (context, error, stackTrace) =>
                        const SizedBox.shrink(),
                  ),
                ),
              Padding(
                padding: EdgeInsets.all(
                  compact ? MakoloSpacing.sm : MakoloSpacing.md,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (item.eyebrow != null) ...[
                      Text(
                        item.eyebrow!,
                        style: theme.textTheme.labelMedium?.copyWith(
                          color: theme.colorScheme.primary,
                        ),
                      ),
                      const SizedBox(height: MakoloSpacing.xs),
                    ],
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            item.title,
                            style: compact
                                ? theme.textTheme.titleSmall
                                : theme.textTheme.titleMedium,
                          ),
                        ),
                        if (compact) const Icon(Icons.chevron_right, size: 20),
                      ],
                    ),
                    if (item.summary.isNotEmpty) ...[
                      const SizedBox(height: MakoloSpacing.xs),
                      Text(
                        item.summary,
                        maxLines: compact ? 2 : 3,
                        overflow: TextOverflow.ellipsis,
                        style: compact ? theme.textTheme.bodySmall : null,
                      ),
                    ],
                    if (item.routeLabel != null)
                      Text(
                        item.routeLabel!,
                        style: theme.textTheme.labelMedium,
                      ),
                    if (!compact && item.owner != null)
                      Text(item.owner!, style: theme.textTheme.bodySmall),
                    if (item.place != null)
                      Text(item.place!, style: theme.textTheme.bodySmall),
                    if (item.timing != null)
                      Text(item.timing!, style: theme.textTheme.bodySmall),
                    if (item.price != null)
                      Text(item.price!, style: theme.textTheme.bodySmall),
                    if (!compact) ...[
                      const SizedBox(height: MakoloSpacing.sm),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: [
                          Text(
                            'Voir le détail',
                            style: TextStyle(color: theme.colorScheme.primary),
                          ),
                          const SizedBox(width: 4),
                          const Icon(Icons.arrow_forward, size: 18),
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
    );
  }
}
