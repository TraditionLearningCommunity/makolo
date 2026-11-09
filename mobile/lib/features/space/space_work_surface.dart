import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../presentation/contracts/space_presentation.dart';

class SpaceWorkSurface extends StatelessWidget {
  const SpaceWorkSurface({
    super.key,
    required this.payload,
    this.onLoadMore,
    this.mediaBaseUri,
  });

  final Map<String, dynamic> payload;
  final void Function(String section)? onLoadMore;
  final Uri? mediaBaseUri;

  @override
  Widget build(BuildContext context) {
    final label = _string(payload['primary_business_label']) ?? 'Activités';
    final presentation = _map(payload['presentation']);
    final emptyMessage =
        _string(presentation?['empty_message']) ??
        'Aucune activité à afficher.';
    final sections = _map(payload['sections']);
    final archetype = _string(payload['archetype']);
    final spaceSlug = _string(_map(payload['space'])?['slug']);
    final limitedToActivities =
        _map(payload['authority'])?['limited_to_activities'] == true;
    final canCreateG1 =
        (archetype == 'generic' ||
            archetype == 'community' ||
            archetype == 'creative' ||
            archetype == 'media') &&
        _string(payload['responsibility']) == 'all' &&
        _map(payload['capabilities'])?['create_activity'] == true &&
        spaceSlug != null;
    final canCreateG2 =
        (archetype == 'education' || archetype == 'service_provider') &&
        _string(payload['responsibility']) == 'all' &&
        _map(payload['capabilities'])?['create_g2'] == true &&
        spaceSlug != null;
    final canCreateTransport =
        archetype == 'transport_operator' &&
        _string(payload['responsibility']) == 'all' &&
        _map(payload['capabilities'])?['create_transport'] == true &&
        spaceSlug != null;
    if (sections == null) {
      return _message('Impossible d’afficher ces informations.');
    }

    // Server composition owns the reading order and eight métier chapters.
    // Never rank/reorder by local timestamps, amounts or UI popularity.
    final visible = _composeSections(sections, presentation);

    return ListView(
      key: const Key('space-work-projection'),
      padding: const EdgeInsets.all(MakoloSpacing.lg),
      children: [
        Semantics(
          header: true,
          child: Text(label, style: Theme.of(context).textTheme.headlineSmall),
        ),
        if (_string(presentation?['question']) case final String question)
          Padding(
            padding: const EdgeInsets.only(top: MakoloSpacing.sm),
            child: Text(question),
          ),
        if (limitedToActivities)
          Padding(
            padding: const EdgeInsets.only(top: MakoloSpacing.sm),
            child: Text(
              'Vous voyez uniquement les activités auxquelles vous avez accès.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        Wrap(
          spacing: MakoloSpacing.sm,
          runSpacing: MakoloSpacing.sm,
          children: [
            if (canCreateTransport)
              MakoloActionButton(
                appearance: MakoloActionAppearance.primary,
                icon: Icons.add,
                label: 'Planifier dans Transport',
                onPressed: () => context.push(
                  '/space/${Uri.encodeComponent(spaceSlug)}/work/g3/transport/new',
                ),
              ),
            if (canCreateG2)
              MakoloActionButton(
                appearance: MakoloActionAppearance.primary,
                icon: Icons.add,
                label: archetype == 'education'
                    ? 'Nouveau programme'
                    : 'Nouvelle prestation',
                onPressed: () => context.push(
                  '/space/${Uri.encodeComponent(spaceSlug)}/work/g2/new'
                  '?archetype=${Uri.encodeComponent(archetype!)}',
                ),
              ),
            if (canCreateG1)
              MakoloActionButton(
                appearance: MakoloActionAppearance.primary,
                icon: Icons.add,
                label: archetype == 'community'
                    ? 'Nouvelle initiative'
                    : archetype == 'creative'
                    ? 'Nouvelle création'
                    : archetype == 'media'
                    ? 'Nouvelle production'
                    : 'Nouvelle activité',
                onPressed: () => context.push(
                  '/space/${Uri.encodeComponent(spaceSlug)}/work/activities/new'
                  '?archetype=${Uri.encodeComponent(archetype!)}',
                ),
              ),
            MakoloActionButton(
              appearance: MakoloActionAppearance.secondary,
              icon: Icons.search,
              label: 'Rechercher',
              onPressed: () => context.push('/space/search'),
            ),
            MakoloActionButton(
              appearance: MakoloActionAppearance.secondary,
              icon: Icons.history,
              label: 'Historique',
              onPressed: () => context.push('/space/history'),
            ),
          ],
        ),
        const SizedBox(height: MakoloSpacing.md),
        if (visible.isEmpty)
          Text(
            payload['coverage_state'] == 'partial' ||
                    payload['composition_state'] == 'partial'
                ? 'Cette vue est partielle. Aucun élément à afficher dans cette sélection.'
                : emptyMessage,
          ),
        if (visible.isNotEmpty)
          if (_string(presentation?['calm_message']) case final String calm)
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.md),
              child: Text(calm),
            ),
        const SizedBox(height: MakoloSpacing.lg),
        for (final section in visible) ...[
          if (section.chapterTitle != null) ...[
            Semantics(
              header: true,
              child: Text(
                section.chapterTitle!,
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            const SizedBox(height: MakoloSpacing.md),
          ],
          Semantics(
            header: true,
            child: Text(
              section.label,
              style: Theme.of(context).textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
          ),
          const SizedBox(height: MakoloSpacing.sm),
          if (section.items.isEmpty)
            const Text('Aucun élément dans cet aperçu.'),
          for (final item in section.items) _item(context, item, section.key),
          if (section.hasMore) ...[
            const Text('Aperçu partiel : d’autres éléments existent.'),
            if (onLoadMore != null ||
                _string(_map(payload['space'])?['slug']) != null)
              MakoloActionButton(
                appearance: MakoloActionAppearance.quiet,
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
                label: 'Afficher la suite',
              ),
          ],
          const SizedBox(height: MakoloSpacing.lg),
        ],
      ],
    );
  }

  Widget _item(
    BuildContext context,
    Map<String, dynamic> item,
    String sectionKey,
  ) {
    final title = _string(item['title']) ?? 'Élément';
    final summary = _string(item['summary']);
    final source = _map(item['source']);
    final kind = _string(item['kind']) ?? _string(source?['kind']);
    final capabilities = item['capabilities'];
    // Only the canonical public PresentationMediaUse delivery URL is rendered.
    // A private resource, bare asset or unverified external URL is never an image.
    final bindings = item['media_bindings'];
    final recognition = bindings is List && bindings.isNotEmpty
        ? _map(bindings.first)
        : null;
    final mediaOwner = _map(recognition?['owner']);
    final mediaPath = _string(recognition?['url']);
    final mediaUri =
        mediaBaseUri != null &&
            (payload['archetype'] == 'creative' ||
                payload['archetype'] == 'media') &&
            recognition?['authorized'] == true &&
            recognition?['purpose'] == 'recognize' &&
            recognition?['kind'] == 'image' &&
            (recognition?['mime_type'] == 'image/jpeg' ||
                recognition?['mime_type'] == 'image/png') &&
            mediaOwner?['kind'] == source?['kind'] &&
            mediaOwner?['id'] == source?['id'] &&
            mediaPath != null &&
            mediaPath.startsWith('/presentation/media/uses/') &&
            mediaPath.endsWith('/file/')
        ? mediaBaseUri!.resolve(mediaPath)
        : null;
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
          '${passengerCapacity.toInt()} places physiques',
          icon: Icons.airline_seat_recline_normal_outlined,
        ),
      );
    }
    // Display only facts already disclosed by each real owner. A vehicle's
    // physical capacity is not availability, and satisfied requirements do
    // not constitute a generic readiness verdict.
    final transport = _map(itemContext?['transport']);
    final routeName = _string(_map(transport?['route'])?['name']);
    if (routeName != null) {
      metadataItems.add(
        MakoloMetadataItem('Route : $routeName', icon: Icons.route_outlined),
      );
    }
    final vehicleName = _string(_map(transport?['vehicle'])?['label']);
    if (vehicleName != null) {
      metadataItems.add(
        MakoloMetadataItem(
          'Véhicule affecté : $vehicleName',
          icon: Icons.directions_bus_outlined,
        ),
      );
    }
    final capacity = _map(itemContext?['capacity']);
    if (capacity?['basis'] == 'capacity_pool') {
      final availability = capacity?['pool_active'] == false
          ? 'Capacité désactivée'
          : capacity?['unlimited'] == true
          ? 'Capacité sans limite définie'
          : capacity?['available'] is num && capacity?['total'] is num
          ? 'Disponibilité : ${capacity!['available']} sur ${capacity['total']}'
          : null;
      if (availability != null) {
        metadataItems.add(
          MakoloMetadataItem(
            availability,
            icon: Icons.event_available_outlined,
          ),
        );
      }
    }
    final assessments = _map(itemContext?['conditions']);
    if (assessments?['basis'] == 'service_requirement_assessment' &&
        assessments?['total'] is int &&
        assessments?['satisfied'] is int) {
      metadataItems.add(
        MakoloMetadataItem(
          'Conditions évaluées : ${assessments!['satisfied']} / '
          '${assessments['total']} satisfaites',
          icon: Icons.fact_check_outlined,
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
        ? spaceWorkOwnerRoute(
            slug: _string(_map(payload['space'])?['slug']),
            kind: _string(source?['kind']),
            id: _string(source?['id']),
            section: sectionKey,
            fromCollection: onLoadMore != null,
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
              child: mediaUri == null
                  ? Icon(
                      _archetypeIcon(kind, _string(payload['archetype'])),
                      color: Theme.of(context).colorScheme.primary,
                      size: 22,
                    )
                  : Semantics(
                      label:
                          _string(recognition?['label']) ??
                          'Visuel publié de reconnaissance',
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: Image.network(
                          mediaUri.toString(),
                          width: 72,
                          height: 72,
                          fit: BoxFit.cover,
                          errorBuilder: (_, _, _) =>
                              const Icon(Icons.image_not_supported_outlined),
                        ),
                      ),
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
                  if (_string(itemContext?['work_label'])
                      case final String workLabel)
                    if (workLabel != title)
                      Padding(
                        padding: const EdgeInsets.only(top: MakoloSpacing.xs),
                        child: Text(
                          workLabel,
                          style: Theme.of(context).textTheme.labelMedium,
                        ),
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
                  if (_map(itemContext?['next_occurrence'])
                      case final Map<String, dynamic> nextDate)
                    if (_string(nextDate['label']) case final String nextLabel)
                      Padding(
                        padding: const EdgeInsets.only(top: MakoloSpacing.xs),
                        child: Text(
                          '${_string(_map(payload['presentation'])?['next_occurrence_label']) ?? 'Prochaine date'} : $nextLabel'
                          '${_string(nextDate['start_date']) == null ? '' : ' · ${nextDate['start_date']}'}',
                        ),
                      ),
                  if (canOpenDayOf)
                    MakoloActionButton(
                      appearance: MakoloActionAppearance.quiet,
                      onPressed: () => context.push(
                        '/space/occurrences/${Uri.encodeComponent(source!['id'] as String)}/day-of',
                      ),
                      icon: Icons.play_circle_outline,
                      label: 'Jour J',
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

  IconData _archetypeIcon(String? kind, String? archetype) {
    if (kind == 'activity') {
      return switch (archetype) {
        'creative' => Icons.palette_outlined,
        'media' => Icons.newspaper_outlined,
        'education' => Icons.school_outlined,
        'community' => Icons.volunteer_activism_outlined,
        'service_provider' => Icons.handshake_outlined,
        'transport_operator' => Icons.directions_bus_outlined,
        'commerce' => Icons.storefront_outlined,
        _ => Icons.local_activity_outlined,
      };
    }
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

  List<_WorkSection> _composeSections(
    Map<String, dynamic> sections,
    Map<String, dynamic>? presentation,
  ) {
    final keys = <String>[];
    final order = presentation?['section_order'];
    if (order is List) {
      for (final raw in order) {
        final key = _string(raw);
        if (key != null && sections.containsKey(key) && !keys.contains(key)) {
          keys.add(key);
        }
      }
    }
    for (final key in sections.keys) {
      if (!keys.contains(key)) keys.add(key);
    }
    final chapters = <String, String>{};
    final groups = presentation?['reading_groups'];
    if (groups is List) {
      for (final raw in groups) {
        final group = _map(raw);
        final title = _string(group?['representation']);
        final groupKeys = group?['section_keys'];
        if (title == null || groupKeys is! List) continue;
        for (final candidate in groupKeys) {
          final key = _string(candidate);
          if (key == null || chapters.containsKey(key)) continue;
          final section = _map(sections[key]);
          if (section == null) continue;
          final rows = section['items'];
          if ((rows is List && rows.isNotEmpty) ||
              section['has_more'] == true) {
            chapters[key] = title;
            break;
          }
        }
      }
    }
    final result = <_WorkSection>[];
    for (final key in keys) {
      final section = _map(sections[key]);
      if (section == null) continue;
      final items = section['items'];
      if (items is! List) continue;
      if (items.isEmpty && section['has_more'] != true) continue;
      result.add(
        _WorkSection(
          key: key,
          label: _string(section['representation']) ?? key,
          chapterTitle: chapters[key],
          items: items.whereType<Map>().map(_copyMap).toList(growable: false),
          hasMore: section['has_more'] == true,
        ),
      );
    }
    return result;
  }
}

class _WorkSection {
  const _WorkSection({
    required this.key,
    required this.label,
    required this.items,
    required this.hasMore,
    this.chapterTitle,
  });

  final String label;
  final String key;
  final String? chapterTitle;
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
