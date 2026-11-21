import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/data/local/makolo_database.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/settings/notification_preferences_screen.dart';
import 'package:makolo_mobile/notifications/notification_repository.dart';
import 'package:makolo_mobile/notifications/notification_routes.dart';
import 'package:makolo_mobile/notifications/notification_screens.dart';

import 'fakes.dart';

void main() {
  test('Notifications cannot alias a store from another Profile', () async {
    final db = MakoloDatabase.memory();
    addTearDown(db.close);
    expect(
      () => NotificationRepository(
        database: db,
        store: ProfileStore(db, 'profile-b'),
        profileId: 'profile-a',
        sync: null,
      ),
      throwsArgumentError,
    );
  });

  testWidgets(
    'inbox and preferences reuse one owner repository and Profile store',
    (tester) async {
      final database = MakoloDatabase.memory();
      addTearDown(database.close);
      final store = ProfileStore(database, 'profile-a');
      final notifications = NotificationRepository(
        database: database,
        store: store,
        profileId: 'profile-a',
        sync: null,
      );
      await store.putProjection(
        kind: NotificationRepository.listProjectionKind,
        schemaVersion: 1,
        payload: {
          'count': 1,
          'next': null,
          'results': [
            {
              'id': 'notification-1',
              'title': 'Nouvelle étape',
              'message': 'Votre dossier a évolué',
              'is_read': false,
              'created_at': '2026-11-05T07:00:00Z',
            },
          ],
        },
      );
      await store.putProjection(
        kind: NotificationRepository.preferencesProjectionKind,
        schemaVersion: 1,
        payload: const {
          'push_notifications': true,
          'email_notifications': false,
        },
      );
      final runtime = AppRuntime(
        tokens: MemoryTokenStore(),
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
        recovery: SessionRecoveryController(),
        database: database,
        store: store,
        notifications: notifications,
      );
      final router = GoRouter(
        initialLocation: '/notifications',
        routes: notificationRoutes(runtime),
      );
      addTearDown(router.dispose);
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();
      final inbox = tester.widget<NotificationInboxScreen>(
        find.byType(NotificationInboxScreen),
      );
      expect(identical(inbox.repository, runtime.notifications), isTrue);
      expect(find.text('Nouvelle étape'), findsOneWidget);

      router.go('/settings/notifications');
      await tester.pumpAndSettle();
      final preferences = tester.widget<NotificationPreferencesScreen>(
        find.byType(NotificationPreferencesScreen),
      );
      expect(identical(preferences.repository, runtime.notifications), isTrue);
      expect(find.text('Préférences'), findsWidgets);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
