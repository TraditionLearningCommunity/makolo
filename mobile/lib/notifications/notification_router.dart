import '../navigation/deep_link_resolver.dart';
import '../navigation/destination.dart';

class NotificationRouteIntent {
  const NotificationRouteIntent({
    required this.kind,
    required this.id,
    this.link,
  });

  final String kind;
  final String id;
  final String? link;
}

class NotificationRouter {
  const NotificationRouter({this.deepLinks = const DeepLinkResolver()});

  final DeepLinkResolver deepLinks;

  String? resolve(NotificationRouteIntent intent) {
    return deepLinks.resolve(
      StructuredDestination(
        kind: intent.kind,
        id: intent.id,
        link: intent.link,
      ),
    );
  }
}
