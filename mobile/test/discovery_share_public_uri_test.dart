import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/discovery/discovery_share_sheet.dart';

void main() {
  test('sharing accepts canonical HTTPS links and local Django development', () {
    expect(
      discoverySharePublicUri('https://makolo.example/s/token/')?.toString(),
      'https://makolo.example/s/token/',
    );
    expect(
      discoverySharePublicUri('http://127.0.0.1:8000/s/token/')?.toString(),
      'http://127.0.0.1:8000/s/token/',
    );
    expect(
      discoverySharePublicUri('http://localhost:8000/s/token/')?.toString(),
      'http://localhost:8000/s/token/',
    );
  });

  test('sharing rejects insecure public links and deceptive authorities', () {
    expect(discoverySharePublicUri('http://example.org/s/token/'), isNull);
    expect(discoverySharePublicUri('https://user@example.org/s/token/'), isNull);
    expect(discoverySharePublicUri('/s/token/'), isNull);
    expect(discoverySharePublicUri('javascript:alert(1)'), isNull);
    expect(discoverySharePublicUri(''), isNull);
  });
}
