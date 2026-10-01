import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/environment.dart';
import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../platform/location/location_capability.dart';
import '../../platform/maps/makolo_map_view.dart';
import '../../sync/freshness.dart';
import 'detail_selector.dart';
import 'discovery_repository.dart';
import 'discovery_selector.dart';

class DiscoveryScreen extends StatefulWidget {
  const DiscoveryScreen({
    super.key,
    required this.repository,
    required this.onOpenActivity,
    required this.onOpenItem,
  });

  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenActivity;
  final void Function(String family, String id) onOpenItem;

  @override
  State<DiscoveryScreen> createState() => _DiscoveryScreenState();
}

class _DiscoveryScreenState extends State<DiscoveryScreen> {
  static const _selector = DiscoverySelector();
  DiscoveryQuery _query = const DiscoveryQuery();
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
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
    } on Object {
      // The existing local snapshot remains usable.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  void _movePage(int page) {
    if (page < 1) return;
    setState(() => _query = _query.copyWith(page: page));
    unawaited(_acquire());
  }

  @override
  Widget build(BuildContext context) {
    final source = widget.repository.itemsSource(_query);
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchItems(_query),
      builder: (context, snapshot) {
        return StreamBuilder<DiscoverySourceState>(
          stream: widget.repository.watchSource(source),
          initialData: DiscoverySourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = snapshot.data;
            if (projection == null) {
              if (_refreshing) {
                return const Center(child: CircularProgressIndicator());
              }
              return _DiscoveryUnavailable(
                source: sourceSnapshot.data,
                onRetry: _refreshItems,
              );
            }
            final presentation = _selector.collection(projection);
            return RefreshIndicator(
              onRefresh: _refreshItems,
              child: _DiscoveryResultsList(
                presentation: presentation,
                onOpenActivity: widget.onOpenActivity,
                onOpenItem: widget.onOpenItem,
                onPage: _movePage,
              ),
            );
          },
        );
      },
    );
  }
}

class DiscoverySearchScreen extends StatefulWidget {
  const DiscoverySearchScreen({
    super.key,
    required this.repository,
    required this.onOpenActivity,
    required this.onOpenItem,
    this.location,
  });

  final DiscoveryRepository repository;
  final ValueChanged<String> onOpenActivity;
  final void Function(String family, String id) onOpenItem;
  final LocationCapability? location;

  @override
  State<DiscoverySearchScreen> createState() => _DiscoverySearchScreenState();
}

class _DiscoverySearchScreenState extends State<DiscoverySearchScreen> {
  static const _selector = DiscoverySelector();
  final _search = TextEditingController();
  DiscoveryQuery _query = const DiscoveryQuery();
  bool _refreshing = false;
  String? _locationMessage;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _submit(String value) async {
    final query = _query.copyWith(text: value, page: 1);
    setState(() {
      _query = query;
      _refreshing = true;
    });
    try {
      await widget.repository.refreshItems(query);
    } on Object {
      // Existing results remain visible when refresh fails.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _aroundMe() async {
    final location = widget.location;
    if (location == null) {
      setState(
        () => _locationMessage =
            'La localisation n’est pas disponible sur cet appareil.',
      );
      return;
    }
    final result = await location.current();
    if (!mounted) return;
    if (!result.available || result.fix == null) {
      setState(
        () => _locationMessage =
            'Votre position n’a pas pu être utilisée. Vous pouvez continuer sans elle.',
      );
      return;
    }
    final query = _query.copyWith(
      latitude: result.fix!.latitude,
      longitude: result.fix!.longitude,
      radiusKm: 25,
      page: 1,
    );
    setState(() {
      _query = query;
      _locationMessage = 'Recherche autour de votre position.';
    });
    await _submit(_search.text);
  }

  void _movePage(int page) {
    if (page < 1) return;
    final query = _query.copyWith(page: page);
    setState(() => _query = query);
    unawaited(_refreshPage(query));
  }

  Future<void> _refreshPage(DiscoveryQuery query) async {
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshItems(query);
    } on Object {
      // Existing results remain visible.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Rechercher')),
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
              key: const Key('discover-search-field'),
              controller: _search,
              autoFocus: true,
              hintText: 'Rechercher une possibilité',
              leading: const Icon(Icons.search_rounded),
              onSubmitted: _submit,
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
          Expanded(
            child: StreamBuilder<StoredProjection?>(
              stream: widget.repository.watchItems(_query),
              builder: (context, snapshot) {
                if (_refreshing && snapshot.data == null) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (_query.text.trim().isEmpty &&
                    _query.latitude == null &&
                    snapshot.data == null) {
                  return const Center(
                    child: Text('Saisissez ce que vous recherchez.'),
                  );
                }
                final presentation = _selector.collection(snapshot.data);
                return RefreshIndicator(
                  onRefresh: () => _refreshPage(_query),
                  child: _DiscoveryResultsList(
                    presentation: presentation,
                    onOpenActivity: widget.onOpenActivity,
                    onOpenItem: widget.onOpenItem,
                    onPage: _movePage,
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class DiscoveryMapScreen extends StatefulWidget {
  const DiscoveryMapScreen({
    super.key,
    required this.repository,
    required this.mapConfig,
    required this.onOpenOccurrence,
  });

  final DiscoveryRepository repository;
  final MakoloMapsConfig mapConfig;
  final ValueChanged<String> onOpenOccurrence;

  @override
  State<DiscoveryMapScreen> createState() => _DiscoveryMapScreenState();
}

class _DiscoveryMapScreenState extends State<DiscoveryMapScreen> {
  static const _selector = DiscoverySelector();
  static const _query = DiscoveryQuery();
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquire());
  }

  Future<void> _acquire() async {
    final local = await widget.repository.readMap(_query);
    if (local == null) await _refresh();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshMap(_query);
    } on Object {
      // Existing map data remains available.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Carte'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: StreamBuilder<StoredProjection?>(
        stream: widget.repository.watchMap(_query),
        builder: (context, snapshot) {
          if (snapshot.data == null) {
            if (_refreshing) {
              return const Center(child: CircularProgressIndicator());
            }
            return MakoloErrorState(
              message: 'Impossible de charger la carte pour le moment.',
              onRetry: _refresh,
            );
          }

          final points = _selector.mapPoints(snapshot.data);
          if (points.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(MakoloSpacing.inner),
                child: Text(
                  'Aucun lieu à afficher sur la carte pour le moment.',
                  textAlign: TextAlign.center,
                ),
              ),
            );
          }

          final first = points.first;
          return Stack(
            children: [
              Positioned.fill(
                child: ConfiguredMakoloMapView(
                  config: widget.mapConfig,
                  initialViewport: MapViewport(
                    center: MapCoordinate(first.latitude, first.longitude),
                    zoom: 11,
                  ),
                  fallbackBuilder: (context, state, retry) {
                    final retryable = state == MakoloMapRuntimeState.error;
                    return MakoloErrorState(
                      message: 'Impossible d’afficher la carte pour le moment.',
                      preservedMessage:
                          'Les possibilités restent accessibles dans la liste.',
                      onRetry: retryable ? retry : null,
                    );
                  },
                ),
              ),
              Align(
                alignment: Alignment.bottomCenter,
                child: SafeArea(
                  minimum: const EdgeInsets.all(MakoloSpacing.md),
                  child: SizedBox(
                    height: 118,
                    child: PageView.builder(
                      controller: PageController(viewportFraction: 0.88),
                      itemCount: points.length,
                      itemBuilder: (context, index) {
                        final point = points[index];
                        return Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: MakoloSpacing.xs,
                          ),
                          child: MakoloCard(
                            onTap: () =>
                                widget.onOpenOccurrence(point.occurrenceId),
                            semanticLabel:
                                'Lieu sur la carte. ${point.title}',
                            child: MakoloStatusMetadataAction(
                              title: point.title,
                              subtitle: [
                                point.placeName,
                                point.locality,
                              ].whereType<String>().join(' · '),
                              metadata: [
                                MakoloMetadataItem(
                                  '${point.latitude.toStringAsFixed(4)}, '
                                  '${point.longitude.toStringAsFixed(4)}',
                                  icon: Icons.location_on_outlined,
                                ),
                              ],
                              action:
                                  const Icon(Icons.chevron_right_rounded),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _DiscoveryResultsList extends StatelessWidget {
  const _DiscoveryResultsList({
    required this.presentation,
    required this.onOpenActivity,
    required this.onOpenItem,
    required this.onPage,
  });

  final DiscoveryCollectionPresentation presentation;
  final ValueChanged<String> onOpenActivity;
  final void Function(String family, String id) onOpenItem;
  final ValueChanged<int> onPage;

  void _open(DiscoveryItemPresentation item) {
    if (item.family == 'activity' ||
        item.family == 'service_activity' ||
        item.family == 'funding_activity') {
      onOpenActivity(item.id);
      return;
    }
    onOpenItem(item.family, item.id);
  }

  @override
  Widget build(BuildContext context) {
    if (presentation.items.isEmpty) {
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        children: const [
          SizedBox(height: 120),
          Padding(
            padding: EdgeInsets.all(MakoloSpacing.inner),
            child: Center(
              child: Text(
                'Aucune possibilité ne correspond actuellement.',
                textAlign: TextAlign.center,
              ),
            ),
          ),
        ],
      );
    }

    return ListView(
      key: ValueKey('discovery-page-${presentation.page}'),
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
      children: [
        for (final item in presentation.items)
          Padding(
            padding: const EdgeInsets.fromLTRB(
              MakoloSpacing.inner,
              MakoloSpacing.sm,
              MakoloSpacing.inner,
              0,
            ),
            child: _DiscoveryCard(item: item, onTap: () => _open(item)),
          ),
        Padding(
          padding: const EdgeInsets.all(MakoloSpacing.inner),
          child: Row(
            children: [
              OutlinedButton.icon(
                onPressed: presentation.page > 1
                    ? () => onPage(presentation.page - 1)
                    : null,
                icon: const Icon(Icons.chevron_left_rounded),
                label: const Text('Précédent'),
              ),
              const Spacer(),
              Text(
                'Page ${presentation.page}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const Spacer(),
              FilledButton.icon(
                onPressed: presentation.hasNext
                    ? () => onPage(presentation.page + 1)
                    : null,
                icon: const Icon(Icons.chevron_right_rounded),
                label: const Text('Suivant'),
              ),
            ],
          ),
        ),
      ],
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
        ? 'Aucune donnée n’est encore disponible hors connexion.'
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
                          body: 'Le serveur indique qu’une profondeur Jour J est disponible pour cette occurrence.',
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
