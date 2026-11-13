import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/actor_context_controller.dart';
import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_status.dart';
import 'conversation_context_screen.dart';
import 'conversation_repository.dart';
import 'objective_repository.dart';
import 'objective_workspace_view_switcher.dart';
import 'objective_filter_reset.dart';
import 'project_description.dart';

enum _ProjectMode { summary, dossiers, calendar }

enum _ProjectSort { title, deadline, state, created, updated }

enum _ProjectTime { all, next30, overdue, undated, active }

Map<String, dynamic> _map(Object? raw) =>
    raw is Map ? raw.map((k, v) => MapEntry(k.toString(), v)) : {};
List<Map<String, dynamic>> _list(Object? raw) =>
    raw is List ? raw.map(_map).where((r) => r.isNotEmpty).toList() : [];
String _text(Object? raw) => raw?.toString() ?? '';
DateTime? _dateFrom(Object? raw) => DateTime.tryParse(_text(raw));
String _humanDate(DateTime date) =>
    '${date.day.toString().padLeft(2, '0')}/'
    '${date.month.toString().padLeft(2, '0')}/${date.year}';
String? _iso(DateTime? date) => date == null
    ? null
    : '${date.year.toString().padLeft(4, '0')}-'
          '${date.month.toString().padLeft(2, '0')}-'
          '${date.day.toString().padLeft(2, '0')}';
String _humanState(Object? raw) => switch (_text(raw)) {
  'draft' => 'En préparation',
  'active' => 'En cours',
  'completed' || 'complete' => 'Terminé',
  'cancelled' => 'Annulé',
  'archived' => 'Archivé',
  'blocked' => 'Bloqué',
  'action_required' => 'Action requise',
  'waiting' => 'En attente',
  'ready' => 'Prêt',
  _ => 'État indisponible',
};

class ProjectWorkspaceScreen extends StatefulWidget {
  const ProjectWorkspaceScreen({
    super.key,
    required this.id,
    required this.repository,
    required this.onOpenDossier,
    this.onOpenPerson,
    this.onOpenMyPassport,
    this.api,
    this.conversations,
    this.onOpenConversation,
    this.actorContext,
  });
  final String id;
  final ObjectiveRepository repository;
  final ValueChanged<String> onOpenDossier;
  final ValueChanged<String>? onOpenPerson;
  final VoidCallback? onOpenMyPassport;
  final MakoloApiClient? api;
  final ConversationRepository? conversations;
  final ValueChanged<String>? onOpenConversation;
  final ActorContextController? actorContext;

  @override
  State<ProjectWorkspaceScreen> createState() => _ProjectWorkspaceScreenState();
}

class _ProjectWorkspaceScreenState extends State<ProjectWorkspaceScreen> {
  late Stream<StoredProjection?> _detail;
  late Stream<OwnerSourceState> _source;
  late Stream<List<StoredProjection>> _pages;
  _ProjectMode _mode = _ProjectMode.summary;
  _ProjectSort _sort = _ProjectSort.deadline;
  _ProjectTime _time = _ProjectTime.all;
  String _stateFilter = 'all';
  String _readinessFilter = 'all';
  String? _spaceSlug;
  int _contextRevision = 0;
  final _search = TextEditingController();

  String? get _selectedSpaceSlug {
    final actor = widget.actorContext?.value;
    return actor is SpaceActorContext ? actor.space.slug : null;
  }

  void _actorChanged() {
    final next = _selectedSpaceSlug;
    if (!mounted || next == _spaceSlug) return;
    _search.clear();
    setState(() {
      _contextRevision++;
      _spaceSlug = next;
      _mode = _ProjectMode.summary;
      _stateFilter = 'all';
      _readinessFilter = 'all';
      _time = _ProjectTime.all;
      _lastOffset = null;
      _ignoreOlderPages = true;
      _loadingMore = false;
      _refreshing = false;
      _busy = false;
      _failed = false;
      _bind();
    });
    unawaited(_refresh());
  }

  bool _refreshing = false,
      _busy = false,
      _loadingMore = false,
      _failed = false;
  bool _ignoreOlderPages = false;
  int? _lastOffset;

  @override
  void initState() {
    super.initState();
    _spaceSlug = _selectedSpaceSlug;
    widget.actorContext?.addListener(_actorChanged);
    _bind();
    _search.addListener(_changed);
    unawaited(_acquire());
  }

  void _bind() {
    _detail = widget.repository.watch(
      ObjectiveDepth.project,
      widget.id,
      spaceSlug: _spaceSlug,
    );
    _source = widget.repository.watchSource(
      ObjectiveDepth.project,
      widget.id,
      spaceSlug: _spaceSlug,
    );
    _pages = widget.repository.watchProjectDossiers();
  }

  @override
  void didUpdateWidget(covariant ProjectWorkspaceScreen previous) {
    super.didUpdateWidget(previous);
    if (previous.actorContext != widget.actorContext) {
      previous.actorContext?.removeListener(_actorChanged);
      widget.actorContext?.addListener(_actorChanged);
    }
    final selected = _selectedSpaceSlug;
    if (previous.id != widget.id ||
        previous.repository != widget.repository ||
        selected != _spaceSlug) {
      _contextRevision++;
      _spaceSlug = selected;
      _bind();
      _mode = _ProjectMode.summary;
      _lastOffset = null;
      _ignoreOlderPages = true;
      _refreshing = false;
      _loadingMore = false;
      _busy = false;
      unawaited(_acquire());
    }
  }

  @override
  void dispose() {
    widget.actorContext?.removeListener(_actorChanged);
    _search.removeListener(_changed);
    _search.dispose();
    super.dispose();
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  bool _has(Map<String, dynamic> row, String capability) =>
      row['capabilities'] is List &&
      (row['capabilities'] as List).contains(capability);
  bool get _offline =>
      SyncStatusScope.maybeOf(context)?.state == SyncVisualState.offline;
  bool get _enabled =>
      widget.api != null && !_busy && !_offline && !_refreshing && !_failed;
  String get _base => 'api/v1/objectives/projects/${widget.id}/';

  Future<void> _acquire() async {
    final repo = widget.repository;
    final id = widget.id;
    final spaceSlug = _spaceSlug;
    final revision = _contextRevision;
    try {
      final snapshot = await repo.read(
        ObjectiveDepth.project,
        id,
        spaceSlug: spaceSlug,
      );
      final source = await repo.readSource(
        ObjectiveDepth.project,
        id,
        spaceSlug: spaceSlug,
      );
      if (!mounted ||
          repo != widget.repository ||
          id != widget.id ||
          revision != _contextRevision)
        return;
      // Recheck scoped Project authority on entry even with a fresh cache.
      if (spaceSlug != null ||
          snapshot == null ||
          ObjectiveRepository.freshnessPolicy.evaluate(
                snapshot,
                now: DateTime.now().toUtc(),
                invalidated: source.invalidated,
              ) !=
              FreshnessState.fresh) {
        unawaited(_refresh());
      }
    } on Object {
      if (mounted && revision == _contextRevision) {
        setState(() => _failed = true);
      }
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final id = widget.id;
    final repo = widget.repository;
    final spaceSlug = _spaceSlug;
    final revision = _contextRevision;
    setState(() {
      _refreshing = true;
      _failed = false;
    });
    try {
      await repo.refresh(ObjectiveDepth.project, id, spaceSlug: spaceSlug);
      final source = await repo.readSource(
        ObjectiveDepth.project,
        id,
        spaceSlug: spaceSlug,
      );
      if (mounted &&
          revision == _contextRevision &&
          (source.invalidated ||
              source.lastErrorCode != null ||
              source.lastSuccessAt == null)) {
        setState(() => _failed = true);
      }
    } on Object {
      if (mounted && id == widget.id && revision == _contextRevision) {
        setState(() => _failed = true);
      }
    } finally {
      if (mounted && id == widget.id && revision == _contextRevision) {
        setState(() => _refreshing = false);
      }
    }
  }

  void _notice(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  Future<bool> _send(
    String endpoint,
    Map<String, dynamic> body, {
    bool patch = false,
  }) async {
    if (!_enabled) return false;
    final revision = _contextRevision;
    final spaceSlug = _spaceSlug;
    final destination =
        '$endpoint${ObjectiveRepository.contextQuery(spaceSlug)}';
    setState(() => _busy = true);
    try {
      if (revision != _contextRevision) return false;
      if (patch) {
        await widget.api!.patch(destination, body: body);
      } else {
        await widget.api!.post(destination, body: body);
      }
      if (revision != _contextRevision) return false;
      _ignoreOlderPages = true;
      _lastOffset = null;
      try {
        await widget.repository.refresh(
          ObjectiveDepth.project,
          widget.id,
          spaceSlug: spaceSlug,
        );
        await widget.repository.refreshOrganizerPage(0, spaceSlug: spaceSlug);
        if (spaceSlug != null) {
          try {
            await widget.repository.refreshOrganizerPage(0);
          } on Object {
            // The server-confirmed Project is fresh in its selected Space.
          }
        }
        if (revision != _contextRevision) return true;
      } on Object {
        if (mounted && revision == _contextRevision) {
          _notice(
            'Action enregistrée. Actualisez les données lorsque le réseau est disponible.',
          );
        }
        return true;
      }
      if (mounted && revision == _contextRevision) {
        _notice('Modification enregistrée.');
      }
      return true;
    } on Object {
      if (mounted && revision == _contextRevision) {
        _notice(
          'Action non confirmée. Vérifiez les permissions et la connexion.',
        );
      }
      return false;
    } finally {
      if (mounted && revision == _contextRevision) {
        setState(() => _busy = false);
      }
    }
  }

  Future<bool> _confirm(
    String title,
    String explanation,
    String action,
  ) async =>
      await showDialog<bool>(
        context: context,
        builder: (dialog) => AlertDialog(
          title: Text(title),
          content: Text(explanation),
          actions: [
            MakoloActionButton(
              label: 'Annuler',
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => Navigator.pop(dialog, false),
            ),
            MakoloActionButton(
              label: action,
              appearance: MakoloActionAppearance.primary,
              onPressed: () => Navigator.pop(dialog, true),
            ),
          ],
        ),
      ) ??
      false;

  Future<void> _create() async {
    final form = GlobalKey<FormState>();
    final title = TextEditingController(),
        description = TextEditingController();
    DateTime? deadline;
    final data = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialog) => StatefulBuilder(
        builder: (dialog, update) => AlertDialog(
          title: const Text('Créer un dossier'),
          content: Form(
            key: form,
            child: SizedBox(
              width: 420,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Le nouveau Dossier sera rattaché à ce Projet et gardera sa propre identité.',
                    ),
                    const SizedBox(height: 15),
                    TextFormField(
                      controller: title,
                      maxLength: 220,
                      decoration: const InputDecoration(
                        labelText: 'Objectif',
                        border: OutlineInputBorder(),
                      ),
                      validator: (s) => s == null || s.trim().isEmpty
                          ? 'Titre obligatoire'
                          : null,
                    ),
                    const SizedBox(height: 10),
                    TextFormField(
                      controller: description,
                      maxLines: 3,
                      decoration: const InputDecoration(
                        labelText: 'Description',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 10),
                    MakoloActionButton(
                      label: deadline == null
                          ? 'Échéance facultative'
                          : _humanDate(deadline!),
                      onPressed: () async {
                        final picked = await showDatePicker(
                          context: dialog,
                          initialDate: deadline ?? DateTime.now(),
                          firstDate: DateTime(1900),
                          lastDate: DateTime(2100),
                        );
                        if (picked != null) update(() => deadline = picked);
                      },
                      appearance: MakoloActionAppearance.secondary,
                      icon: Icons.event_outlined,
                    ),
                    if (deadline != null)
                      MakoloActionButton(
                        label: 'Effacer l’échéance',
                        appearance: MakoloActionAppearance.quiet,
                        onPressed: () => update(() => deadline = null),
                      ),
                  ],
                ),
              ),
            ),
          ),
          actions: [
            MakoloActionButton(
              label: 'Annuler',
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => Navigator.pop(dialog),
            ),
            MakoloActionButton(
              label: 'Créer et rattacher',
              onPressed: () {
                if (!(form.currentState?.validate() ?? false)) return;
                Navigator.pop(dialog, <String, dynamic>{
                  'action': 'create',
                  'title': title.text.trim(),
                  'description': description.text.trim(),
                  if (deadline != null) 'deadline': _iso(deadline),
                });
              },
              appearance: MakoloActionAppearance.primary,
            ),
          ],
        ),
      ),
    );
    title.dispose();
    description.dispose();
    if (data != null && mounted) await _send('${_base}dossiers/', data);
  }

  Future<void> _link(Map<String, dynamic> project) async {
    final candidates = _list(project['link_candidates']);
    if (candidates.isEmpty) {
      _notice('Aucun Dossier indépendant disponible dans cette liste.');
      return;
    }
    final id = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (sheet) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const ListTile(
              title: Text('Rattacher un dossier existant'),
              subtitle: Text(
                'Seuls les dossiers autorisés et indépendants apparaissent.',
              ),
            ),
            if (project['link_candidates_partial'] == true)
              const ListTile(
                subtitle: Text(
                  'Choix partiels : d’autres dossiers peuvent exister.',
                ),
              ),
            for (final row in candidates)
              ListTile(
                leading: const Icon(Icons.folder_outlined),
                title: Text(_text(row['title'])),
                trailing: const Icon(Icons.add_rounded),
                onTap: () => Navigator.pop(sheet, _text(row['id'])),
              ),
          ],
        ),
      ),
    );
    if (id != null && mounted) {
      await _send('${_base}dossiers/', {'action': 'link', 'dossier_id': id});
    }
  }

  Future<void> _manageDossier(
    Map<String, dynamic> row,
    Map<String, dynamic> project,
    String action,
  ) async {
    final id = _text(row['id']);
    if (id.isEmpty || !_enabled) return;
    if (action == 'unlink') {
      final yes = await _confirm(
        'Détacher ce dossier ?',
        'Il restera disponible indépendamment, sans suppression.',
        'Détacher',
      );
      if (yes) await _send('${_base}dossiers/$id/', {'action': 'unlink'});
    } else {
      final targets = _list(project['move_targets']);
      if (targets.isEmpty) {
        _notice('Aucun Projet cible disponible.');
        return;
      }
      final selected = await showModalBottomSheet<String>(
        context: context,
        builder: (sheet) => SafeArea(
          child: ListView(
            shrinkWrap: true,
            children: [
              const ListTile(title: Text('Déplacer vers un Projet autorisé')),
              for (final target in targets)
                ListTile(
                  leading: const Icon(Icons.folder_special_outlined),
                  title: Text(_text(target['title'])),
                  onTap: () => Navigator.pop(sheet, _text(target['id'])),
                ),
            ],
          ),
        ),
      );
      if (selected == null || !mounted) return;
      final yes = await _confirm(
        'Déplacer ce dossier ?',
        'Le Dossier quittera son Projet actuel mais conservera ses démarches.',
        'Déplacer',
      );
      if (yes) {
        await _send('${_base}dossiers/$id/', {
          'action': 'move',
          'target_project_id': selected,
        });
      }
    }
  }

  Future<void> _lifecycle(Map<String, dynamic> project) async {
    final changes = project['allowed_transitions'] is List
        ? project['allowed_transitions'] as List
        : const [];
    if (changes.isEmpty) {
      _notice('Aucune transition disponible.');
      return;
    }
    final chosen = await showModalBottomSheet<String>(
      context: context,
      builder: (sheet) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const ListTile(title: Text('Changer l’état du Projet')),
            for (final code in changes)
              ListTile(
                title: Text(_humanState(code)),
                onTap: () => Navigator.pop(sheet, _text(code)),
              ),
          ],
        ),
      ),
    );
    if (chosen == null || !mounted) return;
    final yes = await _confirm(
      'Changer l’état du Projet ?',
      'Chaque Dossier conserve son état propre.',
      'Confirmer',
    );
    if (yes) await _send('${_base}lifecycle/', {'lifecycle': chosen});
  }

  Future<void> _edit(Map<String, dynamic> project) async {
    final horizon = _map(project['horizon']);
    final title = TextEditingController(text: _text(horizon['title']));
    final description = TextEditingController(
      text: _text(horizon['description']),
    );
    final form = GlobalKey<FormState>();
    DateTime? start = _dateFrom(horizon['starts_on']);
    DateTime? end = _dateFrom(horizon['ends_on']);
    final values = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialog) => StatefulBuilder(
        builder: (dialog, update) => AlertDialog(
          title: const Text('Modifier le Projet'),
          content: Form(
            key: form,
            child: SizedBox(
              width: 420,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextFormField(
                      controller: title,
                      maxLength: 220,
                      decoration: const InputDecoration(
                        labelText: 'Titre',
                        border: OutlineInputBorder(),
                      ),
                      validator: (s) =>
                          s == null || s.trim().isEmpty ? 'Titre requis' : null,
                    ),
                    TextFormField(
                      controller: description,
                      maxLines: 3,
                      decoration: const InputDecoration(
                        labelText: 'Description',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    for (final isStart in [true, false])
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              isStart
                                  ? 'Début : ${start == null ? 'non défini' : _humanDate(start!)}'
                                  : 'Fin : ${end == null ? 'non définie' : _humanDate(end!)}',
                            ),
                          ),
                          MakoloIconActionButton(
                            tooltip: 'Choisir une date',
                            icon: Icons.calendar_month_outlined,
                            onPressed: () async {
                              final picked = await showDatePicker(
                                context: dialog,
                                initialDate:
                                    (isStart ? start : end) ?? DateTime.now(),
                                firstDate: DateTime(1900),
                                lastDate: DateTime(2100),
                              );
                              if (picked != null) {
                                update(() {
                                  if (isStart) {
                                    start = picked;
                                  } else {
                                    end = picked;
                                  }
                                });
                              }
                            },
                          ),
                          MakoloIconActionButton(
                            tooltip: 'Effacer cette date',
                            icon: Icons.close_rounded,
                            onPressed: () => update(() {
                              if (isStart) {
                                start = null;
                              } else {
                                end = null;
                              }
                            }),
                          ),
                        ],
                      ),
                  ],
                ),
              ),
            ),
          ),
          actions: [
            MakoloActionButton(
              label: 'Annuler',
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => Navigator.pop(dialog),
            ),
            MakoloActionButton(
              label: 'Enregistrer',
              onPressed: () {
                if (!(form.currentState?.validate() ?? false)) return;
                if (start != null && end != null && start!.isAfter(end!)) {
                  ScaffoldMessenger.of(dialog).showSnackBar(
                    const SnackBar(
                      content: Text('La fin ne peut pas précéder le début.'),
                    ),
                  );
                  return;
                }
                Navigator.pop(dialog, <String, dynamic>{
                  'title': title.text.trim(),
                  'description': description.text.trim(),
                  'starts_on': _iso(start),
                  'ends_on': _iso(end),
                });
              },
              appearance: MakoloActionAppearance.primary,
            ),
          ],
        ),
      ),
    );
    title.dispose();
    description.dispose();
    if (values != null && mounted) await _send(_base, values, patch: true);
  }

  Future<void> _more(int offset) async {
    if (_loadingMore || _lastOffset == offset) return;
    final revision = _contextRevision;
    final spaceSlug = _spaceSlug;
    _lastOffset = offset;
    setState(() => _loadingMore = true);
    try {
      await widget.repository.refreshProjectDossiers(
        widget.id,
        offset,
        spaceSlug: spaceSlug,
      );
      if (mounted && revision == _contextRevision) {
        setState(() => _ignoreOlderPages = false);
      }
    } on Object {
      if (mounted && revision == _contextRevision) {
        _lastOffset = null;
        setState(() => _failed = true);
        _notice('Suite indisponible. Actualisez pour réessayer.');
      }
    } finally {
      if (mounted && revision == _contextRevision) {
        setState(() => _loadingMore = false);
      }
    }
  }

  (List<Map<String, dynamic>>, bool, int) _dossiers(
    Map<String, dynamic> project,
    List<StoredProjection> cached,
    DateTime projectReceivedAt,
  ) {
    final first = _list(project['visible_dossiers']);
    final page = _map(project['dossiers_page']);
    final rows = <Map<String, dynamic>>[...first];
    final seen = first.map((row) => _text(row['id'])).toSet();
    var offset = page['next_offset'] is int
        ? page['next_offset'] as int
        : first.length;
    var more = page['has_more'] == true;
    if (!_ignoreOlderPages && more) {
      // A refreshed owner detail supersedes older continuation windows.
      // Never merge cached Dossiers from before a possible permission change.
      final fragments =
          cached
              .where(
                (item) =>
                    !item.receivedAt.isBefore(projectReceivedAt) &&
                    item.payload['project_id']?.toString() == widget.id &&
                    _map(item.payload['actor'])['id']?.toString() ==
                        widget.repository.profileId &&
                    (_spaceSlug == null
                        ? _map(item.payload['actor_context'])['kind'] != 'space'
                        : _map(item.payload['actor_context'])['kind'] ==
                                  'space' &&
                              _map(
                                    _map(
                                      item.payload['actor_context'],
                                    )['space'],
                                  )['slug'] ==
                                  _spaceSlug),
              )
              .toList()
            ..sort(
              (a, b) =>
                  (_map(a.payload['page'])['offset'] is int
                          ? _map(a.payload['page'])['offset'] as int
                          : 0)
                      .compareTo(
                        _map(b.payload['page'])['offset'] is int
                            ? _map(b.payload['page'])['offset'] as int
                            : 0,
                      ),
            );
      for (final fragment in fragments) {
        final nextPage = _map(fragment.payload['page']);
        if (!more || nextPage['offset'] != offset) break;
        for (final row in _list(fragment.payload['items'])) {
          if (seen.add(_text(row['id']))) rows.add(row);
        }
        if (nextPage['next_offset'] is! int ||
            nextPage['next_offset'] <= offset) {
          break;
        }
        offset = nextPage['next_offset'] as int;
        more = nextPage['has_more'] == true;
      }
    }
    return (rows, more, offset);
  }

  List<Map<String, dynamic>> _sorted(List<Map<String, dynamic>> rows) {
    final query = _search.text.trim().toLowerCase();
    final output = rows
        .where(
          (row) =>
              (_stateFilter == 'all' || row['state'] == _stateFilter) &&
              (_readinessFilter == 'all' ||
                  _map(row['readiness'])['state'] == _readinessFilter) &&
              (query.isEmpty ||
                  '${_text(row['title'])} ${_text(row['description'])}'
                      .toLowerCase()
                      .contains(query)),
        )
        .toList();
    String value(Map<String, dynamic> row) => switch (_sort) {
      _ProjectSort.title => _text(row['title']).toLowerCase(),
      _ProjectSort.deadline => _text(row['deadline']),
      _ProjectSort.state => _text(row['state']),
      _ProjectSort.created => _text(row['created_at']),
      _ProjectSort.updated => _text(row['updated_at']),
    };
    output.sort((a, b) {
      final first = value(a), second = value(b);
      if (first.isEmpty && second.isNotEmpty) return 1;
      if (second.isEmpty && first.isNotEmpty) return -1;
      return first.compareTo(second);
    });
    return output;
  }

  Future<void> _grantProjectAccess(Map<String, dynamic> project) async {
    final collaboration = _map(project['collaboration']);
    final roles = _list(collaboration['roles']);
    final candidates = _list(collaboration['candidate_profiles']);
    if (roles.isEmpty) return;
    final email = TextEditingController();
    final form = GlobalKey<FormState>();
    String roleCode = _text(roles.first['code']);
    String? profileId;
    final values = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialog) => StatefulBuilder(
        builder: (dialog, update) => AlertDialog(
          title: const Text('Donner accès au Projet'),
          content: Form(
            key: form,
            child: SizedBox(
              width: 420,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Un rôle Projet ne donne pas automatiquement accès aux '
                      'Dossiers ni aux démarches associées.',
                    ),
                    const SizedBox(height: 12),
                    if (candidates.isNotEmpty) ...[
                      const Text('Personnes déjà connues dans les Dossiers'),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: [
                          for (final candidate in candidates)
                            ChoiceChip(
                              label: Text(_text(candidate['label'])),
                              selected: profileId == _text(candidate['id']),
                              onSelected: (_) => update(() {
                                profileId = _text(candidate['id']);
                                email.clear();
                              }),
                            ),
                        ],
                      ),
                      if (collaboration['candidate_profiles_partial'] == true)
                        const Text('Cette liste de personnes est partielle.'),
                      const SizedBox(height: 12),
                    ],
                    TextFormField(
                      controller: email,
                      decoration: const InputDecoration(
                        labelText: 'Ou adresse e-mail Makolo exacte',
                        border: OutlineInputBorder(),
                      ),
                      keyboardType: TextInputType.emailAddress,
                      onChanged: (value) {
                        if (value.isNotEmpty) update(() => profileId = null);
                      },
                      validator: (value) =>
                          profileId == null &&
                              (value == null || !value.contains('@'))
                          ? 'Choisissez une personne ou indiquez son e-mail'
                          : null,
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: roleCode,
                      isExpanded: true,
                      decoration: const InputDecoration(labelText: 'Rôle'),
                      items: [
                        for (final role in roles)
                          DropdownMenuItem<String>(
                            value: _text(role['code']),
                            child: Text(_text(role['label'])),
                          ),
                      ],
                      onChanged: (value) {
                        if (value != null) update(() => roleCode = value);
                      },
                    ),
                  ],
                ),
              ),
            ),
          ),
          actions: [
            MakoloActionButton(
              label: 'Annuler',
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => Navigator.pop(dialog),
            ),
            MakoloActionButton(
              label: 'Accorder',
              appearance: MakoloActionAppearance.primary,
              onPressed: () {
                if (!(form.currentState?.validate() ?? false)) return;
                Navigator.pop(dialog, <String, dynamic>{
                  'action': 'grant',
                  'role_code': roleCode,
                  if (profileId != null) 'profile_id': profileId,
                  if (profileId == null) 'email': email.text.trim(),
                });
              },
            ),
          ],
        ),
      ),
    );
    email.dispose();
    if (values != null && mounted) await _send('${_base}authority/', values);
  }

  Future<void> _projectAccess(Map<String, dynamic> project) async {
    final owner = _map(project['owner']);
    final collaboration = _map(project['collaboration']);
    final members = _list(collaboration['members']);
    final contributors = _list(collaboration['contributors']);
    final manage = collaboration['can_manage_authority'] == true;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 20),
          children: [
            Text(
              'Personnes et accès',
              style: Theme.of(sheet).textTheme.titleLarge,
            ),
            const SizedBox(height: 10),
            ListTile(
              leading: owner['kind'] == 'profile'
                  ? _projectAvatar({
                      'label': owner['holder'],
                      'avatar_url': owner['avatar_url'],
                      'profile_view': owner['profile_view'],
                      'profile_id': owner['id'],
                    }, interactive: false)
                  : const Icon(Icons.groups_2_outlined),
              title: Text(
                _text(
                  owner['kind'] == 'space' ? owner['label'] : owner['holder'],
                ),
              ),
              subtitle: const Text('Porteur'),
              onTap:
                  owner['kind'] == 'profile' &&
                      _canOpenProjectPerson({
                        'profile_view': owner['profile_view'],
                      })
                  ? () {
                      Navigator.pop(sheet);
                      _openProjectPerson({
                        'profile_view': owner['profile_view'],
                        'profile_id': owner['id'],
                      });
                    }
                  : null,
            ),
            if (members.isNotEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('Accès délégués'),
              ),
            for (final member in members)
              ListTile(
                leading: _projectAvatar(member, interactive: false),
                title: Text(_text(member['label'])),
                subtitle: Text(_text(member['role'])),
                onTap: _canOpenProjectPerson(member)
                    ? () {
                        Navigator.pop(sheet);
                        _openProjectPerson(member);
                      }
                    : null,
                trailing: _has(member, 'revoke') && manage
                    ? PopupMenuButton<String>(
                        tooltip: 'Gérer le rôle',
                        enabled: _enabled,
                        onSelected: (value) async {
                          Navigator.pop(sheet);
                          if (value == 'replace') {
                            await _changeProjectRole(project, member);
                            return;
                          }
                          final yes = await _confirm(
                            'Retirer cet accès ?',
                            'Ce mandat Projet sera révoqué.',
                            'Révoquer',
                          );
                          if (yes && mounted) {
                            await _send('${_base}authority/', {
                              'action': 'revoke',
                              'mandate_id': _text(member['id']),
                            });
                          }
                        },
                        itemBuilder: (_) => const [
                          PopupMenuItem(
                            value: 'replace',
                            child: Text('Changer le rôle'),
                          ),
                          PopupMenuItem(
                            value: 'revoke',
                            child: Text('Retirer l’accès'),
                          ),
                        ],
                      )
                    : null,
              ),
            if (contributors.isNotEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('Interventions visibles'),
              ),
            for (final contributor in contributors)
              ListTile(
                leading: _projectAvatar(contributor, interactive: false),
                title: Text(_text(contributor['label'])),
                subtitle: const Text('Intervention visible'),
                onTap: _canOpenProjectPerson(contributor)
                    ? () {
                        Navigator.pop(sheet);
                        _openProjectPerson(contributor);
                      }
                    : null,
              ),
            if (collaboration['contributors_partial'] == true)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: Text('Interventions visibles uniquement.'),
              ),
            if (manage)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: MakoloActionButton(
                  label: 'Donner accès',
                  appearance: MakoloActionAppearance.primary,
                  icon: Icons.person_add_alt_1_outlined,
                  onPressed: _enabled
                      ? () {
                          Navigator.pop(sheet);
                          _grantProjectAccess(project);
                        }
                      : null,
                ),
              ),
          ],
        ),
      ),
    );
  }

  void _openProjectPerson(Map<String, dynamic> person) {
    if (_text(person['profile_view']) == 'self') {
      widget.onOpenMyPassport?.call();
    } else if (_text(person['profile_view']) == 'public') {
      final id = _text(person['profile_id']);
      if (id.isNotEmpty) widget.onOpenPerson?.call(id);
    }
  }

  bool _canOpenProjectPerson(Map<String, dynamic> person) =>
      (_text(person['profile_view']) == 'self' &&
          widget.onOpenMyPassport != null) ||
      (_text(person['profile_view']) == 'public' &&
          widget.onOpenPerson != null);

  ImageProvider<Object>? _projectPhoto(Map<String, dynamic> person) {
    final raw = _text(person['avatar_url']);
    if (raw.isEmpty) return null;
    final input = Uri.tryParse(raw);
    if (input == null) return null;
    final uri = input.hasScheme ? input : widget.api?.baseUri.resolveUri(input);
    if (uri == null ||
        !['https', 'http'].contains(uri.scheme) ||
        uri.host.isEmpty)
      return null;
    return NetworkImage(uri.toString());
  }

  Widget _projectAvatar(
    Map<String, dynamic> person, {
    bool interactive = true,
  }) {
    final label = _text(person['label']);
    final image = _projectPhoto(person);
    final scheme = Theme.of(context).colorScheme;
    final avatar = CircleAvatar(
      radius: 18,
      backgroundColor: scheme.primaryContainer,
      foregroundImage: image,
      // Initials remain the fallback if the public image fails to load.
      child: Text(
        _initials(label),
        style: TextStyle(
          color: scheme.onPrimaryContainer,
          fontWeight: FontWeight.w700,
          fontSize: 11,
        ),
      ),
    );
    return Tooltip(
      message: interactive && _canOpenProjectPerson(person)
          ? 'Voir le Profil de $label'
          : label,
      child: interactive && _canOpenProjectPerson(person)
          ? Semantics(
              button: true,
              label: 'Voir le Profil de $label',
              child: InkWell(
                borderRadius: BorderRadius.circular(22),
                onTap: () => _openProjectPerson(person),
                child: Padding(padding: const EdgeInsets.all(4), child: avatar),
              ),
            )
          : Padding(padding: const EdgeInsets.all(4), child: avatar),
    );
  }

  Future<void> _changeProjectRole(
    Map<String, dynamic> project,
    Map<String, dynamic> member,
  ) async {
    final roles = _list(_map(project['collaboration'])['roles']);
    if (roles.isEmpty) return;
    final selected = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (dialog) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const ListTile(title: Text('Changer le rôle')),
            for (final role in roles)
              ListTile(
                title: Text(_text(role['label'])),
                selected: _text(role['code']) == _text(member['role_code']),
                trailing: _text(role['code']) == _text(member['role_code'])
                    ? const Icon(Icons.check_rounded)
                    : null,
                onTap: () => Navigator.pop(dialog, _text(role['code'])),
              ),
          ],
        ),
      ),
    );
    if (!mounted || selected == null || selected == _text(member['role_code']))
      return;
    await _send('${_base}authority/', {
      'action': 'replace',
      'mandate_id': _text(member['id']),
      'role_code': selected,
    });
  }

  String _initials(String label) {
    final words = label.trim().split(RegExp(r'\s+'));
    if (words.isEmpty || label.trim().isEmpty) return '?';
    return words.take(2).map((word) => word[0].toUpperCase()).join();
  }

  Widget _peoplePreview(Map<String, dynamic> project) {
    final owner = _map(project['owner']);
    final collaboration = _map(project['collaboration']);
    final members = _list(collaboration['members']);
    final people = <Map<String, dynamic>>[];
    if (owner['kind'] == 'profile' && _text(owner['holder']).isNotEmpty) {
      people.add({
        'profile_id': owner['id'],
        'label': owner['holder'],
        'profile_view': owner['profile_view'],
        'avatar_url': owner['avatar_url'],
      });
    }
    for (final member in members) {
      if (!people.any(
        (person) => person['profile_id'] == member['profile_id'],
      )) {
        people.add(member);
      }
    }
    final shown = people.take(4).toList();
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3, horizontal: 2),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(Icons.people_outline_rounded, color: scheme.primary),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Personnes et accès',
                  style: Theme.of(context).textTheme.titleMedium
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
              TextButton.icon(
                onPressed: () => _projectAccess(project),
                iconAlignment: IconAlignment.end,
                icon: const Icon(Icons.chevron_right_rounded, size: 19),
                label: const Text('Voir'),
              ),
            ],
          ),
          const SizedBox(height: 2),
          Row(
            children: [
              if (owner['kind'] == 'space') ...[
                CircleAvatar(
                  radius: 18,
                  backgroundColor: scheme.primaryContainer,
                  child: Icon(
                    Icons.groups_2_outlined,
                    color: scheme.onPrimaryContainer,
                    size: 18,
                  ),
                ),
                const SizedBox(width: 6),
              ],
              for (final person in shown) _projectAvatar(person),
              IconButton(
                tooltip: 'Voir toutes les personnes et accès',
                onPressed: () => _projectAccess(project),
                icon: const Icon(Icons.add_rounded, size: 20),
                style: IconButton.styleFrom(
                  backgroundColor: scheme.surfaceContainerHighest,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// The only Project actions menu lives in the top bar. The owner
  /// capabilities (never actor context labels) decide its entries.
  Widget _projectTopActions(Map<String, dynamic> project) {
    final actions = [
      if (_has(project, 'project.dossier.link')) 'link',
      if (_has(project, 'project.edit')) 'edit',
      if (_has(project, 'project.lifecycle')) 'lifecycle',
    ];
    if (actions.isEmpty) return const SizedBox.shrink();
    return PopupMenuButton<String>(
      tooltip: 'Actions du Projet',
      enabled: _enabled,
      icon: const Icon(Icons.more_vert_rounded),
      onSelected: (choice) {
        switch (choice) {
          case 'link':
            _link(project);
          case 'edit':
            _edit(project);
          case 'lifecycle':
            _lifecycle(project);
        }
      },
      itemBuilder: (_) => [
        if (actions.contains('link'))
          const PopupMenuItem(
            value: 'link',
            child: ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: Icon(Icons.folder_open_outlined),
              title: Text('Rattacher un dossier'),
            ),
          ),
        if (actions.contains('edit'))
          const PopupMenuItem(
            value: 'edit',
            child: ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: Icon(Icons.edit_outlined),
              title: Text('Modifier le Projet'),
            ),
          ),
        if (actions.contains('lifecycle'))
          const PopupMenuItem(
            value: 'lifecycle',
            child: ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: Icon(Icons.sync_alt_rounded),
              title: Text('Changer l’état'),
            ),
          ),
      ],
    );
  }

  Widget _header(Map<String, dynamic> project) {
    final horizon = _map(project['horizon']);
    final start = _dateFrom(horizon['starts_on']);
    final end = _dateFrom(horizon['ends_on']);
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(11),
                color: theme.colorScheme.primary.withValues(alpha: .08),
              ),
              child: Icon(
                Icons.folder_special_outlined,
                size: 21,
                color: theme.colorScheme.primary,
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _text(horizon['title']),
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    _humanState(_map(project['state'])['code']),
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            if (widget.conversations != null &&
                widget.onOpenConversation != null)
              ConversationContextAction(
                repository: widget.conversations!,
                kind: 'project',
                contextId: widget.id,
                onOpen: widget.onOpenConversation!,
                iconOnly: true,
              ),
          ],
        ),
        if (start != null || end != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              [
                if (start != null) 'Début : ${_humanDate(start)}',
                if (end != null) 'Fin : ${_humanDate(end)}',
              ].join(' · '),
              style: theme.textTheme.bodySmall,
            ),
          ),
      ],
    );
  }

  Widget _tabs(Map<String, dynamic> project) => Row(
    children: [
      Expanded(
        child: ObjectiveWorkspaceViewSwitcher<_ProjectMode>(
          selected: _mode,
          options: const [
            ObjectiveViewOption(
              _ProjectMode.summary,
              Icons.dashboard_outlined,
              'Synthèse',
            ),
            ObjectiveViewOption(
              _ProjectMode.dossiers,
              Icons.folder_copy_outlined,
              'Dossiers',
            ),
            ObjectiveViewOption(
              _ProjectMode.calendar,
              Icons.calendar_month_outlined,
              'Calendrier',
            ),
          ],
          onSelected: (mode) => setState(() => _mode = mode),
        ),
      ),
      if (_has(project, 'project.dossier.create')) ...[
        const SizedBox(width: 8),
        IconButton.filledTonal(
          tooltip: 'Créer un dossier',
          onPressed: _enabled ? _create : null,
          icon: const Icon(Icons.create_new_folder_outlined, size: 21),
          style: IconButton.styleFrom(
            minimumSize: const Size(44, 44),
            maximumSize: const Size(44, 44),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        ),
      ],
    ],
  );

  Widget _dossierCard(Map<String, dynamic> row, Map<String, dynamic> project) {
    final readiness = _map(row['readiness']);
    final date = _dateFrom(row['deadline']);
    final scheme = Theme.of(context).colorScheme;
    final canOrganize = _has(row, 'unlink') || _has(row, 'move');
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 5),
      shape: RoundedRectangleBorder(
        side: BorderSide(color: scheme.outlineVariant),
        borderRadius: BorderRadius.circular(13),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
        child: Row(
          children: [
            Icon(Icons.folder_outlined, color: scheme.primary, size: 23),
            const SizedBox(width: 7),
            Expanded(
              child: InkWell(
                onTap: () => widget.onOpenDossier(_text(row['id'])),
                borderRadius: BorderRadius.circular(8),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _text(row['title']),
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                          decoration: TextDecoration.none,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        [
                          _humanState(row['state']),
                          if (date != null) 'Échéance ${_humanDate(date)}',
                        ].join(' · '),
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      if (_text(readiness['label']).isNotEmpty)
                        Text(
                          '${_text(readiness['label'])}'
                          '${readiness['partial'] == true ? ' · vue partielle' : ''}',
                          style: Theme.of(context).textTheme.bodySmall
                              ?.copyWith(color: scheme.primary),
                        ),
                    ],
                  ),
                ),
              ),
            ),
            if (canOrganize)
              PopupMenuButton<String>(
                tooltip: 'Organiser le Dossier',
                enabled: _enabled,
                itemBuilder: (_) => [
                  if (_has(row, 'unlink'))
                    const PopupMenuItem(
                      value: 'unlink',
                      child: Text('Détacher'),
                    ),
                  if (_has(row, 'move') &&
                      _list(project['move_targets']).isNotEmpty)
                    const PopupMenuItem(value: 'move', child: Text('Déplacer')),
                ],
                onSelected: (value) => _manageDossier(row, project, value),
              )
            else
              const Icon(Icons.chevron_right_rounded, size: 19),
          ],
        ),
      ),
    );
  }

  Widget _empty(String message) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 14),
    child: Text(message, style: Theme.of(context).textTheme.bodyMedium),
  );

  Widget _summary(
    Map<String, dynamic> project,
    List<Map<String, dynamic>> rows,
    bool partial,
  ) {
    final active = rows.where((r) => r['state'] == 'active').length;
    final draft = rows.where((r) => r['state'] == 'draft').length;
    final done = rows.where((r) => r['state'] == 'completed').length;
    final dated = rows.where((r) => _dateFrom(r['deadline']) != null).toList()
      ..sort((a, b) => _text(a['deadline']).compareTo(_text(b['deadline'])));
    final today = DateTime.now();
    final midnight = DateTime(today.year, today.month, today.day);
    final next = dated
        .where((r) => !_dateFrom(r['deadline'])!.isBefore(midnight))
        .toList();
    final intervention = rows
        .where((r) => _map(r['readiness'])['state'] == 'action_required')
        .take(2)
        .toList();
    // Summary = useful next steps + a complementary glimpse, not a repeated
    // rendering of the same Dossiers already shown under "À suivre".
    final followIds = intervention.map((row) => _text(row['id'])).toSet();
    final preview = rows
        .where((row) => !followIds.contains(_text(row['id'])))
        .take(3)
        .toList();
    final indicators = <(int, String)>[
      if (rows.isNotEmpty) (rows.length, 'dossiers'),
      if (active > 0) (active, 'en cours'),
      if (draft > 0) (draft, 'à préparer'),
      if (done > 0) (done, 'terminés'),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (partial)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Text(
              'Dossiers chargés uniquement.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        if (indicators.isNotEmpty)
          Semantics(
            label: indicators.map((v) => '${v.$1} ${v.$2}').join(', '),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  for (var index = 0; index < indicators.length; index++) ...[
                    if (index > 0)
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 9),
                        child: Text(
                          '·',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                      ),
                    _metric(indicators[index].$1, indicators[index].$2),
                  ],
                ],
              ),
            ),
          ),
        if (next.isNotEmpty)
          ListTile(
            leading: const Icon(Icons.event_outlined),
            title: const Text('Prochaine échéance visible'),
            subtitle: Text(
              '${_text(next.first['title'])} · '
              '${_humanDate(_dateFrom(next.first['deadline'])!)}',
            ),
            onTap: () => widget.onOpenDossier(_text(next.first['id'])),
          ),
        if (intervention.isNotEmpty) ...[
          const SizedBox(height: 9),
          Text(
            'À suivre',
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          for (final row in intervention)
            ListTile(
              dense: true,
              contentPadding: const EdgeInsets.symmetric(horizontal: 2),
              visualDensity: VisualDensity.compact,
              leading: Icon(
                Icons.error_outline_rounded,
                size: 20,
                color: Theme.of(context).colorScheme.primary,
              ),
              title: Text(
                _text(row['title']),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(decoration: TextDecoration.none),
              ),
              subtitle: Text(
                _text(_map(row['readiness'])['hidden_signal']).isNotEmpty
                    ? _text(_map(row['readiness'])['hidden_signal'])
                    : 'Action requise',
              ),
              trailing: const Icon(Icons.chevron_right_rounded, size: 18),
              onTap: () => widget.onOpenDossier(_text(row['id'])),
            ),
        ],
        if (rows.isEmpty)
          _empty('Aucun dossier visible pour le moment.')
        else ...[
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Dossiers',
                  style: Theme.of(context).textTheme.titleMedium
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
              TextButton(
                onPressed: () => setState(() => _mode = _ProjectMode.dossiers),
                child: const Text('Voir tout'),
              ),
            ],
          ),
          for (final row in preview) _dossierCard(row, project),
        ],
      ],
    );
  }

  Widget _metric(int count, String title) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Text(
        '$count',
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.w800,
          color: Theme.of(context).colorScheme.primary,
        ),
      ),
      const SizedBox(width: 4),
      Text(title, style: Theme.of(context).textTheme.labelSmall),
    ],
  );

  Widget _filter(
    String title,
    String selected,
    Map<String, String> choices,
    ValueChanged<String> onSelected,
  ) => PopupMenuButton<String>(
    tooltip: title,
    initialValue: selected,
    onSelected: onSelected,
    icon: Icon(
      title == 'Tri'
          ? Icons.sort_rounded
          : title == 'État'
          ? Icons.filter_alt_outlined
          : Icons.rule_outlined,
      color: selected == 'all' || (title == 'Tri' && selected == 'deadline')
          ? Theme.of(context).colorScheme.onSurfaceVariant
          : Theme.of(context).colorScheme.primary,
    ),
    itemBuilder: (_) => [
      for (final item in choices.entries)
        CheckedPopupMenuItem(
          value: item.key,
          checked: selected == item.key,
          child: Text(item.value),
        ),
    ],
  );

  Widget _dossierList(
    Map<String, dynamic> project,
    List<Map<String, dynamic>> rows,
  ) {
    final filtered = _sorted(rows);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          controller: _search,
          decoration: InputDecoration(
            prefixIcon: const Icon(Icons.search),
            hintText: 'Rechercher un dossier',
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(13)),
            suffixIcon: _search.text.isEmpty
                ? null
                : MakoloIconActionButton(
                    tooltip: 'Effacer la recherche',
                    icon: Icons.close_rounded,
                    onPressed: _search.clear,
                  ),
          ),
        ),
        const SizedBox(height: 11),
        Wrap(
          spacing: 7,
          runSpacing: 7,
          children: [
            _filter('État', _stateFilter, const {
              'all': 'Tous les états',
              'draft': 'En préparation',
              'active': 'En cours',
              'completed': 'Terminé',
              'cancelled': 'Annulé',
              'archived': 'Archivé',
            }, (v) => setState(() => _stateFilter = v)),
            _filter('Situation', _readinessFilter, const {
              'all': 'Toutes situations',
              'blocked': 'Bloqué',
              'action_required': 'Action requise',
              'waiting': 'En attente',
              'ready': 'Prêt',
              'complete': 'Terminé',
            }, (v) => setState(() => _readinessFilter = v)),
            _filter(
              'Tri',
              _sort.name,
              const {
                'title': 'Nom',
                'deadline': 'Échéance',
                'state': 'État',
                'created': 'Création',
                'updated': 'Modification',
              },
              (v) => setState(
                () =>
                    _sort = _ProjectSort.values.firstWhere((s) => s.name == v),
              ),
            ),
            ObjectiveFilterReset(
              active:
                  _search.text.trim().isNotEmpty ||
                  _stateFilter != 'all' ||
                  _readinessFilter != 'all' ||
                  _sort != _ProjectSort.deadline,
              onClear: () {
                _search.clear();
                setState(() {
                  _stateFilter = 'all';
                  _readinessFilter = 'all';
                  _sort = _ProjectSort.deadline;
                });
              },
            ),
          ],
        ),
        const SizedBox(height: 13),
        if (filtered.isNotEmpty &&
            (_search.text.trim().isNotEmpty ||
                _stateFilter != 'all' ||
                _readinessFilter != 'all'))
          Text(
            '${filtered.length} résultat${filtered.length > 1 ? 's' : ''}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        const SizedBox(height: 10),
        if (filtered.isEmpty)
          _empty(
            rows.isEmpty
                ? 'Aucun Dossier visible parmi les éléments chargés.'
                : 'Aucun Dossier chargé ne correspond à ces critères.',
          )
        else
          for (final row in filtered) _dossierCard(row, project),
      ],
    );
  }

  Widget _calendar(
    Map<String, dynamic> project,
    List<Map<String, dynamic>> rows,
  ) {
    final horizon = _map(project['horizon']);
    final start = _dateFrom(horizon['starts_on']),
        end = _dateFrom(horizon['ends_on']);
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final milestones =
        rows.where((row) {
          final deadline = _dateFrom(row['deadline']);
          final day = deadline == null
              ? null
              : DateTime(deadline.year, deadline.month, deadline.day);
          return switch (_time) {
            _ProjectTime.all => day != null,
            _ProjectTime.next30 =>
              day != null &&
                  !day.isBefore(today) &&
                  !day.isAfter(today.add(const Duration(days: 30))),
            _ProjectTime.overdue =>
              day != null && day.isBefore(today) && row['state'] == 'active',
            _ProjectTime.undated => day == null,
            _ProjectTime.active => day != null && row['state'] == 'active',
          };
        }).toList()..sort((a, b) {
          final aDate = _text(a['deadline']), bDate = _text(b['deadline']);
          if (aDate.isEmpty && bDate.isNotEmpty) return 1;
          if (bDate.isEmpty && aDate.isNotEmpty) return -1;
          return aDate.compareTo(bDate);
        });
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (start != null || end != null)
          Card(
            elevation: 0,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Horizon du Projet',
                    style: Theme.of(context).textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    [
                      if (start != null) 'Début : ${_humanDate(start)}',
                      if (end != null) 'Fin : ${_humanDate(end)}',
                    ].join(' · '),
                  ),
                  if (start != null && end != null && end.isAfter(start))
                    Padding(
                      padding: const EdgeInsets.only(top: 15),
                      child: _track(start, end, rows),
                    ),
                ],
              ),
            ),
          ),
        Row(
          children: [
            PopupMenuButton<_ProjectTime>(
              tooltip: 'Filtrer les jalons',
              initialValue: _time,
              icon: Icon(
                Icons.filter_alt_outlined,
                color: _time == _ProjectTime.all
                    ? Theme.of(context).colorScheme.onSurfaceVariant
                    : Theme.of(context).colorScheme.primary,
              ),
              onSelected: (mode) => setState(() => _time = mode),
              itemBuilder: (_) => [
                for (final (mode, label) in [
                  (_ProjectTime.all, 'Tous'),
                  (_ProjectTime.next30, '30 prochains jours'),
                  (_ProjectTime.overdue, 'En retard'),
                  (_ProjectTime.undated, 'Sans date'),
                  (_ProjectTime.active, 'Dossiers actifs'),
                ])
                  CheckedPopupMenuItem<_ProjectTime>(
                    value: mode,
                    checked: _time == mode,
                    child: Text(label),
                  ),
              ],
            ),
            MakoloIconActionButton(
              tooltip: '30 prochains jours',
              icon: Icons.today_outlined,
              onPressed: () => setState(() => _time = _ProjectTime.next30),
            ),
          ],
        ),
        const SizedBox(height: 11),
        if (milestones.isEmpty)
          _empty(
            _time == _ProjectTime.undated
                ? 'Aucun Dossier sans échéance.'
                : 'Aucune échéance visible.',
          )
        else
          for (final row in milestones)
            ListTile(
              leading: Icon(
                row['deadline'] == null
                    ? Icons.event_busy_outlined
                    : Icons.flag_outlined,
              ),
              title: Text(_text(row['title'])),
              subtitle: Text(
                row['deadline'] == null
                    ? 'Sans échéance'
                    : 'Échéance · ${_humanDate(_dateFrom(row['deadline'])!)}',
              ),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () => widget.onOpenDossier(_text(row['id'])),
            ),
      ],
    );
  }

  Widget _track(
    DateTime start,
    DateTime end,
    List<Map<String, dynamic>> rows,
  ) => LayoutBuilder(
    builder: (context, constraints) {
      final span = end.difference(start).inDays;
      final valid = rows.where((row) {
        final date = _dateFrom(row['deadline']);
        return date != null && !date.isBefore(start) && !date.isAfter(end);
      }).toList();
      return Column(
        children: [
          SizedBox(
            height: 30,
            child: Stack(
              children: [
                Positioned(
                  top: 13,
                  left: 0,
                  right: 0,
                  child: Container(
                    height: 3,
                    color: Theme.of(context).colorScheme.outlineVariant,
                  ),
                ),
                for (final row in valid)
                  Positioned(
                    top: 4,
                    left:
                        (constraints.maxWidth - 18) *
                        (_dateFrom(row['deadline'])!.difference(start).inDays /
                            span),
                    child: Tooltip(
                      message: _text(row['title']),
                      child: InkWell(
                        onTap: () => widget.onOpenDossier(_text(row['id'])),
                        child: Icon(
                          Icons.circle,
                          size: 18,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                _humanDate(start),
                style: Theme.of(context).textTheme.labelSmall,
              ),
              Text(
                _humanDate(end),
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ],
          ),
        ],
      );
    },
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Projet'),
      actions: [
        MakoloIconActionButton(
          tooltip: 'Actualiser',
          onPressed: _refreshing ? null : _refresh,
          icon: Icons.refresh_rounded,
        ),
        StreamBuilder<OwnerSourceState>(
          stream: _source,
          initialData: OwnerSourceState.unknown,
          builder: (context, sourceSnapshot) {
            if (sourceSnapshot.data?.invalidated == true) {
              return const SizedBox.shrink();
            }
            return StreamBuilder<StoredProjection?>(
              stream: _detail,
              builder: (context, snapshot) {
                final project = snapshot.data?.payload;
                return project == null
                    ? const SizedBox.shrink()
                    : _projectTopActions(project);
              },
            );
          },
        ),
      ],
    ),
    body: StreamBuilder<OwnerSourceState>(
      key: ValueKey<String>(
        'project-owner:${widget.id}:${_spaceSlug ?? 'personal'}',
      ),
      stream: _source,
      initialData: OwnerSourceState.unknown,
      builder: (context, sourceSnapshot) {
        final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
        return StreamBuilder<StoredProjection?>(
          key: ValueKey<String>(
            'project-detail:${widget.id}:${_spaceSlug ?? 'personal'}',
          ),
          stream: _detail,
          builder: (context, detailSnapshot) {
            if (source.invalidated) {
              return const Center(
                child: Text(
                  'Ce Projet n’est plus accessible dans ce contexte.',
                ),
              );
            }
            final detail = detailSnapshot.data;
            if (detail == null) {
              return Center(
                child: _refreshing
                    ? const CircularProgressIndicator.adaptive()
                    : MakoloActionButton(
                        label: _failed ? 'Réessayer' : 'Charger ce Projet',
                        onPressed: _refresh,
                        appearance: MakoloActionAppearance.quiet,
                      ),
              );
            }
            return StreamBuilder<List<StoredProjection>>(
              stream: _pages,
              builder: (context, pageSnapshot) {
                final project = detail.payload;
                final (rows, more, offset) = _dossiers(
                  project,
                  pageSnapshot.data ?? const [],
                  detail.receivedAt,
                );
                return NotificationListener<ScrollNotification>(
                  onNotification: (notification) {
                    if (notification.metrics.axis != Axis.vertical ||
                        notification.metrics.extentAfter > 450 ||
                        !more ||
                        _offline ||
                        source.invalidated ||
                        _loadingMore ||
                        _refreshing ||
                        _failed) {
                      return false;
                    }
                    unawaited(_more(offset));
                    return false;
                  },
                  child: RefreshIndicator(
                    onRefresh: _refresh,
                    child: ListView(
                      key: PageStorageKey<String>(
                        'project-workspace-scroll:${_spaceSlug ?? 'personal'}',
                      ),
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: const EdgeInsets.fromLTRB(14, 8, 14, 24),
                      children: [
                        Center(
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 950),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                _header(project),
                                const SizedBox(height: 7),
                                _tabs(project),
                                if (_text(
                                  _map(project['horizon'])['description'],
                                ).trim().isNotEmpty) ...[
                                  const SizedBox(height: 7),
                                  ProjectDescription(
                                    key: ValueKey(
                                      'project-description:${widget.id}',
                                    ),
                                    description: _text(
                                      _map(project['horizon'])['description'],
                                    ),
                                  ),
                                ],
                                const SizedBox(height: 5),
                                _peoplePreview(project),
                                const SizedBox(height: 3),
                                if (_mode == _ProjectMode.summary)
                                  _summary(project, rows, more)
                                else if (_mode == _ProjectMode.dossiers)
                                  _dossierList(project, rows)
                                else
                                  _calendar(project, rows),
                                if (more && !_offline && !_failed)
                                  const Padding(
                                    padding: EdgeInsets.symmetric(vertical: 18),
                                    child: Center(
                                      child:
                                          CircularProgressIndicator.adaptive(),
                                    ),
                                  ),
                                if (_busy) const LinearProgressIndicator(),
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
        );
      },
    ),
  );
}
