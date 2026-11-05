import 'dart:math' as math;

import 'package:maplibre_gl/maplibre_gl.dart';

class DiscoveryMapPin {
  const DiscoveryMapPin(this.latitude, this.longitude, {this.locationKey});
  final double latitude;
  final double longitude;
  final String? locationKey;
}

class DiscoveryMapController {
  DiscoveryMapController(this._controller);
  final MapLibreMapController _controller;

  static const _source = 'makolo-discovery-locations';
  static const _clusters = 'makolo-discovery-clusters';
  static const _counts = 'makolo-discovery-counts';
  static const _points = 'makolo-discovery-points';

  bool _clusterReady = false;
  Circle? _deviceCircle;

  /// Only public geographic facts from the admitted Discovery field reach
  /// the map renderer. No second data owner, no candidate scoring and no
  /// client-side geocoding.
  static Map<String, dynamic> geoJsonForPins(
    List<DiscoveryMapPin> pins,
  ) => {
    'type': 'FeatureCollection',
    'features': [
      for (final pin in pins)
        {
          'type': 'Feature',
          'properties': {
            'location_key':
                pin.locationKey ?? '${pin.latitude}:${pin.longitude}',
          },
          'geometry': {
            'type': 'Point',
            'coordinates': [pin.longitude, pin.latitude],
          },
        },
    ],
  };

  /// MapLibre performs viewport/zoom clustering on the GPU-backed map.
  /// The circle annotation path remains a safe fallback on a style error.
  Future<List<Object>> renderPins(List<DiscoveryMapPin> pins) async {
    final data = geoJsonForPins(pins);
    try {
      if (_clusterReady) {
        await _controller.setGeoJsonSource(_source, data);
      } else {
        await _controller.addSource(
          _source,
          GeojsonSourceProperties(
            data: data,
            cluster: true,
            clusterRadius: 56,
            clusterMaxZoom: 13,
          ),
        );
        await _controller.addCircleLayer(
          _source,
          _clusters,
          CircleLayerProperties(
            circleRadius: [
              Expressions.step,
              [Expressions.get, 'point_count'],
              19,
              10, 25,
              50, 32,
            ],
            circleColor: '#5232DB',
            circleStrokeWidth: 2,
            circleStrokeColor: '#FFFFFF',
          ),
          filter: ['has', 'point_count'],
        );
        await _controller.addSymbolLayer(
          _source,
          _counts,
          SymbolLayerProperties(
            textField: [Expressions.get, 'point_count_abbreviated'],
            textSize: 13,
            textColor: '#FFFFFF',
            textAllowOverlap: true,
          ),
          filter: ['has', 'point_count'],
        );
        await _controller.addCircleLayer(
          _source,
          _points,
          const CircleLayerProperties(
            circleRadius: 8,
            circleColor: '#5232DB',
            circleStrokeWidth: 2,
            circleStrokeColor: '#FFFFFF',
          ),
          filter: ['!', ['has', 'point_count']],
        );
        _clusterReady = true;
      }
      return const [];
    } on Object {
      // Keep the geographic field usable if a platform or style rejects
      // source/layer clustering. Uncluttered annotations are the fallback.
      _clusterReady = false;
      await _removeClusterLayers();
      try {
        await _controller.clearCircles();
        _deviceCircle = null;
        return await addPins(pins);
      } on Object {
        return const [];
      }
    }
  }

  Future<void> _removeClusterLayers() async {
    for (final layer in [_points, _counts, _clusters]) {
      try {
        await _controller.removeLayer(layer);
      } on Object {}
    }
    try {
      await _controller.removeSource(_source);
    } on Object {}
  }

  /// A cluster zooms to its real expansion level; an individual point
  /// resolves only its local location key (which may hold many opportunities).
  Future<String?> selectRenderedPoint(math.Point<double> point) async {
    if (!_clusterReady) return null;
    try {
      final hits = await _controller.queryRenderedFeatures(
        point, [_clusters, _points], null,
      );
      if (hits.isEmpty) return null;
      final feature = hits.first;
      if (feature is! Map) return null;
      final properties = feature['properties'];
      if (properties is! Map) return null;
      final clusterId = properties['cluster_id'];
      if (clusterId is num) {
        final zoom = await _controller.getClusterExpansionZoom(
          _source, clusterId.toInt(),
        );
        final geometry = feature['geometry'];
        final coords = geometry is Map ? geometry['coordinates'] : null;
        if (coords is List && coords.length == 2 &&
            coords[0] is num && coords[1] is num) {
          await _controller.animateCamera(
            CameraUpdate.newLatLngZoom(
              LatLng(
                (coords[1] as num).toDouble(),
                (coords[0] as num).toDouble(),
              ),
              zoom.toDouble(),
            ),
          );
        }
        return null;
      }
      return properties['location_key'] is String
          ? properties['location_key'] as String
          : null;
    } on Object {
      return null;
    }
  }


  Future<void> moveTo(double latitude, double longitude) => _controller
      .animateCamera(CameraUpdate.newLatLng(LatLng(latitude, longitude)));

  /// One camera fit on initial style load. MapLibre owns pan/zoom afterward.
  Future<void> fitPins(List<DiscoveryMapPin> pins) async {
    if (pins.isEmpty) return;
    if (pins.length == 1) {
      await _controller.animateCamera(
        CameraUpdate.newLatLngZoom(
          LatLng(pins.first.latitude, pins.first.longitude),
          11,
        ),
      );
      return;
    }
    var minLatitude = pins.first.latitude;
    var maxLatitude = minLatitude;
    var minLongitude = pins.first.longitude;
    var maxLongitude = minLongitude;
    for (final pin in pins.skip(1)) {
      if (pin.latitude < minLatitude) minLatitude = pin.latitude;
      if (pin.latitude > maxLatitude) maxLatitude = pin.latitude;
      if (pin.longitude < minLongitude) minLongitude = pin.longitude;
      if (pin.longitude > maxLongitude) maxLongitude = pin.longitude;
    }
    if (minLatitude == maxLatitude && minLongitude == maxLongitude) {
      await _controller.animateCamera(
        CameraUpdate.newLatLngZoom(LatLng(minLatitude, minLongitude), 11),
      );
      return;
    }
    await _controller.animateCamera(
      CameraUpdate.newLatLngBounds(
        LatLngBounds(
          southwest: LatLng(minLatitude, minLongitude),
          northeast: LatLng(maxLatitude, maxLongitude),
        ),
        left: 40,
        top: 96,
        right: 40,
        bottom: 180,
      ),
    );
  }

  /// Device fix is rendered locally; it is never sent with Discovery markers.
  Future<void> showDevicePosition(double latitude, double longitude) async {
    final changes = CircleOptions(
      geometry: LatLng(latitude, longitude),
      circleRadius: 10,
      circleColor: '#2563EB',
      circleStrokeWidth: 3,
      circleStrokeColor: '#FFFFFF',
    );
    final existing = _deviceCircle;
    if (existing != null) {
      await _controller.updateCircle(existing, changes);
    } else {
      _deviceCircle = await _controller.addCircle(changes);
    }
  }

  void onPinTapped(void Function(Object) callback) {
    _controller.onCircleTapped.add(callback);
  }

  Future<void> clearPins() => _controller.clearCircles();

  Future<List<Object>> addPins(List<DiscoveryMapPin> pins) async {
    final circles = await _controller.addCircles([
      for (final pin in pins)
        CircleOptions(
          geometry: LatLng(pin.latitude, pin.longitude),
          circleRadius: 8,
          circleColor: '#6741D9',
          circleStrokeWidth: 2,
          circleStrokeColor: '#FFFFFF',
        ),
    ]);
    return circles;
  }
}
