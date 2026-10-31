import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../design/makolo_theme.dart';
import '../../platform/maps/makolo_map_view.dart';
import '../../platform/maps/public_discovery_points_map.dart';
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
  DiscoveryCollectionPresentation _collection =
      DiscoveryCollectionPresentation.empty;
  List<_MappedPossibility> _points = const [];
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
      _collection = DiscoveryCollectionPresentation.empty;
      _points = const [];
      unawaited(_load());
    }
  }

  Future<void> _load({bool next = false}) async {
    if (next && (_loading || !_collection.hasNext)) return;
    final revision = ++_requestRevision;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Public API unavailable');
      // Map is another view of exactly the same public field. Its first
      // request must not silently replace the selected page/size or cursor.
      final query = next
          ? widget.query.copyWith(
              page: _collection.page + 1,
              continuation: _collection.continuationToken,
            )
          : widget.query;
      final response = await api.publicGet(query.path);
      final wire = DiscoveryWire.receive(
        response.jsonObject(),
        scope: 'public',
      );
      final incoming = _selector.publicCollection(wire.snapshotPayload);
      if (!mounted || revision != _requestRevision) return;
      final collection = next ? _collection.reconcile(incoming) : incoming;
      final items = {
        for (final item in collection.items) item.candidateKey: item,
      };
      final anchors = _selector.spatialAnchorsFromCollection(collection);
      setState(() {
        _collection = collection;
        _points = [
          for (final anchor in anchors)
            if (items[anchor.candidateKey] != null)
              (anchor: anchor, item: items[anchor.candidateKey]!),
        ];
        _loading = false;
      });
    } on Object {
      if (!mounted || revision != _requestRevision) return;
      setState(() {
        _loading = false;
        _error = 'Impossible de charger la carte publique.';
      });
    }
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
      child: ListView(
        key: const Key('guest-discover-map'),
        padding: const EdgeInsets.all(MakoloSpacing.lg),
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
          Text('Explorer sur la carte', style: theme.textTheme.headlineSmall),
          const SizedBox(height: MakoloSpacing.md),
          if (_loading && !hasPoints)
            const Center(child: CircularProgressIndicator())
          else if (_error != null && !hasPoints) ...[
            Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
            TextButton(onPressed: _load, child: const Text('Réessayer')),
          ] else if (!hasPoints && !_collection.hasNext)
            const Text(
              'Aucune possibilité géolocalisable pour cette recherche.',
            )
          else ...[
            if (hasPoints) ...[
              SizedBox(
                height: 320,
                child: PublicDiscoveryPointsMap(
                  config: widget.runtime.mapConfig,
                  points: [
                    for (final point in _points)
                      MapCoordinate(
                        point.anchor.latitude,
                        point.anchor.longitude,
                      ),
                  ],
                  fallbackBuilder: (context, state, retry) => Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Text(
                          'Carte indisponible. Les lieux restent consultables.',
                        ),
                        if (state == MakoloMapRuntimeState.error)
                          TextButton(
                            onPressed: retry,
                            child: const Text('Réessayer la carte'),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: MakoloSpacing.md),
              Text(
                '${_points.length} lieux',
                style: theme.textTheme.titleMedium,
              ),
              const SizedBox(height: MakoloSpacing.sm),
              for (final point in _points)
                Card(
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
                ),
            ],
            if (_loading) const Center(child: CircularProgressIndicator()),
            if (_error != null) ...[
              Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
              TextButton(
                onPressed: () => _load(next: true),
                child: const Text('Réessayer'),
              ),
            ],
            if (_collection.hasNext && !_loading && _error == null)
              TextButton(
                onPressed: () => _load(next: true),
                child: const Text('Explorer plus de lieux'),
              ),
          ],
        ],
      ),
    );
  }
}
