import 'package:url_launcher/url_launcher.dart';

/// Open an authorized external web destination in the system browser.
Future<bool> openExternalUrl(Uri uri) =>
    launchUrl(uri, mode: LaunchMode.externalApplication);
