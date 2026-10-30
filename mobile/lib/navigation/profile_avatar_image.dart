import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

/// Profile-scoped, read-only portrait fallback. The Passport owner projection
/// is responsible for writing the authorized media file after a server read.
class ProfileAvatarImage extends StatelessWidget {
  const ProfileAvatarImage({
    super.key,
    required this.profileId,
    required this.size,
    required this.fallback,
    this.url,
  });

  final String? profileId;
  final double size;
  final String? url;
  final Widget fallback;

  Future<Uint8List?> _localBytes() async {
    final id = profileId;
    if (id == null || id.isEmpty) return null;
    final base = await getApplicationSupportDirectory();
    final safe = id.replaceAll(RegExp(r'[^A-Za-z0-9_-]'), '_');
    final file = File('${base.path}/profiles/$safe/passport-avatar.jpg');
    if (!await file.exists()) return null;
    return file.readAsBytes();
  }

  @override
  Widget build(BuildContext context) {
    Widget localFallback() => FutureBuilder<Uint8List?>(
      future: _localBytes(),
      builder: (context, snapshot) => snapshot.data == null
          ? fallback
          : Image.memory(
              snapshot.data!, width: size, height: size, fit: BoxFit.cover,
              errorBuilder: (_, _, _) => fallback,
            ),
    );
    final remote = url;
    if (remote == null || remote.isEmpty) return localFallback();
    return Image.network(
      remote, width: size, height: size, fit: BoxFit.cover,
      errorBuilder: (_, _, _) => localFallback(),
    );
  }
}
