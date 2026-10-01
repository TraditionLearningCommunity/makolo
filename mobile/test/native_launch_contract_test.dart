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

  test(
    'Android host declares PAR-1B capabilities without storage permissions',
    () {
      final manifest = File('android/app/src/main/AndroidManifest.xml')
          .readAsStringSync();

      expect(manifest, contains('android.permission.INTERNET'));
      expect(manifest, contains('android.permission.CAMERA'));
      expect(manifest, contains('android.permission.RECORD_AUDIO'));
      expect(manifest, contains('android.permission.ACCESS_COARSE_LOCATION'));
      expect(manifest, contains('android.permission.ACCESS_FINE_LOCATION'));
      expect(
        manifest,
        contains('android.permission.ACCESS_BACKGROUND_LOCATION'),
      );
      expect(manifest, contains('android.permission.FOREGROUND_SERVICE'));
      expect(
        manifest,
        contains('android.permission.FOREGROUND_SERVICE_LOCATION'),
      );
      expect(manifest, contains('android.permission.POST_NOTIFICATIONS'));
      expect(manifest, contains('android.permission.USE_BIOMETRIC'));

      expect(manifest, isNot(contains('READ_MEDIA')));
      expect(manifest, isNot(contains('READ_EXTERNAL_STORAGE')));
      expect(manifest, isNot(contains('WRITE_EXTERNAL_STORAGE')));
    },
  );

  test('Android host accepts share ingress without inventing app links', () {
    final manifest = File('android/app/src/main/AndroidManifest.xml')
        .readAsStringSync();

    expect(manifest, contains('android.intent.action.SEND'));
    expect(manifest, contains('android.intent.action.SEND_MULTIPLE'));
    expect(manifest, contains('android:mimeType="*/*"'));
    expect(manifest, isNot(contains('android.intent.action.VIEW')));
    expect(manifest, isNot(contains('android:autoVerify="true"')));
  });
}
