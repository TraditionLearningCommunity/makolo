import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../auth/token_store.dart';
import 'api_error.dart';

class ApiResponse {
  const ApiResponse(this.statusCode, this.body, this.headers);

  final int statusCode;
  final String body;
  final Map<String, String> headers;

  Map<String, dynamic> jsonObject() => jsonDecode(body) as Map<String, dynamic>;
}

class MakoloApiClient {
  MakoloApiClient({
    required this.baseUri,
    required http.Client httpClient,
    required TokenStore tokenStore,
    this.timeout = const Duration(seconds: 15),
  }) : _http = httpClient,
       _tokens = tokenStore;

  final Uri baseUri;
  final http.Client _http;
  final TokenStore _tokens;
  final Duration timeout;

  Future<AuthSession> login({
    required String email,
    required String password,
  }) async {
    final response = await _sendPublic(
      'POST',
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
    return _sendPublic('POST', 'api/v1/accounts/auth/register/', body: body);
  }

  Future<ApiResponse> forgotPassword({required String email}) {
    return _sendPublic(
      'POST',
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

  Future<ApiResponse> get(String path) => _authorized('GET', path);

  Future<ApiResponse> publicGet(String path) => _sendPublic('GET', path);

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
      response = await _send(
        'POST',
        'api/v1/accounts/auth/logout/',
        bearer: current.accessToken,
        body: {'refresh': current.refreshToken},
      );
    }
    _ensureSuccess(response);
  }

  Future<ApiResponse> post(
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
  }) => _authorized('POST', path, body: body, extraHeaders: headers);

  Future<ApiResponse> _authorized(
    String method,
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? extraHeaders,
  }) async {
    var session = await _tokens.readSession();
    if (session == null) {
      throw const MakoloApiError(
        statusCode: 401,
        code: 'authentication_required',
        message: 'Reconnectez-vous pour continuer.',
      );
    }

    var response = await _send(
      method,
      path,
      bearer: session.accessToken,
      body: body,
      extraHeaders: extraHeaders,
    );
    if (response.statusCode != 401) return _ensureSuccess(response);

    session = await _refreshSingleFlight();
    response = await _send(
      method,
      path,
      bearer: session.accessToken,
      body: body,
      extraHeaders: extraHeaders,
    );
    return _ensureSuccess(response);
  }

  Future<ApiResponse> _sendPublic(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final response = await _send(method, path, body: body);
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
      final current = await _tokens.readSession();
      if (current == null) {
        throw const MakoloApiError(
          statusCode: 401,
          code: 'authentication_required',
          message: 'Reconnectez-vous pour continuer.',
        );
      }
      final response = await _send(
        'POST',
        'api/v1/accounts/auth/refresh/',
        body: {'refresh': current.refreshToken},
      );
      final checked = _ensureSuccess(response);
      final json = checked.jsonObject();
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
    Map<String, dynamic>? body,
    Map<String, String>? extraHeaders,
  }) async {
    final uri = baseUri.resolve(path);
    final headers = <String, String>{
      'Accept': 'application/json',
      if (body != null) 'Content-Type': 'application/json',
      if (bearer != null) 'Authorization': 'Bearer $bearer',
      ...?extraHeaders,
    };

    late http.Response response;
    if (method == 'GET') {
      response = await _http.get(uri, headers: headers).timeout(timeout);
    } else if (method == 'POST') {
      response = await _http
          .post(
            uri,
            headers: headers,
            body: body == null ? null : jsonEncode(body),
          )
          .timeout(timeout);
    } else {
      throw ArgumentError.value(method, 'method', 'Unsupported HTTP method');
    }
    return ApiResponse(response.statusCode, response.body, response.headers);
  }

  ApiResponse _ensureSuccess(ApiResponse response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return response;
    }
    throw MakoloApiError.fromResponse(response.statusCode, response.body);
  }
}
