import 'dart:async';

import 'package:flutter/services.dart';

enum SharedPayloadKind { text, url, files }

class SharedFileReference {
  SharedFileReference({
    required this.uri,
    required this.name,
    required this.copyTo,
    this.mimeType,
  });

  final String uri;
  final String name;
  final String? mimeType;
  final Future<void> Function(String destinationPath) copyTo;
}

class SharedPayload {
  const SharedPayload({
    required this.kind,
    this.text,
    this.url,
    this.files = const [],
  });

  final SharedPayloadKind kind;
  final String? text;
  final Uri? url;
  final List<SharedFileReference> files;
}

abstract interface class SystemShareReceiver {
  Future<SharedPayload?> initial();
  Stream<SharedPayload> get incoming;
  Future<void> dispose();
}

class AndroidSystemShareReceiver implements SystemShareReceiver {
  AndroidSystemShareReceiver({MethodChannel? channel})
    : _channel = channel ?? const MethodChannel('makolo/native_share') {
    _channel.setMethodCallHandler(_handleMethod);
  }

  final MethodChannel _channel;
  final StreamController<SharedPayload> _incoming =
      StreamController<SharedPayload>.broadcast();

  @override
  Stream<SharedPayload> get incoming => _incoming.stream;

  @override
  Future<SharedPayload?> initial() async {
    final raw = await _channel.invokeMethod<Object?>('initialShare');
    return _decode(raw);
  }

  @override
  Future<void> dispose() async {
    _channel.setMethodCallHandler(null);
    await _incoming.close();
  }

  Future<void> _handleMethod(MethodCall call) async {
    if (call.method != 'shareReceived') return;
    final payload = _decode(call.arguments);
    if (payload != null && !_incoming.isClosed) {
      _incoming.add(payload);
    }
  }

  SharedPayload? _decode(Object? raw) {
    if (raw is! Map) return null;
    final kind = raw['kind']?.toString();
    final text = raw['text']?.toString();

    if (kind == 'text' && text != null && text.isNotEmpty) {
      return SharedPayload(kind: SharedPayloadKind.text, text: text);
    }

    if (kind == 'url' && text != null && text.isNotEmpty) {
      final uri = Uri.tryParse(text);
      if (uri == null || !uri.hasScheme) return null;
      return SharedPayload(kind: SharedPayloadKind.url, url: uri);
    }

    if (kind != 'files') return null;
    final rawFiles = raw['files'];
    if (rawFiles is! List) return null;

    final files = <SharedFileReference>[];
    for (final item in rawFiles) {
      if (item is! Map) continue;
      final uri = item['uri']?.toString();
      if (uri == null || uri.isEmpty) continue;
      final name = item['name']?.toString();
      final mimeType = item['mime_type']?.toString();
      files.add(
        SharedFileReference(
          uri: uri,
          name: name == null || name.isEmpty ? 'shared-file' : name,
          mimeType: mimeType,
          copyTo: (destinationPath) => _channel.invokeMethod<void>(
            'copySharedUri',
            {'uri': uri, 'destination_path': destinationPath},
          ),
        ),
      );
    }
    if (files.isEmpty) return null;
    return SharedPayload(kind: SharedPayloadKind.files, files: files);
  }
}
