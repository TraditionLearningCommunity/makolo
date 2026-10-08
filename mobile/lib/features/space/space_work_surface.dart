import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../design/behavior_states.dart';
import '../../design/makolo_theme.dart';

class SpaceWorkSurface extends StatelessWidget {
  const SpaceWorkSurface({super.key, required this.payload});

  final Map<String, dynamic> payload;

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
          label: _string(section['representation']) ?? entry.key,
          items: items
              .whereType<Map>()
              .map(_copyMap)
              .toList(growable: false),
        ),
      );
    }
    if (visible.isEmpty) return _message(emptyMessage);

    return ListView(
      key: const Key('space-work-projection'),
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      children: [
        Text(label, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: MakoloSpacing.lg),
        for (final section in visible) ...[
          Text(
            section.label,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: MakoloSpacing.sm),
          for (final item in section.items) _item(context, item),
          const SizedBox(height: MakoloSpacing.lg),
        ],
      ],
    );
  }

  Widget _item(BuildContext context, Map<String, dynamic> item) {
    final title = _string(item['title']) ?? 'Élément';
    final subtitle = _subtitle(item);
    final source = _map(item['source']);
    final capabilities = item['capabilities'];
    final canOpenDayOf =
        source?['kind'] == 'occurrence' &&
        source?['id'] is String &&
        capabilities is List &&
        capabilities.contains('open_day_of');
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(title),
      subtitle: subtitle == null ? null : Text(subtitle),
      trailing: canOpenDayOf ? const Icon(Icons.chevron_right_rounded) : null,
      onTap: canOpenDayOf
          ? () =>
                context.push('/space/occurrences/${source!['id']}/day-of')
          : null,
    );
  }

  String? _subtitle(Map<String, dynamic> item) {
    final parts = <String>[];
    final summary = _string(item['summary']);
    if (summary != null) parts.add(summary);
    final timing = _map(item['timing']);
    final day = _string(timing?['start_date']);
    final clock = _string(timing?['start_time']);
    if (day != null) {
      parts.add(clock == null ? day : '$day · $clock');
    }
    final until = _string(timing?['available_until']);
    if (until != null) parts.add('Jusqu’au $until');
    final itemContext = _map(item['context']);
    final passengerCapacity = itemContext?['passenger_capacity'];
    if (passengerCapacity is num) {
      parts.add('${passengerCapacity.toInt()} places');
    }
    return parts.isEmpty ? null : parts.join('\n');
  }

  Widget _message(String message) => ListView(
    padding: const EdgeInsets.all(MakoloSpacing.lg),
    children: [MakoloEmptyState(title: message)],
  );
}

class _WorkSection {
  const _WorkSection({required this.label, required this.items});
  final String label;
  final List<Map<String, dynamic>> items;
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
