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

  test('Conversation notification opens the exact authorized Point target', () {
    const router = NotificationRouter();
    const conversationId = '11111111-1111-4111-8111-111111111111';
    const pointId = '22222222-2222-4222-8222-222222222222';
    final navigation = {
      'schema_version': 1,
      'target': 'conversation',
      'conversation_id': conversationId,
      'point_id': pointId,
      'resource': {'kind': 'conversation', 'id': conversationId},
    };
    expect(
      router.resolveNavigation(navigation),
      '/conversations/$conversationId?focus=$pointId',
    );
  });

  test('malformed Point metadata cannot create an injected focus route', () {
    const router = NotificationRouter();
    const conversationId = '11111111-1111-4111-8111-111111111111';
    for (final rawPoint in ['../other', 'some-name', '0000?tab=all', '']) {
      expect(
        router.resolveNavigation({
          'schema_version': 1,
          'target': 'conversation',
          'conversation_id': conversationId,
          'point_id': rawPoint,
          'resource': {'kind': 'conversation', 'id': conversationId},
        }),
        '/conversations/$conversationId',
      );
    }
  });

  test('unsupported priority cannot manufacture an owner handoff', () {
    const router = NotificationRouter();
    expect(
      router.resolveNavigation({
        'schema_version': 1,
        'resource': {'kind': 'ticket', 'id': 'ticket-42'},
      }),
      isNull,
    );
  });
}
