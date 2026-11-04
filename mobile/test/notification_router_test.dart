import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/notifications/notification_router.dart';

void main() {
  test('notification router reuses structured deep-link resolution', () {
    const router = NotificationRouter();

    expect(
      router.resolve(
        const NotificationRouteIntent(kind: 'Journey', id: 'journey-42'),
      ),
      '/journeys/journey-42',
    );
    expect(
      router.resolve(
        const NotificationRouteIntent(kind: 'Unknown', id: 'value'),
      ),
      isNull,
    );
  });
  test('legacy ticket with explicit Access opens owner destination', () {
    const router = NotificationRouter();
    final target = router.resolveNavigation({
      'schema_version': 1,
      'target': 'ticket',
      'ticket_id': 'ticket-42',
      'access_id': 'access-42',
      'resource': {'kind': 'ticket', 'id': 'ticket-42'},
    });
    expect(target, '/accesses/access-42');
  });

  test('unsupported priority cannot manufacture an owner handoff', () {
    const router = NotificationRouter();
    expect(router.resolveNavigation({
      'schema_version': 1,
      'resource': {'kind': 'ticket', 'id': 'ticket-42'},
    }), isNull);
  });

}
