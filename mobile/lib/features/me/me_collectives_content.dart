import 'package:flutter/material.dart';

import '../../navigation/destination.dart';
import '../../network/makolo_api_client.dart';
import '../../presentation/media/retained_recognition_image.dart';
import 'me_selector.dart';

enum _CollectiveTab { all, spaces, teams, groups }

Map<String, dynamic>? _collectiveMap(Object? raw) {
  if (raw is! Map) return null;
  return raw.map((key, value) => MapEntry(key.toString(), value));
}

int? _collectiveCount(Object? raw) {
  final family = _collectiveMap(raw);
  final count = family?['count'];
  if (count is int && count >= 0) return count;
  final rows = family?['items'];
  if (rows is List && family?['has_more'] == false) return rows.length;
  return null;
}

/// Counts relationships, not distinct institutions. A partial/unknown family
/// cannot be replaced by its loaded page length.
int? meCollectiveTotal(Object? collectives) {
  final section = _collectiveMap(collectives);
  if (section == null) return null;
  final counts = [
    _collectiveCount(section['authorized_spaces']),
    _collectiveCount(section['teams']),
    _collectiveCount(section['groups']),
  ];
  if (counts.any((value) => value == null)) return null;
  return counts.fold<int>(0, (sum, count) => sum + count!);
}

/// Only a published, owner-bound recognition use may supply a collective
/// visual. Activity images and arbitrary profile URLs must never become a
/// Space logo by inference.
String? collectiveRecognitionPath(Object? raw, String kind, String id) {
  final bindings = _collectiveMap(raw)?['media_bindings'];
  if (bindings is! List) return null;
  for (final entry in bindings) {
    final binding = _collectiveMap(entry);
    final target = _collectiveMap(binding?['target']);
    final resource = _collectiveMap(binding?['resource']);
    final path = resource?['url'];
    if (binding?['purpose'] != 'RECOGNIZE' ||
        target?['kind'] != kind ||
        target?['id']?.toString() != id ||
        resource?['kind'] != 'presentation_media_use' ||
        !const {'image/jpeg', 'image/png'}.contains(resource?['mime_type']) ||
        path is! String ||
        !path.startsWith('/') ||
        path.startsWith('//')) {
      continue;
    }
    final uri = Uri.tryParse(path);
    if (uri == null ||
        uri.hasScheme ||
        uri.hasAuthority ||
        uri.hasQuery ||
        uri.hasFragment) {
      continue;
    }
    return path;
  }
  return null;
}

/// Presentation of Profile-scoped collective relationships. No permission,
/// membership or media is inferred from an item name or its parent.
class MeCollectivesContent extends StatefulWidget {
  const MeCollectivesContent({
    super.key,
    required this.items,
    required this.collectives,
    required this.offline,
    required this.hasMore,
    required this.onOpen,
    this.onActSpace,
    this.query = '',
    this.alphabetical = false,
    this.descending = false,
    this.mediaApi,
    this.profileId,
  });

  final List<MeItemPresentation> items;
  final Object? collectives;
  final bool offline;
  final bool hasMore;
  final bool Function(StructuredDestination) onOpen;
  final ValueChanged<MeItemPresentation>? onActSpace;
  final String query;
  final bool alphabetical;
  final bool descending;
  final MakoloApiClient? mediaApi;
  final String? profileId;

  @override
  State<MeCollectivesContent> createState() => _MeCollectivesContentState();
}

class _MeCollectivesContentState extends State<MeCollectivesContent> {
  _CollectiveTab _tab = _CollectiveTab.all;

  Map<String, dynamic>? _family(String kind) {
    final key = switch (kind) {
      'space' => 'authorized_spaces',
      'team' => 'teams',
      _ => 'groups',
    };
    return _collectiveMap(_collectiveMap(widget.collectives)?[key]);
  }

  Map<String, dynamic>? _row(MeItemPresentation item) {
    final rows = _family(item.destination.kind)?['items'];
    if (rows is! List) return null;
    for (final value in rows) {
      final row = _collectiveMap(value);
      if (row?['id']?.toString() == item.destination.id) return row;
    }
    return null;
  }

  StructuredDestination? _destination(MeItemPresentation item) {
    if (item.destination.kind == 'team') {
      final space = _collectiveMap(_row(item)?['space']);
      final id = space?['id'];
      final slug = space?['slug'];
      if (id is String && id.isNotEmpty && slug is String && slug.isNotEmpty) {
        return StructuredDestination(kind: 'space', id: id, link: slug);
      }
      return null;
    }
    return item.canOpen ? item.destination : null;
  }

  bool _canAct(MeItemPresentation item) {
    return item.destination.kind == 'space' &&
        item.canOpen &&
        !widget.offline &&
        widget.onActSpace != null &&
        _row(item)?['can_act'] == true;
  }

  List<MeItemPresentation> _visible(String kind) {
    final query = widget.query.trim().toLowerCase();
    final items = widget.items.where((item) {
      if (item.destination.kind != kind) return false;
      return query.isEmpty ||
          item.title.toLowerCase().contains(query) ||
          (item.subtitle ?? '').toLowerCase().contains(query);
    }).toList();
    if (widget.alphabetical) {
      items.sort((a, b) {
        final result = a.title.toLowerCase().compareTo(b.title.toLowerCase());
        return result != 0
            ? result
            : a.destination.id.compareTo(b.destination.id);
      });
      if (widget.descending) return items.reversed.toList(growable: false);
    }
    return items;
  }

  Widget _filters() {
    final section = _collectiveMap(widget.collectives);
    final tabs = [
      (_CollectiveTab.all, 'Tous', null),
      (
        _CollectiveTab.spaces,
        'Espaces',
        _collectiveCount(section?['authorized_spaces']),
      ),
      (_CollectiveTab.teams, 'Équipes', _collectiveCount(section?['teams'])),
      (_CollectiveTab.groups, 'Groupes', _collectiveCount(section?['groups'])),
    ];
    return SingleChildScrollView(
      key: const Key('me-collectives-filter-scroller'),
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (final tab in tabs) ...[
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: ChoiceChip(
                key: Key('me-collectives-filter-${tab.$1.name}'),
                selected: _tab == tab.$1,
                showCheckmark: false,
                label: Text(
                  tab.$3 != null && tab.$3! > 0
                      ? '${tab.$2} (${tab.$3})'
                      : tab.$2,
                ),
                onSelected: (_) => setState(() => _tab = tab.$1),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _visual(MeItemPresentation item, {double size = 60}) {
    final scheme = Theme.of(context).colorScheme;
    final path = collectiveRecognitionPath(
      _row(item),
      item.destination.kind,
      item.destination.id,
    );
    final initials = item.title
        .trim()
        .split(RegExp(r'\s+'))
        .where((word) => word.isNotEmpty)
        .take(2)
        .map((word) => word.substring(0, 1).toUpperCase())
        .join();
    final fallback = ColoredBox(
      color: scheme.primary.withValues(alpha: 0.08),
      child: Center(
        child: Text(
          initials.isEmpty ? '•' : initials,
          style: Theme.of(context).textTheme.titleMedium
              ?.copyWith(color: scheme.primary, fontWeight: FontWeight.w700),
        ),
      ),
    );
    return ClipRRect(
      key: Key(
        'me-collective-visual-${item.destination.kind}-${item.destination.id}',
      ),
      borderRadius: BorderRadius.circular(14),
      child: SizedBox(
        width: size,
        height: size,
        child: path != null && widget.mediaApi != null
            ? RetainedRecognitionImage(
                key: ValueKey('collective-media-${item.destination.id}-$path'),
                api: widget.mediaApi!,
                profileId: widget.profileId,
                path: path,
                alt: 'Image de ${item.title}',
                width: size,
                height: size,
                placeholder: fallback,
              )
            : fallback,
      ),
    );
  }

  Widget _space(MeItemPresentation item) {
    final scheme = Theme.of(context).colorScheme;
    final destination = widget.offline ? null : _destination(item);
    final canAct = _canAct(item);
    return Material(
      key: Key('me-collective-space-${item.destination.id}'),
      color: scheme.surface,
      borderRadius: BorderRadius.circular(18),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: destination == null ? null : () => widget.onOpen(destination),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              _visual(item, size: 70),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleSmall
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    if (item.subtitle != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        widget.offline ? 'Espace lié à moi' : item.subtitle!,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall
                            ?.copyWith(color: scheme.onSurfaceVariant),
                      ),
                    ],
                  ],
                ),
              ),
              if (canAct)
                TextButton(
                  key: Key('me-collectives-act-${item.destination.id}'),
                  onPressed: () => widget.onActSpace!(item),
                  child: const Text('Agir'),
                )
              else if (destination != null)
                Icon(
                  Icons.chevron_right_rounded,
                  color: scheme.onSurfaceVariant,
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _relation(MeItemPresentation item) {
    final scheme = Theme.of(context).colorScheme;
    final destination = widget.offline ? null : _destination(item);
    final subtitle = item.subtitle;
    return Material(
      key: Key('me-collective-${item.destination.kind}-${item.destination.id}'),
      color: scheme.surface,
      borderRadius: BorderRadius.circular(16),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: destination == null ? null : () => widget.onOpen(destination),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
          child: Row(
            children: [
              _visual(item, size: 52),
              const SizedBox(width: 13),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleSmall
                          ?.copyWith(fontWeight: FontWeight.w600),
                    ),
                    if (subtitle != null) ...[
                      const SizedBox(height: 3),
                      Text(
                        subtitle,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall
                            ?.copyWith(color: scheme.onSurfaceVariant),
                      ),
                    ],
                  ],
                ),
              ),
              if (destination != null)
                Icon(
                  Icons.chevron_right_rounded,
                  color: scheme.onSurfaceVariant,
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _section(
    String title,
    List<MeItemPresentation> items, {
    required String kind,
  }) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (_tab == _CollectiveTab.all)
          Padding(
            padding: const EdgeInsets.fromLTRB(2, 24, 0, 10),
            child: Text(
              title,
              style: Theme.of(context).textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
          )
        else
          const SizedBox(height: 8),
        LayoutBuilder(
          builder: (context, constraints) {
            // Keep the next card visible at the edge: the affordance for a
            // native horizontal swipe, also on compact screens.
            final width = constraints.maxWidth;
            final cardWidth = width < 320
                ? width * 0.87
                : (width * 0.78).clamp(248.0, 300.0).toDouble();
            return SingleChildScrollView(
              key: Key('me-collectives-carousel-${kind}'),
              scrollDirection: Axis.horizontal,
              physics: const BouncingScrollPhysics(),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final item in items) ...[
                    SizedBox(
                      width: cardWidth,
                      child: kind == 'space' ? _space(item) : _relation(item),
                    ),
                    const SizedBox(width: 12),
                  ],
                ],
              ),
            );
          },
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final spaces = _visible('space');
    final teams = _visible('team');
    final groups = _visible('group');
    final hasResults =
        (_tab == _CollectiveTab.all || _tab == _CollectiveTab.spaces) &&
            spaces.isNotEmpty ||
        (_tab == _CollectiveTab.all || _tab == _CollectiveTab.teams) &&
            teams.isNotEmpty ||
        (_tab == _CollectiveTab.all || _tab == _CollectiveTab.groups) &&
            groups.isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _filters(),
        if (_tab == _CollectiveTab.all || _tab == _CollectiveTab.spaces)
          _section('Où on peut agir', spaces, kind: 'space'),
        if (_tab == _CollectiveTab.all || _tab == _CollectiveTab.teams)
          _section('Mes équipes', teams, kind: 'team'),
        if (_tab == _CollectiveTab.all || _tab == _CollectiveTab.groups)
          _section('Mes groupes', groups, kind: 'group'),
        if (!hasResults)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 32),
            child: Text(
              widget.query.trim().isNotEmpty
                  ? widget.hasMore
                        ? 'Aucun résultat parmi les collectifs chargés.'
                        : 'Aucun collectif ne correspond à cette recherche.'
                  : widget.hasMore
                  ? 'Chargement des autres collectifs…'
                  : 'Aucun collectif dans cette catégorie.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
      ],
    );
  }
}
