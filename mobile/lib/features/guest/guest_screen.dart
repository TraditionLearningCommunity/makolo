import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../design/makolo_theme.dart';
import '../discovery/discovery_repository.dart';
import '../discovery/discovery_selector.dart';
import '../../platform/location/geo_search_gateway.dart';
import '../../presentation/fields/geo_autocomplete_field.dart';
import '../../presentation/search/progressive_search_coordinator.dart';
import 'public_shell.dart';

/// Public Discovery consumes the same server projection and parser as personal
/// Discovery. It never invents a Profile or makes a client-side search corpus.
class GuestDiscoverScreen extends StatefulWidget {
  const GuestDiscoverScreen({
    super.key,
    required this.runtime,
    this.initialQuery = '',
    this.initialVertical = '',
  });

  final AppRuntime runtime;
  final String initialQuery;
  final String initialVertical;

  @override
  State<GuestDiscoverScreen> createState() => _GuestDiscoverScreenState();
}

class _GuestDiscoverScreenState extends State<GuestDiscoverScreen> {
  static const _interactionId = 'public-discover';
  static const _selector = DiscoverySelector();

  final _search = TextEditingController();
  final _place = TextEditingController();

  DiscoveryCollectionPresentation _collection =
      DiscoveryCollectionPresentation.empty;
  String _vertical = '';
  String _when = '';
  String _date = '';
  GeoSuggestion? _selectedPlace;
  String _price = '';
  int _page = 1;
  late final ProgressiveSearchCoordinator _searchCoordinator;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _searchCoordinator = ProgressiveSearchCoordinator(onSearch: _loadRevision);
    _search.text = widget.initialQuery;
    _vertical = widget.initialVertical;
    unawaited(_restoreAndLoad());
  }

  @override
  void didUpdateWidget(covariant GuestDiscoverScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialQuery != oldWidget.initialQuery ||
        widget.initialVertical != oldWidget.initialVertical) {
      _search.text = widget.initialQuery;
      _vertical = widget.initialVertical;
      _page = 1;
      _searchCoordinator.changed(immediate: true);
    }
  }

  @override
  void dispose() {
    _searchCoordinator.dispose();
    _search.dispose();
    _place.dispose();
    super.dispose();
  }

  DiscoveryQuery get _query => DiscoveryQuery(
    text: _search.text.trim(),
    place: _selectedPlace == null
        ? _place.text.trim()
        : _selectedPlace!.label.split(',').first.trim(),
    when: _when == 'custom' ? '' : _when,
    date: _date,
    vertical: _vertical,
    price: _price,
    page: _page,
    pageSize: 12,
  );

  Future<void> _restoreAndLoad() async {
    final saved = await widget.runtime.interactions?.read(_interactionId);
    if (!mounted) return;
    if (widget.initialQuery.isEmpty && widget.initialVertical.isEmpty) {
      final query = saved?['query'];
      if (query is String) _search.text = query;
      final place = saved?['place'];
      if (place is String) _place.text = place;
      final vertical = saved?['vertical'];
      if (vertical is String) _vertical = vertical;
    }
    await _searchCoordinator.refresh();
  }

  Future<void> _load() => _searchCoordinator.refresh();

  Future<void> _loadRevision(int revision) async {
    final query = _query;
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      await widget.runtime.interactions?.save(_interactionId, {
        'query': query.text,
        'place': query.place,
        'vertical': query.vertical,
      });
      final api = widget.runtime.api;
      if (api == null) throw StateError('Public API unavailable');
      final response = await api.publicGet(query.path);
      final payload = response.jsonObject()['data'];
      if (payload is! Map) throw const FormatException('Invalid projection');
      final collection = _selector.publicCollection(
        Map<String, dynamic>.from(payload),
      );
      if (!mounted || !_searchCoordinator.isCurrent(revision)) return;
      setState(() {
        _collection = collection;
        _loading = false;
      });
    } on Object {
      if (!mounted || !_searchCoordinator.isCurrent(revision)) return;
      setState(() {
        _loading = false;
        _error = 'Impossible d’actualiser les possibilités publiques.';
      });
    }
  }

  Future<void> _chooseDate() async {
    final now = DateTime.now();
    final initial = DateTime.tryParse(_date) ?? now;
    final chosen = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(now.year - 1),
      lastDate: DateTime(now.year + 5),
      helpText: 'Choisir une date',
      confirmText: 'Valider',
    );
    if (!mounted) return;
    if (chosen == null) return;
    setState(() {
      _when = 'custom';
      _date =
          '${chosen.year.toString().padLeft(4, '0')}-'
          '${chosen.month.toString().padLeft(2, '0')}-'
          '${chosen.day.toString().padLeft(2, '0')}';
    });
    _criteriaChanged(immediate: true);
  }

  void _apply() {
    setState(() => _page = 1);
    _searchCoordinator.changed(immediate: true);
  }

  void _criteriaChanged({bool immediate = false}) {
    setState(() => _page = 1);
    _searchCoordinator.changed(immediate: immediate);
  }

  void _selectVertical(String vertical) {
    setState(() {
      _vertical = vertical;
      _page = 1;
    });
    _searchCoordinator.changed(immediate: true);
  }

  void _movePage(int page) {
    if (page < 1) return;
    setState(() => _page = page);
    _searchCoordinator.changed(immediate: true);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return PublicExperienceShell(
      current: 1,
      child: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          key: const Key('guest-public-landing'),
          padding: const EdgeInsets.all(MakoloSpacing.lg),
          children: [
            Text(
              'Découvrir',
              style: theme.textTheme.labelMedium?.copyWith(
                color: theme.colorScheme.primary,
              ),
            ),
            const SizedBox(height: MakoloSpacing.sm),
            Text(
              'Qu’avez-vous envie de vivre, faire ou obtenir ?',
              style: theme.textTheme.headlineSmall,
            ),
            const SizedBox(height: MakoloSpacing.sm),
            const Text(
              'Décrivez ce que vous cherchez, choisissez une piste ou explorez librement.',
            ),
            const SizedBox(height: MakoloSpacing.lg),
            TextField(
              controller: _search,
              key: const Key('guest-search-query'),
              textInputAction: TextInputAction.search,
              onChanged: (_) => _criteriaChanged(),
              onSubmitted: (_) => _apply(),
              decoration: InputDecoration(
                labelText: 'Rechercher',
                hintText: 'Ex. Voyager à Kolwezi demain',
                border: const OutlineInputBorder(),
                prefixIcon: const Icon(Icons.search),
                suffixIcon: IconButton(
                  key: const Key('guest-discover-search-submit'),
                  tooltip: 'Lancer la recherche',
                  onPressed: _apply,
                  icon: const Icon(Icons.arrow_forward_rounded),
                ),
              ),
            ),
            const SizedBox(height: MakoloSpacing.md),
            SizedBox(
              height: 48,
              child: ListView(
                key: const Key('guest-discover-categories'),
                scrollDirection: Axis.horizontal,
                children: [
                  for (final value in const [
                    ('', 'Tout', Icons.apps_rounded),
                    ('transport', 'Voyager', Icons.directions_bus_outlined),
                    ('event', 'Événements', Icons.event_outlined),
                    ('service', 'Services', Icons.handshake_outlined),
                    ('other', 'Autres', Icons.explore_outlined),
                  ]) ...[
                    ChoiceChip(
                      avatar: Icon(value.$3, size: 18),
                      label: Text(value.$2),
                      selected: _vertical == value.$1,
                      showCheckmark: false,
                      onSelected: (_) => _selectVertical(value.$1),
                    ),
                    const SizedBox(width: MakoloSpacing.sm),
                  ],
                ],
              ),
            ),
            const SizedBox(height: MakoloSpacing.compact),
            Card(
              margin: EdgeInsets.zero,
              elevation: 0,
              clipBehavior: Clip.antiAlias,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(MakoloRadii.card),
                side: BorderSide(color: theme.colorScheme.outlineVariant),
              ),
              child: ExpansionTile(
                key: const Key('guest-filters'),
                leading: const Icon(Icons.tune_rounded),
                title: const Text('Affiner la recherche'),
                subtitle:
                    _when.isNotEmpty ||
                        _date.isNotEmpty ||
                        _price.isNotEmpty ||
                        _place.text.trim().isNotEmpty
                    ? const Text('Critères supplémentaires')
                    : const Text('Lieu, date et prix'),
                childrenPadding: const EdgeInsets.fromLTRB(
                  MakoloSpacing.md,
                  0,
                  MakoloSpacing.md,
                  MakoloSpacing.md,
                ),
                children: [
                  GeoAutocompleteField(
                    fieldKey: const Key('guest-filter-place'),
                    controller: _place,
                    gateway: widget.runtime.geoSearch,
                    onSelected: (suggestion) {
                      setState(() => _selectedPlace = suggestion);
                      _criteriaChanged(immediate: true);
                    },
                    onEdited: () {
                      _selectedPlace = null;
                      _criteriaChanged();
                    },
                    onSubmitted: _apply,
                  ),
                  const SizedBox(height: MakoloSpacing.md),
                  DropdownButtonFormField<String>(
                    key: const Key('guest-filter-when'),
                    initialValue: _when,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Quand ?',
                      prefixIcon: Icon(Icons.calendar_today_outlined),
                      border: OutlineInputBorder(),
                    ),
                    items: const [
                      DropdownMenuItem(
                        value: '',
                        child: Text('Toutes les dates'),
                      ),
                      DropdownMenuItem(
                        value: 'today',
                        child: Text('Aujourd’hui'),
                      ),
                      DropdownMenuItem(
                        value: 'tomorrow',
                        child: Text('Demain'),
                      ),
                      DropdownMenuItem(
                        value: 'weekend',
                        child: Text('Ce week-end'),
                      ),
                      DropdownMenuItem(
                        value: 'week',
                        child: Text('Cette semaine'),
                      ),
                      DropdownMenuItem(
                        value: 'custom',
                        child: Text('Choisir une date…'),
                      ),
                    ],
                    onChanged: (value) {
                      if (value == 'custom') {
                        unawaited(_chooseDate());
                      } else {
                        setState(() {
                          _when = value ?? '';
                          _date = '';
                        });
                        _criteriaChanged(immediate: true);
                      }
                    },
                  ),
                  if (_date.isNotEmpty)
                    TextButton.icon(
                      key: const Key('guest-filter-selected-date'),
                      onPressed: _chooseDate,
                      icon: const Icon(Icons.edit_calendar_outlined),
                      label: Text('Date : $_date'),
                    ),
                  const SizedBox(height: MakoloSpacing.md),
                  DropdownButtonFormField<String>(
                    key: const Key('guest-filter-price'),
                    initialValue: _price,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Budget',
                      prefixIcon: Icon(Icons.payments_outlined),
                      border: OutlineInputBorder(),
                    ),
                    items: const [
                      DropdownMenuItem(value: '', child: Text('Tous les prix')),
                      DropdownMenuItem(value: 'free', child: Text('Gratuit')),
                      DropdownMenuItem(value: 'paid', child: Text('Payant')),
                    ],
                    onChanged: (value) {
                      setState(() => _price = value ?? '');
                      _criteriaChanged(immediate: true);
                    },
                  ),
                  const SizedBox(height: MakoloSpacing.md),
                ],
              ),
            ),
            const SizedBox(height: MakoloSpacing.lg),
            if (_error != null) ...[
              Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
              TextButton(onPressed: _load, child: const Text('Réessayer')),
              const SizedBox(height: MakoloSpacing.sm),
            ],
            if (_loading && _collection.items.isEmpty)
              const Center(child: CircularProgressIndicator())
            else ...[
              Text(
                '${_collection.count} résultats',
                style: theme.textTheme.titleMedium,
              ),
              const SizedBox(height: MakoloSpacing.md),
              if (_collection.items.any((item) => item.isMappable))
                Align(
                  alignment: Alignment.centerLeft,
                  child: OutlinedButton.icon(
                    onPressed: () => context.push(
                      '/discover/map?${_query.mapCanonicalQuery}',
                    ),
                    icon: const Icon(Icons.map_outlined),
                    label: const Text('Voir sur la carte'),
                  ),
                ),
              if (_collection.items.isEmpty && !_loading)
                Padding(
                  padding: EdgeInsets.all(MakoloSpacing.lg),
                  child: Text(
                    _query.place.isEmpty
                        ? 'Aucune possibilité publique à afficher pour cette recherche.'
                        : 'Aucun résultat à ${_query.place} pour le moment.',
                  ),
                ),
              for (final item in _collection.items)
                _PublicPossibilityCard(
                  item: item,
                  onTap: () => context.push(
                    '/discover/items/${Uri.encodeComponent(item.family)}/${Uri.encodeComponent(item.id)}',
                  ),
                ),
              if (_collection.page > 1 || _collection.hasNext)
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    TextButton(
                      onPressed: _collection.page > 1 && !_loading
                          ? () => _movePage(_collection.page - 1)
                          : null,
                      child: const Text('Précédent'),
                    ),
                    Text('Page ${_collection.page}'),
                    TextButton(
                      onPressed: _collection.hasNext && !_loading
                          ? () => _movePage(_collection.page + 1)
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

class _PublicPossibilityCard extends StatelessWidget {
  const _PublicPossibilityCard({required this.item, required this.onTap});

  final DiscoveryItemPresentation item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final media = item.imageUrl == null ? null : Uri.tryParse(item.imageUrl!);
    return Padding(
      padding: const EdgeInsets.only(bottom: MakoloSpacing.md),
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (media != null &&
                  (media.scheme == 'https' || media.scheme == 'http'))
                AspectRatio(
                  aspectRatio: 4 / 3,
                  child: Image.network(
                    item.imageUrl!,
                    fit: BoxFit.cover,
                    errorBuilder: (context, error, stackTrace) =>
                        const SizedBox.shrink(),
                  ),
                ),
              Padding(
                padding: const EdgeInsets.all(MakoloSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (item.eyebrow != null)
                      Text(
                        item.eyebrow!,
                        style: theme.textTheme.labelMedium?.copyWith(
                          color: theme.colorScheme.primary,
                        ),
                      ),
                    const SizedBox(height: MakoloSpacing.xs),
                    Text(item.title, style: theme.textTheme.titleMedium),
                    if (item.summary.isNotEmpty) ...[
                      const SizedBox(height: MakoloSpacing.sm),
                      Text(
                        item.summary,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                    if (item.routeLabel != null)
                      Text(
                        item.routeLabel!,
                        style: theme.textTheme.labelMedium,
                      ),
                    if (item.owner != null)
                      Text(item.owner!, style: theme.textTheme.bodySmall),
                    if (item.place != null)
                      Text(item.place!, style: theme.textTheme.bodySmall),
                    if (item.timing != null)
                      Text(item.timing!, style: theme.textTheme.bodySmall),
                    if (item.price != null)
                      Text(item.price!, style: theme.textTheme.bodySmall),
                    const SizedBox(height: MakoloSpacing.sm),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        Text(
                          'Voir le détail',
                          style: TextStyle(color: theme.colorScheme.primary),
                        ),
                        const SizedBox(width: 4),
                        const Icon(Icons.arrow_forward, size: 18),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
