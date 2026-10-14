import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

import 'makolo_map_view.dart';
import 'map_runtime_config.dart';

/// Platform boundary for public map markers. The guest feature only provides
/// coordinates admitted by the canonical Discovery map projection.
class PublicDiscoveryPointsMap extends StatefulWidget {
  const PublicDiscoveryPointsMap({
    super.key,
    required this.config,
    required this.points,
    required this.fallbackBuilder,
  });

  final MakoloMapsConfig config;
  final List<MapCoordinate> points;
  final MakoloMapFallbackBuilder fallbackBuilder;

  @override
  State<PublicDiscoveryPointsMap> createState() =>
      _PublicDiscoveryPointsMapState();
}

class _PublicDiscoveryPointsMapState extends State<PublicDiscoveryPointsMap> {
  MapLibreMapController? _controller;

  Future<void> _plot() async {
    final controller = _controller;
    if (controller == null) return;
    for (final point in widget.points) {
      try {
        await controller.addCircle(
          CircleOptions(
            geometry: LatLng(point.latitude, point.longitude),
            circleColor: '#5232DB',
            circleStrokeColor: '#FFFFFF',
            circleStrokeWidth: 2,
            circleRadius: 8,
          ),
        );
      } on Object {
        // Rendering is optional; the adjacent list remains usable.
        break;
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final first = widget.points.first;
    return ConfiguredMakoloMapView(
      config: widget.config,
      initialViewport: MapViewport(
        center: first,
        zoom: 10,
      ),
      onMapCreated: (controller) => _controller = controller,
      onStyleReady: () => unawaited(_plot()),
      fallbackBuilder: widget.fallbackBuilder,
    );
  }
}
