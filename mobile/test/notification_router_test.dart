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
}
