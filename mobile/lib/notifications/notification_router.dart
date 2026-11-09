import '../navigation/deep_link_resolver.dart';
import '../navigation/destination.dart';
import '../navigation/structured_destination_codec.dart';

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

  String? resolveNavigation(Object? navigation) {
    const codec = StructuredDestinationCodec();
    final destination = codec.fromNavigation(navigation);
    if (destination == null) return null;
    final path = resolve(
      NotificationRouteIntent(
        kind: destination.kind,
        id: destination.id,
        link: destination.link,
      ),
    );
    if (path != null) {
      // Point identity is explicit notification metadata. Never parse a
      // displayed title/body or an arbitrary URL to infer the destination.
      if (destination.kind.toLowerCase() == 'conversation' &&
          navigation is Map && path == '/conversations/${destination.id}') {
        final pointId = navigation['point_id']?.toString();
        if (pointId != null &&
            RegExp(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}

    // Historical ticket/payment/order priorities can shadow an explicit,
    // usable Access or Journey destination. Never infer an owner from text.
    if (!{
      'ticket',
      'payment',
      'ticket_order',
      'event',
    }.contains(destination.kind.toLowerCase())) {
      return null;
    }
    for (final entry in const [
      ('access_id', 'access'),
      ('journey_id', 'journey'),
    ]) {
      final id = navigation[entry.$1]?.toString().trim();
      if (id == null || id.isEmpty) continue;
      final alternative = resolve(
        NotificationRouteIntent(kind: entry.$2, id: id),
      );
      if (alternative != null) return alternative;
    }
    return null;
  }

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
)
                .hasMatch(pointId)) {
          return '$path?focus=${Uri.encodeQueryComponent(pointId)}';
        }
      }
      return path;
    }
    if (navigation is! Map) return null;

    // Historical ticket/payment/order priorities can shadow an explicit,
    // usable Access or Journey destination. Never infer an owner from text.
    if (!{
      'ticket',
      'payment',
      'ticket_order',
      'event',
    }.contains(destination.kind.toLowerCase())) {
      return null;
    }
    for (final entry in const [
      ('access_id', 'access'),
      ('journey_id', 'journey'),
    ]) {
      final id = navigation[entry.$1]?.toString().trim();
      if (id == null || id.isEmpty) continue;
      final alternative = resolve(
        NotificationRouteIntent(kind: entry.$2, id: id),
      );
      if (alternative != null) return alternative;
    }
    return null;
  }

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
