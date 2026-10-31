import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/settings/notification_preferences_screen.dart';
import 'package:makolo_mobile/notifications/notification_repository.dart';

void main() {
  testWidgets('offline notification settings show owner snapshot without mutation',
      (tester) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    await store.putProjection(
      kind: NotificationRepository.preferencesProjectionKind,
      schemaVersion: 1,
      payload: {
        'push_notifications': true,
        'email_notifications': true,
        'sms_notifications': false,
        'security_notifications': true,
        'event_notifications': true,
        'service_notifications': false,
        'opportunity_notifications': true,
        'marketing_notifications': false,
        'quiet_hours_enabled': false,
        'quiet_hours_start': null,
        'quiet_hours_end': null,
      },
    );
    final repository = NotificationRepository(
      database: database, store: store, profileId: 'profile-a', sync: null,
    );
    await tester.pumpWidget(MaterialApp(
      home: NotificationPreferencesScreen(repository: repository),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Notifications'), findsOneWidget);
    expect(find.text('E-mail'), findsOneWidget);
    expect(find.text('Heures calmes'), findsOneWidget);
    expect(find.textContaining('modification hors ligne indisponible'),
        findsOneWidget);
    final email = tester.widget<SwitchListTile>(
      find.widgetWithText(SwitchListTile, 'E-mail'),
    );
    expect(email.value, isTrue);
    expect(email.onChanged, isNull);
  });
}
