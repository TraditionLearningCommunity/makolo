import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/network/api_error.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'fakes.dart';

typedef RequestHandler = Future<ResponseBody> Function(
  RequestOptions options,
  Stream<Uint8List>? requestStream,
);

class TestHttpAdapter implements HttpClientAdapter {
  TestHttpAdapter(this.handler);

  final RequestHandler handler;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) {
    return handler(options, requestStream);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody jsonResponse(
  Object body,
  int statusCode, {
  Map<String, List<String>> headers = const {
    'content-type': ['application/json'],
  },
}) {
  return ResponseBody.fromString(
    jsonEncode(body),
    statusCode,
    headers: headers,
  );
}

Dio testDio(RequestHandler handler) {
  final dio = Dio();
  dio.httpClientAdapter = TestHttpAdapter(handler);
  return dio;
}

void main() {
  test('public login uses JSON and stores the returned session', () async {
    final tokens = MemoryTokenStore();
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: testDio((request, _) async {
        expect(request.method, 'POST');
        expect(request.path, 'api/v1/accounts/auth/login/');
        expect(request.data, {'email': 'a@b.test', 'password': 'secret'});
        expect(request.headers['Authorization'], isNull);
        return jsonResponse({'access': 'a1', 'refresh': 'r1'}, 200);
      }),
    );

    final session = await api.login(email: 'a@b.test', password: 'secret');

    expect(session.accessToken, 'a1');
    expect((await tokens.readSession())?.refreshToken, 'r1');
  });

  test('authenticated GET carries the current access token', () async {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: testDio((request, _) async {
        expect(request.method, 'GET');
        expect(request.headers['Authorization'], 'Bearer access');
        return jsonResponse({'ok': true}, 200);
      }),
    );

    expect((await api.get('api/v1/me/now/')).jsonObject()['ok'], isTrue);
  });

  test('authenticated POST preserves owner idempotency headers', () async {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: testDio((request, _) async {
        expect(request.method, 'POST');
        expect(request.headers['Idempotency-Key'], 'owner-key');
        expect(request.data, {'value': 1});
        return jsonResponse({'ok': true}, 201);
      }),
    );

    await api.post(
      'api/v1/example/',
      body: {'value': 1},
      headers: {'Idempotency-Key': 'owner-key'},
    );
  });

  test('concurrent 401 responses share a single rotating refresh', () async {
    var refreshCalls = 0;
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'old-access',
        refreshToken: 'old-refresh',
        profileId: 'profile-a',
      ),
    );

    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: testDio((request, _) async {
        if (request.path.endsWith('/auth/refresh/')) {
          refreshCalls += 1;
          await Future<void>.delayed(const Duration(milliseconds: 25));
          expect(request.data, {'refresh': 'old-refresh'});
          return jsonResponse({
            'access': 'new-access',
            'refresh': 'new-refresh',
          }, 200);
        }
        if (request.headers['Authorization'] == 'Bearer old-access') {
          return jsonResponse({'detail': 'Token expired'}, 401);
        }
        expect(request.headers['Authorization'], 'Bearer new-access');
        return jsonResponse({'ok': true}, 200);
      }),
    );

    final responses = await Future.wait([
      api.get('api/v1/me/now/'),
      api.get('api/v1/me/ongoing/'),
    ]);

    expect(responses.every((response) => response.statusCode == 200), isTrue);
    expect(refreshCalls, 1);
    expect((await tokens.readSession())?.refreshToken, 'new-refresh');
  });

  test('refresh rotation is persisted before the retried mutation', () async {
    final seen = <String>[];
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'old-access',
        refreshToken: 'old-refresh',
        profileId: 'profile-a',
      ),
    );
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: testDio((request, _) async {
        if (request.path.endsWith('/auth/refresh/')) {
          seen.add('refresh');
          return jsonResponse({
            'access': 'new-access',
            'refresh': 'new-refresh',
          }, 200);
        }
        if (request.headers['Authorization'] == 'Bearer old-access') {
          seen.add('old');
          return jsonResponse({'detail': 'expired'}, 401);
        }
        seen.add((await tokens.readSession())!.refreshToken);
        return jsonResponse({'ok': true}, 200);
      }),
    );

    await api.post('api/v1/example/', body: {'x': 1});

    expect(seen, ['old', 'refresh', 'new-refresh']);
  });

  test(
    'invalid refresh removes credentials without touching local data',
    () async {
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'expired',
          refreshToken: 'revoked',
          profileId: 'profile-a',
        ),
      );
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: tokens,
        dio: testDio((request, _) async {
          return jsonResponse({'detail': 'invalid'}, 401);
        }),
      );

      await expectLater(
        api.get('api/v1/me/now/'),
        throwsA(isA<MakoloApiError>()),
      );
      expect(await tokens.readSession(), isNull);
    },
  );

  test('server errors are normalized through MakoloApiError', () async {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: testDio((request, _) async {
        return jsonResponse({
          'error': {
            'code': 'validation_error',
            'message': 'Invalid.',
            'fields': {
              'field': ['Required.'],
            },
          },
        }, 422);
      }),
    );

    await expectLater(
      api.post('api/v1/example/'),
      throwsA(
        isA<MakoloApiError>()
            .having((error) => error.code, 'code', 'validation_error')
            .having((error) => error.statusCode, 'status', 422),
      ),
    );
  });

  test(
    'transport timeout remains distinguishable from server errors',
    () async {
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final dio = Dio();
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (options, handler) {
            handler.reject(
              DioException(
                requestOptions: options,
                type: DioExceptionType.receiveTimeout,
              ),
            );
          },
        ),
      );
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: tokens,
        dio: dio,
      );

      await expectLater(
        api.get('api/v1/me/now/'),
        throwsA(isA<TimeoutException>()),
      );
    },
  );

  test('cancellation is exposed without leaking Dio CancelToken', () async {
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          handler.reject(
            DioException(
              requestOptions: options,
              type: DioExceptionType.cancel,
            ),
          );
        },
      ),
    );
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: dio,
    );

    await expectLater(
      api.get('api/v1/me/now/', cancel: MakoloCancelHandle()),
      throwsA(isA<MakoloRequestCancelled>()),
    );
  });

  test(
    'multipart upload keeps transport generic and owner path explicit',
    () async {
      final directory = await Directory.systemTemp.createTemp('makolo-upload-');
      addTearDown(() => directory.delete(recursive: true));
      final file = File('${directory.path}/proof.txt');
      await file.writeAsString('payload');

      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: tokens,
        dio: testDio((request, _) async {
          expect(request.path, 'api/v1/owner-specific-endpoint/');
          expect(request.data, isA<FormData>());
          final form = request.data as FormData;
          expect(form.fields, contains(const MapEntry('kind', 'proof')));
          expect(form.files.single.key, 'file');
          return jsonResponse({'ok': true}, 201);
        }),
      );

      await api.upload(
        'api/v1/owner-specific-endpoint/',
        fields: {'kind': 'proof'},
        files: [
          MakoloUploadFile(
            fieldName: 'file',
            path: file.path,
            filename: 'proof.txt',
          ),
        ],
      );
    },
  );

  test('download writes through a partial file and commits the destination', () async {
    final directory = await Directory.systemTemp.createTemp('makolo-download-');
    addTearDown(() => directory.delete(recursive: true));
    final destination = File('${directory.path}/resource.bin');

    final tokens = MemoryTokenStore(
      session: const AuthSession(
        accessToken: 'access',
        refreshToken: 'refresh',
        profileId: 'profile-a',
      ),
    );
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: testDio((request, _) async {
        expect(request.path, 'api/v1/resources/r-1/file/');
        expect(request.headers['Authorization'], 'Bearer access');
        return ResponseBody.fromString(
          'download-body',
          200,
          headers: {
            'content-type': ['application/octet-stream'],
            'content-length': ['13'],
          },
        );
      }),
    );

    await api.download(
      'api/v1/resources/r-1/file/',
      destinationPath: destination.path,
    );

    expect(await destination.readAsString(), 'download-body');
    expect(File('${destination.path}.part').existsSync(), isFalse);
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
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: testDio((request, _) async {
        if (request.path.endsWith('/auth/refresh/')) {
          refreshCalls += 1;
          return jsonResponse({
            'access': 'fresh-access',
            'refresh': 'fresh-refresh',
          }, 200);
        }
        if (request.path.endsWith('/auth/logout/')) {
          if (request.headers['Authorization'] == 'Bearer expired-access') {
            return jsonResponse({'detail': 'expired'}, 401);
          }
          loggedOutRefresh =
              (request.data as Map<String, dynamic>)['refresh'] as String;
          return jsonResponse({'message': 'ok'}, 200);
        }
        throw StateError('unexpected request');
      }),
    );

    await api.logoutCurrentSession();

    expect(refreshCalls, 1);
    expect(loggedOutRefresh, 'fresh-refresh');
  });
}
