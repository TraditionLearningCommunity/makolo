import 'launch_preferences.dart';

enum BrandMomentCadence { oneDay, threeDays }

extension BrandMomentCadenceDuration on BrandMomentCadence {
  Duration get duration => switch (this) {
    BrandMomentCadence.oneDay => const Duration(days: 1),
    BrandMomentCadence.threeDays => const Duration(days: 3),
  };
}

class BrandMomentPolicy {
  const BrandMomentPolicy({this.cadence = configuredCadence});

  static const configuredCadence = BrandMomentCadence.oneDay;

  final BrandMomentCadence cadence;

  bool isEligible({
    required LaunchPreferencesSnapshot preferences,
    required DateTime now,
    bool isResume = false,
    bool hasPriorityNavigation = false,
  }) {
    if (isResume || hasPriorityNavigation) return false;

    final lastShownAt = preferences.lastBrandMomentAt;
    if (lastShownAt == null) return true;

    final elapsed = now.toUtc().difference(lastShownAt.toUtc());
    if (elapsed.isNegative) return false;
    return elapsed >= cadence.duration;
  }
}

bool hasPriorityLaunchPath(String path, {required bool authenticated}) {
  final defaultPath = authenticated ? '/now' : '/discover';
  return path.isNotEmpty && path != '/' && path != defaultPath;
}
