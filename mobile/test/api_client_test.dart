import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'fakes.dart';

void main() {
  test('concurrent 401 responses share a single rotating refresh', () async {
    var refreshCalls = 0;
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'old-access',
        refreshToken: 'old-refresh',
        profileId: 'profile-a',
      ),
    );

    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/refresh/')) {
        refreshCalls += 1;
        await Future<void>.delayed(const Duration(milliseconds: 25));
        expect(jsonDecode(request.body)['refresh'], 'old-refresh');
        return http.Response(
          jsonEncode({
            'access': 'new-access',
            'refresh': 'new-refresh',
          }),
          200,
        );
      }
      if (request.headers['Authorization'] == 'Bearer old-access') {
        return http.Response(
          jsonEncode({'detail': 'Token expired'}),
          401,
        );
      }
      expect(request.headers['Authorization'], 'Bearer new-access');
      return http.Response(jsonEncode({'ok': true}), 200);
    });

    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      httpClient: client,
      tokenStore: tokens,
    );

    final responses = await Future.wait([
      api.get('api/v1/me/now/'),
      api.get('api/v1/me/ongoing/'),
    ]);

    expect(responses.every((response) => response.statusCode == 200), isTrue);
    expect(refreshCalls, 1);
    expect((await tokens.readSession())?.refreshToken, 'new-refresh');
  });

  test('logout after access expiry blacklists the rotated refresh', () async {
    var refreshCalls = 0;
    String? loggedOutRefresh;
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'expired-access',
        refreshToken: 'old-refresh',
        profileId: 'profile-a',
      ),
    );
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/refresh/')) {
        refreshCalls += 1;
        return http.Response(
          jsonEncode({
            'access': 'fresh-access',
            'refresh': 'fresh-refresh',
          }),
          200,
        );
      }
      if (request.url.path.endsWith('/auth/logout/')) {
        if (request.headers['Authorization'] == 'Bearer expired-access') {
          return http.Response(jsonEncode({'detail': 'expired'}), 401);
        }
        loggedOutRefresh =
            (jsonDecode(request.body) as Map<String, dynamic>)['refresh']
                as String;
        return http.Response(jsonEncode({'message': 'ok'}), 200);
      }
      throw StateError('unexpected request');
    });
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      httpClient: client,
      tokenStore: tokens,
    );

    await api.logoutCurrentSession();

    expect(refreshCalls, 1);
    expect(loggedOutRefresh, 'fresh-refresh');
  });

  test('invalid refresh removes credentials without touching local data', () async {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'expired',
        refreshToken: 'revoked',
        profileId: 'profile-a',
      ),
    );
    final client = MockClient((request) async {
      return http.Response(jsonEncode({'detail': 'invalid'}), 401);
    });
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      httpClient: client,
      tokenStore: tokens,
    );

    await expectLater(
      api.get('api/v1/me/now/'),
      throwsA(isA<Exception>()),
    );
    expect(await tokens.readSession(), isNull);
  });
}
