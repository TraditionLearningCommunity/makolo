import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/resumable_interaction_store.dart';

void main() {
  test('resumable interaction store excludes sensitive values', () async {
    final store = ResumableInteractionStore.memory();

    await store.save('signup', {
      'email': 'amina@example.com',
      'username': 'amina',
      'password': 'plain-secret',
      'password_confirm': 'plain-secret',
      'refresh_token': 'refresh-secret',
      'remember_on_device': true,
    });

    final draft = await store.read('signup');
    expect(draft['email'], 'amina@example.com');
    expect(draft['username'], 'amina');
    expect(draft['remember_on_device'], isTrue);
    expect(draft.containsKey('password'), isFalse);
    expect(draft.containsKey('password_confirm'), isFalse);
    expect(draft.containsKey('refresh_token'), isFalse);
  });

  test(
    'clearing one interaction leaves other resumable state intact',
    () async {
      final store = ResumableInteractionStore.memory();
      await store.save('login', {'email': 'a@example.com'});
      await store.save('public-discover', {'query': 'formation'});

      await store.clear('login');

      expect(await store.read('login'), isEmpty);
      expect((await store.read('public-discover'))['query'], 'formation');
    },
  );
}
