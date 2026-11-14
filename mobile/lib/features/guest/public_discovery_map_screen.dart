import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../design/makolo_theme.dart';
import '../../platform/maps/discovery_map_controller.dart';
import '../../platform/maps/makolo_map_view.dart';
import '../../platform/maps/public_discovery_points_map.dart';
import '../discovery/discovery_mature_view.dart';
import '../discovery/discovery_repository.dart';
import '../discovery/discovery_selector.dart';
import '../discovery/discovery_wire.dart';
import 'public_shell.dart';

typedef _MappedPossibility = ({
  DiscoverySpatialAnchor anchor,
  DiscoveryItemPresentation item,
});

class PublicDiscoveryMapScreen extends StatefulWidget {
  const PublicDiscoveryMapScreen({
    super.key,
    required this.runtime,
    required this.query,
  });

  final AppRuntime runtime;
  final DiscoveryQuery query;

  @override
  State<PublicDiscoveryMapScreen> createState() =>
      _PublicDiscoveryMapScreenState();
}

class _PublicDiscoveryMapScreenState extends State<PublicDiscoveryMapScreen> {
  static const _selector = DiscoverySelector();
  List<_MappedPossibility> _points = const [];
  List<DiscoveryMapPin> _mapPins = const [];
  bool _loading = true;
  String? _error;
  int _requestRevision = 0;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  @override
  void dispose() {
    _requestRevision++;
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant PublicDiscoveryMapScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.query.mapCanonicalQuery != widget.query.mapCanonicalQuery) {
      _points = const [];
      _mapPins = const [];
      unawaited(_load());
    }
  }

  Future<void> _load() async {
    final revision = ++_requestRevision;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Public API unavailable');
      // A Map is the complete admitted geographic field, not the current
      // N1 page. The owner already provides an unpaginated compact index
      // alongside the first paginated Discovery response.
      final root = widget.query.copyWith(page: 1, clearContinuation: true);
      final path = root.path;
      final response = await api.publicGet(
        '$path${path.contains('?') ? '&' : '?'}include_spatial_index=compact',
      );
      final wire = DiscoveryWire.receive(
        response.jsonObject(),
        scope: 'public',
      );
      final index = wire.snapshotPayload['spatial_index'];
      if (index is! Map ||
          index['results'] is! List ||
          index['count'] is! int ||
          index['detail_available'] != false) {
        throw const FormatException('Invalid public spatial index');
      }
      final spatial = _selector.publicCollection(<String, dynamic>{
        ...wire.snapshotPayload,
        'results': index['results'],
        'items': index['results'],
        'count': index['count'],
        'page': 1,
        'page_size': index['count'],
        'has_next': false,
      });
      if (!mounted || revision != _requestRevision) return;
      final items = {for (final item in spatial.items) item.candidateKey: item};
      final anchors = _selector.spatialAnchorsFromCollection(spatial);
      final mapped = <_MappedPossibility>[
        for (final anchor in anchors)
          if (items[anchor.candidateKey] != null)
            (anchor: anchor, item: items[anchor.candidateKey]!),
      ];
      final locationAnchors = <String, DiscoverySpatialAnchor>{};
      final candidatesAtLocation = <String, Set<String>>{};
      for (final point in mapped) {
        final key = _locationKey(point.anchor);
        locationAnchors.putIfAbsent(key, () => point.anchor);
        candidatesAtLocation
            .putIfAbsent(key, () => <String>{})
            .add(point.item.candidateKey);
      }
      final pins = <DiscoveryMapPin>[
        for (final entry in locationAnchors.entries)
          DiscoveryMapPin(
            entry.value.latitude,
            entry.value.longitude,
            locationKey: entry.key,
            opportunityCount: candidatesAtLocation[entry.key]!.length,
          ),
      ];
      setState(() {
        _points = mapped;
        _mapPins = pins;
        _loading = false;
      });
    } on Object {
      if (!mounted || revision != _requestRevision) return;
      setState(() {
        _loading = false;
        _error = 'Impossible de charger les lieux.';
      });
    }
  }

  static String _locationKey(DiscoverySpatialAnchor anchor) =>
      '${anchor.latitude}:${anchor.longitude}';

  void _openMapLocation(String key) {
    final choices = <String, DiscoveryItemPresentation>{};
    for (final point in _points) {
      if (_locationKey(point.anchor) == key) {
        choices[point.item.candidateKey] = point.item;
      }
    }
    if (choices.isEmpty) return;
    if (choices.length == 1) {
      _open(choices.values.single);
      return;
    }
    // Reuse the same chooser as authenticated Discovery for co-located items.
    unawaited(_chooseCoLocated(choices.values.toList()));
  }

  Future<void> _chooseCoLocated(List<DiscoveryItemPresentation> items) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (sheetContext) => DiscoveryCoLocatedPicker(
        items: items,
        onChoose: (item) {
          Navigator.of(sheetContext).pop();
          if (mounted) _open(item);
        },
      ),
    );
  }

  void _open(DiscoveryItemPresentation item) {
    context.push(
      '/discover/items/${Uri.encodeComponent(item.family)}/'
      '${Uri.encodeComponent(item.id)}',
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final hasPoints = _points.isNotEmpty;
    return PublicExperienceShell(
      current: 1,
      // Lazy cards: 500 map pins must not build 500 Flutter ListTiles at once.
      child: ListView.builder(
        key: const Key('guest-discover-map'),
        padding: const EdgeInsets.all(MakoloSpacing.lg),
        itemCount: _points.length + 1,
        itemBuilder: (context, index) {
          if (index > 0) {
            final point = _points[index - 1];
            return Card(
              child: ListTile(
                title: Text(point.item.title),
                subtitle: Text(
                  (point.anchor.fact['place'] is Map
                              ? (point.anchor.fact['place'] as Map)['name']
                              : null)
                          ?.toString() ??
                      point.item.place ??
                      '',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _open(point.item),
              ),
            );
          }
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextButton.icon(
                onPressed: () {
                  if (context.canPop()) {
                    context.pop();
                  } else {
                    context.go(widget.query.routeLocation('/discover'));
                  }
                },
                icon: const Icon(Icons.arrow_back),
                label: const Text('Retour aux résultats'),
              ),
              const SizedBox(height: MakoloSpacing.sm),
              Text(
                'Explorer sur la carte',
                style: theme.textTheme.headlineSmall,
              ),
              const SizedBox(height: MakoloSpacing.md),
              if (_loading && !hasPoints)
                const Center(child: CircularProgressIndicator())
              else if (_error != null && !hasPoints) ...[
                Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
                TextButton(
                  onPressed: () => unawaited(_load()),
                  child: const Text('Réessayer'),
                ),
              ] else if (!hasPoints && !_loading)
                const Text('Aucun lieu à afficher pour cette recherche.')
              else if (hasPoints) ...[
                SizedBox(
                  height: 320,
                  child: PublicDiscoveryPointsMap(
                    config: widget.runtime.mapConfig,
                    pins: _mapPins,
                    onLocationTap: _openMapLocation,
                    fallbackBuilder: (context, state, retry) => Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Text('Impossible d’afficher la carte.'),
                          if (state == MakoloMapRuntimeState.error)
                            TextButton(
                              onPressed: retry,
                              child: const Text('Réessayer'),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: MakoloSpacing.md),
                Text(
                  '${_points.length} emplacements sur la carte',
                  style: theme.textTheme.titleMedium,
                ),
                const SizedBox(height: MakoloSpacing.sm),
              ],
              if (_loading && hasPoints)
                const Center(child: CircularProgressIndicator()),
              if (_error != null && hasPoints) ...[
                Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
                TextButton(
                  onPressed: () => unawaited(_load()),
                  child: const Text('Réessayer'),
                ),
              ],
            ],
          );
        },
      ),
    );
  }
}
