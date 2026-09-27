import 'package:flutter/widgets.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

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
