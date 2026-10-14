import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app/providers.dart';
import '../../design/makolo_theme.dart';
import '../discovery/discovery_selector.dart';
import 'public_shell.dart';

/// Read-only, server-authorized guest depth. A personal operation always
/// crosses the authentication boundary; it cannot be simulated locally.
class PublicPossibilityDetailScreen extends StatefulWidget {
  const PublicPossibilityDetailScreen({
    super.key,
    required this.runtime,
    required this.family,
    required this.id,
  });

  final AppRuntime runtime;
  final String family;
  final String id;

  @override
  State<PublicPossibilityDetailScreen> createState() =>
      _PublicPossibilityDetailScreenState();
}

class _PublicPossibilityDetailScreenState
    extends State<PublicPossibilityDetailScreen> {
  static const _selector = DiscoverySelector();
  DiscoveryItemPresentation? _item;
  Map<String, dynamic> _detail = const {};
  bool _loading = true;
  String? _error;

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
        'api/v1/discovery/items/${Uri.encodeComponent(widget.family)}/'
        '${Uri.encodeComponent(widget.id)}/',
      );
      final body = response.jsonObject()['data'];
      if (body is! Map || body['item'] is! Map) {
        throw const FormatException('Invalid item detail');
      }
      final raw = Map<String, dynamic>.from(body['item'] as Map);
      final item = _selector.publicItem(raw);
      if (item == null) throw const FormatException('Unknown possibility');
      if (!mounted) return;
      setState(() {
        _item = item;
        _detail = raw;
        _loading = false;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Cette possibilité publique n’est pas disponible.';
      });
    }
  }

  void _requireAuthentication() {
    final path = '/discover/items/${widget.family}/${widget.id}';
    widget.runtime.recovery.requireAuthentication(path);
    context.push('/login');
  }

  Future<void> _openServerLink(String link) async {
    final api = widget.runtime.api;
    if (api == null) return;
    final uri = api.baseUri.resolve(link);
    if (uri.scheme != 'https' && uri.scheme != 'http') return;
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication) &&
        mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Impossible d’ouvrir cette page.')),
      );
    }
  }

  String? _text(Map<String, dynamic> source, String key) {
    final value = source[key];
    if (value is! String || value.trim().isEmpty) return null;
    return value.trim();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final item = _item;
    final detail = _detail['detail'];
    final description = detail is Map ? detail['description']?.toString() : null;
    final engagement = _detail['engagement'];
    final engagementMap = engagement is Map
        ? Map<String, dynamic>.from(engagement)
        : const <String, dynamic>{};
    final primary = engagementMap['presentation'];
    final primaryMap = primary is Map
        ? Map<String, dynamic>.from(primary)
        : const <String, dynamic>{};
    final primaryWeb = _text(primaryMap, 'web');
    final links = _detail['links'];
    final linksMap = links is Map
        ? Map<String, dynamic>.from(links)
        : const <String, dynamic>{};
    final publicWeb = _text(linksMap, 'web');

    return PublicExperienceShell(
      current: 1,
      child: ListView(
        key: const Key('guest-possibility-detail'),
        padding: const EdgeInsets.all(MakoloSpacing.lg),
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: () => context.pop(),
              icon: const Icon(Icons.arrow_back),
              label: const Text('Retour à Découvrir'),
            ),
          ),
          const SizedBox(height: MakoloSpacing.md),
          if (_loading && item == null)
            const Center(child: CircularProgressIndicator())
          else if (_error != null && item == null) ...[
            Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
            TextButton(onPressed: _load, child: const Text('Réessayer')),
          ] else if (item != null) ...[
            if (item.eyebrow != null)
              Text(
                item.eyebrow!,
                style: theme.textTheme.labelMedium?.copyWith(
                  color: theme.colorScheme.primary,
                ),
              ),
            const SizedBox(height: MakoloSpacing.sm),
            Text(item.title, style: theme.textTheme.headlineSmall),
            const SizedBox(height: MakoloSpacing.md),
            if (item.summary.isNotEmpty) Text(item.summary),
            if (description != null && description.isNotEmpty &&
                description != item.summary) ...[
              const SizedBox(height: MakoloSpacing.lg),
              Text(description),
            ],
            const SizedBox(height: MakoloSpacing.lg),
            if (item.owner != null)
              ListTile(
                leading: const Icon(Icons.business_outlined),
                title: const Text('Proposé par'),
                subtitle: Text(item.owner!),
              ),
            if (item.place != null)
              ListTile(
                leading: const Icon(Icons.place_outlined),
                title: const Text('Lieu'),
                subtitle: Text(item.place!),
              ),
            if (item.timing != null)
              ListTile(
                leading: const Icon(Icons.schedule_outlined),
                title: const Text('Quand'),
                subtitle: Text(item.timing!),
              ),
            if (item.price != null)
              ListTile(
                leading: const Icon(Icons.payments_outlined),
                title: const Text('Prix'),
                subtitle: Text(item.price!),
              ),
            if (item.availability != null)
              ListTile(
                leading: const Icon(Icons.event_available_outlined),
                title: const Text('Disponibilité'),
                subtitle: Text(item.availability!),
              ),
            const SizedBox(height: MakoloSpacing.lg),
            if (primaryMap['enabled'] == true && primaryWeb != null)
              FilledButton(
                onPressed: () => unawaited(_openServerLink(primaryWeb)),
                child: Text(_text(primaryMap, 'label') ?? 'Continuer'),
              )
            else if (publicWeb != null)
              OutlinedButton.icon(
                onPressed: () => unawaited(_openServerLink(publicWeb)),
                icon: const Icon(Icons.open_in_new),
                label: const Text('Voir la page publique'),
              ),
            const SizedBox(height: MakoloSpacing.sm),
            OutlinedButton.icon(
              onPressed: _requireAuthentication,
              icon: const Icon(Icons.bookmark_border),
              label: const Text('Se connecter pour enregistrer'),
            ),
          ],
        ],
      ),
    );
  }
}
