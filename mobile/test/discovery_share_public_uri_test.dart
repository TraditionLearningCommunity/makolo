import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/discovery/discovery_share_sheet.dart';

void main() {
  test('local LAN share URL requires the exact trusted API origin', () {
    expect(
      discoverySharePublicUri(
        'http://192.168.1.20:8000/s/token/',
        trustedBaseUri: Uri.parse('http://192.168.1.20:8000/'),
      )?.toString(),
      'http://192.168.1.20:8000/s/token/',
    );
    expect(
      discoverySharePublicUri(
        'http://10.0.2.2:8000/s/token/',
        trustedBaseUri: Uri.parse('http://10.0.2.2:8000/'),
      ),
      isNotNull,
    );
  });
  test(
    'sharing accepts canonical HTTPS links and local Django development',
    () {
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
    },
  );

  test('sharing rejects insecure public links and deceptive authorities', () {
    expect(discoverySharePublicUri('http://example.org/s/token/'), isNull);
    expect(
      discoverySharePublicUri('http://192.168.1.20:8000/s/token/'),
      isNull,
    );
    expect(
      discoverySharePublicUri(
        'http://192.168.1.20:8000/s/token/',
        trustedBaseUri: Uri.parse('http://192.168.1.21:8000/'),
      ),
      isNull,
    );
    expect(
      discoverySharePublicUri(
        'http://8.8.8.8:8000/s/token/',
        trustedBaseUri: Uri.parse('http://8.8.8.8:8000/'),
      ),
      isNull,
    );
    expect(
      discoverySharePublicUri('https://user@example.org/s/token/'),
      isNull,
    );
    expect(discoverySharePublicUri('/s/token/'), isNull);
    expect(discoverySharePublicUri('javascript:alert(1)'), isNull);
    expect(discoverySharePublicUri(''), isNull);
  });
}
