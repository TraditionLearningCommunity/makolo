import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/resumable_interaction_store.dart';

void main() {
  test(
    'Service request intent and idempotence survive screen recreation',
    () async {
      final store = ResumableInteractionStore.memory();
      const key = 'services.start:profile-1:service-1';
      await store.save(key, {
        'idempotency_key': 'request-001',
        'objective': 'Obtenir un accompagnement',
        'opportunity': 'opportunity-1',
      });
      final reopened = await store.read(key);
      expect(reopened['idempotency_key'], 'request-001');
      expect(reopened['objective'], 'Obtenir un accompagnement');
      expect(reopened['opportunity'], 'opportunity-1');
      await store.clear(key);
      expect(await store.read(key), isEmpty);
    },
  );

  test('resumable interactions never persist sensitive credentials', () async {
    final store = ResumableInteractionStore.memory();
    await store.save('services.start:profile-1:service-1', {
      'idempotency_key': 'request-001',
      'objective': 'Aide',
      'access_token': 'must-not-persist',
      'credential': 'must-not-persist',
    });
    final recovered = await store.read('services.start:profile-1:service-1');
    expect(recovered['idempotency_key'], 'request-001');
    expect(recovered, isNot(contains('access_token')));
    expect(recovered, isNot(contains('credential')));
  });
}
