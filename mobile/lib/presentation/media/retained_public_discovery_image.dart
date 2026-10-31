import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../possibilities/discovery_offline_store.dart';

/// Public, first-party Discovery recognition image, retained beyond OS cache.
///
/// No bearer token or private document is fetched here. Explicit downloads
/// and user-retained Reader files remain separate.
class RetainedPublicDiscoveryImage extends StatefulWidget {
  const RetainedPublicDiscoveryImage({
    super.key,
    required this.url,
    required this.trustedOrigin,
    required this.placeholder,
    this.storeOverride,
  });

  final Uri url;
  final Uri trustedOrigin;
  final Widget placeholder;
  final DiscoveryOfflineStore? storeOverride;

  @override
  State<RetainedPublicDiscoveryImage> createState() =>
      _RetainedPublicDiscoveryImageState();
}

class _RetainedPublicDiscoveryImageState
    extends State<RetainedPublicDiscoveryImage> {
  Uint8List? _bytes;
  int _generation = 0;

  DiscoveryOfflineStore get _store =>
      widget.storeOverride ??
      DiscoveryOfflineStore(trustedOrigin: widget.trustedOrigin);

  @override
  void initState() {
    super.initState();
    unawaited(_restore());
  }

  @override
  void didUpdateWidget(covariant RetainedPublicDiscoveryImage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.url != widget.url ||
        oldWidget.trustedOrigin != widget.trustedOrigin ||
        oldWidget.storeOverride != widget.storeOverride) {
      _bytes = null;
      unawaited(_restore());
    }
  }

  Future<void> _restore() async {
    final generation = ++_generation;
    final url = widget.url;
    final store = _store;
    if (!DiscoveryOfflineStore.isPublishedRecognitionUri(
      url,
      trustedOrigin: widget.trustedOrigin,
    )) {
      return;
    }
    try {
      final local = await store.recognizedImage(url);
      if (local != null && mounted && generation == _generation) {
        setState(() => _bytes = local);
      }
    } on Object {
      // A file-system failure cannot block a public online image.
    }

    final client = HttpClient()
      ..connectionTimeout = const Duration(seconds: 10);
    try {
      final request = await client
          .getUrl(url)
          .timeout(const Duration(seconds: 12));
      request.followRedirects = false;
      final response = await request.close().timeout(
        const Duration(seconds: 12),
      );
      if (response.statusCode == HttpStatus.forbidden ||
          response.statusCode == HttpStatus.notFound) {
        await store.removeRecognitionImage(url);
        if (mounted && generation == _generation) {
          setState(() => _bytes = null);
        }
        return;
      }
      if (response.statusCode != HttpStatus.ok ||
          response.headers.contentType?.primaryType != 'image') {
        return;
      }
      final builder = BytesBuilder(copy: false);
      var length = 0;
      await for (final part in response) {
        length += part.length;
        if (length > DiscoveryOfflineStore.maxRecognitionBytes) {
          throw const FormatException('Published image too large');
        }
        builder.add(part);
      }
      final bytes = builder.takeBytes();
      if (bytes.isEmpty || !mounted || generation != _generation) return;
      try {
        await store.retainRecognitionImage(url, bytes);
      } on Object {
        // Newly acquired public bytes may still be presented.
      }
      if (mounted && generation == _generation) {
        setState(() => _bytes = bytes);
      }
    } on Object {
      // An unavailable server must not erase a previously received image.
    } finally {
      client.close(force: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final bytes = _bytes;
    if (bytes == null) return widget.placeholder;
    return Image.memory(
      bytes,
      fit: BoxFit.cover,
      gaplessPlayback: true,
      errorBuilder: (_, _, _) => widget.placeholder,
    );
  }
}
