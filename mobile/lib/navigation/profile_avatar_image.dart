import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../network/makolo_api_client.dart';
import 'profile_portrait_store.dart';

/// A single profile-scoped portrait for Moi, header and actor sheet.
///
/// Reuses private persistent storage before trying the authenticated owner
/// media. A cache purge must not remove this portrait or its local identity.
class ProfileAvatarImage extends StatefulWidget {
  const ProfileAvatarImage({
    super.key,
    required this.profileId,
    required this.size,
    required this.fallback,
    this.url,
    this.api,
    this.revision,
  });

  final String? profileId;
  final double size;
  final String? url;
  final MakoloApiClient? api;
  final Object? revision;
  final Widget fallback;

  @override
  State<ProfileAvatarImage> createState() => _ProfileAvatarImageState();
}

class _ProfileAvatarImageState extends State<ProfileAvatarImage> {
  Uint8List? _bytes;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    unawaited(_restore());
  }

  @override
  void didUpdateWidget(covariant ProfileAvatarImage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.profileId != widget.profileId ||
        oldWidget.url != widget.url ||
        oldWidget.revision != widget.revision) {
      unawaited(_restore(forceRefresh: oldWidget.url != widget.url));
    }
  }

  Future<void> _restore({bool forceRefresh = false}) async {
    final generation = ++_generation;
    final id = widget.profileId;
    if (id == null || id.isEmpty) {
      if (mounted) setState(() => _bytes = null);
      return;
    }
    final store = ProfilePortraitStore(id);
    try {
      final local = await store.read();
      if (!mounted || generation != _generation) return;
      setState(() => _bytes = local);
      // Do not re-fetch cached media on every rebuild; the owner update
      // explicitly saves its newly confirmed portrait to this same file.
      if (local != null && !forceRefresh) return;
      final api = widget.api;
      if (api == null) return;
      final received = await store.refreshFromOwner(
        api: api,
        avatarUrl: widget.url,
      );
      if (mounted && generation == _generation && received != null) {
        setState(() => _bytes = received);
      }
    } on Object {
      // Preserve the private local file and avoid a second offline message.
    }
  }

  @override
  Widget build(BuildContext context) {
    final bytes = _bytes;
    if (bytes == null) return widget.fallback;
    return Image.memory(
      bytes,
      width: widget.size,
      height: widget.size,
      fit: BoxFit.cover,
      gaplessPlayback: true,
      errorBuilder: (_, _, _) => widget.fallback,
    );
  }
}
