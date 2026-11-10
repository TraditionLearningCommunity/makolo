import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../platform/preferences/secure_string_preferences.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/actor_context_controller.dart';
import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_status.dart';
import 'objective_organizer_data.dart';
import 'organizer_view_switcher.dart';
import 'organizer_linked_item.dart';
import 'objective_repository.dart';

class ObjectiveOrganizerScreen extends StatefulWidget {
  const ObjectiveOrganizerScreen({
    super.key,
    required this.repository,
    required this.onOpenItem,
    required this.onCreate,
    this.spaceSlug,
    this.actorContext,
  });

  final ObjectiveRepository repository;
  final void Function(String kind, String id) onOpenItem;
  final ValueChanged<String> onCreate;
  final String? spaceSlug;
  final ActorContextController? actorContext;

  @override
  State<ObjectiveOrganizerScreen> createState() =>
      _ObjectiveOrganizerScreenState();
}

class _ObjectiveOrganizerScreenState extends State<ObjectiveOrganizerScreen> {
  static const _storage = SecureStringPreferences();
  final _search = TextEditingController();
  bool _searchOpen = false;
  late Stream<List<StoredProjection>> _pages;
  late Stream<OwnerSourceState> _source;
  OrganizerMode _mode = OrganizerMode.cards;
  OrganizerSort _sort = OrganizerSort.name;
  OrganizerSort _dateField = OrganizerSort.deadline;
  String _kind = 'all';
  String _status = 'all';
  String _relation = 'all';
  String _period = 'all';
  bool _descending = false;
  bool _refreshing = false;
  bool _loadingMore = false;
  bool _failed = false;
  int? _requestedOffset;
  bool _canCreateSpace = false;
  int _scopeRevision = 0;
  final Set<String> _expanded = {};

  bool get _actorValid {
    final slug = widget.spaceSlug;
    if (slug == null) return true;
    final actor = widget.actorContext?.value;
    return actor is SpaceActorContext && actor.space.slug == slug;
  }

  String get _viewStoreKey =>
      'organizer.view.${widget.repository.profileId}'
      '${widget.spaceSlug == null ? '' : ':space:${widget.spaceSlug}'}';

  void _actorChanged() {
    if (!mounted) return;
    setState(() {
      _scopeRevision++;
      _refreshing = false;
      _loadingMore = false;
      _failed = false;
      _requestedOffset = null;
      _canCreateSpace = false;
    });
    if (_actorValid) {
      // Revalidate the current Space at the owner. A cached page is not
      // evidence that permissions survived an actor switch.
      unawaited(_refresh());
    }
  }

  void _readCreateCapability(StoredProjection? projection) {
    final actor = widget.actorContext?.value;
    final spaces = projection?.payload['manageable_spaces'];
    final allowed =
        widget.spaceSlug == null ||
        (actor is SpaceActorContext &&
            spaces is List &&
            spaces.any(
              (row) => row is Map && row['id']?.toString() == actor.space.id,
            ));
    if (mounted && _canCreateSpace != allowed) {
      setState(() => _canCreateSpace = allowed);
    }
  }

  @override
  void initState() {
    super.initState();
    widget.actorContext?.addListener(_actorChanged);
    _bind();
    _search.addListener(_changed);
    unawaited(_restore());
    unawaited(_acquire());
  }

  @override
  void didUpdateWidget(covariant ObjectiveOrganizerScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.actorContext != widget.actorContext) {
      oldWidget.actorContext?.removeListener(_actorChanged);
      widget.actorContext?.addListener(_actorChanged);
    }
    if (oldWidget.repository != widget.repository ||
        oldWidget.spaceSlug != widget.spaceSlug ||
        oldWidget.actorContext != widget.actorContext) {
      _scopeRevision++;
      _bind();
      _expanded.clear();
      _failed = false;
      _refreshing = false;
      _loadingMore = false;
      _requestedOffset = null;
      _canCreateSpace = false;
      _mode = OrganizerMode.cards;
      unawaited(_restore());
      if (_actorValid) unawaited(_acquire());
    }
  }

  void _bind() {
    _pages = widget.repository.watchOrganizer();
    _source = widget.repository.watchOrganizerSource(
      spaceSlug: widget.spaceSlug,
    );
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  void _startSearch() => setState(() => _searchOpen = true);

  void _stopSearch() {
    // Hiding the field does not remove the keyword from the local filters.
    // The clear icon or "Tout effacer" explicitly resets it.
    FocusScope.of(context).unfocus();
    setState(() => _searchOpen = false);
  }

  @override
  void dispose() {
    widget.actorContext?.removeListener(_actorChanged);
    _search.removeListener(_changed);
    _search.dispose();
    super.dispose();
  }

  Future<void> _restore() async {
    final key = _viewStoreKey;
    try {
      final value = await _storage.read(key: key);
      if (mounted && key == _viewStoreKey) {
        setState(
          () => _mode = OrganizerMode.values.firstWhere(
            (item) => item.name == value,
            orElse: () => OrganizerMode.cards,
          ),
        );
      }
    } on Object {
      // Local preference failure never blocks content.
    }
  }

  Future<void> _remember(OrganizerMode value) async {
    try {
      await _storage.write(key: _viewStoreKey, value: value.name);
    } on Object {
      // The selected view stays usable for the current session.
    }
  }

  void _setMode(OrganizerMode value) {
    setState(() => _mode = value);
    unawaited(_remember(value));
  }

  Future<void> _acquire() async {
    if (!_actorValid) return;
    final repository = widget.repository;
    final slug = widget.spaceSlug;
    final revision = _scopeRevision;
    try {
      final local = await repository.readOrganizerPage(0, spaceSlug: slug);
      final source = await repository.readOrganizerSource(spaceSlug: slug);
      if (!mounted ||
          repository != widget.repository ||
          revision != _scopeRevision ||
          !_actorValid)
        return;
      // A cached Space organizer is not a fresh permission grant.
      if (slug == null) _readCreateCapability(local);
      // Permissions may have changed since the last Space acquisition.
      if (slug != null ||
          local == null ||
          ObjectiveRepository.freshnessPolicy.evaluate(
                local,
                now: DateTime.now().toUtc(),
                invalidated: source.invalidated,
              ) !=
              FreshnessState.fresh) {
        unawaited(_refresh());
      }
    } on Object {
      if (mounted && revision == _scopeRevision && _actorValid) {
        setState(() => _failed = true);
      }
    }
  }

  Future<void> _refresh() async {
    if (_refreshing || !_actorValid) return;
    final repository = widget.repository;
    final slug = widget.spaceSlug;
    final revision = _scopeRevision;
    setState(() {
      _refreshing = true;
      _failed = false;
      _requestedOffset = null;
    });
    try {
      await repository.refreshOrganizerPage(0, spaceSlug: slug);
      // Only the scope's owner source can confirm this acquisition.
      final local = await repository.readOrganizerPage(0, spaceSlug: slug);
      final owner = await repository.readOrganizerSource(spaceSlug: slug);
      if (mounted &&
          repository == widget.repository &&
          revision == _scopeRevision &&
          _actorValid) {
        final confirmed =
            !owner.invalidated &&
            owner.lastErrorCode == null &&
            owner.lastSuccessAt != null &&
            local != null;
        _readCreateCapability(confirmed ? local : null);
        setState(() => _failed = !confirmed);
      }
    } on Object {
      if (mounted &&
          repository == widget.repository &&
          revision == _scopeRevision &&
          _actorValid) {
        setState(() => _failed = true);
      }
    } finally {
      if (mounted &&
          repository == widget.repository &&
          revision == _scopeRevision) {
        setState(() => _refreshing = false);
      }
    }
  }

  Future<void> _more(OrganizerPage page) async {
    if (_loadingMore ||
        _refreshing ||
        _failed ||
        !_actorValid ||
        !page.hasMore ||
        _requestedOffset == page.nextOffset) {
      return;
    }
    final repository = widget.repository;
    final slug = widget.spaceSlug;
    final revision = _scopeRevision;
    _requestedOffset = page.nextOffset;
    setState(() => _loadingMore = true);
    try {
      await repository.refreshOrganizerPage(page.nextOffset, spaceSlug: slug);
      final received = await repository.readOrganizerPage(
        page.nextOffset,
        spaceSlug: slug,
      );
      final owner = await repository.readOrganizerSourceForOffset(
        page.nextOffset,
        spaceSlug: slug,
      );
      if (received == null ||
          owner.invalidated ||
          owner.lastErrorCode != null ||
          owner.lastSuccessAt == null) {
        if (mounted &&
            repository == widget.repository &&
            revision == _scopeRevision) {
          _requestedOffset = null;
          setState(() => _failed = true);
        }
      }
    } on Object {
      if (mounted &&
          repository == widget.repository &&
          revision == _scopeRevision) {
        _requestedOffset = null;
        setState(() => _failed = true);
      }
    } finally {
      if (mounted &&
          repository == widget.repository &&
          revision == _scopeRevision) {
        setState(() => _loadingMore = false);
      }
    }
  }

  static String _fold(String value) {
    const accents = 'àâäáãåçéèêëíìîïñóòôöõúùûüýÿ';
    const plain = 'aaaaaaceeeeiiiinooooouuuuyy';
    return value.trim().toLowerCase().split('').map((char) {
      final pos = accents.indexOf(char);
      return pos < 0 ? char : plain[pos];
    }).join();
  }

  bool _matches(OrganizerEntry entry) {
    if (_kind != 'all' && entry.kind != _kind) return false;
    if (_relation == 'independent' && !entry.isIndependent) return false;
    if (_relation == 'mine' && entry.relation != 'mine') return false;
    if (_relation == 'space' && entry.relation != 'space') return false;
    final terminalJourney = {'fulfilled', 'rejected', 'cancelled', 'expired'};
    if (_status == 'active' && entry.kind == 'journey') {
      if (terminalJourney.contains(entry.state)) return false;
    } else if (_status == 'completed' && entry.kind == 'journey') {
      if (entry.state != 'fulfilled') return false;
    } else if (_status != 'all' && entry.state != _status) {
      return false;
    }
    final q = _fold(_search.text);
    if (q.isNotEmpty &&
        !_fold('${entry.title} ${entry.description} ${entry.space ?? ''}')
            .contains(q)) {
      return false;
    }
    if (_period != 'all') {
      final date = entry.dateFor(_dateField);
      if (date == null) return false;
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);
      final day = DateTime(date.year, date.month, date.day);
      final days = switch (_period) {
        'week' => 7,
        'month' => 30,
        _ => 90,
      };
      if (day.isBefore(today) || day.isAfter(today.add(Duration(days: days)))) {
        return false;
      }
    }
    return true;
  }

  List<OrganizerEntry> _ordered(Iterable<OrganizerEntry> entries) {
    final result = entries.toList();
    result.sort((a, b) {
      int delta;
      if (_sort == OrganizerSort.name) {
        delta = _fold(a.title).compareTo(_fold(b.title));
      } else {
        final first = a.dateFor(_sort);
        final second = b.dateFor(_sort);
        if (first == null && second == null) {
          delta = 0;
        } else if (first == null) {
          return 1;
        } else if (second == null) {
          return -1;
        } else {
          delta = first.compareTo(second);
        }
      }
      if (_descending) delta = -delta;
      return delta != 0 ? delta : a.key.compareTo(b.key);
    });
    return result;
  }

  Widget _dropdown(
    String label,
    String selected,
    Map<String, String> choices,
    ValueChanged<String> onSelected, {
    required IconData icon,
  }) {
    return PopupMenuButton<String>(
      tooltip: label,
      initialValue: selected,
      onSelected: onSelected,
      itemBuilder: (_) => [
        for (final option in choices.entries)
          PopupMenuItem(value: option.key, child: Text(option.value)),
      ],
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 10),
        decoration: BoxDecoration(
          border: Border.all(
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 17, color: Theme.of(context).colorScheme.primary),
            const SizedBox(width: 7),
            Text(
              choices[selected] ?? label,
              style: Theme.of(context).textTheme.labelMedium,
            ),
            const SizedBox(width: 5),
            const Icon(Icons.keyboard_arrow_down_rounded, size: 17),
          ],
        ),
      ),
    );
  }

  bool get _hasExtraFilters =>
      _period != 'all' ||
      _dateField != OrganizerSort.deadline ||
      _sort != OrganizerSort.name ||
      _descending;

  bool get _hasSelectionFilters =>
      _search.text.isNotEmpty ||
      _kind != 'all' ||
      _status != 'all' ||
      _relation != 'all' ||
      _period != 'all';

  bool get _hasAnyFilters => _hasSelectionFilters || _hasExtraFilters;

  void _clearFilters() {
    _search.clear();
    setState(() {
      _kind = 'all';
      _status = 'all';
      _relation = 'all';
      _period = 'all';
      _sort = OrganizerSort.name;
      _dateField = OrganizerSort.deadline;
      _descending = false;
    });
  }

  Future<void> _showContentFilters() async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => StatefulBuilder(
        builder: (sheet, refreshSheet) {
          void change(VoidCallback command) {
            setState(command);
            refreshSheet(() {});
          }

          return SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 10, 20, 24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Filtres', style: Theme.of(sheet).textTheme.titleLarge),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      _dropdown(
                        'Type',
                        _kind,
                        const {
                          'all': 'Tous les types',
                          'project': 'Projets',
                          'dossier': 'Dossiers',
                          'journey': 'Démarches',
                        },
                        (v) => change(() => _kind = v),
                        icon: Icons.category_outlined,
                      ),
                      _dropdown(
                        'État',
                        _status,
                        const {
                          'all': 'Tous les états',
                          'draft': 'En préparation',
                          'active': 'En cours',
                          'completed': 'Terminé',
                          'cancelled': 'Annulé',
                          'archived': 'Archivé',
                        },
                        (v) => change(() => _status = v),
                        icon: Icons.tune_rounded,
                      ),
                      _dropdown(
                        'Contexte',
                        _relation,
                        const {
                          'all': 'Tous les contextes',
                          'mine': 'Personnel',
                          'space': 'Espace',
                          'independent': 'Indépendants',
                        },
                        (v) => change(() => _relation = v),
                        icon: Icons.account_tree_outlined,
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  Row(
                    children: [
                      if (_hasAnyFilters)
                        TextButton.icon(
                          onPressed: () {
                            _clearFilters();
                            refreshSheet(() {});
                          },
                          icon: const Icon(Icons.filter_alt_off_outlined),
                          label: const Text('Tout effacer'),
                        ),
                      const Spacer(),
                      MakoloActionButton(
                        label: 'Terminé',
                        appearance: MakoloActionAppearance.primary,
                        onPressed: () => Navigator.pop(sheet),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Future<void> _advancedFilters() async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => StatefulBuilder(
        builder: (sheet, refreshSheet) {
          void change(VoidCallback command) {
            setState(command);
            refreshSheet(() {});
          }

          return SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 10, 20, 24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Dates et tri',
                    style: Theme.of(sheet).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      _dropdown(
                        'Date concernée',
                        _dateField.name,
                        const {
                          'created': 'Création',
                          'updated': 'Modification',
                          'deadline': 'Échéance',
                          'start': 'Début',
                          'completed': 'Réalisation',
                        },
                        (v) => change(
                          () => _dateField = OrganizerSort.values.firstWhere(
                            (x) => x.name == v,
                          ),
                        ),
                        icon: Icons.event_outlined,
                      ),
                      _dropdown(
                        'Période',
                        _period,
                        const {
                          'all': 'Toutes les dates',
                          'week': '7 prochains jours',
                          'month': '30 prochains jours',
                          'quarter': '90 prochains jours',
                        },
                        (v) => change(() => _period = v),
                        icon: Icons.date_range_outlined,
                      ),
                      _dropdown(
                        'Trier',
                        _sort.name,
                        const {
                          'name': 'Nom A–Z',
                          'created': 'Création',
                          'updated': 'Modification',
                          'deadline': 'Échéance',
                          'start': 'Début',
                          'completed': 'Réalisation',
                        },
                        (v) => change(
                          () => _sort = OrganizerSort.values.firstWhere(
                            (x) => x.name == v,
                          ),
                        ),
                        icon: Icons.sort_by_alpha_rounded,
                      ),
                      ActionChip(
                        avatar: Icon(
                          _descending
                              ? Icons.arrow_downward_rounded
                              : Icons.arrow_upward_rounded,
                        ),
                        label: Text(_descending ? 'Décroissant' : 'Croissant'),
                        onPressed: () =>
                            change(() => _descending = !_descending),
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      if (_hasExtraFilters)
                        TextButton.icon(
                          onPressed: () => change(() {
                            _dateField = OrganizerSort.deadline;
                            _period = 'all';
                            _sort = OrganizerSort.name;
                            _descending = false;
                          }),
                          icon: const Icon(Icons.restart_alt_rounded),
                          label: const Text('Réinitialiser'),
                        ),
                      const Spacer(),
                      MakoloActionButton(
                        label: 'Appliquer',
                        appearance: MakoloActionAppearance.primary,
                        onPressed: () => Navigator.pop(sheet),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _createQuickAction(String kind, String label) {
    final primary = kind == 'dossier';
    final scheme = Theme.of(context).colorScheme;
    final child = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.add_rounded, size: 17),
        const SizedBox(width: 3),
        Text(
          label,
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
        ),
      ],
    );
    final style = ButtonStyle(
      minimumSize: const WidgetStatePropertyAll(Size(0, 44)),
      padding: const WidgetStatePropertyAll(
        EdgeInsets.symmetric(horizontal: 9),
      ),
      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
      visualDensity: VisualDensity.compact,
      shape: WidgetStatePropertyAll(
        RoundedRectangleBorder(borderRadius: BorderRadius.circular(11)),
      ),
    );
    return Tooltip(
      message: 'Créer un ${label.toLowerCase()}',
      child: primary
          ? FilledButton(
              style: style,
              onPressed: () => widget.onCreate(kind),
              child: child,
            )
          : OutlinedButton(
              style: style.copyWith(
                foregroundColor: WidgetStatePropertyAll(scheme.primary),
              ),
              onPressed: () => widget.onCreate(kind),
              child: child,
            ),
    );
  }

  // The action bar belongs to the app chrome, never the scrolling collection.
  // On very narrow screens it scrolls as a single accessible toolbar rather
  // than hiding either creation command or any view mode.
  Widget _persistentActions() {
    final scheme = Theme.of(context).colorScheme;
    final canCreate = widget.spaceSlug == null || _canCreateSpace;
    final create = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _createQuickAction('dossier', 'Dossier'),
        const SizedBox(width: 6),
        _createQuickAction('project', 'Projet'),
      ],
    );
    final modes = OrganizerViewSwitcher(selected: _mode, onSelected: _setMode);
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: scheme.surface,
        border: Border(bottom: BorderSide(color: scheme.outlineVariant)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        child: LayoutBuilder(
          builder: (context, constraints) {
            if (constraints.maxWidth < 330 ||
                MediaQuery.textScalerOf(context).scale(14) > 15) {
              return SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    if (canCreate) create,
                    if (canCreate) const SizedBox(width: 12),
                    modes,
                  ],
                ),
              );
            }
            return Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [if (canCreate) create, modes],
            );
          },
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => !_actorValid
      ? const Scaffold(
          body: Center(child: Text('Cet Espace n’est plus le contexte actif.')),
        )
      : Scaffold(
          appBar: AppBar(
            titleSpacing: 4,
            leadingWidth: 48,
            title: _searchOpen
                ? TextField(
                    key: const Key('organizer-search'),
                    autofocus: true,
                    controller: _search,
                    textInputAction: TextInputAction.search,
                    decoration: const InputDecoration(
                      hintText: 'Rechercher…',
                      border: InputBorder.none,
                      isDense: true,
                    ),
                  )
                : Text(
                    widget.spaceSlug == null
                        ? 'Mes démarches'
                        : 'Projets et dossiers',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w700),
                  ),
            actions: _searchOpen
                ? [
                    if (_search.text.isNotEmpty)
                      MakoloIconActionButton(
                        tooltip: 'Effacer la recherche',
                        onPressed: _search.clear,
                        icon: Icons.backspace_outlined,
                      ),
                    MakoloIconActionButton(
                      tooltip: 'Fermer la recherche',
                      onPressed: _stopSearch,
                      icon: Icons.close_rounded,
                    ),
                  ]
                : [
                    MakoloIconActionButton(
                      tooltip: _search.text.trim().isNotEmpty
                          ? 'Recherche active'
                          : 'Rechercher',
                      onPressed: _startSearch,
                      icon: Icons.search_rounded,
                      color: _search.text.trim().isNotEmpty
                          ? Theme.of(context).colorScheme.primary
                          : null,
                    ),
                    MakoloIconActionButton(
                      tooltip:
                          _kind != 'all' ||
                              _status != 'all' ||
                              _relation != 'all'
                          ? 'Filtres actifs'
                          : 'Filtrer',
                      onPressed: _showContentFilters,
                      icon: Icons.tune_rounded,
                      color:
                          _kind != 'all' ||
                              _status != 'all' ||
                              _relation != 'all'
                          ? Theme.of(context).colorScheme.primary
                          : null,
                    ),
                    MakoloIconActionButton(
                      tooltip: _hasExtraFilters
                          ? 'Dates et tri actifs'
                          : 'Dates et tri',
                      onPressed: _advancedFilters,
                      icon: Icons.sort_rounded,
                      color: _hasExtraFilters
                          ? Theme.of(context).colorScheme.primary
                          : null,
                    ),
                  ],
            bottom: PreferredSize(
              preferredSize: const Size.fromHeight(60),
              child: _persistentActions(),
            ),
          ),
          body: StreamBuilder<OwnerSourceState>(
            key: ValueKey<String>(
              'organizer-owner:${widget.spaceSlug ?? 'personal'}',
            ),
            stream: _source,
            initialData: OwnerSourceState.unknown,
            builder: (context, ownerSnapshot) {
              final source = ownerSnapshot.data ?? OwnerSourceState.unknown;
              // An unavailable Objectives route or projection error is not proof
              // that this device is offline: other Makolo surfaces may still work.
              final networkFailure = const {
                'timeout',
                'makolo_unreachable',
                'secure_connection_failed',
                'transport_error',
              }.contains(source.lastErrorCode);
              final offline =
                  SyncStatusScope.maybeOf(context)?.state ==
                      SyncVisualState.offline ||
                  networkFailure;
              return StreamBuilder<List<StoredProjection>>(
                key: ValueKey<String>(
                  'organizer-pages:${widget.spaceSlug ?? 'personal'}',
                ),
                stream: _pages,
                builder: (context, projectionSnapshot) {
                  final page = OrganizerPage.read(
                    projectionSnapshot.data ?? const [],
                    widget.repository.profileId,
                    spaceSlug: widget.spaceSlug,
                  );
                  final entries = page.entries;
                  final hierarchy = OrganizerHierarchy(entries);
                  final byKey = hierarchy.byKey;
                  List<OrganizerEntry> children(OrganizerEntry parent) =>
                      _ordered(hierarchy.childrenOf(parent));

                  // Include ancestors of matching descendants. With search or type
                  // filters the tree opens the matching path; partial parents are
                  // shown as ungrouped, not falsely labelled independent.
                  final visibleCache = <String, bool>{};
                  late bool Function(OrganizerEntry) visible;
                  visible = (item) => visibleCache.putIfAbsent(
                    item.key,
                    () => _matches(item) || children(item).any(visible),
                  );

                  final roots = _ordered(hierarchy.roots)
                      .where(visible)
                      .toList();

                  final flat = _ordered(entries.where(_matches));
                  final showFlat =
                      _mode == OrganizerMode.list ||
                      (_mode == OrganizerMode.cards &&
                          (_kind != 'all' || _relation == 'independent'));
                  final shown = showFlat ? flat : roots;

                  return NotificationListener<ScrollNotification>(
                    onNotification: (notification) {
                      if (notification.metrics.axis != Axis.vertical ||
                          notification.metrics.extentAfter > 450 ||
                          !page.hasFirst ||
                          !page.hasMore ||
                          offline ||
                          source.invalidated ||
                          _failed ||
                          _loadingMore ||
                          _refreshing) {
                        return false;
                      }
                      // Keep pagination owner-backed and contiguous. A scroll near
                      // the end is the trigger; no page-number or next-page button.
                      unawaited(_more(page));
                      return false;
                    },
                    child: RefreshIndicator(
                      onRefresh: _refresh,
                      child: ListView(
                        key: PageStorageKey<String>(
                          'organizer-scroll:${widget.spaceSlug ?? 'personal'}',
                        ),
                        physics: const AlwaysScrollableScrollPhysics(),
                        padding: EdgeInsets.fromLTRB(
                          _mode == OrganizerMode.explorer ? 4 : 16,
                          10,
                          _mode == OrganizerMode.explorer ? 4 : 16,
                          44,
                        ),
                        children: [
                          Center(
                            child: ConstrainedBox(
                              constraints: const BoxConstraints(maxWidth: 960),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  if (source.invalidated)
                                    Column(
                                      children: [
                                        ListTile(
                                          leading: Icon(
                                            source.lastErrorCode ==
                                                    'permission_denied'
                                                ? Icons.lock_outline
                                                : Icons.sync_problem_outlined,
                                          ),
                                          title: Text(
                                            source.lastErrorCode ==
                                                    'permission_denied'
                                                ? 'Vous n’avez pas accès à cet espace.'
                                                : source.lastErrorCode ==
                                                      'not_found'
                                                ? 'Cet espace de démarches est momentanément introuvable.'
                                                : 'Retrouvons vos démarches.',
                                          ),
                                          subtitle: Text(
                                            source.lastErrorCode ==
                                                    'permission_denied'
                                                ? 'Vérifiez le compte utilisé.'
                                                : 'Vos autres rubriques restent disponibles.',
                                          ),
                                        ),
                                        TextButton.icon(
                                          onPressed: _refreshing
                                              ? null
                                              : _refresh,
                                          icon: const Icon(
                                            Icons.refresh_rounded,
                                          ),
                                          label: const Text('Réessayer'),
                                        ),
                                      ],
                                    )
                                  else if (!page.hasFirst) ...[
                                    if (_refreshing)
                                      const Center(
                                        child: Padding(
                                          padding: EdgeInsets.all(30),
                                          child: Column(
                                            children: [
                                              CircularProgressIndicator.adaptive(),
                                              SizedBox(height: 14),
                                              Text(
                                                'Nous préparons vos démarches…',
                                              ),
                                            ],
                                          ),
                                        ),
                                      )
                                    else
                                      Padding(
                                        padding: const EdgeInsets.all(20),
                                        child: Column(
                                          children: [
                                            Text(
                                              source.lastErrorCode ==
                                                          'endpoint_unavailable' ||
                                                      source.lastErrorCode ==
                                                          'not_found'
                                                  ? 'Vos démarches ne sont pas encore disponibles ici.'
                                                  : _failed
                                                  ? 'Impossible d’afficher vos démarches pour le moment.'
                                                  : 'Retrouvez vos projets, dossiers et démarches ici.',
                                              textAlign: TextAlign.center,
                                            ),
                                            const SizedBox(height: 10),
                                            Text(
                                              offline
                                                  ? 'Réessayez lorsque la connexion revient.'
                                                  : source.lastErrorCode ==
                                                            'endpoint_unavailable' ||
                                                        source.lastErrorCode ==
                                                            'not_found'
                                                  ? 'Les autres rubriques restent disponibles. Réessayez plus tard.'
                                                  : 'Touchez Réessayer pour les retrouver.',
                                              textAlign: TextAlign.center,
                                            ),
                                            MakoloActionButton(
                                              label: 'Réessayer',
                                              onPressed: _refreshing
                                                  ? null
                                                  : _refresh,
                                              icon: Icons.refresh_rounded,
                                              appearance:
                                                  MakoloActionAppearance.quiet,
                                            ),
                                          ],
                                        ),
                                      ),
                                  ] else ...[
                                    if (_search.text.trim().isNotEmpty &&
                                        flat.isNotEmpty)
                                      Padding(
                                        padding: const EdgeInsets.only(
                                          top: 8,
                                          bottom: 12,
                                        ),
                                        child: Wrap(
                                          spacing: 6,
                                          runSpacing: 6,
                                          children: [
                                            for (final item in flat.take(5))
                                              ActionChip(
                                                avatar: Icon(
                                                  item.icon,
                                                  size: 17,
                                                ),
                                                label: Text(item.title),
                                                onPressed: () =>
                                                    widget.onOpenItem(
                                                      item.kind,
                                                      item.id,
                                                    ),
                                              ),
                                          ],
                                        ),
                                      ),
                                    Padding(
                                      padding: const EdgeInsets.symmetric(
                                        vertical: 12,
                                      ),
                                      child: Text(
                                        organizerCountLabel(
                                          flat,
                                          filtered: _hasSelectionFilters,
                                        ),
                                        style: Theme.of(context)
                                            .textTheme
                                            .labelMedium,
                                      ),
                                    ),
                                    if (shown.isEmpty)
                                      _empty(entries.isEmpty)
                                    else if (_mode == OrganizerMode.cards)
                                      LayoutBuilder(
                                        builder: (context, constraints) {
                                          final itemWidth =
                                              constraints.maxWidth >= 700
                                              ? (constraints.maxWidth - 12) / 2
                                              : constraints.maxWidth;
                                          return Wrap(
                                            spacing: 12,
                                            runSpacing: 12,
                                            children: [
                                              for (final item in shown)
                                                SizedBox(
                                                  width: itemWidth,
                                                  child: _card(
                                                    item,
                                                    children(item),
                                                    hierarchy,
                                                  ),
                                                ),
                                            ],
                                          );
                                        },
                                      )
                                    else if (_mode == OrganizerMode.list ||
                                        showFlat)
                                      for (final item in flat) _row(item, byKey)
                                    else
                                      for (final item in roots)
                                        _tree(
                                          item,
                                          children,
                                          visible,
                                          hierarchy,
                                          0,
                                        ),
                                    if (page.hasMore && !offline && !_failed)
                                      const Padding(
                                        padding: EdgeInsets.symmetric(
                                          vertical: 18,
                                        ),
                                        child: Center(
                                          child:
                                              CircularProgressIndicator.adaptive(),
                                        ),
                                      ),
                                    if (_failed)
                                      TextButton.icon(
                                        onPressed: _refresh,
                                        icon: const Icon(Icons.refresh_rounded),
                                        label: const Text(
                                          'Impossible de mettre à jour · Réessayer',
                                        ),
                                      ),
                                  ],
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              );
            },
          ),
        );

  Widget _empty(bool noData) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 38),
    child: Column(
      children: [
        Icon(
          Icons.folder_open_outlined,
          size: 38,
          color: Theme.of(context).colorScheme.primary,
        ),
        const SizedBox(height: 12),
        Text(
          noData
              ? 'Votre espace est prêt.'
              : 'Aucun résultat pour ces critères.',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        Text(
          noData
              ? 'Créez un projet ou un dossier pour organiser ce qui compte pour vous.'
              : 'Modifiez la recherche ou les filtres.',
          textAlign: TextAlign.center,
        ),
      ],
    ),
  );

  Widget _card(
    OrganizerEntry item,
    List<OrganizerEntry> children,
    OrganizerHierarchy hierarchy,
  ) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      margin: EdgeInsets.zero,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: scheme.outlineVariant),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: () => widget.onOpenItem(item.kind, item.id),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(item.icon, color: scheme.primary, size: 26),
                  const Spacer(),
                  Text(
                    item.humanState,
                    style: Theme.of(context).textTheme.labelSmall
                        ?.copyWith(color: scheme.onSurfaceVariant),
                  ),
                  const SizedBox(width: 8),
                  Icon(Icons.arrow_forward_rounded, color: scheme.primary),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                item.title,
                style: Theme.of(context).textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              if (item.description.trim().isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(
                  item.description,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall
                      ?.copyWith(color: scheme.onSurfaceVariant),
                ),
              ],
              const SizedBox(height: 12),
              Wrap(
                spacing: 7,
                runSpacing: 7,
                children: [
                  _tag(item.kindLabel),
                  if (item.space != null) _tag(item.space!),
                  if (item.displayDate != null) _tag(item.displayDate!),
                ],
              ),
              if (item.kind == 'dossier' &&
                  hierarchy.additionalSharedLinks(item) > 0)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    organizerSharedLinksLabel(
                      hierarchy.additionalSharedLinks(item),
                    ),
                    style: Theme.of(context).textTheme.bodySmall
                        ?.copyWith(color: scheme.onSurfaceVariant),
                  ),
                ),
              if (children.isNotEmpty) ...[
                const SizedBox(height: 12),
                for (final child in children.take(3))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 7),
                    child: OrganizerLinkedItem(
                      key: Key('organizer-child-${child.key}'),
                      title: child.title,
                      kind: child.kindLabel,
                      icon: child.icon,
                      dense: true,
                      onOpen: () => widget.onOpenItem(child.kind, child.id),
                    ),
                  ),
                if (children.length > 3)
                  Text(
                    organizerMoreChildrenLabel(item, children.length - 3),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _tag(String text) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.primary.withValues(alpha: .07),
      borderRadius: BorderRadius.circular(9),
    ),
    child: Text(text, style: Theme.of(context).textTheme.labelSmall),
  );

  Widget _row(OrganizerEntry item, Map<String, OrganizerEntry> byKey) {
    final visibleParents = item.dossierIds
        .map((id) => byKey['dossier:$id'])
        .whereType<OrganizerEntry>();
    final parent = item.kind == 'dossier' && item.projectId != null
        ? byKey['project:${item.projectId}']
        : item.kind == 'journey' && visibleParents.isNotEmpty
        ? visibleParents.first
        : null;
    final details = <String>[
      item.humanState,
      if (item.kind == 'journey' && item.dossierIds.toSet().length > 1)
        'Liée à ${item.dossierIds.toSet().length} dossiers'
      else if (parent != null)
        'Dans : ${parent.title}',
      if (item.kind == 'journey' && item.dossierIds.isNotEmpty && parent == null)
        'Dossier non affiché',
      if (item.kind == 'dossier' && item.projectId != null && parent == null)
        'Projet non affiché',
      if (item.displayDate != null) item.displayDate!,
    ];
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Card(
        margin: EdgeInsets.zero,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: scheme.outlineVariant),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          key: Key('organizer-row-${item.key}'),
          onTap: () => widget.onOpenItem(item.kind, item.id),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 12),
            child: Row(
              children: [
                Icon(item.icon, size: 25, color: scheme.primary),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${item.kindLabel} · ${details.join(' · ')}',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Icon(Icons.chevron_right_rounded, color: scheme.primary),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _tree(
    OrganizerEntry item,
    List<OrganizerEntry> Function(OrganizerEntry) children,
    bool Function(OrganizerEntry) visible,
    OrganizerHierarchy hierarchy,
    int depth,
  ) {
    final nodes = children(item).where(visible).toList();
    final key = item.key;
    final expandable = item.kind == 'project' || item.kind == 'dossier';
    final expanded = _expanded.contains(key) || _hasSelectionFilters;
    return Column(
      children: [
        Padding(
          padding: EdgeInsetsDirectional.only(start: depth * 3.0),
          child: Row(
            children: [
              if (expandable)
                IconButton(
                  key: Key('organizer-expand-$key'),
                  tooltip: expanded
                      ? 'Replier ${item.title}'
                      : 'Déplier ${item.title}',
                  visualDensity: VisualDensity.compact,
                  constraints: const BoxConstraints(
                    minWidth: 28,
                    minHeight: 44,
                  ),
                  padding: EdgeInsets.zero,
                  onPressed: _hasSelectionFilters
                      ? null
                      : () => setState(() {
                          if (_expanded.contains(key)) {
                            _expanded.remove(key);
                          } else {
                            _expanded.add(key);
                          }
                        }),
                  icon: Icon(
                    expanded
                        ? Icons.keyboard_arrow_down_rounded
                        : Icons.chevron_right_rounded,
                  ),
                  iconSize: 19,
                )
              else
                const SizedBox(width: 28),
              Expanded(
                child: InkWell(
                  key: Key('organizer-open-$key'),
                  borderRadius: BorderRadius.circular(6),
                  onTap: () => widget.onOpenItem(item.kind, item.id),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(minHeight: 48),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 5),
                      child: Row(
                        children: [
                          Icon(
                            item.icon,
                            size: 18,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(
                                  item.title,
                                  style: Theme.of(context).textTheme.titleSmall
                                      ?.copyWith(fontWeight: FontWeight.w700),
                                ),
                                Text(
                                  [
                                    item.kindLabel,
                                    item.humanState,
                                    if (item.kind == 'journey' &&
                                        item.dossierIds.toSet().length > 1)
                                      'Liée à ${item.dossierIds.toSet().length} dossiers',
                                    if (item.kind == 'journey' &&
                                        item.dossierIds.isNotEmpty &&
                                        !item.dossierIds.any(
                                          (id) => hierarchy.byKey.containsKey(
                                            'dossier:$id',
                                          ),
                                        ))
                                      'Dossier non chargé',
                                    if (item.kind == 'dossier' &&
                                        item.projectId != null &&
                                        !hierarchy.byKey.containsKey(
                                          'project:${item.projectId}',
                                        ))
                                      'Projet non chargé',
                                    if (item.kind == 'dossier' &&
                                        hierarchy.additionalSharedLinks(item) >
                                            0)
                                      organizerSharedLinksLabel(
                                        hierarchy.additionalSharedLinks(item),
                                      ),
                                  ].join(' · '),
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 4),
                          Icon(
                            Icons.arrow_forward_ios_rounded,
                            size: 14,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
        if (expanded)
          for (final child in nodes)
            _tree(child, children, visible, hierarchy, depth + 1),
      ],
    );
  }
}
