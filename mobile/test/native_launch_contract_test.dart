import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('native launch uses Makolo indigo and the canonical white Mark', () {
    final colors = File('android/app/src/main/res/values/colors.xml')
        .readAsStringSync();
    final launch = File(
      'android/app/src/main/res/drawable/launch_background.xml',
    ).readAsStringSync();
    final launchNight = File(
      'android/app/src/main/res/drawable-night/launch_background.xml',
    ).readAsStringSync();
    final launch31 = File('android/app/src/main/res/values-v31/styles.xml')
        .readAsStringSync();
    final launch31Night = File(
      'android/app/src/main/res/values-night-v31/styles.xml',
    ).readAsStringSync();

    expect(colors, contains('#5232DB'));
    expect(launch, contains('@drawable/ic_makolo_mark_white'));
    expect(launchNight, contains('@drawable/ic_makolo_mark_white'));
    expect(
      launch31,
      contains(
        '<item name="android:windowSplashScreenAnimatedIcon">'
        '@drawable/makolo_splash_animated</item>',
      ),
    );
    expect(launch31Night, contains('@drawable/makolo_splash_animated'));
    expect(launch31, contains('windowSplashScreenAnimationDuration">620'));
    expect(colors, contains('#FF704D'));
    expect(File('assets/brand/makolo-mark-white.svg').existsSync(), isTrue);
  });

  test('Android 12 AVD has progressive steps and the exact canonical Mark', () {
    const root = 'android/app/src/main/res/';
    final avd = File('${root}drawable-v31/makolo_splash_animated.xml')
        .readAsStringSync();
    final vector = File('${root}drawable-v31/makolo_splash_vector.xml')
        .readAsStringSync();
    expect(avd, contains('<animated-vector'));
    expect(avd, contains('@drawable/makolo_splash_vector'));
    expect(vector, contains('android:width="432dp"'));
    expect(vector, contains('android:viewportWidth="432"'));
    expect(vector, contains('android:fillColor="@color/makolo_splash_step"'));
    String normalize(String path) => path.replaceAll(RegExp(r'[\s,]+'), '');
    final canonical = File('assets/brand/makolo-mark-white.svg')
        .readAsStringSync();
    final canonicalPath = RegExp(r'<path d="([^"]+)"')
        .firstMatch(canonical)!
        .group(1)!;
    final nativePaths = RegExp(r'android:pathData="([^"]+)"')
        .allMatches(vector)
        .map((match) => normalize(match.group(1)!));
    expect(nativePaths, contains(normalize(canonicalPath)));
    for (final name in ['step1', 'step2', 'step3', 'mark']) {
      expect(avd, contains('android:name="$name"'));
      final animation = File('${root}animator-v31/makolo_splash_$name.xml')
          .readAsStringSync();
      expect(animation, contains('android:duration="620"'));
      expect(animation, contains('android:propertyName="fillAlpha"'));
      expect(
        animation,
        contains(
          'android:fraction="1" android:value="${name == 'mark' ? 1 : 0}"',
        ),
      );
    }
    // A visible first step avoids a blank drawable before animation starts.
    expect(vector, contains('android:fillAlpha="1"'));
    final host = File('android/app/src/main/kotlin/com/makolo/MainActivity.kt')
        .readAsStringSync();
    expect(host, contains('Build.VERSION_CODES.S'));
    expect(host, contains('view.remove()'));
    expect(host, contains('call.method == "ready"'));
    expect(host, contains('removeNativeSplash?.invoke()'));
    expect(host, isNot(contains('OnPreDrawListener')));
    expect(host, isNot(contains('postDelayed')));
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

  test(
    'Android host accepts shares and only parameterized verified app links',
    () {
      final manifest = File('android/app/src/main/AndroidManifest.xml')
          .readAsStringSync();

      expect(manifest, contains('android.intent.action.SEND'));
      expect(manifest, contains('android.intent.action.SEND_MULTIPLE'));
      expect(manifest, contains('android:mimeType="*/*"'));
      // Link handling exists, but its scheme and host come from build configuration.
      // The checked-in manifest must not claim a real deployment host.
      expect(manifest, contains('android.intent.action.VIEW'));
      expect(manifest, contains('android:autoVerify="true"'));
      expect(
        manifest,
        contains('android:scheme="\u0024{makoloAppLinkScheme}"'),
      );
      expect(manifest, contains('android:host="\u0024{makoloAppLinkHost}"'));
      expect(manifest, contains('android:pathPrefix="/s/"'));
      expect(manifest, contains('android:pathPrefix="/shares/"'));
    },
  );
}
