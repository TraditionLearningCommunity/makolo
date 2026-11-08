import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:maplibre_gl/maplibre_gl.dart';

class DiscoveryMapPin {
  const DiscoveryMapPin(
    this.latitude,
    this.longitude, {
    this.locationKey,
    this.opportunityCount = 1,
    this.selected = false,
    this.symbol = '',
  });

  final double latitude;
  final double longitude;
  final String? locationKey;
  final int opportunityCount;
  final bool selected;

  /// Short, public category glyph only; never an inferred business fact.
  final String symbol;
}

class DiscoveryMapController {
  DiscoveryMapController(this._controller);
  final MapLibreMapController _controller;

  static const _source = 'makolo-discovery-locations';
  static const _clusters = 'makolo-discovery-clusters';
  static const _counts = 'makolo-discovery-counts';
  static const _points = 'makolo-discovery-points';
  static const _locationCounts = 'makolo-discovery-location-counts';
  static const _pointIcons = 'makolo-discovery-point-icons';
  static const _singlePins = 'makolo-discovery-single-pins';
  static const _multiPlaces = 'makolo-discovery-multi-places';
  static const _pinImage = 'makolo-discovery-pin-image';
  static const _pinSelectedImage = 'makolo-discovery-pin-selected-image';
  static const _placeImage = 'makolo-discovery-multi-image';
  static const _placeSelectedImage = 'makolo-discovery-multi-selected-image';

  bool _clusterReady = false;
  bool _symbolPinsReady = false;
  bool _fallbackPinsActive = false;
  Circle? _deviceCircle;

  /// Only public geographic facts from the admitted Discovery field reach
  /// the map renderer. No second data owner, no candidate scoring and no
  /// client-side geocoding.
  static Map<String, dynamic> geoJsonForPins(List<DiscoveryMapPin> pins) => {
    'type': 'FeatureCollection',
    'features': [
      for (final pin in pins)
        {
          'type': 'Feature',
          'properties': {
            'location_key':
                pin.locationKey ?? '${pin.latitude}:${pin.longitude}',
            'opportunity_count': pin.opportunityCount,
            'selected': pin.selected,
            'symbol': pin.symbol,
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
        try {
          await _controller.setGeoJsonSource(_source, data);
        } on Object {
          // A native style reload drops app-owned layers and sources.
          // Restore the same clustering recipe before using annotations.
          _clusterReady = false;
          _symbolPinsReady = false;
          await _removeClusterLayers();
          return await renderPins(pins);
        }
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
              10,
              25,
              50,
              32,
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

        // MapLibre owns the clustering, while our *unclustered* locations
        // have two distinct visual vocabularies: pins (one possibility) and
        // rounded-count badges (several at one exact public coordinate).
        try {
          await _registerMarkerImages();
          await _controller.addSymbolLayer(
            _source,
            _singlePins,
            SymbolLayerProperties(
              iconImage: [
                'case',
                [
                  '==',
                  [Expressions.get, 'selected'],
                  true,
                ],
                _pinSelectedImage,
                _pinImage,
              ],
              iconSize: 0.5,
              iconAnchor: 'bottom',
              iconAllowOverlap: true,
              iconIgnorePlacement: true,
            ),
            filter: [
              'all',
              [
                '!',
                ['has', 'point_count'],
              ],
              [
                '==',
                [Expressions.get, 'opportunity_count'],
                1,
              ],
            ],
          );
          await _controller.addSymbolLayer(
            _source,
            _multiPlaces,
            SymbolLayerProperties(
              iconImage: [
                'case',
                [
                  '==',
                  [Expressions.get, 'selected'],
                  true,
                ],
                _placeSelectedImage,
                _placeImage,
              ],
              iconSize: 0.5,
              iconAnchor: 'center',
              iconAllowOverlap: true,
              iconIgnorePlacement: true,
            ),
            filter: [
              'all',
              [
                '!',
                ['has', 'point_count'],
              ],
              [
                '>',
                [Expressions.get, 'opportunity_count'],
                1,
              ],
            ],
          );
          _symbolPinsReady = true;
        } on Object {
          // A missing sprite or unsupported symbol must never remove native
          // clustering. Keep the old circles as the visible fallback.
          _symbolPinsReady = false;
          for (final layer in [_multiPlaces, _singlePins]) {
            try {
              await _controller.removeLayer(layer);
            } on Object {
              // A native style reload may already have removed this layer.
            }
          }
          await _addUnclusteredCircleFallback();
        }
        // Exact-location multiplicity is different from a zoom cluster.
        // A pin can represent many admitted opportunities at one Place.
        await _controller.addSymbolLayer(
          _source,
          _locationCounts,
          SymbolLayerProperties(
            textField: [
              'to-string',
              [Expressions.get, 'opportunity_count'],
            ],
            textSize: 12,
            textColor: '#FFFFFF',
            textAllowOverlap: true,
          ),
          filter: [
            'all',
            [
              '!',
              ['has', 'point_count'],
            ],
            [
              '>',
              [Expressions.get, 'opportunity_count'],
              1,
            ],
          ],
        );
        // A glyph is shown only for one opportunity with an admitted type.
        // The native clusters and exact-location counts retain their own layers.
        if (_symbolPinsReady) {
          try {
            await _controller.addSymbolLayer(
              _source,
              _pointIcons,
              SymbolLayerProperties(
                textField: [Expressions.get, 'symbol'],
                textSize: 15,
                textColor: '#2B176E',
                // Keep the category inside the native pin head (not floating above it).
                textOffset: [0, -1.0],
                textAllowOverlap: true,
              ),
              filter: [
                'all',
                [
                  '!',
                  ['has', 'point_count'],
                ],
                [
                  '==',
                  [Expressions.get, 'opportunity_count'],
                  1,
                ],
                [
                  '!=',
                  [Expressions.get, 'symbol'],
                  '',
                ],
              ],
            );
          } on Object {
            // A missing glyph/font must NEVER disable native clustering.
          }
        }
        _clusterReady = true;
      }
      if (_fallbackPinsActive) {
        // The source recovered after using legacy annotations. Do not show
        // two identical pin layers; the device dot is immediately repainted
        // by the caller with its owner-independent local coordinates.
        await _controller.clearCircles();
        _deviceCircle = null;
        _fallbackPinsActive = false;
      }
      return const [];
    } on Object {
      // Keep the geographic field usable if a platform or style rejects
      // source/layer clustering. Uncluttered annotations are the fallback.
      _clusterReady = false;
      _symbolPinsReady = false;
      await _removeClusterLayers();
      try {
        await _controller.clearCircles();
        _deviceCircle = null;
        final annotations = await addPins(pins);
        _fallbackPinsActive = true;
        return annotations;
      } on Object {
        return const [];
      }
    }
  }

  /// Native circle fallback only: the original cluster source, grouping,
  /// expansion and counters remain unchanged.
  Future<void> _addUnclusteredCircleFallback() => _controller.addCircleLayer(
    _source,
    _points,
    CircleLayerProperties(
      circleRadius: [
        'case',
        [
          '==',
          [Expressions.get, 'selected'],
          true,
        ],
        26,
        [
          Expressions.step,
          [Expressions.get, 'opportunity_count'],
          8,
          2,
          16,
          10,
          20,
          100,
          24,
        ],
      ],
      circleColor: [
        'case',
        [
          '==',
          [Expressions.get, 'selected'],
          true,
        ],
        '#2B176E',
        '#5232DB',
      ],
      circleStrokeWidth: [
        'case',
        [
          '==',
          [Expressions.get, 'selected'],
          true,
        ],
        4,
        2,
      ],
      circleStrokeColor: [
        'case',
        [
          '==',
          [Expressions.get, 'selected'],
          true,
        ],
        '#FF704D',
        '#FFFFFF',
      ],
    ),
    filter: [
      '!',
      ['has', 'point_count'],
    ],
  );

  // Rendered once per MapLibre style, never per point or camera movement.
  // Draw twice the display size and use iconSize=0.5 (maplibre_gl 0.27.1).
  // Do not use addImage(pixelRatio), introduced only in later plugin versions.
  Future<void> _registerMarkerImages() async {
    await _controller.addImage(_pinImage, await _drawPin(false));
    await _controller.addImage(_pinSelectedImage, await _drawPin(true));
    await _controller.addImage(_placeImage, await _drawPlaceBadge(false));
    await _controller.addImage(
      _placeSelectedImage,
      await _drawPlaceBadge(true),
    );
  }

  static Future<Uint8List> _png(
    ui.PictureRecorder recorder,
    int width,
    int height,
  ) async {
    final picture = recorder.endRecording();
    try {
      final image = await picture.toImage(width, height);
      try {
        final data = await image.toByteData(format: ui.ImageByteFormat.png);
        if (data == null) throw StateError('Map marker PNG unavailable');
        return data.buffer.asUint8List();
      } finally {
        image.dispose();
      }
    } finally {
      picture.dispose();
    }
  }

  static Future<Uint8List> _drawPin(bool selected) {
    final recorder = ui.PictureRecorder();
    final canvas = ui.Canvas(recorder);
    final shape = ui.Path()
      ..moveTo(48, 108)
      ..cubicTo(35, 90, 15, 69, 15, 44)
      ..cubicTo(15, 25, 29, 10, 48, 10)
      ..cubicTo(67, 10, 81, 25, 81, 44)
      ..cubicTo(81, 69, 61, 90, 48, 108)
      ..close();
    canvas.drawPath(
      shape,
      ui.Paint()..color = ui.Color(selected ? 0xFF2B176E : 0xFF5232DB),
    );
    canvas.drawPath(
      shape,
      ui.Paint()
        ..style = ui.PaintingStyle.stroke
        ..strokeWidth = selected ? 8 : 6
        ..color = ui.Color(selected ? 0xFFFF704D : 0xFFFFFFFF),
    );
    canvas.drawCircle(
      const ui.Offset(48, 43),
      13,
      ui.Paint()..color = const ui.Color(0xFFFFFFFF),
    );
    return _png(recorder, 96, 112);
  }

  static Future<Uint8List> _drawPlaceBadge(bool selected) {
    final recorder = ui.PictureRecorder();
    final canvas = ui.Canvas(recorder);
    final rounded = ui.RRect.fromRectAndRadius(
      const ui.Rect.fromLTWH(4, 6, 100, 52),
      const ui.Radius.circular(24),
    );
    canvas.drawRRect(
      rounded,
      ui.Paint()..color = ui.Color(selected ? 0xFF2B176E : 0xFF5232DB),
    );
    canvas.drawRRect(
      rounded,
      ui.Paint()
        ..style = ui.PaintingStyle.stroke
        ..strokeWidth = selected ? 7 : 5
        ..color = ui.Color(selected ? 0xFFFF704D : 0xFFFFFFFF),
    );
    return _png(recorder, 108, 64);
  }

  Future<void> _removeClusterLayers() async {
    for (final layer in [
      _pointIcons,
      _locationCounts,
      _multiPlaces,
      _singlePins,
      _points,
      _counts,
      _clusters,
    ]) {
      try {
        await _controller.removeLayer(layer);
      } on Object {
        // A native style reload may already have removed this layer.
      }
    }
    try {
      await _controller.removeSource(_source);
    } on Object {
      // A native style reload may already have removed this layer.
    }
  }

  /// A cluster zooms to its real expansion level; an individual point
  /// resolves only its local location key (which may hold many opportunities).
  Future<String?> selectRenderedPoint(math.Point<double> point) async {
    if (!_clusterReady) return null;
    try {
      final hits = await _controller.queryRenderedFeatures(point, [
        _clusters,
        _locationCounts,
        if (_symbolPinsReady) ...[_multiPlaces, _singlePins] else _points,
      ], null);
      if (hits.isEmpty) return null;
      final feature = hits.first;
      if (feature is! Map) return null;
      final properties = feature['properties'];
      if (properties is! Map) return null;
      final clusterId = properties['cluster_id'];
      if (clusterId is num) {
        final zoom = await _controller.getClusterExpansionZoom(
          _source,
          clusterId.toInt(),
        );
        final geometry = feature['geometry'];
        final coords = geometry is Map ? geometry['coordinates'] : null;
        if (coords is List &&
            coords.length == 2 &&
            coords[0] is num &&
            coords[1] is num) {
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

  /// A selected possibility should be readable even when the previous map
  /// viewport covered multiple continents. Pan alone retains the old zoom.
  Future<void> focusLocation(
    double latitude,
    double longitude, {
    double zoom = 11,
  }) => _controller.animateCamera(
    CameraUpdate.newLatLngZoom(LatLng(latitude, longitude), zoom),
  );

  /// Choose a useful first neighbourhood when remote, unrelated places
  /// would otherwise force a whole-world camera fit. This is *presentation*
  /// only: it never removes candidates, ranks Discovery or changes the
  /// canonical MapLibre source. All pins remain accessible by panning.
  ///
  /// Returns only public geographic points. This does not use device
  /// coordinates or require location permission.
  static List<DiscoveryMapPin> initialFocusPins(List<DiscoveryMapPin> pins) {
    if (pins.length < 2) return pins;
    final minLat = pins.map((pin) => pin.latitude).reduce(math.min);
    final maxLat = pins.map((pin) => pin.latitude).reduce(math.max);
    final minLon = pins.map((pin) => pin.longitude).reduce(math.min);
    final maxLon = pins.map((pin) => pin.longitude).reduce(math.max);
    // One country-sized field keeps the existing inclusive bounds fit.
    if (maxLat - minLat < 12 && maxLon - minLon < 12) return pins;
    const radiusKm = 250.0;
    var bestWeight = -1;
    var bestCount = -1;
    var best = <DiscoveryMapPin>[];
    for (final center in pins) {
      final group = <DiscoveryMapPin>[];
      var weight = 0;
      for (final point in pins) {
        if (_distanceKm(center, point) > radiusKm) continue;
        group.add(point);
        weight += math.max(1, point.opportunityCount);
      }
      if (weight > bestWeight ||
          (weight == bestWeight && group.length > bestCount)) {
        bestWeight = weight;
        bestCount = group.length;
        best = group;
      }
    }
    return best.isNotEmpty ? best : pins;
  }

  static double _distanceKm(DiscoveryMapPin a, DiscoveryMapPin b) {
    const rad = math.pi / 180;
    final dLat = (b.latitude - a.latitude) * rad;
    final dLon = (b.longitude - a.longitude) * rad;
    final h =
        math.pow(math.sin(dLat / 2), 2) +
        math.cos(a.latitude * rad) *
            math.cos(b.latitude * rad) *
            math.pow(math.sin(dLon / 2), 2);
    return 12742 * math.asin(math.sqrt(h.clamp(0.0, 1.0)));
  }

  /// One camera fit on initial style load. MapLibre owns pan/zoom afterward.
  Future<void> fitPins(List<DiscoveryMapPin> pins) async {
    if (pins.isEmpty) return;
    // Initial camera uses a dense local region, not a transcontinental
    // bounding box that makes every marker too small to inspect.
    pins = initialFocusPins(pins);
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
          circleRadius: pin.selected ? 26 : (pin.opportunityCount > 1 ? 12 : 8),
          circleColor: pin.selected ? '#2B176E' : '#5232DB',
          circleStrokeWidth: pin.selected ? 4 : 2,
          circleStrokeColor: pin.selected ? '#FF704D' : '#FFFFFF',
        ),
    ]);
    return circles;
  }
}
