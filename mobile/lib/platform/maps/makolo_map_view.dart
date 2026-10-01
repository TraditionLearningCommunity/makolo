import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

import 'map_runtime_config.dart';

class MapCoordinate {
  const MapCoordinate(this.latitude, this.longitude);

  final double latitude;
  final double longitude;
}

class MapViewport {
  const MapViewport({
    required this.center,
    this.zoom = 12,
    this.bearing = 0,
    this.tilt = 0,
  });

  final MapCoordinate center;
  final double zoom;
  final double bearing;
  final double tilt;
}

class MakoloMapView extends StatelessWidget {
  const MakoloMapView({
    required this.styleString,
    required this.initialViewport,
    this.onTap,
    this.onStyleReady,
    super.key,
  });

  final String styleString;
  final MapViewport initialViewport;
  final ValueChanged<MapCoordinate>? onTap;
  final VoidCallback? onStyleReady;

  @override
  Widget build(BuildContext context) {
    return MapLibreMap(
      styleString: styleString,
      initialCameraPosition: CameraPosition(
        target: LatLng(
          initialViewport.center.latitude,
          initialViewport.center.longitude,
        ),
        zoom: initialViewport.zoom,
        bearing: initialViewport.bearing,
        tilt: initialViewport.tilt,
      ),
      onMapClick: onTap == null
          ? null
          : (_, coordinate) => onTap!(
              MapCoordinate(coordinate.latitude, coordinate.longitude),
            ),
      onStyleLoadedCallback: onStyleReady,
    );
  }
}

enum MakoloMapRuntimeState { disabled, loading, ready, error }

typedef MakoloMapFallbackBuilder = Widget Function(
  BuildContext context,
  MakoloMapRuntimeState state,
  VoidCallback retry,
);

class ConfiguredMakoloMapView extends StatefulWidget {
  const ConfiguredMakoloMapView({
    required this.config,
    required this.initialViewport,
    required this.fallbackBuilder,
    this.onTap,
    this.onStyleReady,
    this.styleLoadTimeout = const Duration(seconds: 20),
    super.key,
  });

  final MakoloMapsConfig config;
  final MapViewport initialViewport;
  final MakoloMapFallbackBuilder fallbackBuilder;
  final ValueChanged<MapCoordinate>? onTap;
  final VoidCallback? onStyleReady;
  final Duration styleLoadTimeout;

  @override
  State<ConfiguredMakoloMapView> createState() =>
      _ConfiguredMakoloMapViewState();
}

class _ConfiguredMakoloMapViewState extends State<ConfiguredMakoloMapView> {
  Timer? _styleTimer;
  bool _styleReady = false;
  bool _styleFailed = false;
  int _attempt = 0;

  String? get _style {
    final value = widget.config.style?.trim();
    return value == null || value.isEmpty ? null : value;
  }

  MakoloMapRuntimeState get _state {
    if (!widget.config.enabled) return MakoloMapRuntimeState.disabled;
    if (_style == null || _styleFailed) return MakoloMapRuntimeState.error;
    if (_styleReady) return MakoloMapRuntimeState.ready;
    return MakoloMapRuntimeState.loading;
  }

  @override
  void initState() {
    super.initState();
    _armStyleTimeout();
  }

  @override
  void didUpdateWidget(covariant ConfiguredMakoloMapView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.config.enabled != widget.config.enabled ||
        oldWidget.config.style != widget.config.style ||
        oldWidget.styleLoadTimeout != widget.styleLoadTimeout) {
      _resetAttempt();
    }
  }

  @override
  void dispose() {
    _styleTimer?.cancel();
    super.dispose();
  }

  void _armStyleTimeout() {
    _styleTimer?.cancel();
    if (!widget.config.enabled || _style == null) return;
    _styleTimer = Timer(widget.styleLoadTimeout, () {
      if (!mounted || _styleReady) return;
      setState(() => _styleFailed = true);
    });
  }

  void _resetAttempt() {
    _styleTimer?.cancel();
    _styleReady = false;
    _styleFailed = false;
    _attempt += 1;
    _armStyleTimeout();
    if (mounted) setState(() {});
  }

  void _handleStyleReady() {
    _styleTimer?.cancel();
    if (mounted && !_styleReady) {
      setState(() {
        _styleReady = true;
        _styleFailed = false;
      });
    }
    widget.onStyleReady?.call();
  }

  @override
  Widget build(BuildContext context) {
    final state = _state;
    if (state == MakoloMapRuntimeState.disabled ||
        state == MakoloMapRuntimeState.error) {
      return widget.fallbackBuilder(context, state, _resetAttempt);
    }

    return MakoloMapView(
      key: ValueKey(_attempt),
      styleString: _style!,
      initialViewport: widget.initialViewport,
      onTap: widget.onTap,
      onStyleReady: _handleStyleReady,
    );
  }
}
