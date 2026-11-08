import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../data/local/profile_store.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_status.dart';
import 'objective_organizer_data.dart';
import 'objective_repository.dart';

class ObjectiveOrganizerScreen extends StatefulWidget {
  const ObjectiveOrganizerScreen({
    super.key,
    required this.repository,
    required this.onOpenItem,
    required this.onCreate,
  });

  final ObjectiveRepository repository;
  final void Function(String kind, String id) onOpenItem;
  final ValueChanged<String> onCreate;

  @override
  State<ObjectiveOrganizerScreen> createState() =>
      _ObjectiveOrganizerScreenState();
}

class _ObjectiveOrganizerScreenState extends State<ObjectiveOrganizerScreen> {
  static const _storage = FlutterSecureStorage();
  final _search = TextEditingController();
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
  final Set<String> _expanded = {};

  @override
  void initState() {
    super.initState();
    _bind();
    _search.addListener(_changed);
    unawaited(_restore());
    unawaited(_acquire());
  }

  @override
  void didUpdateWidget(covariant ObjectiveOrganizerScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository) {
      _bind();
      _expanded.clear();
      _failed = false;
      _requestedOffset = null;
      _mode = OrganizerMode.cards;
      unawaited(_restore());
      unawaited(_acquire());
    }
  }

  void _bind() {
    _pages = widget.repository.watchOrganizer();
    _source = widget.repository.watchOrganizerSource();
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _search.removeListener(_changed);
    _search.dispose();
    super.dispose();
  }

  Future<void> _restore() async {
    final id = widget.repository.profileId;
    try {
      final value = await _storage.read(key: 'organizer.view.$id');
      if (mounted && id == widget.repository.profileId) {
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
      await _storage.write(
        key: 'organizer.view.${widget.repository.profileId}',
        value: value.name,
      );
    } on Object {
      // The selected view stays usable for the current session.
    }
  }

  void _setMode(OrganizerMode value) {
    setState(() => _mode = value);
    unawaited(_remember(value));
  }

  Future<void> _acquire() async {
    final repository = widget.repository;
    try {
      final local = await repository.readOrganizerPage(0);
      final source = await repository.readOrganizerSource();
      if (!mounted || repository != widget.repository) return;
      if (local == null ||
          ObjectiveRepository.freshnessPolicy.evaluate(
                local,
                now: DateTime.now().toUtc(),
                invalidated: source.invalidated,
              ) !=
              FreshnessState.fresh) {
        unawaited(_refresh());
      }
    } on Object {
      if (mounted && repository == widget.repository) {
        setState(() => _failed = true);
      }
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final repository = widget.repository;
    setState(() {
      _refreshing = true;
      _failed = false;
      _requestedOffset = null;
    });
    try {
      await repository.refreshOrganizerPage(0);
      // The sync engine can retain the local snapshot and record a scoped
      // failure without throwing. Read its durable status, not just the Future.
      final local = await repository.readOrganizerPage(0);
      final owner = await repository.readOrganizerSource();
      if (mounted && repository == widget.repository) {
        setState(() {
          _failed = owner.lastErrorCode != null ||
              (local == null && owner.lastSuccessAt == null);
        });
      }
    } on Object {
      if (mounted && repository == widget.repository) {
        setState(() => _failed = true);
      }
    } finally {
      if (mounted && repository == widget.repository) {
        setState(() => _refreshing = false);
      }
    }
  }

  Future<void> _more(OrganizerPage page) async {
    if (_loadingMore ||
        _refreshing ||
        !page.hasMore ||
        _requestedOffset == page.nextOffset) {
      return;
    }
    final repository = widget.repository;
    _requestedOffset = page.nextOffset;
    setState(() => _loadingMore = true);
    try {
      await repository.refreshOrganizerPage(page.nextOffset);
    } on Object {
      _requestedOffset = null;
      if (mounted && repository == widget.repository) {
        setState(() => _failed = true);
      }
    } finally {
      if (mounted && repository == widget.repository) {
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

  Widget _controls() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      LayoutBuilder(
        builder: (context, constraints) {
          final createDossier = FilledButton.icon(
            onPressed: () => widget.onCreate('dossier'),
            icon: const Icon(Icons.folder_open_outlined),
            label: const Text('Créer un dossier'),
          );
          final createProject = OutlinedButton.icon(
            onPressed: () => widget.onCreate('project'),
            icon: const Icon(Icons.create_new_folder_outlined),
            label: const Text('Créer un projet'),
          );
          if (constraints.maxWidth < 350) {
            return Column(
              children: [
                SizedBox(width: double.infinity, child: createDossier),
                const SizedBox(height: 8),
                SizedBox(width: double.infinity, child: createProject),
              ],
            );
          }
          return Row(
            children: [
              Expanded(child: createDossier),
              const SizedBox(width: 10),
              Expanded(child: createProject),
            ],
          );
        },
      ),
      const SizedBox(height: 16),
      TextField(
        key: const Key('organizer-search'),
        controller: _search,
        decoration: InputDecoration(
          prefixIcon: const Icon(Icons.search_rounded),
          hintText: 'Rechercher dans mes démarches',
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
          suffixIcon: _search.text.isEmpty
              ? null
              : IconButton(
                  tooltip: 'Effacer',
                  icon: const Icon(Icons.close_rounded),
                  onPressed: _search.clear,
                ),
        ),
      ),
      const SizedBox(height: 12),
      SizedBox(
        height: 53,
        child: ListView(
          scrollDirection: Axis.horizontal,
          children: [
            // All six filters remain immediately available in one row.
            // Horizontal scrolling preserves their labels on small screens.
            Row(
              children: [
          _dropdown('Type', _kind, const {
            'all': 'Tous les types',
            'project': 'Projets',
            'dossier': 'Dossiers',
            'journey': 'Démarches',
          }, (v) => setState(() => _kind = v), icon: Icons.category_outlined),
          _dropdown('État', _status, const {
            'all': 'Tous les états',
            'draft': 'En préparation',
            'active': 'En cours',
            'completed': 'Terminé',
            'cancelled': 'Annulé',
            'archived': 'Archivé',
          }, (v) => setState(() => _status = v), icon: Icons.tune_rounded),
          _dropdown('Contexte', _relation, const {
            'all': 'Tous les contextes',
            'mine': 'Personnel',
            'space': 'Espace',
            'independent': 'Indépendants',
          }, (v) => setState(() => _relation = v), icon: Icons.account_tree_outlined),
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
            (v) => setState(
              () => _dateField = OrganizerSort.values.firstWhere(
                (element) => element.name == v,
              ),
            ),
            icon: Icons.event_outlined,
          ),
          _dropdown('Période', _period, const {
            'all': 'Toutes les dates',
            'week': '7 prochains jours',
            'month': '30 prochains jours',
            'quarter': '90 prochains jours',
          }, (v) => setState(() => _period = v), icon: Icons.date_range_outlined),
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
            (v) => setState(
              () => _sort = OrganizerSort.values.firstWhere(
                (element) => element.name == v,
              ),
            ),
            icon: Icons.sort_by_alpha_rounded,
          ),
          IconButton(
            tooltip: _descending ? 'Décroissant' : 'Croissant',
            onPressed: () => setState(() => _descending = !_descending),
            icon: Icon(
              _descending
                  ? Icons.arrow_downward_rounded
                  : Icons.arrow_upward_rounded,
            ),
          ),
          if (_search.text.isNotEmpty ||
              _kind != 'all' ||
              _status != 'all' ||
              _relation != 'all' ||
              _period != 'all' ||
              _sort != OrganizerSort.name ||
              _dateField != OrganizerSort.deadline)
            TextButton(
              onPressed: () {
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
              },
              child: const Text('Effacer les filtres'),
            ),
              ],
            ),
          ],
        ),
      ),
      const SizedBox(height: 12),
      LayoutBuilder(
        builder: (context, constraints) {
          if (constraints.maxWidth < 470) {
            return Wrap(
              spacing: 7,
              runSpacing: 7,
              children: [
                ChoiceChip(
                  avatar: const Icon(Icons.grid_view_rounded, size: 17),
                  label: const Text('Cartes'),
                  selected: _mode == OrganizerMode.cards,
                  onSelected: (_) => _setMode(OrganizerMode.cards),
                ),
                ChoiceChip(
                  avatar: const Icon(Icons.view_list_rounded, size: 17),
                  label: const Text('Liste'),
                  selected: _mode == OrganizerMode.list,
                  onSelected: (_) => _setMode(OrganizerMode.list),
                ),
                ChoiceChip(
                  avatar: const Icon(Icons.account_tree_outlined, size: 17),
                  label: const Text('Explorateur'),
                  selected: _mode == OrganizerMode.explorer,
                  onSelected: (_) => _setMode(OrganizerMode.explorer),
                ),
              ],
            );
          }
          return SegmentedButton<OrganizerMode>(
            key: const Key('organizer-view-toggle'),
            showSelectedIcon: false,
            selected: {_mode},
            segments: const [
              ButtonSegment(
                value: OrganizerMode.cards,
                icon: Icon(Icons.grid_view_rounded),
                label: Text('Cartes'),
              ),
              ButtonSegment(
                value: OrganizerMode.list,
                icon: Icon(Icons.view_list_rounded),
                label: Text('Liste'),
              ),
              ButtonSegment(
                value: OrganizerMode.explorer,
                icon: Icon(Icons.account_tree_outlined),
                label: Text('Explorateur'),
              ),
            ],
            onSelectionChanged: (values) => _setMode(values.first),
          );
        },
      ),
    ],
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Mes démarches'),
      actions: [
        IconButton(
          tooltip: 'Actualiser',
          onPressed: _refreshing ? null : _refresh,
          icon: const Icon(Icons.refresh_rounded),
        ),
      ],
    ),
    body: StreamBuilder<OwnerSourceState>(
      stream: _source,
      initialData: OwnerSourceState.unknown,
      builder: (context, ownerSnapshot) {
        final source = ownerSnapshot.data ?? OwnerSourceState.unknown;
        final offline =
            SyncStatusScope.maybeOf(context)?.state ==
                SyncVisualState.offline ||
            source.reachability == ReachabilityState.unreachable;
        return StreamBuilder<List<StoredProjection>>(
          stream: _pages,
          builder: (context, projectionSnapshot) {
            final page = OrganizerPage.read(
              projectionSnapshot.data ?? const [],
              widget.repository.profileId,
            );
            final entries = page.entries;
            final byKey = {for (final item in entries) item.key: item};
            final projects = entries.where((item) => item.kind == 'project');
            final dossiers = entries.where((item) => item.kind == 'dossier');
            final journeys = entries.where((item) => item.kind == 'journey');

            List<OrganizerEntry> children(OrganizerEntry parent) => _ordered(
              parent.kind == 'project'
                  ? dossiers.where((d) => d.projectId == parent.id)
                  : parent.kind == 'dossier'
                  ? journeys.where((j) => j.dossierIds.contains(parent.id))
                  : const <OrganizerEntry>[],
            );

            bool visible(OrganizerEntry item) =>
                _matches(item) ||
                children(item).any((child) {
                  // Project > Dossier > Journey; no cycle can exist here.
                  if (_kind == 'journey' && item.kind == 'project') {
                    return _matches(child) || children(child).any(_matches);
                  }
                  return _matches(child) || children(child).any(_matches);
                });

            final roots = _ordered([
              ...projects,
              ...dossiers.where(
                (d) =>
                    d.projectId == null ||
                    !byKey.containsKey('project:${d.projectId}'),
              ),
              ...journeys.where(
                (j) =>
                    j.dossierIds.isEmpty ||
                    !j.dossierIds.any((id) => byKey.containsKey('dossier:$id')),
              ),
            ]).where(visible).toList();

            final flat = _ordered(entries.where(_matches));
            final showFlat =
                _mode == OrganizerMode.list ||
                (_mode == OrganizerMode.cards &&
                    (_kind != 'all' || _relation == 'independent'));
            final shown = showFlat ? flat : roots;

            return RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(
                key: const PageStorageKey<String>('organizer-scroll'),
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 44),
                children: [
                  Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 960),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            'Mon espace d’organisation',
                            style: Theme.of(context).textTheme.titleLarge
                                ?.copyWith(fontWeight: FontWeight.w800),
                          ),
                          const SizedBox(height: 5),
                          Text(
                            'Projets, dossiers et démarches, à votre rythme.',
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurfaceVariant,
                                ),
                          ),
                          const SizedBox(height: 19),
                          _controls(),
                          const SizedBox(height: 12),
                          const Divider(),
                          if (source.invalidated)
                            const ListTile(
                              leading: Icon(Icons.lock_outline),
                              title: Text('Accès à cette collection retiré.'),
                              subtitle: Text(
                                'Vérifiez votre session pour actualiser.',
                              ),
                            )
                          else if (!page.hasFirst) ...[
                            if (_refreshing)
                              const Center(
                                child: Padding(
                                  padding: EdgeInsets.all(30),
                                  child: CircularProgressIndicator.adaptive(),
                                ),
                              )
                            else
                              Padding(
                                padding: const EdgeInsets.all(20),
                                child: Text(
                                  offline || _failed
                                      ? 'Première synchronisation nécessaire. Réessayez lorsque le réseau est disponible.'
                                      : 'Aucune collection acquise. Actualisez pour commencer.',
                                ),
                              ),
                          ] else ...[
                            if (offline)
                              const ListTile(
                                dense: true,
                                leading: Icon(Icons.offline_bolt_outlined),
                                title: Text(
                                  'Données disponibles sur cet appareil',
                                ),
                                subtitle: Text(
                                  'Actualisation à la reconnexion.',
                                ),
                              ),
                            if (page.hasMore)
                              Text(
                                'Recherche et tri parmi les éléments acquis. '
                                'D’autres éléments peuvent être chargés.',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
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
                                        avatar: Icon(item.icon, size: 17),
                                        label: Text(item.title),
                                        onPressed: () => widget.onOpenItem(
                                          item.kind,
                                          item.id,
                                        ),
                                      ),
                                  ],
                                ),
                              ),
                            Padding(
                              padding: const EdgeInsets.symmetric(vertical: 12),
                              child: Text(
                                '${flat.length} résultat(s) dans les données acquises',
                                style: Theme.of(context).textTheme.labelMedium,
                              ),
                            ),
                            if (shown.isEmpty)
                              _empty(entries.isEmpty)
                            else if (_mode == OrganizerMode.cards)
                              LayoutBuilder(
                                builder: (context, constraints) {
                                  final itemWidth = constraints.maxWidth >= 700
                                      ? (constraints.maxWidth - 12) / 2
                                      : constraints.maxWidth;
                                  return Wrap(
                                    spacing: 12,
                                    runSpacing: 12,
                                    children: [
                                      for (final item in shown)
                                        SizedBox(
                                          width: itemWidth,
                                          child: _card(item, children(item)),
                                        ),
                                    ],
                                  );
                                },
                              )
                            else if (_mode == OrganizerMode.list || showFlat)
                              for (final item in flat) _row(item, byKey)
                            else
                              for (final item in roots)
                                _tree(item, children, visible, 0),
                            if (page.hasMore)
                              Padding(
                                padding: const EdgeInsets.only(top: 18),
                                child: OutlinedButton.icon(
                                  onPressed: offline || _loadingMore
                                      ? null
                                      : () => _more(page),
                                  icon: _loadingMore
                                      ? const SizedBox(
                                          height: 16,
                                          width: 16,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                          ),
                                        )
                                      : const Icon(Icons.add_rounded),
                                  label: Text(
                                    offline
                                        ? 'Suite disponible après reconnexion'
                                        : 'Charger les éléments suivants',
                                  ),
                                ),
                              ),
                            if (_failed)
                              TextButton.icon(
                                onPressed: _refresh,
                                icon: const Icon(Icons.refresh_rounded),
                                label: const Text(
                                  'Actualisation impossible · Réessayer',
                                ),
                              ),
                          ],
                        ],
                      ),
                    ),
                  ),
                ],
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
              ? 'Aucun élément accessible pour le moment.'
              : 'Aucun résultat pour ces critères.',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        Text(
          noData
              ? 'Créez un projet ou un dossier pour commencer.'
              : 'Modifiez la recherche ou les filtres.',
          textAlign: TextAlign.center,
        ),
      ],
    ),
  );

  Widget _card(OrganizerEntry item, List<OrganizerEntry> children) {
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
          padding: const EdgeInsets.all(17),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(item.icon, color: scheme.primary, size: 29),
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
              const SizedBox(height: 13),
              Text(
                item.title,
                style: Theme.of(context).textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 6),
              Text(
                item.description.isEmpty ? item.kindLabel : item.description,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall
                    ?.copyWith(color: scheme.onSurfaceVariant),
              ),
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
              if (children.isNotEmpty) ...[
                const Divider(height: 28),
                for (final child in children.take(3))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 7),
                    child: Row(
                      children: [
                        Icon(child.icon, size: 17, color: scheme.primary),
                        const SizedBox(width: 9),
                        Expanded(
                          child: Text(
                            child.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ),
                if (children.length > 3)
                  Text(
                    'Et ${children.length - 3} autre(s) élément(s) acquis',
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
    final parent = item.kind == 'dossier' && item.projectId != null
        ? byKey['project:${item.projectId}']
        : item.kind == 'journey' && item.dossierIds.isNotEmpty
        ? byKey['dossier:${item.dossierIds.first}']
        : null;
    return Column(
      children: [
        ListTile(
          contentPadding: const EdgeInsets.symmetric(vertical: 4),
          leading: Icon(
            item.icon,
            color: Theme.of(context).colorScheme.primary,
          ),
          title: Text(item.title),
          subtitle: Text(
            [
              item.kindLabel,
              item.humanState,
              if (parent != null) 'Dans : ${parent.title}',
              if (item.displayDate != null) item.displayDate!,
            ].join(' · '),
          ),
          trailing: const Icon(Icons.chevron_right_rounded),
          onTap: () => widget.onOpenItem(item.kind, item.id),
        ),
        const Divider(height: 1),
      ],
    );
  }

  Widget _tree(
    OrganizerEntry item,
    List<OrganizerEntry> Function(OrganizerEntry) children,
    bool Function(OrganizerEntry) visible,
    int depth,
  ) {
    final nodes = children(item).where(visible).toList();
    final key = item.key;
    final expanded = _expanded.contains(key) || _search.text.trim().isNotEmpty;
    return Column(
      children: [
        Padding(
          padding: EdgeInsetsDirectional.only(start: depth * 14.0),
          child: Row(
            children: [
              if (nodes.isNotEmpty)
                IconButton(
                  tooltip: expanded ? 'Replier' : 'Déplier',
                  onPressed: () => setState(() {
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
                  iconSize: 20,
                )
              else
                const SizedBox(width: 48),
              Expanded(
                child: ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(
                    item.icon,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  title: Text(
                    item.title,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: Text('${item.kindLabel} · ${item.humanState}'),
                  onTap: () => widget.onOpenItem(item.kind, item.id),
                ),
              ),
            ],
          ),
        ),
        if (expanded)
          for (final child in nodes) _tree(child, children, visible, depth + 1),
      ],
    );
  }
}
