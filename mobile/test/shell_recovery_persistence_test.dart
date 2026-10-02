import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/launch_preferences.dart';
import 'package:makolo_mobile/app/session_recovery.dart';

void main() {
  test('shell location persists independently per Profile', () async {
    final directory = await Directory.systemTemp.createTemp(
      'makolo-shell-location-test-',
    );
    addTearDown(() => directory.delete(recursive: true));
    final file = File('${directory.path}/preferences.json');
    final store = FileLaunchPreferencesStore.forFile(file);

    await store.writeShellLocation('profile-a', '/space/work');
    await store.writeShellLocation('profile-b', '/me');

    final reopened = FileLaunchPreferencesStore.forFile(file);
    expect(await reopened.readShellLocation('profile-a'), '/space/work');
    expect(await reopened.readShellLocation('profile-b'), '/me');
  });

  test('launch recovery uses persisted shell location without creating actor state', () {
    final recovery = SessionRecoveryController();
    recovery.restoreLaunchLocation('/space/us');

    expect(recovery.initialLocation(), '/space/us');
    expect(recovery.awaitingAuthentication, isFalse);
  });

  test('account switch clears restored navigation context', () {
    final recovery = SessionRecoveryController();
    recovery.restoreLaunchLocation('/space/work');
    recovery.markAccountSwitch();

    expect(recovery.initialLocation(), '/now');
  });
}
