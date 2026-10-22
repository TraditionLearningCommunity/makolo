import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../design/makolo_theme.dart';
import '../../design/behavior_states.dart';
import '../../network/api_error.dart';
import '../../presentation/possibilities/public_possibility_card.dart';
import '../../presentation/search/load_more_on_scroll.dart';
import '../discovery/discovery_repository.dart';
import '../discovery/discovery_selector.dart';
import '../discovery/discovery_wire.dart';
import '../../platform/location/geo_search_gateway.dart';
import '../../presentation/fields/geo_autocomplete_field.dart';
import '../../presentation/fields/search_filter_bar.dart';
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
  static const _localTimeout = Duration(seconds: 3);
  static const _requestTimeout = Duration(seconds: 25);

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
  String? _continuationToken;
  late final ProgressiveSearchCoordinator _searchCoordinator;
  bool _loading = true;
  bool _updatingCriteria = false;
  String? _error;
  String? _localWarning;
  bool _continuationRejected = false;
  bool _serviceUnavailable = false;

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
      _criteriaChanged(immediate: true);
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
    continuation: _page > 1 ? _continuationToken : null,
  );

  // Diagnostic phases deliberately avoid query text, coordinates and tokens.
  void _trace(String phase, {int? revision, String? detail}) {
    if (!kDebugMode) return;
    debugPrint(
      '[DISCOVERY_PUBLIC] $phase'
      '${revision == null ? '' : ' revision=$revision'}'
      '${detail == null ? '' : ' $detail'}',
    );
  }

  void _reportFailure(
    String phase,
    Object error,
    StackTrace stack, {
    int? revision,
  }) {
    _trace(phase, revision: revision, detail: 'type=${error.runtimeType}');
    if (kDebugMode) {
      debugPrintStack(label: '[DISCOVERY_PUBLIC] $phase', stackTrace: stack);
    }
  }

  Future<void> _restoreAndLoad() async {
    _trace('RESTORE_BEGIN');
    Map<String, dynamic>? saved;
    try {
      saved = await widget.runtime.interactions
          ?.read(_interactionId)
          .timeout(_localTimeout);
      _trace('RESTORE_DONE');
    } on Object catch (error, stack) {
      _reportFailure('RESTORE_ERROR', error, stack);
      if (mounted) {
        setState(() {
          _localWarning =
              'La dernière recherche locale n’a pas pu être restaurée. '
              'Vous pouvez continuer à explorer.';
        });
      }
    }

    if (!mounted) return;
    if (widget.initialQuery.isEmpty && widget.initialVertical.isEmpty) {
      final query = saved?['query'];
      if (query is String) _search.text = query;
      final place = saved?['place'];
      if (place is String) _place.text = place;
      final vertical = saved?['vertical'];
      if (vertical is String) _vertical = vertical;
    }
    _trace('SEARCH_SCHEDULED');
    await _searchCoordinator.refresh();
  }

  // A failed local write must never block an otherwise valid server response.
  Future<void> _persistQuery(DiscoveryQuery query, int revision) async {
    try {
      await widget.runtime.interactions
          ?.save(_interactionId, {
            'query': query.text,
            'place': query.place,
            'vertical': query.vertical,
          })
          .timeout(_localTimeout);
    } on Object catch (error, stack) {
      _reportFailure('PERSIST_ERROR', error, stack, revision: revision);
      if (!mounted || !_searchCoordinator.isCurrent(revision)) return;
      setState(() {
        _localWarning =
            'Les filtres n’ont pas pu être enregistrés sur cet appareil.';
      });
    }
  }

  Future<void> _load() => _searchCoordinator.refresh();

  Future<void> _refresh() async {
    setState(() {
      _page = 1;
      _continuationToken = null;
      _updatingCriteria = true;
    });
    await _load();
  }

  Future<void> _loadRevision(int revision) async {
    final query = _query;
    _trace('SEARCH_START', revision: revision);
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
        _continuationRejected = false;
        _serviceUnavailable = false;
      });
    }
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Public API unavailable');
      _trace('API_REQUEST_START', revision: revision);
      final response = await api.publicGet(query.path).timeout(_requestTimeout);
      _trace(
        'API_RESPONSE',
        revision: revision,
        detail: 'status=${response.statusCode} chars=${response.body.length}',
      );
      final wire = DiscoveryWire.receive(
        response.jsonObject(),
        scope: 'public',
      );
      _trace('WIRE_OK', revision: revision);
      final collection = _selector.publicCollection(wire.snapshotPayload);
      _trace(
        'SELECT_OK',
        revision: revision,
        detail: 'items=${collection.items.length}',
      );
      if (!mounted || !_searchCoordinator.isCurrent(revision)) {
        _trace('REVISION_DISCARDED', revision: revision);
        return;
      }
      setState(() {
        _collection = query.page == 1
            ? collection
            : _collection.reconcile(collection);
        _loading = false;
        _updatingCriteria = false;
        _serviceUnavailable = false;
      });
      _trace('REVISION_ACCEPTED', revision: revision);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _searchCoordinator.isCurrent(revision)) {
          _trace('FRAME_BUILT', revision: revision);
        }
      });
      _trace('LOAD_FINISHED', revision: revision, detail: 'state=content');
      unawaited(_persistQuery(query, revision));
    } on MakoloApiError catch (error, stack) {
      _reportFailure('API_ERROR', error, stack, revision: revision);
      if (!mounted || !_searchCoordinator.isCurrent(revision)) return;
      final rejected = query.continuation != null && error.statusCode == 400;
      setState(() {
        _loading = false;
        _updatingCriteria = false;
        _continuationRejected = rejected;
        _serviceUnavailable = error.statusCode >= 500;
        _error = rejected
            ? 'Cette recherche doit être actualisée depuis le début.'
            : 'Impossible d’actualiser les possibilités.';
      });
      _trace('LOAD_FINISHED', revision: revision, detail: 'state=http_error');
    } on FormatException catch (error, stack) {
      _reportFailure('WIRE_OR_SELECT_ERROR', error, stack, revision: revision);
      if (!mounted || !_searchCoordinator.isCurrent(revision)) return;
      setState(() {
        _loading = false;
        _updatingCriteria = false;
        _error = 'Contrat Discovery incompatible : les informations reçues ne peuvent pas être affichées.';
      });
      _trace(
        'LOAD_FINISHED',
        revision: revision,
        detail: 'state=contract_error',
      );
    } on TimeoutException catch (error, stack) {
      _reportFailure('TIMEOUT', error, stack, revision: revision);
      if (!mounted || !_searchCoordinator.isCurrent(revision)) return;
      setState(() {
        _loading = false;
        _updatingCriteria = false;
        _error = 'L’actualisation prend trop de temps.';
      });
      _trace('LOAD_FINISHED', revision: revision, detail: 'state=timeout');
    } on Object catch (error, stack) {
      _reportFailure('LOAD_ERROR', error, stack, revision: revision);
      if (!mounted || !_searchCoordinator.isCurrent(revision)) return;
      setState(() {
        _loading = false;
        _updatingCriteria = false;
        _serviceUnavailable = error is MakoloTransportError;
        _error = error is MakoloTransportError
            ? 'Connexion à Makolo indisponible.'
            : 'Impossible d’actualiser les possibilités.';
      });
      _trace('LOAD_FINISHED', revision: revision, detail: 'state=error');
    }
  }

  Future<void> _retry() => _continuationRejected ? _refresh() : _load();

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

  void _apply() => _criteriaChanged(immediate: true);

  void _criteriaChanged({bool immediate = false}) {
    setState(() {
      _page = 1;
      _continuationToken = null;
      _updatingCriteria = true;
      _loading = true;
      _error = null;
    });
    _searchCoordinator.changed(immediate: immediate);
  }

  void _selectVertical(String vertical) {
    setState(() => _vertical = vertical);
    _criteriaChanged(immediate: true);
  }

  void _loadNextPage() {
    if (_loading ||
        _updatingCriteria ||
        _error != null ||
        !_collection.hasNext) {
      return;
    }
    setState(() {
      _continuationToken = _collection.continuationToken;
      _page++;
    });
    _searchCoordinator.changed(immediate: true);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return PublicExperienceShell(
      current: 1,
      child: LoadMoreOnScroll(
        hasMore: _collection.hasNext && _error == null && !_updatingCriteria,
        loading: _loading,
        loadMore: _loadNextPage,
        child: RefreshIndicator(
          onRefresh: _refresh,
          child: ListView(
            key: const Key('guest-public-landing'),
            padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.lg),
            children: [
              if (_serviceUnavailable)
                const OfflineBanner(message: 'Connexion à Makolo indisponible'),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.lg,
                ),
                child: Text(
                  'Découvrir',
                  style: theme.textTheme.labelMedium?.copyWith(
                    color: theme.colorScheme.primary,
                  ),
                ),
              ),
              const SizedBox(height: MakoloSpacing.sm),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.lg,
                ),
                child: Text(
                  'Explorez les possibilités.',
                  style: theme.textTheme.headlineSmall,
                ),
              ),
              const SizedBox(height: MakoloSpacing.sm),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: MakoloSpacing.lg),
                child: Text(
                  'Activités, événements, services et opportunités à découvrir.',
                ),
              ),
              const SizedBox(height: MakoloSpacing.md),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.lg,
                ),
                child: SearchFilterBar(
                  searchField: TextField(
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
                      suffixIcon: _search.text.isEmpty
                          ? null
                          : IconButton(
                              key: const Key('guest-discover-search-clear'),
                              tooltip: 'Effacer la recherche',
                              onPressed: () {
                                _search.clear();
                                _criteriaChanged(immediate: true);
                              },
                              icon: const Icon(Icons.close_rounded),
                            ),
                    ),
                  ),
                  filterButtonKey: const Key('guest-filter-toggle'),
                  filterPanelKey: const Key('guest-filters'),
                  hasActiveFilters:
                      _when.isNotEmpty ||
                      _date.isNotEmpty ||
                      _price.isNotEmpty ||
                      _place.text.trim().isNotEmpty,
                  filters: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
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
                          DropdownMenuItem(
                            value: '',
                            child: Text('Tous les prix'),
                          ),
                          DropdownMenuItem(
                            value: 'free',
                            child: Text('Gratuit'),
                          ),
                          DropdownMenuItem(
                            value: 'paid',
                            child: Text('Payant'),
                          ),
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
              ),
              const SizedBox(height: MakoloSpacing.md),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.lg,
                ),
                child: SizedBox(
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
              ),
              const SizedBox(height: MakoloSpacing.sm),
              if (_localWarning != null) ...[
                Text(
                  _localWarning!,
                  key: const Key('guest-discover-local-warning'),
                  style: TextStyle(color: theme.colorScheme.error),
                ),
                const SizedBox(height: MakoloSpacing.sm),
              ],
              if (_error != null) ...[
                if (!_serviceUnavailable)
                  Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: MakoloSpacing.lg,
                    ),
                    child: Text(
                      _error!,
                      key: const Key('guest-discover-load-error'),
                      style: TextStyle(color: theme.colorScheme.error),
                    ),
                  ),
                TextButton(
                  onPressed: _retry,
                  child: Text(
                    _continuationRejected
                        ? 'Actualiser la recherche'
                        : 'Réessayer',
                  ),
                ),
                const SizedBox(height: MakoloSpacing.sm),
              ],
              if (_loading && _collection.items.isEmpty)
                const Center(child: CircularProgressIndicator())
              else ...[
                if (_collection.items.isNotEmpty) ...[
                  Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: MakoloSpacing.lg,
                    ),
                    child: Text(
                      _updatingCriteria
                          ? (_error == null
                                ? 'Actualisation… résultats précédents'
                                : 'Résultats précédents')
                          : '${_collection.count} ${_collection.count == 1 ? 'résultat' : 'résultats'}',
                      style: theme.textTheme.titleMedium,
                    ),
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                  const Divider(height: 1),
                  const SizedBox(height: MakoloSpacing.sm),
                ],
                if (!_updatingCriteria &&
                    _selector
                        .spatialAnchorsFromCollection(_collection)
                        .isNotEmpty)
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
                if (_collection.items.isEmpty && !_loading && _error == null)
                  Padding(
                    padding: EdgeInsets.all(MakoloSpacing.lg),
                    child: Text(
                      _query.place.isEmpty
                          ? 'Aucune possibilité publique à afficher pour cette recherche.'
                          : 'Aucun résultat à ${_query.place} pour le moment.',
                    ),
                  ),
                for (final item in _collection.items)
                  PublicPossibilityCard(
                    item: item,
                    baseUri: widget.runtime.api?.baseUri,
                    shareApi: widget.runtime.api,
                    onSignIn: () {
                      widget.runtime.recovery.requireAuthentication(
                        '/discover/items/${Uri.encodeComponent(item.family)}/${Uri.encodeComponent(item.id)}',
                      );
                      context.push('/login');
                    },
                    onTap: () => context.push(
                      '/discover/items/${Uri.encodeComponent(item.family)}/${Uri.encodeComponent(item.id)}',
                    ),
                    onSave: () async {
                      widget.runtime.recovery.requireAuthentication(
                        '/discover/items/${Uri.encodeComponent(item.family)}/${Uri.encodeComponent(item.id)}',
                      );
                      if (context.mounted) context.push('/login');
                    },
                  ),
                if (_loading && _collection.items.isNotEmpty)
                  const Center(child: CircularProgressIndicator()),
                if (!_updatingCriteria &&
                    _error == null &&
                    !_collection.hasNext &&
                    _collection.items.isNotEmpty)
                  const Center(child: Text('Vous avez tout exploré.')),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
