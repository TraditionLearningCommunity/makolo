import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../design/makolo_theme.dart';
import '../../platform/maps/makolo_map_view.dart';
import '../../platform/maps/public_discovery_points_map.dart';
import '../discovery/discovery_repository.dart';
import 'public_shell.dart';

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
  List<Map<String, dynamic>> _points = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Map<String, dynamic> _object(Object? value) =>
      value is Map ? Map<String, dynamic>.from(value) : const {};

  double? _number(Object? value) => value is num
      ? value.toDouble()
      : double.tryParse(value?.toString() ?? '');

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Public API unavailable');
      final response = await api.publicGet(widget.query.mapPath);
      final raw = response.jsonObject()['results'];
      if (raw is! List) throw const FormatException('Invalid map results');
      final points = raw
          .whereType<Map>()
          .map(_object)
          .where((item) {
            final place = _object(item['place']);
            return _number(place['latitude']) != null &&
                _number(place['longitude']) != null;
          })
          .toList(growable: false);
      if (!mounted) return;
      setState(() {
        _points = points;
        _loading = false;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Impossible de charger la carte publique.';
      });
    }
  }

  void _open(Map<String, dynamic> item) {
    final id = item['activity_id']?.toString();
    if (id == null || id.isEmpty) return;
    context.push('/discover/items/activity/${Uri.encodeComponent(id)}');
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
                context.go('/discover');
              }
            },
            icon: const Icon(Icons.arrow_back),
            label: const Text('Retour aux résultats'),
          ),
          const SizedBox(height: MakoloSpacing.sm),
          Text('Explorer sur la carte', style: theme.textTheme.headlineSmall),
          const SizedBox(height: MakoloSpacing.md),
          if (_loading)
            const Center(child: CircularProgressIndicator())
          else if (_error != null) ...[
            Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
            TextButton(onPressed: _load, child: const Text('Réessayer')),
          ] else if (!hasPoints)
            const Text(
              'Aucune possibilité géolocalisable pour cette recherche.',
            )
          else ...[
            SizedBox(
              height: 320,
              child: PublicDiscoveryPointsMap(
                config: widget.runtime.mapConfig,
                points: [
                  for (final point in _points)
                    MapCoordinate(
                      _number(_object(point['place'])['latitude'])!,
                      _number(_object(point['place'])['longitude'])!,
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
            Text('${_points.length} lieux', style: theme.textTheme.titleMedium),
            const SizedBox(height: MakoloSpacing.sm),
            for (final item in _points)
              Card(
                child: ListTile(
                  title: Text(item['title']?.toString() ?? 'Possibilité'),
                  subtitle: Text(
                    _object(item['place'])['name']?.toString() ?? '',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => _open(item),
                ),
              ),
          ],
        ],
      ),
    );
  }
}
