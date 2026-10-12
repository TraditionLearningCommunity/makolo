import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../presentation/contracts/space_presentation.dart';

class SpaceWorkSurface extends StatelessWidget {
  const SpaceWorkSurface({super.key, required this.payload, this.onLoadMore});

  final Map<String, dynamic> payload;
  final void Function(String section)? onLoadMore;

  @override
  Widget build(BuildContext context) {
    final label = _string(payload['primary_business_label']) ?? 'Activités';
    final presentation = _map(payload['presentation']);
    final emptyMessage =
        _string(presentation?['empty_message']) ??
        'Aucune activité visible pour le moment.';
    final sections = _map(payload['sections']);
    if (sections == null) {
      return _message('Cette vue n’est pas disponible pour le moment.');
    }

    final visible = <_WorkSection>[];
    for (final entry in sections.entries) {
      final section = _map(entry.value);
      final items = section?['items'];
      if (section == null || items is! List || items.isEmpty) continue;
      visible.add(
        _WorkSection(
          key: entry.key,
          label: _string(section['representation']) ?? entry.key,
          items: items.whereType<Map>().map(_copyMap).toList(growable: false),
          hasMore: section['has_more'] == true,
        ),
      );
    }

    return ListView(
      key: const Key('space-work-projection'),
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      children: [
        Text(label, style: Theme.of(context).textTheme.headlineSmall),
        Wrap(
          spacing: MakoloSpacing.sm,
          runSpacing: MakoloSpacing.sm,
          children: [
            OutlinedButton.icon(
              icon: const Icon(Icons.search),
              label: const Text('Rechercher'),
              onPressed: () => context.push('/space/search'),
            ),
            OutlinedButton.icon(
              icon: const Icon(Icons.history),
              label: const Text('Historique'),
              onPressed: () => context.push('/space/history'),
            ),
          ],
        ),
        const SizedBox(height: MakoloSpacing.md),
        if (visible.isEmpty) Text(emptyMessage),
        const SizedBox(height: MakoloSpacing.lg),
        for (final section in visible) ...[
          Text(
            section.label,
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: MakoloSpacing.sm),
          for (final item in section.items) _item(context, item),
          if (section.hasMore) ...[
            const Text('Aperçu partiel : d’autres éléments existent.'),
            if (onLoadMore != null ||
                _string(_map(payload['space'])?['slug']) != null)
              TextButton(
                onPressed: () {
                  if (onLoadMore != null) {
                    onLoadMore!(section.key);
                  } else {
                    final slug = _string(_map(payload['space'])?['slug'])!;
                    context.push(
                      '/space/${Uri.encodeComponent(slug)}/work/${Uri.encodeComponent(section.key)}',
                    );
                  }
                },
                child: const Text('Afficher la suite'),
              ),
          ],
          const SizedBox(height: MakoloSpacing.lg),
        ],
      ],
    );
  }

  Widget _item(BuildContext context, Map<String, dynamic> item) {
    final title = _string(item['title']) ?? 'Élément';
    final summary = _string(item['summary']);
    final source = _map(item['source']);
    final kind = _string(item['kind']) ?? _string(source?['kind']);
    final capabilities = item['capabilities'];
    final canOpenDayOf =
        source?['kind'] == 'occurrence' &&
        source?['id'] is String &&
        capabilities is List &&
        capabilities.contains('open_day_of');

    final metadataItems = <MakoloMetadataItem>[];
    final timing = _map(item['timing']);
    final day = _string(timing?['start_date']);
    final clock = _string(timing?['start_time']);
    if (day != null) {
      metadataItems.add(
        MakoloMetadataItem(
          clock == null ? day : '$day · $clock',
          icon: Icons.schedule_outlined,
        ),
      );
    }
    final until = _string(timing?['available_until']);
    if (until != null) {
      metadataItems.add(
        MakoloMetadataItem(
          'Jusqu’au $until',
          icon: Icons.event_available_outlined,
        ),
      );
    }
    final itemContext = _map(item['context']);
    final passengerCapacity = itemContext?['passenger_capacity'];
    if (passengerCapacity is num) {
      metadataItems.add(
        MakoloMetadataItem(
          '${passengerCapacity.toInt()} places',
          icon: Icons.airline_seat_recline_normal_outlined,
        ),
      );
    }

    final state = _string(item['state']);
    final activity = _map(itemContext?['activity']);
    final activityTitle = _string(activity?['title']);
    final place = _string(_map(itemContext?['place'])?['name']);
    if (place != null) {
      metadataItems.add(MakoloMetadataItem(place, icon: Icons.place_outlined));
    }
    final pricing = _map(itemContext?['pricing']);
    final amount = _string(pricing?['unit_price']);
    final currency = _string(pricing?['currency']);
    if (amount != null && currency != null) {
      metadataItems.add(
        MakoloMetadataItem(
          'Prix unitaire : $amount $currency',
          icon: Icons.payments_outlined,
        ),
      );
    }
    final route = capabilities is List && capabilities.contains('view')
        ? spaceOwnerRoute(
            slug: _string(_map(payload['space'])?['slug']),
            kind: _string(source?['kind']),
            id: _string(source?['id']),
          )
        : null;

    return Padding(
      padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
      child: MakoloCard(
        onTap: route != null
            ? () => context.push(route)
            : canOpenDayOf
            ? () => context.push('/space/occurrences/${source!['id']}/day-of')
            : null,
        semanticLabel: title,
        padding: const EdgeInsets.all(MakoloSpacing.md),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(top: 2, right: MakoloSpacing.md),
              child: Icon(
                _archetypeIcon(kind),
                color: Theme.of(context).colorScheme.primary,
                size: 22,
              ),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w600),
                  ),
                  if (summary != null) ...[
                    const SizedBox(height: MakoloSpacing.xs),
                    Text(
                      summary,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                  if (metadataItems.isNotEmpty) ...[
                    const SizedBox(height: MakoloSpacing.sm),
                    MakoloMetadata(items: metadataItems),
                  ],
                  if (state != null) ...[
                    const SizedBox(height: MakoloSpacing.xs),
                    MakoloStatus(label: spaceStateLabel(state)),
                  ],
                  if (activityTitle != null && activityTitle != title)
                    Text(activityTitle),
                  if (canOpenDayOf)
                    TextButton.icon(
                      onPressed: () => context.push(
                        '/space/occurrences/${Uri.encodeComponent(source!['id'] as String)}/day-of',
                      ),
                      icon: const Icon(Icons.play_circle_outline),
                      label: const Text('Jour J'),
                    ),
                ],
              ),
            ),
            if (route != null || canOpenDayOf)
              Padding(
                padding: const EdgeInsets.only(left: MakoloSpacing.sm, top: 2),
                child: Icon(
                  Icons.chevron_right_rounded,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
          ],
        ),
      ),
    );
  }

  IconData _archetypeIcon(String? kind) {
    return switch (kind) {
      'departure' || 'transport_route' => Icons.directions_bus_outlined,
      'occurrence' => Icons.schedule_outlined,
      'activity' => Icons.local_activity_outlined,
      'offer' || 'order' => Icons.shopping_bag_outlined,
      'journey' => Icons.timeline_outlined,
      _ => Icons.work_outline_rounded,
    };
  }

  Widget _message(String message) => ListView(
    padding: const EdgeInsets.all(MakoloSpacing.lg),
    children: [MakoloEmptyState(title: message)],
  );
}

class _WorkSection {
  const _WorkSection({
    required this.key,
    required this.label,
    required this.items,
    required this.hasMore,
  });
  final String label;
  final String key;
  final List<Map<String, dynamic>> items;
  final bool hasMore;
}

Map<String, dynamic>? _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return _copyMap(value);
  return null;
}

Map<String, dynamic> _copyMap(Map value) => <String, dynamic>{
  for (final entry in value.entries)
    if (entry.key is String) entry.key as String: entry.value,
};

String? _string(Object? value) {
  if (value is! String) return null;
  final trimmed = value.trim();
  return trimmed.isEmpty ? null : trimmed;
}
