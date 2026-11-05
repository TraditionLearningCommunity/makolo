import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/notifications/notification_repository.dart';
import 'package:makolo_mobile/notifications/notification_screens.dart';

import 'support/presentation_harness.dart';

void main() {
  testWidgets('contextual inbox and empty unread stay readable', (tester) async {
    final database = MakoloDatabase.memory();
    addTearDown(database.close);
    final store = ProfileStore(database, 'profile-a');
    await store.putProjection(
      kind: NotificationRepository.listProjectionKind,
      schemaVersion: 1,
      payload: {
        'count': 1, 'total_count': 1, 'unread_count': 0, 'next': null,
        'results': [
          {
            'id': 'journey-confirmed',
            'title': 'Confirmation Makolo',
            'message': 'Votre démarche pour « Louer un véhicule à Kolwezi » est confirmée.',
            'is_read': true,
          },
        ],
      },
    );
    await store.putProjection(
      kind: NotificationRepository.unreadProjectionKind,
      schemaVersion: 1,
      payload: {
        'count': 0, 'total_count': 1, 'unread_count': 0,
        'next': null, 'results': <Object>[],
      },
    );
    final repository = NotificationRepository(
      database: database, store: store, profileId: 'profile-a', sync: null,
    );
    await PresentationHarness.pump(
      tester,
      child: MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(1.6)),
        child: NotificationInboxScreen(
          repository: repository,
          onOpenDestination: (_) async {},
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Louer un véhicule à Kolwezi'), findsOneWidget);
    expect(find.text('Votre démarche est confirmée.'), findsNothing);
    expect(find.text('Confirmée'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('Non lues (0)'));
    await tester.pumpAndSettle();
    expect(find.text('Aucune notification non lue.'), findsOneWidget);
    expect(find.text('Toutes (1)'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
