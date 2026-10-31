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
