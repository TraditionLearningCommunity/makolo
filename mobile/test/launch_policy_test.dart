import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/launch_policy.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/notifications/notification_router.dart';

void main() {
  final now = DateTime.utc(2026, 9, 27, 8);

  test('brand moment is eligible when it has never been shown', () {
    const policy = BrandMomentPolicy();

    expect(
      policy.isEligible(
        preferences: const LaunchPreferencesSnapshot(),
        now: now,
      ),
      isTrue,
    );
  });

  test('recent brand moment is not shown again', () {
    const policy = BrandMomentPolicy();

    expect(
      policy.isEligible(
        preferences: LaunchPreferencesSnapshot(
          lastBrandMomentAt: now.subtract(const Duration(hours: 8)),
        ),
        now: now,
      ),
      isFalse,
    );
  });

  test('brand moment becomes eligible after the configured cadence', () {
    const policy = BrandMomentPolicy();

    expect(
      policy.isEligible(
        preferences: LaunchPreferencesSnapshot(
          lastBrandMomentAt: now.subtract(const Duration(days: 1, minutes: 1)),
        ),
        now: now,
      ),
      isTrue,
    );
  });

  test('three-day cadence is switchable in one policy value', () {
    const policy = BrandMomentPolicy(cadence: BrandMomentCadence.threeDays);

    expect(
      policy.isEligible(
        preferences: LaunchPreferencesSnapshot(
          lastBrandMomentAt: now.subtract(const Duration(days: 2)),
        ),
        now: now,
      ),
      isFalse,
    );
    expect(
      policy.isEligible(
        preferences: LaunchPreferencesSnapshot(
          lastBrandMomentAt: now.subtract(const Duration(days: 3, minutes: 1)),
        ),
        now: now,
      ),
      isTrue,
    );
  });

  test('deep-link or notification priority suppresses brand moment', () {
    const policy = BrandMomentPolicy();

    expect(
      policy.isEligible(
        preferences: const LaunchPreferencesSnapshot(),
        now: now,
        hasPriorityNavigation: true,
      ),
      isFalse,
    );
  });

  test('notification destination remains a priority launch path', () {
    const notifications = NotificationRouter();
    final route = notifications.resolve(
      const NotificationRouteIntent(kind: 'Journey', id: 'journey-1'),
    );

    expect(route, '/journeys/journey-1');
    expect(hasPriorityLaunchPath(route!, authenticated: true), isTrue);
  });

  test('background resume never replays brand moment', () {
    const policy = BrandMomentPolicy();

    expect(
      policy.isEligible(
        preferences: const LaunchPreferencesSnapshot(),
        now: now,
        isResume: true,
      ),
      isFalse,
    );
  });

  test('priority launch path is any non-default destination', () {
    expect(hasPriorityLaunchPath('/journeys/abc', authenticated: true), isTrue);
    expect(hasPriorityLaunchPath('/now', authenticated: true), isFalse);
    expect(hasPriorityLaunchPath('/discover', authenticated: false), isFalse);
  });
}
