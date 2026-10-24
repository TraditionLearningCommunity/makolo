import '../app/session_recovery.dart';
import 'deep_link_resolver.dart';
import 'destination.dart';

enum IncomingIntentSource {
  notification,
  push,
  qr,
  widget,
  appLink,
  customScheme,
}

class IncomingIntent {
  const IncomingIntent({required this.source, required this.destination});

  final IncomingIntentSource source;
  final StructuredDestination destination;
}

class IngressResolution {
  const IngressResolution({
    required this.route,
    required this.requiresAuthentication,
  });

  final String route;
  final bool requiresAuthentication;
}

class IncomingIntentResolver {
  const IncomingIntentResolver({this.deepLinks = const DeepLinkResolver()});

  final DeepLinkResolver deepLinks;

  IngressResolution? resolve({
    required IncomingIntent intent,
    required bool authenticated,
    required SessionRecoveryController recovery,
  }) {
    final route = deepLinks.resolve(intent.destination);
    if (route == null) return null;
    // A public, revocable Sharing URL remains readable before login.
    // Private deliveries still require the recipient's authenticated session.
    if (route.startsWith('/s/')) {
      return IngressResolution(route: route, requiresAuthentication: false);
    }
    if (authenticated) {
      return IngressResolution(route: route, requiresAuthentication: false);
    }
    recovery.requireAuthenticationFor(route);
    return const IngressResolution(
      route: '/login',
      requiresAuthentication: true,
    );
  }
}
