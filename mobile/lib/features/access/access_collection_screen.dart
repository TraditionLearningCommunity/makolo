
import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../sync/freshness.dart';
import 'access_repository.dart';

class AccessCollectionScreen extends StatefulWidget {
  const AccessCollectionScreen({
    super.key,
    required this.repository,
    required this.onOpenAccess,
    this.onOpenHistory,
  });

  final AccessRepository repository;
  final ValueChanged<String> onOpenAccess;
  final VoidCallback? onOpenHistory;

  @override
  State<AccessCollectionScreen> createState() => _AccessCollectionScreenState();
}

class _AccessCollectionScreenState extends State<AccessCollectionScreen> {
  static const _mine = 'beneficiary';
  static const _forOther = 'purchased_for_other';

  String _relationship = _mine;
  bool _refreshing = false;
  bool _loadingMore = false;

  @override
  void initState() {
    super.initState();
    unawaited(_ensureFirstPage());
  }

  Future<void> _ensureFirstPage() async {
    final cached = await widget.repository.readCollectionPage(
      relationship: _relationship,
      offset: 0,
    );
    if (cached == null && mounted) {
      await _refreshFirst();
    }
  }

  Future<void> _refreshFirst() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshCollectionPage(
        relationship: _relationship,
        offset: 0,
      );
    } on Object {
      // Keep any cached owner projection readable.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _loadMore(_AccessCollectionView view) async {
    if (_loadingMore || !view.hasMore) return;
    setState(() => _loadingMore = true);
    try {
      await widget.repository.refreshCollectionPage(
        relationship: _relationship,
        offset: view.nextOffset,
      );
    } on Object {
      // Keep the pages already available locally.
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  void _selectRelationship(String relationship) {
    if (_relationship == relationship) return;
    setState(() => _relationship = relationship);
    unawaited(_ensureFirstPage());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mes accès'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refreshFirst,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: StreamBuilder<List<StoredProjection>>(
        stream: widget.repository.watchCollectionPages(),
        initialData: const [],
        builder: (context, pagesSnapshot) {
          final view = _AccessCollectionView.fromPages(
            pagesSnapshot.data ?? const [],
            relationship: _relationship,
          );
          return StreamBuilder<AccessSourceState>(
            stream: widget.repository.watchCollectionSource(
              relationship: _relationship,
            ),
            initialData: AccessSourceState.unknown,
            builder: (context, sourceSnapshot) {
              final source = sourceSnapshot.data ?? AccessSourceState.unknown;
              return RefreshIndicator(
                onRefresh: _refreshFirst,
                child: ListView(
                  key: PageStorageKey<String>(
                    'personal-accesses-' + _relationship,
                  ),
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(MakoloSpacing.inner),
                  children: [
                    Text(
                      'Vos droits déjà accordés, avant leur représentation.',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: MakoloSpacing.md),
                    Wrap(
                      spacing: MakoloSpacing.sm,
                      runSpacing: MakoloSpacing.sm,
                      children: [
                        ChoiceChip(
                          label: const Text('Pour moi'),
                          selected: _relationship == _mine,
                          onSelected: (_) => _selectRelationship(_mine),
                        ),
                        ChoiceChip(
                          label: const Text('Pour une autre personne'),
                          selected: _relationship == _forOther,
                          onSelected: (_) => _selectRelationship(_forOther),
                        ),
                      ],
                    ),
                    if (source.reachability == ReachabilityState.unreachable &&
                        view.items.isNotEmpty) ...[
                      const SizedBox(height: MakoloSpacing.md),
                      Text(
                        'Dernier état connu sur cet appareil. '
                        'L’usage réel sera revalidé par le domaine Access.',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                    const SizedBox(height: MakoloSpacing.lg),
                    if (view.items.isEmpty)
                      Padding(
                        padding: const EdgeInsets.symmetric(
                          vertical: MakoloSpacing.xl,
                        ),
                        child: _refreshing
                            ? const Center(
                                child: CircularProgressIndicator.adaptive(),
                              )
                            : Text(
                                _relationship == _mine
                                    ? 'Aucun accès disponible pour le moment.'
                                    : 'Aucun accès obtenu pour une autre personne.',
                                textAlign: TextAlign.center,
                              ),
                      )
                    else
                      for (var index = 0;
                          index < view.items.length;
                          index++) ...[
                        _AccessCollectionCard(
                          item: view.items[index],
                          onOpen: () =>
                              widget.onOpenAccess(view.items[index].id),
                        ),
                        if (index < view.items.length - 1)
                          const SizedBox(height: MakoloSpacing.sm),
                      ],
                    if (view.hasMore) ...[
                      const SizedBox(height: MakoloSpacing.md),
                      OutlinedButton(
                        onPressed:
                            _loadingMore ? null : () => _loadMore(view),
                        child: Text(
                          _loadingMore ? 'Chargement…' : 'Afficher la suite',
                        ),
                      ),
                    ],
                    if (_relationship == _mine &&
                        widget.onOpenHistory != null) ...[
                      const SizedBox(height: MakoloSpacing.lg),
                      TextButton.icon(
                        onPressed: widget.onOpenHistory,
                        icon: const Icon(Icons.history_rounded),
                        label: const Text('Voir les accès terminés'),
                      ),
                    ],
                  ],
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class _AccessCollectionCard extends StatelessWidget {
  const _AccessCollectionCard({required this.item, required this.onOpen});

  final _AccessCollectionItem item;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final details = <String>[
      if (item.context != null) item.context!,
      item.stateLabel,
      if (item.validity != null) item.validity!,
      if (item.holder != null) 'Pour ' + item.holder!,
    ];

    return MakoloCard(
      onTap: onOpen,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.badge_outlined),
          const SizedBox(width: MakoloSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.title,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: MakoloSpacing.xs),
                Text(
                  details.join(' · '),
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right_rounded),
        ],
      ),
    );
  }
}

class _AccessCollectionView {
  const _AccessCollectionView({
    required this.items,
    required this.hasMore,
    required this.nextOffset,
  });

  final List<_AccessCollectionItem> items;
  final bool hasMore;
  final int nextOffset;

  factory _AccessCollectionView.fromPages(
    List<StoredProjection> pages, {
    required String relationship,
  }) {
    final prefix = relationship + ':';
    final selected = pages
        .where(
          (page) =>
              page.kind == AccessRepository.collectionProjectionKind &&
              page.resourceKey.startsWith(prefix),
        )
        .toList()
      ..sort((a, b) => _offset(a).compareTo(_offset(b)));

    if (selected.isEmpty) {
      return const _AccessCollectionView(
        items: [],
        hasMore: false,
        nextOffset: 0,
      );
    }

    final seen = <String>{};
    final items = <_AccessCollectionItem>[];
    for (final page in selected) {
      final rows = page.payload['items'];
      if (rows is! List) continue;
      for (final raw in rows) {
        final row = _map(raw);
        final identity = _map(row['identity']);
        final id = _string(identity['id']);
        final activity = _map(row['activity']);
        final title = _string(activity['title']);
        if (id == null || title == null || !seen.add(id)) continue;
        final state = _map(row['state']);
        final occurrence = _map(row['occurrence']);
        final timing = _map(occurrence['timing']);
        final place = _map(occurrence['place']);
        final validity = _map(row['validity']);
        final holder = _map(row['holder']);
        items.add(
          _AccessCollectionItem(
            id: id,
            title: title,
            stateLabel:
                _string(state['label']) ??
                _humanState(_string(state['code'])),
            context: _contextLabel(timing, place),
            validity: _validityLabel(validity),
            holder: _string(holder['display_name']),
          ),
        );
      }
    }

    final last = selected.last;
    final page = _map(last.payload['page']);
    final offset = page['offset'] is num
        ? (page['offset'] as num).toInt()
        : _offset(last);
    final limit = page['limit'] is num
        ? (page['limit'] as num).toInt()
        : AccessRepository.defaultCollectionLimit;

    return _AccessCollectionView(
      items: List.unmodifiable(items),
      hasMore: page['has_more'] == true,
      nextOffset: offset + limit,
    );
  }

  static int _offset(StoredProjection page) {
    final parts = page.resourceKey.split(':');
    if (parts.length >= 3) return int.tryParse(parts[1]) ?? 0;
    return 0;
  }
}

class _AccessCollectionItem {
  const _AccessCollectionItem({
    required this.id,
    required this.title,
    required this.stateLabel,
    this.context,
    this.validity,
    this.holder,
  });

  final String id;
  final String title;
  final String stateLabel;
  final String? context;
  final String? validity;
  final String? holder;
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const {};
}

String? _string(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}

String _humanState(String? value) => switch (value) {
  'pending' => 'En attente',
  'valid' => 'Valide',
  'used' => 'Utilisé',
  'cancelled' => 'Annulé',
  'revoked' => 'Révoqué',
  'expired' => 'Expiré',
  'transferred' => 'Transféré',
  _ => 'État connu',
};

String? _contextLabel(
  Map<String, dynamic> timing,
  Map<String, dynamic> place,
) {
  final placeName = _string(place['name']) ?? _string(place['locality']);
  final startAt = _dateTime(timing['start_at']);
  final startDate = _string(timing['start_date']);
  final parts = <String>[
    if (startAt != null) _shortDateTime(startAt)
    else if (startDate != null) startDate,
    if (placeName != null) placeName,
  ];
  return parts.isEmpty ? null : parts.join(' · ');
}

String? _validityLabel(Map<String, dynamic> validity) {
  final from = _dateTime(validity['from']);
  final until = _dateTime(validity['until']);
  if (from == null && until == null) return null;
  if (from != null && until != null) {
    return 'Valable du ' + _shortDate(from) + ' au ' + _shortDate(until);
  }
  if (from != null) return 'Valable à partir du ' + _shortDate(from);
  return 'Valable jusqu’au ' + _shortDate(until!);
}

String _shortDate(DateTime value) {
  final local = value.toLocal();
  return local.day.toString().padLeft(2, '0') +
      '/' +
      local.month.toString().padLeft(2, '0') +
      '/' +
      local.year.toString();
}

String _shortDateTime(DateTime value) {
  final local = value.toLocal();
  return local.day.toString().padLeft(2, '0') +
      '/' +
      local.month.toString().padLeft(2, '0') +
      ' ' +
      local.hour.toString().padLeft(2, '0') +
      ':' +
      local.minute.toString().padLeft(2, '0');
}

DateTime? _dateTime(Object? value) {
  final raw = _string(value);
  return raw == null ? null : DateTime.tryParse(raw);
}
