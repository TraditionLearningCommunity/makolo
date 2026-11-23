import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/widgets.dart';

import 'discovery_map_controller.dart';
import 'makolo_map_view.dart';
import 'map_runtime_config.dart';

/// The public card/map shares the same native clustering and marker layers
/// as personal Discovery. Only admitted public coordinates reach this view.
class PublicDiscoveryPointsMap extends StatefulWidget {
  const PublicDiscoveryPointsMap({
    super.key,
    required this.config,
    required this.pins,
    required this.fallbackBuilder,
    this.onLocationTap,
  });

  final MakoloMapsConfig config;
  final List<DiscoveryMapPin> pins;
  final MakoloMapFallbackBuilder fallbackBuilder;
  final ValueChanged<String>? onLocationTap;

  @override
  State<PublicDiscoveryPointsMap> createState() =>
      _PublicDiscoveryPointsMapState();
}

class _PublicDiscoveryPointsMapState extends State<PublicDiscoveryPointsMap> {
  DiscoveryMapController? _controller;
  bool _styleReady = false;
  bool _initialCameraPositioned = false;
  Future<void> _renderQueue = Future<void>.value();

  Future<void> _plot() {
    final controller = _controller;
    if (!_styleReady || controller == null) return Future<void>.value();
    // Serialize style/source updates so stale presentation cannot overwrite
    // a newer field. MapLibre does the zoom grouping, never a Dart pin loop.
    final pins = List<DiscoveryMapPin>.unmodifiable(widget.pins);
    final operation = _renderQueue.then((_) async {
      if (!mounted || _controller != controller) return;
      try {
        await controller.renderPins(pins);
        if (!_initialCameraPositioned && pins.isNotEmpty) {
          _initialCameraPositioned = true;
          try {
            await controller.fitPins(pins);
          } on Object {
            _initialCameraPositioned = false;
          }
        }
      } on Object {
        // The adjacent lazy list remains usable if the native map fails.
      }
    });
    _renderQueue = operation;
    return operation;
  }

  Future<void> _onFeatureTap(math.Point<double> point) async {
    final controller = _controller;
    if (controller == null) return;
    final key = await controller.selectRenderedPoint(point);
    if (!mounted || _controller != controller || key == null) return;
    widget.onLocationTap?.call(key);
  }

  @override
  void didUpdateWidget(covariant PublicDiscoveryPointsMap oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.pins, widget.pins)) unawaited(_plot());
  }

  @override
  void dispose() {
    _styleReady = false;
    _controller = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final first = widget.pins.isEmpty ? null : widget.pins.first;
    return ConfiguredMakoloMapView(
      config: widget.config,
      initialViewport: MapViewport(
        center: first == null
            ? const MapCoordinate(0, 0)
            : MapCoordinate(first.latitude, first.longitude),
        zoom: first == null ? 1 : 10,
      ),
      onMapCreated: (controller) {
        _controller = DiscoveryMapController(controller);
        _styleReady = false;
        _initialCameraPositioned = false;
      },
      onStyleReady: () {
        _styleReady = true;
        unawaited(_plot());
      },
      onFeatureTap: (point, _) => unawaited(_onFeatureTap(point)),
      fallbackBuilder: widget.fallbackBuilder,
    );
  }
}
