import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/presentation/possibilities/discovery_reader.dart';

void main() {
  test('reader rejects non-web and credential-bearing destinations', () {
    expect(discoverySafeDestination(Uri.parse('javascript:alert(1)')), isFalse);
    expect(discoverySafeDestination(Uri.parse('file:///tmp/private.pdf')), isFalse);
    expect(discoverySafeDestination(Uri.parse('https://user:pass@example.org/a')), isFalse);
    expect(discoverySafeDestination(Uri.parse('/preparation/resources/1/download/')), isFalse);
    expect(discoverySafeDestination(Uri.parse('https://example.org/a.pdf')), isTrue);
  });
}
