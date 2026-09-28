import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

class MockRequest {
  const MockRequest({
    required this.url,
    required this.headers,
    required this.data,
  });

  final Uri url;
  final Map<String, dynamic> headers;
  final Object? data;

  String get body => data == null
      ? ''
      : data is String
      ? data! as String
      : jsonEncode(data);
}

class MockResponse {
  const MockResponse(
    this.body,
    this.statusCode, {
    this.headers = const {'content-type': 'application/json'},
  });

  final String body;
  final int statusCode;
  final Map<String, String> headers;
}

typedef MockHandler = Future<MockResponse> Function(MockRequest request);

class MockClient {
  MockClient(this.handler);

  final MockHandler handler;

  Dio get dio {
    final client = Dio();
    client.httpClientAdapter = _MockAdapter(handler);
    return client;
  }
}

class _MockAdapter implements HttpClientAdapter {
  _MockAdapter(this.handler);

  final MockHandler handler;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final response = await handler(
      MockRequest(
        url: options.uri,
        headers: options.headers,
        data: options.data,
      ),
    );
    return ResponseBody.fromString(
      response.body,
      response.statusCode,
      headers: response.headers.map(
        (key, value) => MapEntry(key, <String>[value]),
      ),
    );
  }

  @override
  void close({bool force = false}) {}
}
