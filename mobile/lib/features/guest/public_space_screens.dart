import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../presentation/fields/geo_autocomplete_field.dart';
import '../../presentation/fields/search_filter_bar.dart';
import '../../presentation/search/progressive_search_coordinator.dart';
import '../../presentation/search/load_more_on_scroll.dart';

import '../../app/providers.dart';
import '../../design/makolo_theme.dart';
import '../../design/behavior_states.dart';
import '../discovery/discovery_selector.dart';
import '../../presentation/possibilities/public_possibility_card.dart';
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
  final _city = TextEditingController();
  String? _selectedCity;
  late final ProgressiveSearchCoordinator _searchCoordinator;
  String _category = '';
  List<({String value, String label})> _categories = const [];
  List<Map<String, dynamic>> _spaces = const [];
  int _page = 1;
  int _count = 0;
  bool _hasNext = false;
  bool _loading = true;
  bool _updatingCriteria = false;
  String? _error;
  bool _serviceUnavailable = false;

  @override
  void initState() {
    super.initState();
    _searchCoordinator = ProgressiveSearchCoordinator(onSearch: _loadRevision);
    unawaited(_load());
  }

  @override
  void dispose() {
    _searchCoordinator.dispose();
    _search.dispose();
    _city.dispose();
    super.dispose();
  }

  Future<void> _load() => _searchCoordinator.refresh();

  Future<void> _refresh() async {
    setState(() {
      _page = 1;
      _updatingCriteria = true;
    });
    await _load();
  }

  Future<void> _loadRevision(int revision) async {
    final page = _page;
    final publicStore = widget.runtime.publicStore;
    const cacheKind = 'public.spaces.directory';
    final query = Uri(
      queryParameters: {
        if (_search.text.trim().isNotEmpty) 'q': _search.text.trim(),
        if (_category.isNotEmpty) 'category': _category,
        if (_city.text.trim().isNotEmpty)
          'city': _selectedCity ?? _city.text.trim(),
        'page': page.toString(),
        'page_size': '20',
      },
    ).query;
    setState(() {
      _loading = true;
      _error = null;
      _serviceUnavailable = false;
    });
    try {
      final cached = await publicStore?.readProjection(
        cacheKind,
        resourceKey: query,
      );
      if (cached != null && mounted && _searchCoordinator.isCurrent(revision)) {
        final data = cached.payload;
        final raw = data['results'];
        if (raw is List) {
          setState(() {
            final incoming = raw.whereType<Map>().map(_object).toList();
            if (page == 1) {
              _spaces = incoming;
            } else {
              final seen = _spaces
                  .map((space) => _field(space, 'slug'))
                  .toSet();
              _spaces = [
                ..._spaces,
                ...incoming.where((space) => seen.add(_field(space, 'slug'))),
              ];
            }
            final categoryRows = data['categories'];
            if (categoryRows is List) {
              _categories = categoryRows
                  .whereType<Map>()
                  .map(
                    (row) => (
                      value: _field(_object(row), 'value'),
                      label: _field(_object(row), 'label'),
                    ),
                  )
                  .where((row) => row.value.isNotEmpty && row.label.isNotEmpty)
                  .toList();
            }
            _count = data['count'] is int
                ? data['count'] as int
                : _spaces.length;
            _hasNext = data['has_next'] == true;
            _loading = false;
          });
        }
      }
    } on Object {
      // The UI can still load remotely when the local copy is unavailable.
    }
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Public API unavailable');

      final response = await api.publicGet(
        'api/v1/organizations/public-spaces/?$query',
      );
      final data = _object(response.jsonObject()['data']);
      final raw = data['results'];
      if (raw is! List) throw const FormatException('Invalid directory');
      if (!mounted || !_searchCoordinator.isCurrent(revision)) return;
      setState(() {
        final incoming = raw
            .whereType<Map>()
            .map(_object)
            .toList(growable: false);
        if (page == 1) {
          _spaces = incoming;
        } else {
          final seen = _spaces.map((space) => _field(space, 'slug')).toSet();
          _spaces = [
            ..._spaces,
            ...incoming.where((space) => seen.add(_field(space, 'slug'))),
          ];
        }
        final categoryRows = data['categories'];
        if (categoryRows is List) {
          _categories = categoryRows
              .whereType<Map>()
              .map(
                (row) => (
                  value: _field(_object(row), 'value'),
                  label: _field(_object(row), 'label'),
                ),
              )
              .where((row) => row.value.isNotEmpty && row.label.isNotEmpty)
              .toList(growable: false);
        }
        _count = data['count'] is int ? data['count'] as int : _spaces.length;
        _hasNext = data['has_next'] == true;
        _loading = false;
        _updatingCriteria = false;
        _serviceUnavailable = false;
      });
      if (publicStore != null) {
        unawaited(
          publicStore
              .putProjection(
                kind: cacheKind,
                resourceKey: query,
                schemaVersion: 1,
                payload: data,
              )
              .catchError((Object _) {}),
        );
      }
    } on Object {
      if (!mounted || !_searchCoordinator.isCurrent(revision)) return;
      setState(() {
        _loading = false;
        _updatingCriteria = false;
        _serviceUnavailable = true;
        _error = 'Impossible d’actualiser les Espaces publics.';
      });
      if (_spaces.isNotEmpty) {
        _notifyRefreshIssue('Actualisation indisponible.');
      }
    }
  }

  void _notifyRefreshIssue(String message) {
    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 5),
        content: Text(message),
        action: SnackBarAction(label: 'Réessayer', onPressed: () => _load()),
      ),
    );
  }

  void _onCityEdited() {
    _selectedCity = null;
    _criteriaChanged();
  }

  void _criteriaChanged({bool immediate = false}) {
    setState(() {
      _page = 1;
      _updatingCriteria = true;
      _loading = true;
      _error = null;
    });
    _searchCoordinator.changed(immediate: immediate);
  }

  void _searchSpaces() => _criteriaChanged(immediate: true);

  void _loadNextPage() {
    if (_loading || _updatingCriteria || _error != null || !_hasNext) {
      return;
    }
    setState(() => _page++);
    unawaited(_load());
  }

  void _resetFilters() {
    _search.clear();
    _city.clear();
    _selectedCity = null;
    setState(() {
      _category = '';
      _page = 1;
    });
    _criteriaChanged(immediate: true);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return PublicExperienceShell(
      current: 2,
      child: LoadMoreOnScroll(
        hasMore: _hasNext && _error == null && !_updatingCriteria,
        loading: _loading,
        loadMore: _loadNextPage,
        child: RefreshIndicator(
          onRefresh: _refresh,
          child: ListView(
            key: const Key('guest-public-spaces'),
            padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.lg),
            children: [
              if (_serviceUnavailable)
                const OfflineBanner(
                  message: 'Actualisation des Espaces indisponible',
                ),
              Text(
                'ESPACES',
                style: theme.textTheme.labelMedium?.copyWith(
                  color: theme.colorScheme.primary,
                ),
              ),
              const SizedBox(height: MakoloSpacing.sm),
              Text(
                'Les Espaces sur Makolo',
                style: theme.textTheme.headlineSmall,
              ),
              const SizedBox(height: MakoloSpacing.sm),
              const Text(
                'Chaque Espace présente une organisation, une équipe ou une communauté, et ce qu’elle propose.',
              ),
              const SizedBox(height: MakoloSpacing.lg),
              SearchFilterBar(
                searchField: TextField(
                  key: const Key('guest-space-query'),
                  controller: _search,
                  textInputAction: TextInputAction.search,
                  onChanged: (_) => _criteriaChanged(),
                  onSubmitted: (_) => _searchSpaces(),
                  decoration: InputDecoration(
                    labelText: 'Rechercher un Espace',
                    hintText: 'Nom d’une organisation ou communauté',
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon: _search.text.isEmpty
                        ? null
                        : IconButton(
                            key: const Key('guest-space-search-clear'),
                            tooltip: 'Effacer la recherche',
                            onPressed: () {
                              _search.clear();
                              _criteriaChanged(immediate: true);
                            },
                            icon: const Icon(Icons.close_rounded),
                          ),
                    border: const OutlineInputBorder(),
                  ),
                ),
                filterButtonKey: const Key('guest-spaces-filter-toggle'),
                filterPanelKey: const Key('guest-spaces-filters'),
                hasActiveFilters:
                    _category.isNotEmpty || _city.text.trim().isNotEmpty,
                filters: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    KeyedSubtree(
                      key: ValueKey('space-category-$_category'),
                      child: DropdownButtonFormField<String>(
                        key: const Key('guest-spaces-category'),
                        initialValue: _category,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          labelText: 'Catégorie',
                          prefixIcon: Icon(Icons.category_outlined),
                          border: OutlineInputBorder(),
                        ),
                        items: [
                          const DropdownMenuItem(
                            value: '',
                            child: Text('Toutes les catégories'),
                          ),
                          for (final item in _categories)
                            DropdownMenuItem(
                              value: item.value,
                              child: Text(item.label),
                            ),
                        ],
                        onChanged: (value) {
                          setState(() => _category = value ?? '');
                          _criteriaChanged(immediate: true);
                        },
                      ),
                    ),
                    const SizedBox(height: MakoloSpacing.md),
                    GeoAutocompleteField(
                      fieldKey: const Key('guest-spaces-city'),
                      controller: _city,
                      gateway: widget.runtime.geoSearch,
                      labelText: 'Ville',
                      hintText: 'Ex. Lubumbashi',
                      onEdited: _onCityEdited,
                      onSelected: (suggestion) {
                        _selectedCity = suggestion.label
                            .split(',')
                            .first
                            .trim();
                        _criteriaChanged(immediate: true);
                      },
                      onSubmitted: _searchSpaces,
                    ),
                    const SizedBox(height: MakoloSpacing.md),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton(
                        key: const Key('guest-spaces-reset'),
                        onPressed: _resetFilters,
                        child: const Text('Effacer les filtres'),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: MakoloSpacing.md),
              if (_error != null && _page == 1 && _spaces.isEmpty) ...[
                if (!_serviceUnavailable)
                  Text(
                    _error!,
                    style: TextStyle(color: theme.colorScheme.error),
                  ),
                TextButton(onPressed: _load, child: const Text('Réessayer')),
              ],
              if (_loading && _spaces.isEmpty)
                const Center(child: CircularProgressIndicator())
              else ...[
                if (_spaces.isNotEmpty) ...[
                  Text(
                    _updatingCriteria
                        ? (_error == null
                              ? 'Actualisation… résultats précédents'
                              : 'Résultats précédents')
                        : '$_count ${_count == 1 ? 'Espace' : 'Espaces'}',
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: MakoloSpacing.md),
                ],
                if (_spaces.isEmpty && !_loading && _error == null)
                  Text(
                    _city.text.trim().isEmpty
                        ? 'Aucun Espace public ne correspond à cette recherche.'
                        : 'Aucun Espace correspondant à « ${_selectedCity ?? _city.text.trim()} ».',
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
                        subtitle:
                            _spaceArchetypes[_field(space, 'archetype')] == null
                            ? null
                            : Text(
                                _spaceArchetypes[_field(space, 'archetype')]!,
                              ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => context.push(
                          '/spaces/${Uri.encodeComponent(_field(space, 'slug'))}',
                        ),
                      ),
                    ),
                  ),
                if (_loading && _spaces.isNotEmpty)
                  const Center(child: CircularProgressIndicator()),
                if (_error != null && _page > 1 && _spaces.isNotEmpty) ...[
                  Padding(
                    padding: const EdgeInsets.symmetric(
                      vertical: MakoloSpacing.sm,
                    ),
                    child: Text(
                      _error!,
                      style: TextStyle(color: theme.colorScheme.error),
                    ),
                  ),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton(
                      key: const Key('guest-spaces-page-retry'),
                      onPressed: _load,
                      child: const Text('Réessayer'),
                    ),
                  ),
                ],
                if (_error != null && _page > 1 && _spaces.isEmpty) ...[
                  Text(
                    _error!,
                    style: TextStyle(color: theme.colorScheme.error),
                  ),
                  TextButton(onPressed: _load, child: const Text('Réessayer')),
                ],
                if (!_updatingCriteria &&
                    _error == null &&
                    !_hasNext &&
                    _spaces.isNotEmpty)
                  const Center(child: Text('Vous avez tout exploré.')),
              ],
            ],
          ),
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

const _spaceArchetypes = <String, String>{
  'generic': 'Espace générique',
  'creative': 'Artiste / création',
  'media': 'Média / journalisme',
  'education': 'Enseignement / formation',
  'commerce': 'Commerce / distribution',
  'service_provider': 'Prestataire de services',
  'transport_operator': 'Opérateur de transport',
  'community': 'Association / communauté',
};

class _PublicSpaceIdentity extends StatelessWidget {
  const _PublicSpaceIdentity({required this.space});

  final Map<String, dynamic> space;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final name = _field(space, 'name');
    final category = _spaceArchetypes[_field(space, 'archetype')];
    final location = [
      _field(space, 'city'),
      _field(space, 'country'),
    ].where((value) => value.isNotEmpty).join(' · ');
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        CircleAvatar(
          radius: 30,
          backgroundColor: theme.colorScheme.primaryContainer,
          foregroundColor: theme.colorScheme.onPrimaryContainer,
          child: Text(
            name.isEmpty ? '?' : name.substring(0, 1).toUpperCase(),
            style: theme.textTheme.headlineSmall,
          ),
        ),
        const SizedBox(width: MakoloSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: theme.textTheme.headlineSmall),
              if (category != null)
                Text(category, style: theme.textTheme.labelMedium),
              if (location.isNotEmpty) ...[
                const SizedBox(height: MakoloSpacing.xs),
                Text(location, style: theme.textTheme.bodySmall),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _PublicSpaceDetailScreenState extends State<PublicSpaceDetailScreen> {
  Map<String, dynamic> _space = const {};
  static const _selector = DiscoverySelector();
  List<DiscoveryItemPresentation> _possibilities = const [];
  int _count = 0;
  int _page = 1;
  bool _hasNext = false;
  bool _loading = true;
  String? _error;
  int _revision = 0;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant PublicSpaceDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.slug != widget.slug) {
      _revision++;
      _space = const {};
      _possibilities = const [];
      _count = 0;
      _page = 1;
      _hasNext = false;
      unawaited(_load());
    }
  }

  @override
  void dispose() {
    _revision++;
    super.dispose();
  }

  Future<void> _refresh() async {
    setState(() => _page = 1);
    await _load();
  }

  Future<void> _load() async {
    final revision = ++_revision;
    final page = _page;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Public API unavailable');
      final response = await api.publicGet(
        'api/v1/organizations/public-spaces/'
        '${Uri.encodeComponent(widget.slug)}/?page=$page&page_size=12',
      );
      final data = _object(response.jsonObject()['data']);
      final possibilities = _object(data['possibilities']);
      final raw = possibilities['results'];
      if (raw is! List || data['space'] is! Map) {
        throw const FormatException('Invalid public space');
      }
      if (!mounted || revision != _revision) return;
      setState(() {
        _space = _object(data['space']);
        final incoming = _selector.publicCollection({
          'results': raw,
          'count': possibilities['count'],
          'page': possibilities['page'],
          'page_size': possibilities['page_size'],
          'has_next': possibilities['has_next'],
        }).items;
        if (page == 1) {
          _possibilities = incoming;
        } else {
          final seen = _possibilities.map((item) => item.candidateKey).toSet();
          _possibilities = [
            ..._possibilities,
            ...incoming.where((item) => seen.add(item.candidateKey)),
          ];
        }
        _count = possibilities['count'] is int
            ? possibilities['count'] as int
            : _possibilities.length;
        _hasNext = possibilities['has_next'] == true;
        _loading = false;
      });
    } on Object {
      if (!mounted || revision != _revision) return;
      setState(() {
        _loading = false;
        _error = 'Impossible de charger cette fiche publique. Réessayez.';
      });
    }
  }

  void _loadNextPage() {
    if (_loading || _error != null || !_hasNext) return;
    setState(() => _page++);
    unawaited(_load());
  }

  void _openPossibility(DiscoveryItemPresentation possibility) {
    final family = possibility.family;
    final id = possibility.id;
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
      child: LoadMoreOnScroll(
        hasMore: _hasNext && _error == null,
        loading: _loading,
        loadMore: _loadNextPage,
        child: RefreshIndicator(
          onRefresh: _refresh,
          child: ListView(
            key: const Key('guest-public-space-detail'),
            padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.lg),
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.lg,
                ),
                child: Align(
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
              ),
              const SizedBox(height: MakoloSpacing.md),
              if (_loading && _space.isEmpty)
                const Center(child: CircularProgressIndicator())
              else if (_error != null && _space.isEmpty) ...[
                Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
                TextButton(onPressed: _load, child: const Text('Réessayer')),
              ] else ...[
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: MakoloSpacing.lg,
                  ),
                  child: _PublicSpaceIdentity(space: _space),
                ),
                if (_field(_space, 'description').isNotEmpty) ...[
                  const SizedBox(height: MakoloSpacing.lg),
                  Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: MakoloSpacing.lg,
                    ),
                    child: Text('À propos', style: theme.textTheme.titleMedium),
                  ),
                  const SizedBox(height: MakoloSpacing.xs),
                  Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: MakoloSpacing.lg,
                    ),
                    child: Text(_field(_space, 'description')),
                  ),
                ],
                const SizedBox(height: MakoloSpacing.xl),
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: MakoloSpacing.lg,
                  ),
                  child: Text(
                    'Ce que propose cet Espace',
                    style: theme.textTheme.titleLarge,
                  ),
                ),
                if (_count > 0)
                  Padding(
                    padding: const EdgeInsets.only(top: MakoloSpacing.xs),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: MakoloSpacing.lg,
                      ),
                      child: Text(
                        '$_count possibilités',
                        style: theme.textTheme.bodySmall,
                      ),
                    ),
                  ),
                const SizedBox(height: MakoloSpacing.xl),
                const Divider(height: 1),
                const SizedBox(height: MakoloSpacing.md),
                if (_possibilities.isEmpty && !_loading && _error == null)
                  const Text(
                    'Cet Espace ne propose pas encore de possibilité publique.',
                  ),
                for (final possibility in _possibilities)
                  PublicPossibilityCard(
                    item: possibility,
                    compact: true,
                    baseUri: widget.runtime.api?.baseUri,
                    shareApi: widget.runtime.api,
                    onSignIn: () {
                      widget.runtime.recovery.requireAuthentication(
                        '/discover/items/${Uri.encodeComponent(possibility.family)}/${Uri.encodeComponent(possibility.id)}',
                      );
                      context.push('/login');
                    },
                    onSave: () async {
                      widget.runtime.recovery.requireAuthentication(
                        '/discover/items/${Uri.encodeComponent(possibility.family)}/${Uri.encodeComponent(possibility.id)}',
                      );
                      if (context.mounted) context.push('/login');
                    },
                    onTap: () => _openPossibility(possibility),
                  ),
                if (_loading && _possibilities.isNotEmpty)
                  const Center(child: CircularProgressIndicator()),
                if (_error == null && !_hasNext && _possibilities.isNotEmpty)
                  const Center(child: Text('Vous avez tout exploré.')),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
