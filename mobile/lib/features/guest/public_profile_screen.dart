import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';

/// Read-only native Profile view backed by the canonical public Passeport.
class PublicProfileScreen extends StatefulWidget {
  const PublicProfileScreen({
    super.key,
    required this.runtime,
    required this.profileId,
  });

  final AppRuntime runtime;
  final String profileId;

  @override
  State<PublicProfileScreen> createState() => _PublicProfileScreenState();
}

class _PublicProfileScreenState extends State<PublicProfileScreen> {
  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _profile;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Public API unavailable');
      final response = await api.publicGet(
        'api/v1/accounts/public-profiles/'
        '${Uri.encodeComponent(widget.profileId)}/',
      );
      final body = response.jsonObject();
      final data = body['data'];
      final profile = data is Map ? data['profile'] : null;
      if (profile is! Map ||
          profile['kind'] != 'profile' ||
          profile['id'] != widget.profileId ||
          profile['name'] is! String) {
        throw const FormatException('Invalid public Profile identity');
      }
      if (!mounted) return;
      setState(() {
        _profile = Map<String, dynamic>.from(profile);
        _loading = false;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Ce Profil public n’est pas disponible.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final profile = _profile;
    final name = profile?['name']?.toString() ?? '';
    final avatarRaw = profile?['avatar_url']?.toString();
    final resolved = avatarRaw == null || avatarRaw.isEmpty
        ? null
        : Uri.tryParse(avatarRaw);
    final apiBase = widget.runtime.api?.baseUri;
    final avatar = resolved == null
        ? null
        : resolved.hasScheme
        ? resolved
        : apiBase?.resolveUri(resolved);
    final avatarUrl =
        avatar != null &&
            (avatar.scheme == 'https' || avatar.scheme == 'http') &&
            avatar.host.isNotEmpty
        ? avatar.toString()
        : null;
    return Scaffold(
      appBar: AppBar(title: const Text('Profil public')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (_loading)
            const Center(child: CircularProgressIndicator())
          else if (_error != null) ...[
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            TextButton(onPressed: _load, child: const Text('Réessayer')),
          ] else if (profile != null) ...[
            Align(
              alignment: Alignment.centerLeft,
              child: CircleAvatar(
                radius: 36,
                foregroundImage: avatarUrl == null
                    ? null
                    : NetworkImage(avatarUrl),
                child: avatarUrl == null && name.isNotEmpty
                    ? Text(name[0].toUpperCase())
                    : null,
              ),
            ),
            const SizedBox(height: 16),
            Text(name, style: Theme.of(context).textTheme.headlineMedium),
            for (final key in ['headline', 'location', 'bio'])
              if ((profile[key]?.toString().trim() ?? '').isNotEmpty) ...[
                const SizedBox(height: 12),
                Text(
                  profile[key].toString(),
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
              ],
          ],
        ],
      ),
    );
  }
}
