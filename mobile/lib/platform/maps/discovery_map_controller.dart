import 'package:maplibre_gl/maplibre_gl.dart';

class DiscoveryMapPin {
  const DiscoveryMapPin(this.latitude, this.longitude);
  final double latitude;
  final double longitude;
}

class DiscoveryMapController {
  const DiscoveryMapController(this._controller);
  final MapLibreMapController _controller;

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
    await _controller.addCircle(
      CircleOptions(
        geometry: LatLng(latitude, longitude),
        circleRadius: 10,
        circleColor: '#2563EB',
        circleStrokeWidth: 3,
        circleStrokeColor: '#FFFFFF',
      ),
    );
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
