import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../data/files/profile_recognition_image_store.dart';
import '../../network/api_error.dart';
import '../../network/makolo_api_client.dart';

/// Same native image in every reachability state, fed by durable Profile bytes.
///
/// Only published recognition media may use this widget. Private documents,
/// access credentials, proofs and unverified owner media use their own policy.
class RetainedRecognitionImage extends StatefulWidget {
  const RetainedRecognitionImage({
    super.key,
    required this.api,
    required this.profileId,
    required this.path,
    required this.alt,
    required this.placeholder,
    this.width,
    this.height,
    this.fit = BoxFit.cover,
    this.storeOverride,
  });

  final MakoloApiClient api;
  final String? profileId;
  final String path;
  final String alt;
  final Widget placeholder;
  final double? width;
  final double? height;
  final BoxFit fit;
  final ProfileRecognitionImageStore? storeOverride;

  @override
  State<RetainedRecognitionImage> createState() =>
      _RetainedRecognitionImageState();
}

class _RetainedRecognitionImageState extends State<RetainedRecognitionImage> {
  Uint8List? _bytes;
  int _generation = 0;

  ProfileRecognitionImageStore? get _store =>
      widget.storeOverride ??
      (widget.profileId == null
          ? null
          : ProfileRecognitionImageStore(profileId: widget.profileId!));

  @override
  void initState() {
    super.initState();
    unawaited(_restore());
  }

  @override
  void didUpdateWidget(covariant RetainedRecognitionImage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.path != widget.path ||
        oldWidget.profileId != widget.profileId ||
        oldWidget.api != widget.api ||
        oldWidget.storeOverride != widget.storeOverride) {
      _bytes = null;
      unawaited(_restore());
    }
  }

  Future<void> _restore() async {
    final generation = ++_generation;
    final path = widget.path;
    final store = _store;
    final uri = Uri.tryParse(path);
    if (uri == null ||
        uri.hasScheme ||
        uri.hasAuthority ||
        !path.startsWith('/')) {
      return;
    }

    try {
      final local = await store?.read(path);
      if (mounted && generation == _generation && local != null) {
        setState(() => _bytes = local);
      }
    } on Object {
      // File-system failure does not prevent trying the owner transport.
    }

    try {
      // Even when local bytes exist, check the owner in the background.
      // An explicit 403/404 revokes this copy; an outage does not erase it.
      final fresh = await widget.api.getPresentationImage(path);
      if (fresh.isEmpty ||
          fresh.length > ProfileRecognitionImageStore.maxImageBytes) {
        throw const FormatException('Invalid recognition image');
      }
      if (!mounted || generation != _generation) return;
      try {
        await store?.save(path, fresh);
      } on Object {
        // A received image remains visible if device persistence fails.
      }
      if (mounted && generation == _generation) {
        setState(() => _bytes = fresh);
      }
    } on MakoloApiError catch (error) {
      if (error.statusCode == 403 || error.statusCode == 404) {
        try {
          await store?.remove(path);
        } on Object {
          // The active presentation is still revoked.
        }
        if (mounted && generation == _generation) {
          setState(() => _bytes = null);
        }
      }
    } on Object {
      // A transient network failure preserves the last received image.
    }
  }

  @override
  Widget build(BuildContext context) {
    final bytes = _bytes;
    if (bytes == null) return widget.placeholder;
    return Image.memory(
      bytes,
      width: widget.width,
      height: widget.height,
      fit: widget.fit,
      semanticLabel: widget.alt,
      gaplessPlayback: true,
      errorBuilder: (_, _, _) => widget.placeholder,
    );
  }
}
