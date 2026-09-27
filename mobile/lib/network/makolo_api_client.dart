import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';

import '../auth/token_store.dart';
import 'api_error.dart';

typedef TransferProgress = void Function(int transferred, int total);

class ApiResponse {
  const ApiResponse(this.statusCode, this.body, this.headers);

  final int statusCode;
  final String body;
  final Map<String, String> headers;

  Map<String, dynamic> jsonObject() {
    final decoded = jsonDecode(body);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Expected a JSON object response');
    }
    return decoded;
  }
}

class MakoloCancelHandle {
  MakoloCancelHandle();

  final CancelToken _token = CancelToken();

  bool get isCancelled => _token.isCancelled;

  void cancel([String reason = 'cancelled']) {
    if (!_token.isCancelled) _token.cancel(reason);
  }
}

class MakoloUploadFile {
  const MakoloUploadFile({
    required this.fieldName,
    required this.path,
    this.filename,
  });

  final String fieldName;
  final String path;
  final String? filename;
}

class MakoloApiClient {
  MakoloApiClient({
    required this.baseUri,
    required TokenStore tokenStore,
    Dio? dio,
    this.timeout = const Duration(seconds: 15),
  }) : _tokens = tokenStore,
       _dio =
           dio ??
           Dio(
             BaseOptions(
               baseUrl: _normalizedBase(baseUri),
               connectTimeout: timeout,
               sendTimeout: timeout,
               receiveTimeout: timeout,
             ),
           ) {
    _dio.options
      ..baseUrl = _normalizedBase(baseUri)
      ..connectTimeout = timeout
      ..sendTimeout = timeout
      ..receiveTimeout = timeout;
  }

  final Uri baseUri;
  final Dio _dio;
  final TokenStore _tokens;
  final Duration timeout;

  static String _normalizedBase(Uri uri) {
    final value = uri.toString();
    return value.endsWith('/') ? value : '$value/';
  }

  void close({bool force = false}) => _dio.close(force: force);

  Future<AuthSession> login({
    required String email,
    required String password,
  }) async {
    final response = await publicPost(
      'api/v1/accounts/auth/login/',
      body: {'email': email, 'password': password},
    );
    final json = response.jsonObject();
    final session = AuthSession(
      accessToken: json['access'] as String,
      refreshToken: json['refresh'] as String,
    );
    await _tokens.writeSession(session);
    return session;
  }

  Future<ApiResponse> register({
    required String email,
    required String username,
    required String password,
    required String passwordConfirm,
    String? firstName,
    String? lastName,
    String? phone,
  }) {
    final body = <String, dynamic>{
      'email': email,
      'username': username,
      'password': password,
      'password_confirm': passwordConfirm,
    };
    if (firstName != null && firstName.isNotEmpty) {
      body['first_name'] = firstName;
    }
    if (lastName != null && lastName.isNotEmpty) {
      body['last_name'] = lastName;
    }
    if (phone != null && phone.isNotEmpty) {
      body['phone'] = phone;
    }
    return publicPost('api/v1/accounts/auth/register/', body: body);
  }

  Future<ApiResponse> forgotPassword({required String email}) {
    return publicPost(
      'api/v1/accounts/auth/password/forgot/',
      body: {'email': email},
    );
  }

  Future<ApiResponse> changePassword({
    required String currentPassword,
    required String newPassword,
    required String newPasswordConfirm,
  }) {
    return post(
      'api/v1/accounts/auth/password/change/',
      body: {
        'current_password': currentPassword,
        'new_password': newPassword,
        'new_password_confirm': newPasswordConfirm,
      },
    );
  }

  Future<ApiResponse> publicGet(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) {
    return _publicRequest('GET', path, extraHeaders: headers, cancel: cancel);
  }

  Future<ApiResponse> publicPost(
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) {
    return _publicRequest(
      'POST',
      path,
      bodyFactory: body == null ? null : () => body,
      extraHeaders: headers,
      cancel: cancel,
    );
  }

  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) {
    return _authorized('GET', path, extraHeaders: headers, cancel: cancel);
  }

  Future<ApiResponse> post(
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) {
    return _authorized(
      'POST',
      path,
      bodyFactory: body == null ? null : () => body,
      extraHeaders: headers,
      cancel: cancel,
    );
  }

  Future<ApiResponse> put(
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) {
    return _authorized(
      'PUT',
      path,
      bodyFactory: body == null ? null : () => body,
      extraHeaders: headers,
      cancel: cancel,
    );
  }

  Future<ApiResponse> patch(
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) {
    return _authorized(
      'PATCH',
      path,
      bodyFactory: body == null ? null : () => body,
      extraHeaders: headers,
      cancel: cancel,
    );
  }

  Future<ApiResponse> delete(
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) {
    return _authorized(
      'DELETE',
      path,
      bodyFactory: body == null ? null : () => body,
      extraHeaders: headers,
      cancel: cancel,
    );
  }

  Future<ApiResponse> upload(
    String path, {
    String method = 'POST',
    Map<String, Object?> fields = const {},
    List<MakoloUploadFile> files = const [],
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
    TransferProgress? onProgress,
  }) {
    return _authorized(
      method,
      path,
      bodyFactory: () async {
        final data = FormData();
        for (final entry in fields.entries) {
          final value = entry.value;
          if (value != null) {
            data.fields.add(MapEntry(entry.key, value.toString()));
          }
        }
        for (final file in files) {
          data.files.add(
            MapEntry(
              file.fieldName,
              await MultipartFile.fromFile(file.path, filename: file.filename),
            ),
          );
        }
        return data;
      },
      extraHeaders: headers,
      cancel: cancel,
      onSendProgress: onProgress,
    );
  }

  Future<ApiResponse> download(
    String path, {
    required String destinationPath,
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
    TransferProgress? onProgress,
  }) async {
    var session = await _requireSession();
    var response = await _downloadOnce(
      path,
      destinationPath: destinationPath,
      bearer: session.accessToken,
      extraHeaders: headers,
      cancel: cancel,
      onProgress: onProgress,
    );
    if (response.statusCode == 401) {
      await _deleteIfExists('$destinationPath.part');
      session = await _refreshSingleFlight();
      response = await _downloadOnce(
        path,
        destinationPath: destinationPath,
        bearer: session.accessToken,
        extraHeaders: headers,
        cancel: cancel,
        onProgress: onProgress,
      );
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      final errorBody = await _readBounded('$destinationPath.part');
      await _deleteIfExists('$destinationPath.part');
      throw MakoloApiError.fromResponse(response.statusCode, errorBody);
    }

    final partial = File('$destinationPath.part');
    final destination = File(destinationPath);
    await destination.parent.create(recursive: true);
    if (await destination.exists()) {
      await destination.delete();
    }
    await partial.rename(destinationPath);
    return response;
  }

  Future<void> logoutCurrentSession() async {
    final session = await _tokens.readSession();
    if (session == null) return;
    await logoutSession(session);
  }

  Future<void> logoutSession(AuthSession session) async {
    var current = session;
    var response = await _send(
      'POST',
      'api/v1/accounts/auth/logout/',
      bearer: current.accessToken,
      body: {'refresh': current.refreshToken},
    );
    if (response.statusCode == 401) {
      final refreshed = _ensureSuccess(
        await _send(
          'POST',
          'api/v1/accounts/auth/refresh/',
          body: {'refresh': current.refreshToken},
        ),
      );
      final json = refreshed.jsonObject();
      current = AuthSession(
        accessToken: json['access'] as String,
        refreshToken: (json['refresh'] as String?) ?? current.refreshToken,
        profileId: current.profileId,
      );
      await _tokens.writeSession(current);
      response = await _send(
        'POST',
        'api/v1/accounts/auth/logout/',
        bearer: current.accessToken,
        body: {'refresh': current.refreshToken},
      );
    }
    _ensureSuccess(response);
  }

  Future<AuthSession> _requireSession() async {
    final session = await _tokens.readSession();
    if (session == null) {
      throw const MakoloApiError(
        statusCode: 401,
        code: 'authentication_required',
        message: 'Reconnectez-vous pour continuer.',
      );
    }
    return session;
  }

  Future<ApiResponse> _authorized(
    String method,
    String path, {
    FutureOr<Object?> Function()? bodyFactory,
    Map<String, String>? extraHeaders,
    MakoloCancelHandle? cancel,
    TransferProgress? onSendProgress,
  }) async {
    var session = await _requireSession();
    var response = await _send(
      method,
      path,
      bearer: session.accessToken,
      body: await bodyFactory?.call(),
      extraHeaders: extraHeaders,
      cancel: cancel,
      onSendProgress: onSendProgress,
    );
    if (response.statusCode != 401) {
      return _ensureSuccess(response);
    }

    session = await _refreshSingleFlight();
    response = await _send(
      method,
      path,
      bearer: session.accessToken,
      body: await bodyFactory?.call(),
      extraHeaders: extraHeaders,
      cancel: cancel,
      onSendProgress: onSendProgress,
    );
    return _ensureSuccess(response);
  }

  Future<ApiResponse> _publicRequest(
    String method,
    String path, {
    FutureOr<Object?> Function()? bodyFactory,
    Map<String, String>? extraHeaders,
    MakoloCancelHandle? cancel,
  }) async {
    final response = await _send(
      method,
      path,
      body: await bodyFactory?.call(),
      extraHeaders: extraHeaders,
      cancel: cancel,
    );
    return _ensureSuccess(response);
  }

  Completer<AuthSession>? _refreshCompleter;

  Future<AuthSession> _refreshSingleFlight() {
    final existing = _refreshCompleter;
    if (existing != null) return existing.future;

    final completer = Completer<AuthSession>();
    _refreshCompleter = completer;
    _performRefresh()
        .then(completer.complete, onError: completer.completeError)
        .whenComplete(() {
          if (identical(_refreshCompleter, completer)) {
            _refreshCompleter = null;
          }
        });
    return completer.future;
  }

  Future<AuthSession> _performRefresh() async {
    try {
      final current = await _requireSession();
      final response = _ensureSuccess(
        await _send(
          'POST',
          'api/v1/accounts/auth/refresh/',
          body: {'refresh': current.refreshToken},
        ),
      );
      final json = response.jsonObject();
      final rotated = AuthSession(
        accessToken: json['access'] as String,
        refreshToken: (json['refresh'] as String?) ?? current.refreshToken,
        profileId: current.profileId,
      );
      await _tokens.writeSession(rotated);
      return rotated;
    } on Object catch (error) {
      if (error is MakoloApiError &&
          error.statusCode >= 400 &&
          error.statusCode < 500) {
        await _tokens.clearSession();
      }
      rethrow;
    }
  }

  Future<ApiResponse> _send(
    String method,
    String path, {
    String? bearer,
    Object? body,
    Map<String, String>? extraHeaders,
    MakoloCancelHandle? cancel,
    TransferProgress? onSendProgress,
  }) async {
    try {
      final response = await _dio.request<Object?>(
        path,
        data: body,
        options: Options(
          method: method,
          headers: {
            'Accept': 'application/json',
            if (bearer != null) 'Authorization': 'Bearer $bearer',
            ...?extraHeaders,
          },
          contentType: body is Map ? Headers.jsonContentType : null,
          responseType: ResponseType.json,
          validateStatus: (_) => true,
        ),
        cancelToken: cancel?._token,
        onSendProgress: onSendProgress,
      );
      return ApiResponse(
        response.statusCode ?? 0,
        _responseBody(response.data),
        _headers(response.headers),
      );
    } on DioException catch (error) {
      throw _transportError(error);
    }
  }

  Future<ApiResponse> _downloadOnce(
    String path, {
    required String destinationPath,
    required String bearer,
    Map<String, String>? extraHeaders,
    MakoloCancelHandle? cancel,
    TransferProgress? onProgress,
  }) async {
    try {
      final response = await _dio.download(
        path,
        '$destinationPath.part',
        options: Options(
          headers: {
            'Accept': '*/*',
            'Authorization': 'Bearer $bearer',
            ...?extraHeaders,
          },
          validateStatus: (_) => true,
        ),
        cancelToken: cancel?._token,
        onReceiveProgress: onProgress,
        deleteOnError: true,
      );
      return ApiResponse(
        response.statusCode ?? 0,
        '',
        _headers(response.headers),
      );
    } on DioException catch (error) {
      throw _transportError(error);
    }
  }

  Object _transportError(DioException error) {
    switch (error.type) {
      case DioExceptionType.cancel:
        return const MakoloRequestCancelled();
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.transformTimeout:
        return TimeoutException('Makolo network request timed out.');
      case DioExceptionType.connectionError:
      case DioExceptionType.badCertificate:
        return const MakoloTransportError(
          'network_unreachable',
          'Le réseau est indisponible.',
        );
      case DioExceptionType.badResponse:
      case DioExceptionType.unknown:
        return const MakoloTransportError(
          'transport_error',
          'La requête réseau a échoué.',
        );
    }
  }

  ApiResponse _ensureSuccess(ApiResponse response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return response;
    }
    throw MakoloApiError.fromResponse(response.statusCode, response.body);
  }

  static String _responseBody(Object? data) {
    if (data == null) return '';
    if (data is String) return data;
    return jsonEncode(data);
  }

  static Map<String, String> _headers(Headers headers) {
    return headers.map.map((key, values) => MapEntry(key, values.join(',')));
  }

  static Future<void> _deleteIfExists(String path) async {
    final file = File(path);
    if (await file.exists()) {
      await file.delete();
    }
  }

  static Future<String> _readBounded(String path) async {
    final file = File(path);
    if (!await file.exists()) return '';
    const maxBytes = 64 * 1024;
    final bytes = await file
        .openRead(0, maxBytes)
        .fold<List<int>>(<int>[], (buffer, chunk) => buffer..addAll(chunk));
    return utf8.decode(bytes, allowMalformed: true);
  }
}
