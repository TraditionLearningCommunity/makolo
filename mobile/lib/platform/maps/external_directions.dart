import 'package:url_launcher/url_launcher.dart';

/// A destination already published by Makolo. The user's GPS coordinates are
/// never inserted in the URL; the chosen navigation app owns the route.
class ExternalDirections {
  const ExternalDirections._();

  static bool valid(double latitude, double longitude) =>
      latitude.isFinite &&
      longitude.isFinite &&
      latitude >= -90 &&
      latitude <= 90 &&
      longitude >= -180 &&
      longitude <= 180;

  static Uri googleMaps(double latitude, double longitude) {
    _requireValid(latitude, longitude);
    return Uri.https('www.google.com', '/maps/dir/', {
      'api': '1',
      'destination': '${latitude.toString()},${longitude.toString()}',
      'dir_action': 'navigate',
    });
  }

  static void _requireValid(double latitude, double longitude) {
    if (!valid(latitude, longitude)) {
      throw ArgumentError('Invalid public destination coordinates');
    }
  }

  /// Universal HTTPS links work with the installed app or the browser.
  /// No API credential, new dependency, simulated ETA or internal navigation.
  static Future<bool> open(Uri destination) async {
    if (destination.scheme != 'https') return false;
    try {
      return await launchUrl(destination, mode: LaunchMode.externalApplication);
    } on Object {
      return false;
    }
  }
}
