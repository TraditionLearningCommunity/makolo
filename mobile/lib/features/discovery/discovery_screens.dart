import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../platform/location/location_capability.dart';
import '../../sync/freshness.dart';
import 'detail_selector.dart';
import 'discovery_repository.dart';
import 'discovery_selector.dart';

class DiscoveryScreen extends StatefulWidget {
  const DiscoveryScreen({
    super.key,
    required this.repository,
    required this.onOpenActivity,
    required this.onOpenOccurrence,
    required this.onOpenItem,
    required this.onOpenWatches,
    this.location,
  });

  final DiscoveryRepository repository;
  final LocationCapability? location;
  final ValueChanged<String> onOpenActivity;
  final ValueChanged<String> onOpenOccurrence;
  final void Function(String family, String id) onOpenItem;
  final VoidCallback onOpenWatches;

  @override
  State<DiscoveryScreen> createState() => _DiscoveryScreenState();
}

class _DiscoveryScreenState extends State<DiscoveryScreen> {
  static const _selector = DiscoverySelector();

  final _search = TextEditingController();
  DiscoveryQuery _query = const DiscoveryQuery();
  bool _refreshing = false;
  bool _mapMode = false;
  String? _locationMessage;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _acquire() async {
    final local = await widget.repository.readItems(_query);
    final source = await widget.repository.readSource(
      widget.repository.itemsSource(_query),
    );
    if (local == null ||
        DiscoveryRepository.discoveryFreshness.evaluate(
              local,
              now: DateTime.now(),
              invalidated: source.invalidated,
            ) !=
            FreshnessState.fresh) {
      await _refreshItems();
    }
  }

  Future<void> _refreshItems() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshItems(_query);
      if (_mapMode) await widget.repository.refreshMap(_query);
    } on Object {
      // SyncSource keeps the old local pack and records reachability.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _showMap() async {
    setState(() => _mapMode = true);
    final local = await widget.repository.readMap(_query);
    if (local == null) {
      try {
        await widget.repository.refreshMap(_query);
      } on Object {
        // The list remains usable even when the map acquisition fails.
      }
    }
  }

  Future<void> _aroundMe() async {
    final capability = widget.location;
    if (capability == null) {
      setState(
        () => _locationMessage =
            'La localisation n’est pas disponible sur cet appareil.',
      );
      return;
    }
    setState(() => _locationMessage = null);
    final result = await capability.current();
    if (!mounted) return;
    if (!result.available || result.fix == null) {
      setState(
        () => _locationMessage = 'La position n’a pas été utilisée. Vous pouvez continuer sans elle.',
      );
      return;
    }
    setState(() {
      _query = _query.copyWith(
        latitude: result.fix!.latitude,
        longitude: result.fix!.longitude,
        radiusKm: 25,
        page: 1,
      );
      _locationMessage = 'Recherche autour de votre position actuelle.';
    });
    await _refreshItems();
  }

  void _submitSearch(String value) {
    setState(() {
      _query = _query.copyWith(text: value, page: 1);
      _mapMode = false;
    });
    unawaited(_refreshItems());
  }

  void _movePage(int page) {
    if (page < 1) return;
    setState(() => _query = _query.copyWith(page: page));
    unawaited(_acquire());
  }

  @override
  Widget build(BuildContext context) {
    final source = widget.repository.itemsSource(_query);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Découvrir'),
        actions: [
          IconButton(
            tooltip: 'Veilles',
            onPressed: widget.onOpenWatches,
            icon: const Icon(Icons.notifications_active_outlined),
          ),
          IconButton(
            tooltip: _mapMode ? 'Voir la liste' : 'Voir la carte',
            onPressed: () {
              if (_mapMode) {
                setState(() => _mapMode = false);
              } else {
                unawaited(_showMap());
              }
            },
            icon: Icon(_mapMode ? Icons.view_list_rounded : Icons.map_outlined),
          ),
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refreshItems,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              MakoloSpacing.inner,
              MakoloSpacing.sm,
              MakoloSpacing.inner,
              MakoloSpacing.sm,
            ),
            child: SearchBar(
              controller: _search,
              hintText: 'Rechercher une possibilité',
              leading: const Icon(Icons.search_rounded),
              onSubmitted: _submitSearch,
              trailing: [
                IconButton(
                  tooltip: 'Autour de moi',
                  onPressed: _aroundMe,
                  icon: const Icon(Icons.near_me_outlined),
                ),
              ],
            ),
          ),
          if (_locationMessage != null)
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: MakoloSpacing.inner,
              ),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  _locationMessage!,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            ),
          if (_refreshing) const LinearProgressIndicator(minHeight: 2),
          Expanded(
            child: _mapMode
                ? _DiscoveryMapPane(
                    repository: widget.repository,
                    query: _query,
                    onOpenOccurrence: widget.onOpenOccurrence,
                  )
                : StreamBuilder<StoredProjection?>(
                    stream: widget.repository.watchItems(_query),
                    builder: (context, snapshot) {
                      return StreamBuilder<DiscoverySourceState>(
                        stream: widget.repository.watchSource(source),
                        initialData: DiscoverySourceState.unknown,
                        builder: (context, sourceSnapshot) {
                          final projection = snapshot.data;
                          if (projection == null) {
                            if (_refreshing) {
                              return const Center(
                                child: CircularProgressIndicator(),
                              );
                            }
                            return _DiscoveryUnavailable(
                              source: sourceSnapshot.data,
                              onRetry: _refreshItems,
                            );
                          }
                          final presentation = _selector.collection(projection);
                          if (presentation.items.isEmpty) {
                            return RefreshIndicator(
                              onRefresh: _refreshItems,
                              child: ListView(
                                physics: const AlwaysScrollableScrollPhysics(),
                                children: const [
                                  SizedBox(height: 120),
                                  Padding(
                                    padding: EdgeInsets.all(
                                      MakoloSpacing.inner,
                                    ),
                                    child: Center(
                                      child: Text(
                                        'Aucune possibilité ne correspond actuellement à cette recherche.',
                                        textAlign: TextAlign.center,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            );
                          }
                          return RefreshIndicator(
                            onRefresh: _refreshItems,
                            child: ListView(
                              key: ValueKey(
                                'discovery-page-${presentation.page}',
                              ),
                              padding: const EdgeInsets.only(
                                bottom: MakoloSpacing.xl,
                              ),
                              children: [
                                for (final item in presentation.items)
                                  Padding(
                                    padding: const EdgeInsets.fromLTRB(
                                      MakoloSpacing.inner,
                                      MakoloSpacing.sm,
                                      MakoloSpacing.inner,
                                      0,
                                    ),
                                    child: _DiscoveryCard(
                                      item: item,
                                      onTap: () {
                                        if (item.family == 'activity' ||
                                            item.family == 'service_activity' ||
                                            item.family == 'funding_activity') {
                                          widget.onOpenActivity(item.id);
                                        } else {
                                          widget.onOpenItem(
                                            item.family,
                                            item.id,
                                          );
                                        }
                                      },
                                    ),
                                  ),
                                Padding(
                                  padding: const EdgeInsets.all(
                                    MakoloSpacing.inner,
                                  ),
                                  child: Row(
                                    children: [
                                      OutlinedButton.icon(
                                        onPressed: presentation.page > 1
                                            ? () => _movePage(
                                                presentation.page - 1,
                                              )
                                            : null,
                                        icon: const Icon(
                                          Icons.chevron_left_rounded,
                                        ),
                                        label: const Text('Précédent'),
                                      ),
                                      const Spacer(),
                                      Text(
                                        'Page ${presentation.page}',
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodySmall,
                                      ),
                                      const Spacer(),
                                      FilledButton.icon(
                                        onPressed: presentation.hasNext
                                            ? () => _movePage(
                                                presentation.page + 1,
                                              )
                                            : null,
                                        icon: const Icon(
                                          Icons.chevron_right_rounded,
                                        ),
                                        label: const Text('Suivant'),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _DiscoveryCard extends StatelessWidget {
  const _DiscoveryCard({required this.item, required this.onTap});

  final DiscoveryItemPresentation item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final metadata = <MakoloMetadataItem>[
      if (item.owner != null)
        MakoloMetadataItem(item.owner!, icon: Icons.business_outlined),
      if (item.place != null)
        MakoloMetadataItem(item.place!, icon: Icons.place_outlined),
      if (item.timing != null)
        MakoloMetadataItem(item.timing!, icon: Icons.schedule_outlined),
      if (item.price != null)
        MakoloMetadataItem(item.price!, icon: Icons.payments_outlined),
    ];
    return MakoloCard(
      onTap: onTap,
      semanticLabel: 'Possibilité. ${item.title}',
      child: MakoloStatusMetadataAction(
        title: item.title,
        subtitle: item.summary.isEmpty ? null : item.summary,
        status: item.availability == null
            ? null
            : MakoloStatus(label: item.availability!),
        metadata: metadata,
        action: const Icon(Icons.chevron_right_rounded),
      ),
    );
  }
}

class _DiscoveryUnavailable extends StatelessWidget {
  const _DiscoveryUnavailable({required this.source, required this.onRetry});

  final DiscoverySourceState? source;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    final message = source?.reachability == ReachabilityState.unreachable
        ? 'Le réseau est indisponible et aucune copie locale de ce corpus n’existe encore.'
        : 'Impossible de charger de nouvelles possibilités pour le moment.';
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(MakoloSpacing.inner),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: MakoloSpacing.md),
            OutlinedButton(
              onPressed: () => unawaited(onRetry()),
              child: const Text('Réessayer'),
            ),
          ],
        ),
      ),
    );
  }
}

class _DiscoveryMapPane extends StatefulWidget {
  const _DiscoveryMapPane({
    required this.repository,
    required this.query,
    required this.onOpenOccurrence,
  });

  final DiscoveryRepository repository;
  final DiscoveryQuery query;
  final ValueChanged<String> onOpenOccurrence;

  @override
  State<_DiscoveryMapPane> createState() => _DiscoveryMapPaneState();
}

class _DiscoveryMapPaneState extends State<_DiscoveryMapPane> {
  static const _selector = DiscoverySelector();

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchMap(widget.query),
      builder: (context, snapshot) {
        final points = _selector.mapPoints(snapshot.data);
        if (snapshot.data == null) {
          return const Center(child: CircularProgressIndicator());
        }
        if (points.isEmpty) {
          return const Center(
            child: Padding(
              padding: EdgeInsets.all(MakoloSpacing.inner),
              child: Text(
                'Aucun point cartographiable dans ce corpus. La liste reste disponible.',
                textAlign: TextAlign.center,
              ),
            ),
          );
        }
        return ListView(
          padding: const EdgeInsets.all(MakoloSpacing.inner),
          children: [
            const MakoloAttentionBlock(
              title: 'Carte',
              body: 'Les données géographiques owner sont disponibles localement. Le runtime Mobile ne fournit pas encore de style MapLibre configuré ; aucun fournisseur n’est inventé ici.',
              icon: Icons.map_outlined,
            ),
            const SizedBox(height: MakoloSpacing.md),
            for (final point in points) ...[
              MakoloCard(
                onTap: () => widget.onOpenOccurrence(point.occurrenceId),
                semanticLabel: 'Point cartographique. ${point.title}',
                child: MakoloStatusMetadataAction(
                  title: point.title,
                  subtitle: [
                    point.placeName,
                    point.locality,
                  ].whereType<String>().join(' · '),
                  metadata: [
                    MakoloMetadataItem(
                      '${point.latitude.toStringAsFixed(5)}, ${point.longitude.toStringAsFixed(5)}',
                      icon: Icons.location_on_outlined,
                    ),
                  ],
                  action: const Icon(Icons.chevron_right_rounded),
                ),
              ),
              const SizedBox(height: MakoloSpacing.sm),
            ],
          ],
        );
      },
    );
  }
}

class DiscoveryItemDetailScreen extends StatefulWidget {
  const DiscoveryItemDetailScreen({
    super.key,
    required this.family,
    required this.id,
    required this.repository,
  });

  final String family;
  final String id;
  final DiscoveryRepository repository;

  @override
  State<DiscoveryItemDetailScreen> createState() =>
      _DiscoveryItemDetailScreenState();
}

class _DiscoveryItemDetailScreenState extends State<DiscoveryItemDetailScreen> {
  static const _selector = DiscoverySelector();
  bool _refreshing = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  Future<void> _acquire() async {
    final local = await widget.repository.readItem(widget.family, widget.id);
    if (local == null) await _refresh();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshItem(widget.family, widget.id);
    } on Object {
      // Preserve local item if present.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _setSaved(bool saved) async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await widget.repository.setSaved(
        family: widget.family,
        id: widget.id,
        saved: saved,
      );
    } on Object {
      await _refresh();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Le changement n’a pas été confirmé. L’état serveur a été relu.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchItem(widget.family, widget.id),
      builder: (context, snapshot) {
        final item = _selector.detail(snapshot.data);
        return Scaffold(
          appBar: AppBar(
            title: const Text('Possibilité'),
            actions: [
              IconButton(
                tooltip: 'Actualiser',
                onPressed: _refreshing ? null : _refresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          body: item == null
              ? Center(
                  child: _refreshing
                      ? const CircularProgressIndicator()
                      : OutlinedButton(
                          onPressed: _refresh,
                          child: const Text('Réessayer'),
                        ),
                )
              : ListView(
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
                  children: [
                    MakoloDetailHeader(
                      eyebrow: item.eyebrow ?? 'Découvrir',
                      title: item.title,
                      subtitle: item.summary.isEmpty ? null : item.summary,
                      status: item.availability == null
                          ? null
                          : MakoloStatus(label: item.availability!),
                      metadata: [
                        if (item.owner != null)
                          MakoloMetadataItem(
                            item.owner!,
                            icon: Icons.business_outlined,
                          ),
                        if (item.place != null)
                          MakoloMetadataItem(
                            item.place!,
                            icon: Icons.place_outlined,
                          ),
                        if (item.timing != null)
                          MakoloMetadataItem(
                            item.timing!,
                            icon: Icons.schedule_outlined,
                          ),
                        if (item.price != null)
                          MakoloMetadataItem(
                            item.price!,
                            icon: Icons.payments_outlined,
                          ),
                      ],
                    ),
                    if (item.canSave || item.canUnsave)
                      Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: MakoloSpacing.inner,
                        ),
                        child: FilledButton.icon(
                          onPressed: _saving
                              ? null
                              : () => _setSaved(item.canSave),
                          icon: Icon(
                            item.canUnsave
                                ? Icons.bookmark_rounded
                                : Icons.bookmark_border_rounded,
                          ),
                          label: Text(
                            item.canUnsave
                                ? 'Retirer des favoris'
                                : 'Enregistrer',
                          ),
                        ),
                      ),
                  ],
                ),
        );
      },
    );
  }
}

class ActivityDetailScreen extends StatefulWidget {
  const ActivityDetailScreen({
    super.key,
    required this.activityId,
    required this.repository,
    required this.onOpenOccurrence,
  });

  final String activityId;
  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenOccurrence;

  @override
  State<ActivityDetailScreen> createState() => _ActivityDetailScreenState();
}

class _ActivityDetailScreenState extends State<ActivityDetailScreen> {
  static const _selector = DiscoveryDetailSelector();
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  Future<void> _acquire() async {
    if (await widget.repository.readActivity(widget.activityId) == null) {
      await _refresh();
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshActivity(widget.activityId);
    } on Object {
      // Scoped errors are recorded by SyncSource.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchActivity(widget.activityId),
      builder: (context, snapshot) {
        final activity = _selector.activity(snapshot.data);
        return Scaffold(
          appBar: AppBar(
            title: const Text('Activité'),
            actions: [
              IconButton(
                tooltip: 'Actualiser',
                onPressed: _refreshing ? null : _refresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          body: activity == null
              ? Center(
                  child: _refreshing
                      ? const CircularProgressIndicator()
                      : OutlinedButton(
                          onPressed: _refresh,
                          child: const Text('Réessayer'),
                        ),
                )
              : ListView(
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
                  children: [
                    MakoloDetailHeader(
                      eyebrow: activity.vertical,
                      title: activity.title,
                      subtitle: activity.summary.isEmpty
                          ? null
                          : activity.summary,
                      status: MakoloStatus(label: activity.state),
                      metadata: [
                        if (activity.owner != null)
                          MakoloMetadataItem(
                            activity.owner!,
                            icon: Icons.business_outlined,
                          ),
                        MakoloMetadataItem(
                          activity.availability,
                          icon: Icons.event_available_outlined,
                        ),
                      ],
                    ),
                    if (activity.occurrences.isNotEmpty)
                      MakoloSection(
                        title: 'Dates et réalisations',
                        child: Column(
                          children: [
                            for (
                              var index = 0;
                              index < activity.occurrences.length;
                              index++
                            ) ...[
                              MakoloCard(
                                onTap: () => widget.onOpenOccurrence(
                                  activity.occurrences[index].id,
                                ),
                                child: MakoloStatusMetadataAction(
                                  title: activity.occurrences[index].label,
                                  status: MakoloStatus(
                                    label: activity.occurrences[index].state,
                                  ),
                                  metadata: [
                                    if (activity.occurrences[index].timing !=
                                        null)
                                      MakoloMetadataItem(
                                        activity.occurrences[index].timing!,
                                        icon: Icons.schedule_outlined,
                                      ),
                                  ],
                                  action: const Icon(
                                    Icons.chevron_right_rounded,
                                  ),
                                ),
                              ),
                              if (index < activity.occurrences.length - 1)
                                const SizedBox(height: MakoloSpacing.sm),
                            ],
                          ],
                        ),
                      ),
                  ],
                ),
        );
      },
    );
  }
}

class OccurrenceDetailScreen extends StatefulWidget {
  const OccurrenceDetailScreen({
    super.key,
    required this.occurrenceId,
    required this.repository,
    required this.onOpenActivity,
    this.onOpenDayOf,
  });

  final String occurrenceId;
  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenActivity;
  final VoidCallback? onOpenDayOf;

  @override
  State<OccurrenceDetailScreen> createState() => _OccurrenceDetailScreenState();
}

class _OccurrenceDetailScreenState extends State<OccurrenceDetailScreen> {
  static const _selector = DiscoveryDetailSelector();
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  Future<void> _acquire() async {
    if (await widget.repository.readOccurrence(widget.occurrenceId) == null) {
      await _refresh();
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshOccurrence(widget.occurrenceId);
    } on Object {
      // Scoped errors are recorded by SyncSource.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchOccurrence(widget.occurrenceId),
      builder: (context, snapshot) {
        final occurrence = _selector.occurrence(snapshot.data);
        return Scaffold(
          appBar: AppBar(
            title: const Text('Occurrence'),
            actions: [
              IconButton(
                tooltip: 'Actualiser',
                onPressed: _refreshing ? null : _refresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          body: occurrence == null
              ? Center(
                  child: _refreshing
                      ? const CircularProgressIndicator()
                      : OutlinedButton(
                          onPressed: _refresh,
                          child: const Text('Réessayer'),
                        ),
                )
              : ListView(
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
                  children: [
                    MakoloDetailHeader(
                      eyebrow: 'Occurrence',
                      title: occurrence.activityTitle,
                      status: MakoloStatus(label: occurrence.state),
                      metadata: [
                        if (occurrence.timing != null)
                          MakoloMetadataItem(
                            occurrence.timing!,
                            icon: Icons.schedule_outlined,
                          ),
                        if (occurrence.place != null)
                          MakoloMetadataItem(
                            occurrence.place!,
                            icon: Icons.place_outlined,
                          ),
                        MakoloMetadataItem(
                          occurrence.availability,
                          icon: Icons.event_available_outlined,
                        ),
                      ],
                    ),
                    Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: MakoloSpacing.inner,
                      ),
                      child: OutlinedButton.icon(
                        onPressed: () =>
                            widget.onOpenActivity(occurrence.activityId),
                        icon: const Icon(Icons.arrow_back_rounded),
                        label: const Text('Voir l’activité'),
                      ),
                    ),
                    if (occurrence.canOpenDayOf)
                      Padding(
                        padding: const EdgeInsets.fromLTRB(
                          MakoloSpacing.inner,
                          MakoloSpacing.md,
                          MakoloSpacing.inner,
                          0,
                        ),
                        child: MakoloAttentionBlock(
                          title: 'Jour J disponible',
                          body:
                              'Le serveur indique qu’une profondeur Jour J est disponible pour cette occurrence.',
                          icon: Icons.directions_walk_rounded,
                          action: widget.onOpenDayOf == null
                              ? null
                              : FilledButton.icon(
                                  onPressed: widget.onOpenDayOf,
                                  icon: const Icon(
                                    Icons.directions_walk_rounded,
                                  ),
                                  label: const Text('Ouvrir le Jour J'),
                                ),
                        ),
                      ),
                  ],
                ),
        );
      },
    );
  }
}
