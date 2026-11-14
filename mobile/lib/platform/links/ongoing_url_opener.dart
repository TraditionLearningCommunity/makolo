import 'package:url_launcher/url_launcher.dart';

Future<bool> openOngoingUrl(Uri uri) =>
    launchUrl(uri, mode: LaunchMode.inAppBrowserView);
