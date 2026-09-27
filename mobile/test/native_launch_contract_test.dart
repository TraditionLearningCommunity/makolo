import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('native launch uses Makolo indigo and the canonical white Mark', () {
    final colors = File('android/app/src/main/res/values/colors.xml')
        .readAsStringSync();
    final launch = File(
      'android/app/src/main/res/drawable/launch_background.xml',
    ).readAsStringSync();
    final launch31 = File('android/app/src/main/res/values-v31/styles.xml')
        .readAsStringSync();

    expect(colors, contains('#5232DB'));
    expect(launch, contains('@drawable/ic_makolo_mark_white'));
    expect(
      launch31,
      contains(
        '<item name="android:windowSplashScreenAnimatedIcon">'
        '@drawable/ic_makolo_mark_white</item>',
      ),
    );
    expect(File('assets/brand/makolo-mark-white.svg').existsSync(), isTrue);
  });

  test('onboarding adds no speculative Android runtime permission', () {
    final manifest = File('android/app/src/main/AndroidManifest.xml')
        .readAsStringSync();

    expect(manifest, contains('android.permission.INTERNET'));
    expect(manifest, isNot(contains('POST_NOTIFICATIONS')));
    expect(manifest, isNot(contains('android.permission.CAMERA')));
    expect(manifest, isNot(contains('ACCESS_FINE_LOCATION')));
    expect(manifest, isNot(contains('READ_MEDIA')));
  });
}
