import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/presentation/possibilities/discovery_offline_store.dart';
import 'package:makolo_mobile/presentation/possibilities/discovery_reader.dart';

void main() {
  test('reader rejects unsafe destinations', () {
    expect(discoverySafeDestination(Uri.parse('javascript:alert(1)')), isFalse);
    expect(
      discoverySafeDestination(Uri.parse('file:///tmp/private.pdf')),
      isFalse,
    );
    expect(
      discoverySafeDestination(Uri.parse('https://user:pass@example.org/a')),
      isFalse,
    );
    expect(
      discoverySafeDestination(Uri.parse('/preparation/resources/1/download/')),
      isFalse,
    );
    expect(
      discoverySafeDestination(Uri.parse('https://example.org/a.pdf')),
      isTrue,
    );
  });

  test('offline filenames are stable and scoped to destination', () {
    final one = Uri.parse('https://makolo.example/media/one.png');
    final two = Uri.parse('https://makolo.example/media/two.png');
    expect(
      DiscoveryOfflineStore.keyFor(one),
      DiscoveryOfflineStore.keyFor(one),
    );
    expect(
      DiscoveryOfflineStore.keyFor(one),
      isNot(DiscoveryOfflineStore.keyFor(two)),
    );
    expect(DiscoveryOfflineStore.keyFor(one).length, 16);
  });
}
