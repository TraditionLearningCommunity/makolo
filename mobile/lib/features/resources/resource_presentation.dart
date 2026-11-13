import 'package:flutter/material.dart';

import '../../design/action_controls.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';

/// Presentation-only description of one Resources territory.
///
/// Owners, permissions and authority stay outside this model. It only carries
/// facts that have already been projected for the active actor context.
class ResourceHubEntryData {
  const ResourceHubEntryData({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.count,
    this.onTap,
    this.key,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final int? count;
  final VoidCallback? onTap;
  final Key? key;
}

/// Shared Resources hub presentation for Profile and Space contexts.
class ResourceHubScaffold extends StatelessWidget {
  const ResourceHubScaffold({
    super.key,
    required this.title,
    required this.onRefresh,
    required this.refreshing,
    required this.entries,
    this.notice,
    this.emptyMessage,
  });

  final String title;
  final Future<void> Function() onRefresh;
  final bool refreshing;
  final List<ResourceHubEntryData> entries;
  final Widget? notice;
  final String? emptyMessage;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(title),
      actions: [
        MakoloIconActionButton(
          tooltip: 'Actualiser',
          icon: Icons.refresh_rounded,
          onPressed: refreshing ? null : onRefresh,
        ),
      ],
    ),
    body: RefreshIndicator(
      onRefresh: onRefresh,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 860),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(MakoloSpacing.inner),
            children: [
              if (notice != null) ...[
                notice!,
                const SizedBox(height: MakoloSpacing.md),
              ],
              if (entries.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(
                    vertical: MakoloSpacing.xl,
                  ),
                  child: Center(
                    child: Text(
                      emptyMessage ?? 'Aucune ressource disponible.',
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              else
                for (var index = 0; index < entries.length; index++) ...[
                  ResourceHubEntry(entry: entries[index]),
                  if (index != entries.length - 1)
                    const SizedBox(height: MakoloSpacing.md),
                ],
            ],
          ),
        ),
      ),
    ),
  );
}

class ResourceHubEntry extends StatelessWidget {
  const ResourceHubEntry({super.key, required this.entry});

  final ResourceHubEntryData entry;

  @override
  Widget build(BuildContext context) => MakoloCard(
    key: entry.key,
    onTap: entry.onTap,
    child: Row(
      children: [
        Container(
          width: 52,
          height: 52,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.primary.withValues(alpha: .10),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Icon(
            entry.icon,
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
        const SizedBox(width: MakoloSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                entry.title,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: MakoloSpacing.xs),
              Text(
                entry.subtitle,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        if (entry.count != null && entry.count! > 0) ...[
          const SizedBox(width: MakoloSpacing.sm),
          Text(
            '${entry.count}',
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
              color: Theme.of(context).colorScheme.primary,
            ),
          ),
        ],
        if (entry.onTap != null) ...[
          const SizedBox(width: MakoloSpacing.xs),
          const Icon(Icons.chevron_right_rounded),
        ],
      ],
    ),
  );
}

/// Shared title treatment used by Resources collections.
class ResourceCountTitle extends StatelessWidget {
  const ResourceCountTitle({
    super.key,
    required this.title,
    this.count,
  });

  final String title;
  final int? count;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Flexible(
        child: Text(
          title,
          maxLines: 1,
          overflow: TextOverflow.clip,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      if (count != null) ...[
        const SizedBox(width: MakoloSpacing.sm),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.primary.withValues(alpha: .10),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Text(
            '$count',
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: Theme.of(context).colorScheme.primary,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    ],
  );
}

/// Shared collection chrome. Data acquisition and owner decisions remain in
/// the feature screen; this widget only keeps presentation consistent.
class ResourceCollectionScaffold extends StatelessWidget {
  const ResourceCollectionScaffold({
    super.key,
    required this.title,
    required this.count,
    required this.searching,
    required this.searchController,
    required this.searchHint,
    required this.onSearchChanged,
    required this.onOpenSearch,
    required this.onCloseSearch,
    required this.onRefresh,
    required this.refreshing,
    required this.children,
    this.actions = const [],
    this.filterBar,
    this.scrollController,
    this.storageKey,
  });

  final String title;
  final int? count;
  final bool searching;
  final TextEditingController searchController;
  final String searchHint;
  final ValueChanged<String> onSearchChanged;
  final VoidCallback onOpenSearch;
  final VoidCallback onCloseSearch;
  final Future<void> Function() onRefresh;
  final bool refreshing;
  final List<Widget> actions;
  final Widget? filterBar;
  final ScrollController? scrollController;
  final Key? storageKey;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: searching
          ? TextField(
              controller: searchController,
              autofocus: true,
              onChanged: onSearchChanged,
              textInputAction: TextInputAction.search,
              decoration: InputDecoration(
                hintText: searchHint,
                border: InputBorder.none,
                isDense: true,
              ),
            )
          : ResourceCountTitle(title: title, count: count),
      actions: [
        if (searching)
          MakoloIconActionButton(
            tooltip: 'Fermer la recherche',
            icon: Icons.close_rounded,
            onPressed: onCloseSearch,
          )
        else
          MakoloIconActionButton(
            tooltip: 'Rechercher',
            icon: Icons.search_rounded,
            onPressed: onOpenSearch,
          ),
        ...actions,
        MakoloIconActionButton(
          tooltip: 'Actualiser',
          icon: Icons.refresh_rounded,
          onPressed: refreshing ? null : onRefresh,
        ),
      ],
    ),
    body: RefreshIndicator(
      onRefresh: onRefresh,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 860),
          child: ListView(
            controller: scrollController,
            key: storageKey,
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(MakoloSpacing.inner),
            children: [
              if (filterBar != null) ...[
                filterBar!,
                const SizedBox(height: MakoloSpacing.sm),
              ],
              ...children,
            ],
          ),
        ),
      ),
    ),
  );

class ResourceDocumentHeader extends StatelessWidget {
  const ResourceDocumentHeader({
    super.key,
    required this.title,
    required this.subtitle,
    this.icon = Icons.description_outlined,
  });

  final String title;
  final String subtitle;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Icon(
        icon,
        size: 32,
        color: Theme.of(context).colorScheme.primary,
      ),
      const SizedBox(width: MakoloSpacing.md),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: MakoloSpacing.xs),
            Text(
              subtitle,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    ],
  );
}

class ResourceSectionHeader extends StatelessWidget {
  const ResourceSectionHeader({
    super.key,
    required this.title,
    this.count,
    this.action,
  });

  final String title;
  final int? count;
  final Widget? action;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(
        child: Text(title, style: Theme.of(context).textTheme.titleLarge),
      ),
      if (count != null) ...[
        Text(
          '$count',
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
        if (action != null) const SizedBox(width: MakoloSpacing.xs),
      ],
      if (action != null) action!,
    ],
  );
}

class ResourceVersionCard extends StatelessWidget {
  const ResourceVersionCard({
    super.key,
    required this.title,
    required this.subtitle,
    this.leading,
    this.onTap,
    this.actions = const [],
  });

  final String title;
  final String subtitle;
  final IconData? leading;
  final VoidCallback? onTap;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) => MakoloCard(
    onTap: onTap,
    child: Row(
      children: [
        if (leading != null) ...[
          Icon(leading),
          const SizedBox(width: MakoloSpacing.md),
        ],
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: MakoloSpacing.xs),
              Text(
                subtitle,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        if (actions.isNotEmpty) ...[
          const SizedBox(width: MakoloSpacing.sm),
          Row(mainAxisSize: MainAxisSize.min, children: actions),
        ] else if (onTap != null) ...[
          const SizedBox(width: MakoloSpacing.sm),
          const Icon(Icons.chevron_right_rounded),
        ],
      ],
    ),
  );
}

}
