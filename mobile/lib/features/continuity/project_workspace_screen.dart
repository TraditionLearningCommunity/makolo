import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../data/local/profile_store.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_status.dart';
import 'conversation_context_screen.dart';
import 'conversation_repository.dart';
import 'objective_repository.dart';

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
    this.api,
    this.conversations,
    this.onOpenConversation,
  });
  final String id;
  final ObjectiveRepository repository;
  final ValueChanged<String> onOpenDossier;
  final MakoloApiClient? api;
  final ConversationRepository? conversations;
  final ValueChanged<String>? onOpenConversation;

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
  final _search = TextEditingController();
  bool _refreshing = false,
      _busy = false,
      _loadingMore = false,
      _failed = false;
  bool _ignoreOlderPages = false;
  int? _lastOffset;

  @override
  void initState() {
    super.initState();
    _bind();
    _search.addListener(_changed);
    unawaited(_acquire());
  }

  void _bind() {
    _detail = widget.repository.watch(ObjectiveDepth.project, widget.id);
    _source = widget.repository.watchSource(ObjectiveDepth.project, widget.id);
    _pages = widget.repository.watchProjectDossiers();
  }

  @override
  void didUpdateWidget(covariant ProjectWorkspaceScreen previous) {
    super.didUpdateWidget(previous);
    if (previous.id != widget.id || previous.repository != widget.repository) {
      _bind();
      _mode = _ProjectMode.summary;
      _lastOffset = null;
      _ignoreOlderPages = false;
      unawaited(_acquire());
    }
  }

  @override
  void dispose() {
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
  bool get _enabled => widget.api != null && !_busy && !_offline;
  String get _base => 'api/v1/objectives/projects/${widget.id}/';

  Future<void> _acquire() async {
    final repo = widget.repository;
    final id = widget.id;
    try {
      final snapshot = await repo.read(ObjectiveDepth.project, id);
      final source = await repo.readSource(ObjectiveDepth.project, id);
      if (!mounted || repo != widget.repository || id != widget.id) return;
      if (snapshot == null ||
          ObjectiveRepository.freshnessPolicy.evaluate(
                snapshot,
                now: DateTime.now().toUtc(),
                invalidated: source.invalidated,
              ) !=
              FreshnessState.fresh) {
        unawaited(_refresh());
      }
    } on Object {
      if (mounted) setState(() => _failed = true);
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final id = widget.id;
    final repo = widget.repository;
    setState(() {
      _refreshing = true;
      _failed = false;
    });
    try {
      await repo.refresh(ObjectiveDepth.project, id);
    } on Object {
      if (mounted && id == widget.id) setState(() => _failed = true);
    } finally {
      if (mounted && id == widget.id) setState(() => _refreshing = false);
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
    setState(() => _busy = true);
    try {
      if (patch) {
        await widget.api!.patch(endpoint, body: body);
      } else {
        await widget.api!.post(endpoint, body: body);
      }
      _ignoreOlderPages = true;
      _lastOffset = null;
      try {
        await widget.repository.refresh(ObjectiveDepth.project, widget.id);
        await widget.repository.refreshOrganizerPage(0);
      } on Object {
        _notice(
          'Action enregistrée. Actualisez les données lorsque le réseau est disponible.',
        );
        return true;
      }
      _notice('Modification enregistrée.');
      return true;
    } on Object {
      _notice(
        'Action non confirmée. Vérifiez les permissions et la connexion.',
      );
      return false;
    } finally {
      if (mounted) setState(() => _busy = false);
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
                        labelText: 'Contexte',
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
    _lastOffset = offset;
    setState(() => _loadingMore = true);
    try {
      await widget.repository.refreshProjectDossiers(widget.id, offset);
      if (mounted) setState(() => _ignoreOlderPages = false);
    } on Object {
      _lastOffset = null;
      if (mounted) {
        setState(() => _failed = true);
        _notice('Suite indisponible. Actualisez pour réessayer.');
      }
    } finally {
      if (mounted) setState(() => _loadingMore = false);
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
                        widget.repository.profileId,
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

  Widget _actionBar(Map<String, dynamic> project) => Wrap(
    spacing: 9,
    runSpacing: 9,
    children: [
      if (_has(project, 'project.dossier.create'))
        MakoloActionButton(
          label: 'Créer un dossier',
          onPressed: _enabled ? _create : null,
          icon: Icons.create_new_folder_outlined,
          appearance: MakoloActionAppearance.primary,
        ),
      if (_has(project, 'project.dossier.link'))
        MakoloActionButton(
          label: 'Rattacher un dossier',
          onPressed: _enabled ? () => _link(project) : null,
          icon: Icons.link_rounded,
          appearance: MakoloActionAppearance.secondary,
        ),
      if (_has(project, 'project.lifecycle'))
        MakoloActionButton(
          label: 'Changer l’état',
          onPressed: _enabled ? () => _lifecycle(project) : null,
          icon: Icons.change_circle_outlined,
          appearance: MakoloActionAppearance.secondary,
        ),
    ],
  );

  Widget _header(Map<String, dynamic> project) {
    final horizon = _map(project['horizon']);
    final owner = _map(project['owner']);
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
              width: 55,
              height: 55,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(15),
                color: theme.colorScheme.primary.withValues(alpha: .08),
              ),
              child: Icon(
                Icons.folder_special_outlined,
                size: 29,
                color: theme.colorScheme.primary,
              ),
            ),
            const SizedBox(width: 13),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _text(owner['label']),
                    style: theme.textTheme.labelMedium?.copyWith(
                      color: theme.colorScheme.primary,
                      letterSpacing: .7,
                    ),
                  ),
                  const SizedBox(height: 7),
                  Text(
                    _text(horizon['title']),
                    style: theme.textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            ),
            if (_has(project, 'project.edit'))
              MakoloIconActionButton(
                tooltip: 'Modifier ce Projet',
                onPressed: _enabled ? () => _edit(project) : null,
                icon: Icons.edit_outlined,
              ),
          ],
        ),
        if (_text(horizon['description']).trim().isNotEmpty) ...[
          const SizedBox(height: 13),
          Text(_text(horizon['description'])),
        ],
        const SizedBox(height: 12),
        Wrap(
          spacing: 7,
          runSpacing: 7,
          children: [
            Chip(label: Text(_humanState(_map(project['state'])['code']))),
            if (start != null)
              Chip(label: Text('Début · ${_humanDate(start)}')),
            if (end != null)
              Chip(label: Text('Fin de l’horizon · ${_humanDate(end)}')),
          ],
        ),
        if (widget.conversations != null && widget.onOpenConversation != null)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: ConversationContextAction(
              repository: widget.conversations!,
              kind: 'project',
              contextId: widget.id,
              onOpen: widget.onOpenConversation!,
            ),
          ),
      ],
    );
  }

  Widget _tabs() => LayoutBuilder(
    builder: (context, constraints) {
      if (constraints.maxWidth < 480) {
        return Wrap(
          spacing: 7,
          runSpacing: 7,
          children: [
            for (final (mode, label, icon) in [
              (_ProjectMode.summary, 'Synthèse', Icons.dashboard_outlined),
              (_ProjectMode.dossiers, 'Dossiers', Icons.folder_copy_outlined),
              (
                _ProjectMode.calendar,
                'Calendrier',
                Icons.calendar_month_outlined,
              ),
            ])
              ChoiceChip(
                selected: _mode == mode,
                avatar: Icon(icon, size: 17),
                label: Text(label),
                onSelected: (_) => setState(() => _mode = mode),
              ),
          ],
        );
      }
      return SegmentedButton<_ProjectMode>(
        showSelectedIcon: false,
        selected: {_mode},
        segments: const [
          ButtonSegment(
            value: _ProjectMode.summary,
            icon: Icon(Icons.dashboard_outlined),
            label: Text('Synthèse'),
          ),
          ButtonSegment(
            value: _ProjectMode.dossiers,
            icon: Icon(Icons.folder_copy_outlined),
            label: Text('Dossiers'),
          ),
          ButtonSegment(
            value: _ProjectMode.calendar,
            icon: Icon(Icons.calendar_month_outlined),
            label: Text('Calendrier'),
          ),
        ],
        onSelectionChanged: (value) => setState(() => _mode = value.first),
      );
    },
  );

  Widget _dossierCard(Map<String, dynamic> row, Map<String, dynamic> project) {
    final readiness = _map(row['readiness']);
    final date = _dateFrom(row['deadline']);
    final scheme = Theme.of(context).colorScheme;
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(
        side: BorderSide(color: scheme.outlineVariant),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Padding(
        padding: const EdgeInsets.all(11),
        child: Row(
          children: [
            Icon(Icons.folder_outlined, color: scheme.primary, size: 27),
            const SizedBox(width: 10),
            Expanded(
              child: InkWell(
                onTap: () => widget.onOpenDossier(_text(row['id'])),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _text(row['title']),
                      style: Theme.of(context).textTheme.titleMedium
                          ?.copyWith(fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      [
                        _humanState(row['state']),
                        if (date != null) 'Échéance ${_humanDate(date)}',
                      ].join(' · '),
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    if (_text(readiness['label']).isNotEmpty)
                      Text(
                        'Situation · ${_text(readiness['label'])}'
                        '${readiness['partial'] == true ? ' · vue partielle' : ''}',
                        style: Theme.of(context).textTheme.bodySmall
                            ?.copyWith(color: scheme.primary),
                      ),
                  ],
                ),
              ),
            ),
            if (_has(row, 'unlink') || _has(row, 'move'))
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
              ),
            MakoloIconActionButton(
              tooltip: 'Ouvrir le Dossier',
              icon: Icons.chevron_right_rounded,
              onPressed: () => widget.onOpenDossier(_text(row['id'])),
            ),
          ],
        ),
      ),
    );
  }

  Widget _empty(String message) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 34),
    child: Column(
      children: [
        Icon(
          Icons.folder_open_outlined,
          size: 37,
          color: Theme.of(context).colorScheme.primary,
        ),
        const SizedBox(height: 12),
        Text(
          message,
          style: Theme.of(context).textTheme.titleMedium,
          textAlign: TextAlign.center,
        ),
      ],
    ),
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
        .take(3);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Vue d’ensemble',
          style: Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 7),
        Text(
          'Les chiffres portent uniquement sur les dossiers visibles acquis.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 13),
        Wrap(
          spacing: 9,
          runSpacing: 9,
          children: [
            _metric(
              rows.length,
              partial ? 'Dossiers acquis (partiel)' : 'Dossiers visibles',
            ),
            _metric(active, 'En cours'),
            _metric(draft, 'En préparation'),
            _metric(done, 'Terminés'),
          ],
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
          const SizedBox(height: 16),
          Text(
            'À suivre',
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          for (final row in intervention)
            ListTile(
              title: Text(_text(row['title'])),
              subtitle: const Text(
                'Une action est requise selon les faits visibles.',
              ),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () => widget.onOpenDossier(_text(row['id'])),
            ),
        ],
        const SizedBox(height: 18),
        Text(
          'Dossiers du Projet',
          style: Theme.of(context).textTheme.titleMedium
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 11),
        if (rows.isEmpty)
          _empty('Aucun dossier visible pour le moment.')
        else
          for (final row in rows.take(6)) _dossierCard(row, project),
        if (rows.length > 6)
          MakoloActionButton(
            label: 'Voir tous les Dossiers acquis',
            onPressed: () => setState(() => _mode = _ProjectMode.dossiers),
            appearance: MakoloActionAppearance.quiet,
          ),
      ],
    );
  }

  Widget _metric(int count, String title) => Container(
    constraints: const BoxConstraints(minWidth: 125),
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    decoration: BoxDecoration(
      border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
      borderRadius: BorderRadius.circular(14),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '$count',
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w800,
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
        const SizedBox(height: 7),
        Text(title, style: Theme.of(context).textTheme.labelSmall),
      ],
    ),
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
    itemBuilder: (_) => [
      for (final item in choices.entries)
        PopupMenuItem(value: item.key, child: Text(item.value)),
    ],
    child: Chip(
      label: Text(choices[selected] ?? title),
      avatar: const Icon(Icons.keyboard_arrow_down_rounded, size: 15),
    ),
  );

  Widget _dossierList(
    Map<String, dynamic> project,
    List<Map<String, dynamic>> rows,
  ) {
    final filtered = _sorted(rows);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Dossiers',
          style: Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 9),
        TextField(
          controller: _search,
          decoration: InputDecoration(
            prefixIcon: const Icon(Icons.search),
            hintText: 'Rechercher parmi les dossiers acquis',
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
          ],
        ),
        const SizedBox(height: 13),
        Text(
          '${filtered.length} '
          '${_search.text.trim().isNotEmpty || _stateFilter != 'all' || _readinessFilter != 'all'
              ? (filtered.length == 1 ? 'résultat' : 'résultats')
              : (filtered.length == 1 ? 'dossier' : 'dossiers')} '
          '${filtered.length == 1 ? 'chargé' : 'chargés'}',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 10),
        if (filtered.isEmpty)
          _empty('Aucun résultat pour ces critères.')
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
            _ProjectTime.all => true,
            _ProjectTime.next30 =>
              day != null &&
                  !day.isBefore(today) &&
                  !day.isAfter(today.add(const Duration(days: 30))),
            _ProjectTime.overdue =>
              day != null && day.isBefore(today) && row['state'] == 'active',
            _ProjectTime.undated => day == null,
            _ProjectTime.active => row['state'] == 'active',
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
        Text(
          'Calendrier',
          style: Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 8),
        const Text(
          'Les échéances des Dossiers sont des jalons ponctuels, '
          'pas des périodes ni des pourcentages d’avancement.',
        ),
        const SizedBox(height: 13),
        Card(
          elevation: 0,
          child: Padding(
            padding: const EdgeInsets.all(18),
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
                  start == null && end == null
                      ? 'Dates non renseignées'
                      : 'Début : ${start == null ? 'non défini' : _humanDate(start)}'
                            ' · Fin : ${end == null ? 'non définie' : _humanDate(end)}',
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
        const SizedBox(height: 11),
        Wrap(
          spacing: 6,
          runSpacing: 7,
          children: [
            for (final (mode, label) in [
              (_ProjectTime.all, 'Tous'),
              (_ProjectTime.next30, '30 prochains jours'),
              (_ProjectTime.overdue, 'En retard'),
              (_ProjectTime.undated, 'Sans date'),
              (_ProjectTime.active, 'Dossiers actifs'),
            ])
              ChoiceChip(
                selected: _time == mode,
                label: Text(label),
                onSelected: (_) => setState(() => _time = mode),
              ),
            MakoloActionButton(
              label: 'Aujourd’hui',
              onPressed: () => setState(() => _time = _ProjectTime.next30),
              appearance: MakoloActionAppearance.quiet,
              icon: Icons.today_outlined,
            ),
          ],
        ),
        const SizedBox(height: 11),
        if (milestones.isEmpty)
          _empty('Aucun jalon correspondant.')
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
      ],
    ),
    body: StreamBuilder<OwnerSourceState>(
      stream: _source,
      initialData: OwnerSourceState.unknown,
      builder: (context, sourceSnapshot) {
        final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
        return StreamBuilder<StoredProjection?>(
          stream: _detail,
          builder: (context, detailSnapshot) {
            if (source.invalidated) {
              return const Center(
                child: Text(
                  'Ce Projet n’est plus accessible depuis ce Profil.',
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
                    key: const PageStorageKey<String>(
                      'project-workspace-scroll',
                    ),
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 48),
                    children: [
                      Center(
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 950),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              _header(project),
                              if (_offline)
                                const Padding(
                                  padding: EdgeInsets.only(top: 10),
                                  child: Text(
                                    'Données locales disponibles hors ligne.',
                                  ),
                                ),
                              const SizedBox(height: 16),
                              _actionBar(project),
                              const SizedBox(height: 23),
                              _tabs(),
                              const SizedBox(height: 24),
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
                                    child: CircularProgressIndicator.adaptive(),
                                  ),
                                ),
                              if (_failed)
                                MakoloActionButton(
                                  label: 'Actualisation impossible · Réessayer',
                                  onPressed: _refresh,
                                  appearance: MakoloActionAppearance.quiet,
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
