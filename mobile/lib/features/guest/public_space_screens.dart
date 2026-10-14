import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../platform/sharing/share_gateway.dart';

import '../../app/providers.dart';
import '../../design/makolo_theme.dart';
import 'public_shell.dart';

Map<String, dynamic> _object(Object? value) =>
    value is Map ? Map<String, dynamic>.from(value) : const {};

String _field(Map<String, dynamic> value, String name) =>
    value[name]?.toString().trim() ?? '';

class PublicSpacesScreen extends StatefulWidget {
  const PublicSpacesScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  State<PublicSpacesScreen> createState() => _PublicSpacesScreenState();
}

class _PublicSpacesScreenState extends State<PublicSpacesScreen> {
  final _search = TextEditingController();
  List<Map<String, dynamic>> _spaces = const [];
  int _page = 1;
  int _count = 0;
  bool _hasNext = false;
  bool _loading = true;
  String? _error;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  @override
  void dispose() {
    _generation++;
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final generation = ++_generation;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Public API unavailable');
      final query = Uri(
        queryParameters: {
          if (_search.text.trim().isNotEmpty) 'q': _search.text.trim(),
          'page': _page.toString(),
          'page_size': '20',
        },
      ).query;
      final response = await api.publicGet(
        'api/v1/organizations/public-spaces/?$query',
      );
      final data = _object(response.jsonObject()['data']);
      final raw = data['results'];
      if (raw is! List) throw const FormatException('Invalid directory');
      if (!mounted || generation != _generation) return;
      setState(() {
        _spaces = raw.whereType<Map>().map(_object).toList(growable: false);
        _count = data['count'] is int ? data['count'] as int : _spaces.length;
        _hasNext = data['has_next'] == true;
        _loading = false;
      });
    } on Object {
      if (!mounted || generation != _generation) return;
      setState(() {
        _loading = false;
        _error = 'Impossible d’actualiser les Espaces publics.';
      });
    }
  }

  void _searchSpaces() {
    setState(() => _page = 1);
    unawaited(_load());
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return PublicExperienceShell(
      current: 2,
      child: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          key: const Key('guest-public-spaces'),
          padding: const EdgeInsets.all(MakoloSpacing.lg),
          children: [
            Text(
              'ESPACES',
              style: theme.textTheme.labelMedium?.copyWith(
                color: theme.colorScheme.primary,
              ),
            ),
            const SizedBox(height: MakoloSpacing.sm),
            Text(
              'Découvrez les Espaces sur Makolo.',
              style: theme.textTheme.headlineSmall,
            ),
            const SizedBox(height: MakoloSpacing.sm),
            const Text(
              'Organisations, équipes et communautés qui rendent des possibilités accessibles.',
            ),
            const SizedBox(height: MakoloSpacing.lg),
            TextField(
              key: const Key('guest-space-query'),
              controller: _search,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _searchSpaces(),
              decoration: const InputDecoration(
                labelText: 'Nom de l’Espace',
                prefixIcon: Icon(Icons.search),
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: MakoloSpacing.sm),
            FilledButton(
              onPressed: _searchSpaces,
              child: const Text('Rechercher'),
            ),
            const SizedBox(height: MakoloSpacing.lg),
            if (_error != null) ...[
              Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
              TextButton(onPressed: _load, child: const Text('Réessayer')),
            ],
            if (_loading && _spaces.isEmpty)
              const Center(child: CircularProgressIndicator())
            else ...[
              Text('$_count Espaces', style: theme.textTheme.titleMedium),
              const SizedBox(height: MakoloSpacing.md),
              if (_spaces.isEmpty && !_loading)
                const Text(
                  'Aucun Espace public ne correspond à cette recherche.',
                ),
              for (final space in _spaces)
                Padding(
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                  child: Card(
                    child: ListTile(
                      leading: CircleAvatar(
                        child: Text(
                          _field(space, 'name').isEmpty
                              ? '?'
                              : _field(space, 'name')[0].toUpperCase(),
                        ),
                      ),
                      title: Text(_field(space, 'name')),
                      subtitle: Text(
                        [
                          _field(space, 'city'),
                          _field(space, 'country'),
                        ].where((part) => part.isNotEmpty).join(' · '),
                      ),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => context.push(
                        '/spaces/${Uri.encodeComponent(_field(space, 'slug'))}',
                      ),
                    ),
                  ),
                ),
              if (_page > 1 || _hasNext)
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    TextButton(
                      onPressed: _page > 1 && !_loading
                          ? () {
                              setState(() => _page--);
                              unawaited(_load());
                            }
                          : null,
                      child: const Text('Précédent'),
                    ),
                    Text('Page $_page'),
                    TextButton(
                      onPressed: _hasNext && !_loading
                          ? () {
                              setState(() => _page++);
                              unawaited(_load());
                            }
                          : null,
                      child: const Text('Suivant'),
                    ),
                  ],
                ),
            ],
          ],
        ),
      ),
    );
  }
}

class PublicSpaceDetailScreen extends StatefulWidget {
  const PublicSpaceDetailScreen({
    super.key,
    required this.runtime,
    required this.slug,
  });

  final AppRuntime runtime;
  final String slug;

  @override
  State<PublicSpaceDetailScreen> createState() =>
      _PublicSpaceDetailScreenState();
}

class _PublicSpaceDetailScreenState extends State<PublicSpaceDetailScreen> {
  Map<String, dynamic> _space = const {};
  List<Map<String, dynamic>> _possibilities = const [];
  int _count = 0;
  int _page = 1;
  bool _hasNext = false;
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
        'api/v1/organizations/public-spaces/'
        '${Uri.encodeComponent(widget.slug)}/?page=$_page&page_size=12',
      );
      final data = _object(response.jsonObject()['data']);
      final possibilities = _object(data['possibilities']);
      final raw = possibilities['results'];
      if (raw is! List || data['space'] is! Map) {
        throw const FormatException('Invalid public space');
      }
      if (!mounted) return;
      setState(() {
        _space = _object(data['space']);
        _possibilities = raw
            .whereType<Map>()
            .map(_object)
            .toList(growable: false);
        _count = possibilities['count'] is int
            ? possibilities['count'] as int
            : _possibilities.length;
        _hasNext = possibilities['has_next'] == true;
        _loading = false;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Ce profil public d’Espace n’est pas disponible.';
      });
    }
  }

  Future<void> _openWebsite() async {
    final website = _field(_space, 'website');
    final uri = Uri.tryParse(website);
    if (uri == null || !{'http', 'https'}.contains(uri.scheme)) return;
    await const SystemShareGateway().openExternal(uri);
  }

  void _openPossibility(Map<String, dynamic> raw) {
    final identity = _object(raw['identity']);
    final resource = _object(identity['resource']);
    final family = _field(identity, 'family');
    final id = _field(resource, 'id');
    if (family.isEmpty || id.isEmpty) return;
    context.push(
      '/discover/items/${Uri.encodeComponent(family)}/${Uri.encodeComponent(id)}',
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return PublicExperienceShell(
      current: 2,
      child: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          key: const Key('guest-public-space-detail'),
          padding: const EdgeInsets.all(MakoloSpacing.lg),
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: () {
                  if (context.canPop()) {
                    context.pop();
                  } else {
                    context.go('/spaces');
                  }
                },
                icon: const Icon(Icons.arrow_back),
                label: const Text('Tous les Espaces'),
              ),
            ),
            const SizedBox(height: MakoloSpacing.md),
            if (_loading && _space.isEmpty)
              const Center(child: CircularProgressIndicator())
            else if (_error != null && _space.isEmpty) ...[
              Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
              TextButton(onPressed: _load, child: const Text('Réessayer')),
            ] else ...[
              Text(
                _field(_space, 'name'),
                style: theme.textTheme.headlineSmall,
              ),
              const SizedBox(height: MakoloSpacing.sm),
              if (_field(_space, 'archetype').isNotEmpty)
                Text(
                  _field(_space, 'archetype'),
                  style: theme.textTheme.labelMedium,
                ),
              if (_field(_space, 'city').isNotEmpty ||
                  _field(_space, 'country').isNotEmpty)
                Text(
                  [
                    _field(_space, 'city'),
                    _field(_space, 'country'),
                  ].where((value) => value.isNotEmpty).join(' · '),
                ),
              const SizedBox(height: MakoloSpacing.lg),
              if (_field(_space, 'description').isNotEmpty)
                Text(_field(_space, 'description')),
              if (_field(_space, 'website').isNotEmpty)
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: () => unawaited(_openWebsite()),
                    icon: const Icon(Icons.open_in_new),
                    label: const Text('Site officiel'),
                  ),
                ),
              const SizedBox(height: MakoloSpacing.xl),
              Text('Possibilités publiques', style: theme.textTheme.titleLarge),
              const SizedBox(height: MakoloSpacing.xs),
              Text('$_count possibilités accessibles à découvrir'),
              const SizedBox(height: MakoloSpacing.md),
              if (_possibilities.isEmpty && !_loading)
                const Text(
                  'Aucune possibilité publique à afficher pour cet Espace.',
                ),
              for (final possibility in _possibilities)
                Padding(
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                  child: Card(
                    child: ListTile(
                      title: Text(
                        _field(_object(possibility['representation']), 'title'),
                      ),
                      subtitle: Text(
                        _field(
                          _object(possibility['representation']),
                          'summary',
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => _openPossibility(possibility),
                    ),
                  ),
                ),
              if (_page > 1 || _hasNext)
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    TextButton(
                      onPressed: _page > 1 && !_loading
                          ? () {
                              setState(() => _page--);
                              unawaited(_load());
                            }
                          : null,
                      child: const Text('Précédent'),
                    ),
                    Text('Page $_page'),
                    TextButton(
                      onPressed: _hasNext && !_loading
                          ? () {
                              setState(() => _page++);
                              unawaited(_load());
                            }
                          : null,
                      child: const Text('Suivant'),
                    ),
                  ],
                ),
            ],
          ],
        ),
      ),
    );
  }
}
