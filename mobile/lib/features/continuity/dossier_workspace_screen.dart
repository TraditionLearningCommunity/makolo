import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../data/local/profile_store.dart';
import '../../app/runtime/actor_context.dart';
import '../../app/runtime/actor_context_controller.dart';
import '../../network/makolo_api_client.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import '../../sync/sync_status.dart';
import 'conversation_context_screen.dart';
import 'conversation_repository.dart';
import 'objective_repository.dart';
import 'objective_workspace_view_switcher.dart';
import 'objective_filter_reset.dart';

enum _DossierMode { overview, list, timeline, dependencies }

enum _ListSort {
  recent,
  name,
  state,
  action,
  created,
  started,
  fulfilled,
  expiry,
}

enum _TimeScale { week, month, quarter }

Map<String, dynamic> _map(Object? raw) =>
    raw is Map ? raw.map((key, value) => MapEntry('$key', value)) : {};
List<Map<String, dynamic>> _rows(Object? raw) => raw is List
    ? raw.map(_map).where((row) => row.isNotEmpty).toList()
    : const [];
String _text(Object? raw) => raw?.toString() ?? '';
DateTime? _parse(Object? value) => DateTime.tryParse(_text(value));
bool _cap(Map<String, dynamic> row, String capability) =>
    row['capabilities'] is List &&
    (row['capabilities'] as List).contains(capability);
String _humanState(Object? value) => switch (_text(value)) {
  'draft' => 'En préparation',
  'active' || 'in_progress' => 'En cours',
  'completed' || 'complete' || 'fulfilled' => 'Terminé',
  'cancelled' => 'Annulé',
  'archived' => 'Archivé',
  'rejected' => 'Rejetée',
  'expired' => 'Expirée',
  'submitted' => 'Soumise',
  'confirmed' => 'Confirmée',
  'approved' => 'Approuvée',
  'pending_approval' => 'Approbation attendue',
  'pending_payment' => 'Paiement attendu',
  'ready' => 'Prêt',
  'action_required' => 'Action requise',
  'blocked' => 'Bloqué',
  'waiting' => 'En attente',
  _ => 'État non précisé',
};
String _iso(DateTime? date) => date == null
    ? ''
    : '${date.year.toString().padLeft(4, '0')}-'
          '${date.month.toString().padLeft(2, '0')}-'
          '${date.day.toString().padLeft(2, '0')}';
String _dateLabel(BuildContext context, DateTime date) =>
    MaterialLocalizations.of(context).formatMediumDate(date);
String _instantLabel(BuildContext context, DateTime date) {
  final local = date.toLocal();
  final time = MaterialLocalizations.of(context)
      .formatTimeOfDay(TimeOfDay.fromDateTime(local));
  return '${_dateLabel(context, local)} · $time';
}

class DossierWorkspaceScreen extends StatefulWidget {
  const DossierWorkspaceScreen({
    super.key,
    required this.id,
    required this.repository,
    required this.onOpenJourney,
    this.onOpenProject,
    this.onOpenOwnerSpace,
    this.onOpenPerson,
    this.onOpenMyPassport,
    this.onOpenPeople,
    this.api,
    this.conversations,
    this.onOpenConversation,
    this.actorContext,
    this.sourceProjectId,
    this.onReturnToProject,
  });
  final String id;
  final ObjectiveRepository repository;
  final MakoloApiClient? api;
  final ValueChanged<String> onOpenJourney;
  final ValueChanged<String>? onOpenProject;
  final ValueChanged<String>? onOpenOwnerSpace;
  final ValueChanged<String>? onOpenPerson;
  final VoidCallback? onOpenMyPassport;
  final VoidCallback? onOpenPeople;
  final ConversationRepository? conversations;
  final ValueChanged<String>? onOpenConversation;
  final ActorContextController? actorContext;
  final String? sourceProjectId;
  final VoidCallback? onReturnToProject;

  @override
  State<DossierWorkspaceScreen> createState() => _DossierWorkspaceState();
}

class _DossierWorkspaceState extends State<DossierWorkspaceScreen> {
  late Stream<StoredProjection?> _detail;
  late Stream<OwnerSourceState> _owner;
  final _search = TextEditingController();
  final _transform = TransformationController();
  final _pageScroll = ScrollController();
  _DossierMode _mode = _DossierMode.overview;
  _ListSort _sort = _ListSort.recent;
  _TimeScale _timeScale = _TimeScale.month;
  String _filter = 'all';
  String? _spaceSlug;
  int _contextRevision = 0;
  bool _refreshing = false, _busy = false, _failed = false;

  String? get _selectedSpaceSlug {
    final actor = widget.actorContext?.value;
    return actor is SpaceActorContext ? actor.space.slug : null;
  }

  void _selectMode(_DossierMode mode) {
    if (_mode == mode) return;
    setState(() => _mode = mode);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _pageScroll.hasClients) {
        _pageScroll.jumpTo(0);
      }
    });
  }

  void _resetPresentation() {
    _mode = _DossierMode.overview;
    _filter = 'all';
    _sort = _ListSort.recent;
    _timeScale = _TimeScale.month;
    _transform.value = Matrix4.identity();
  }

  void _actorChanged() {
    final next = _selectedSpaceSlug;
    if (!mounted || next == _spaceSlug) return;
    _search.clear();
    setState(() {
      _contextRevision++;
      _spaceSlug = next;
      _resetPresentation();
      _refreshing = false;
      _busy = false;
      _failed = false;
      _bind();
    });
    // A new Space lens must never display another Space's cached detail.
    unawaited(_refresh());
  }

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
      ObjectiveDepth.dossier,
      widget.id,
      spaceSlug: _spaceSlug,
    );
    _owner = widget.repository.watchSource(
      ObjectiveDepth.dossier,
      widget.id,
      spaceSlug: _spaceSlug,
    );
  }

  @override
  void didUpdateWidget(covariant DossierWorkspaceScreen old) {
    super.didUpdateWidget(old);
    if (old.actorContext != widget.actorContext) {
      old.actorContext?.removeListener(_actorChanged);
      widget.actorContext?.addListener(_actorChanged);
    }
    final nextSpace = _selectedSpaceSlug;
    if (old.id != widget.id ||
        old.repository != widget.repository ||
        nextSpace != _spaceSlug) {
      _contextRevision++;
      _spaceSlug = nextSpace;
      _bind();
      _resetPresentation();
      _refreshing = false;
      _busy = false;
      unawaited(_acquire());
    }
  }

  @override
  void dispose() {
    widget.actorContext?.removeListener(_actorChanged);
    _search.removeListener(_changed);
    _search.dispose();
    _transform.dispose();
    _pageScroll.dispose();
    super.dispose();
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  bool get _offline =>
      SyncStatusScope.maybeOf(context)?.state == SyncVisualState.offline;
  bool get _canMutate =>
      widget.api != null && !_busy && !_offline && !_refreshing && !_failed;
  String get _path => 'api/v1/objectives/dossiers/${widget.id}/';

  Future<void> _acquire() async {
    final repo = widget.repository;
    final id = widget.id;
    final spaceSlug = _spaceSlug;
    final revision = _contextRevision;
    try {
      final cached = await repo.read(
        ObjectiveDepth.dossier,
        id,
        spaceSlug: spaceSlug,
      );
      final source = await repo.readSource(
        ObjectiveDepth.dossier,
        id,
        spaceSlug: spaceSlug,
      );
      if (!mounted ||
          widget.id != id ||
          widget.repository != repo ||
          revision != _contextRevision)
        return;
      // A cached Space lens is not proof that its Mandates still exist.
      // Always ask the owner when entering this Space depth.
      if (spaceSlug != null ||
          cached == null ||
          cached.payload['visible_journeys_complete'] != true ||
          ObjectiveRepository.freshnessPolicy.evaluate(
                cached,
                now: DateTime.now().toUtc(),
                invalidated: source.invalidated,
              ) !=
              FreshnessState.fresh) {
        unawaited(_refresh());
      }
    } on Object {
      if (mounted &&
          repo == widget.repository &&
          revision == _contextRevision) {
        setState(() => _failed = true);
      }
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final repo = widget.repository;
    final id = widget.id;
    final spaceSlug = _spaceSlug;
    final revision = _contextRevision;
    setState(() {
      _refreshing = true;
      _failed = false;
    });
    try {
      await repo.refresh(ObjectiveDepth.dossier, id, spaceSlug: spaceSlug);
      final source = await repo.readSource(
        ObjectiveDepth.dossier,
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
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), behavior: SnackBarBehavior.floating),
    );
  }

  Future<bool> _command(
    String action,
    Map<String, dynamic> fields, {
    bool edit = false,
  }) async {
    if (!_canMutate) return false;
    final revision = _contextRevision;
    final spaceSlug = _spaceSlug;
    final suffix = ObjectiveRepository.contextQuery(spaceSlug);
    setState(() => _busy = true);
    try {
      final before = await widget.repository.read(
        ObjectiveDepth.dossier,
        widget.id,
        spaceSlug: spaceSlug,
      );
      if (revision != _contextRevision) return false;
      final oldParent = _text(_map(before?.payload['parent_project'])['id']);
      if (edit) {
        await widget.api!.patch('$_path$suffix', body: fields);
      } else {
        await widget.api!.post(
          '${_path}actions/$suffix',
          body: {'action': action, ...fields},
        );
      }
      if (revision != _contextRevision) return false;
      try {
        await widget.repository.refresh(
          ObjectiveDepth.dossier,
          widget.id,
          spaceSlug: spaceSlug,
        );
        // Refresh the active surface first, then the transcontextual Moi
        // index opportunistically. Failure of the second read never undoes
        // a server-confirmed Dossier mutation.
        await widget.repository.refreshOrganizerPage(0, spaceSlug: spaceSlug);
        if (spaceSlug != null) {
          try {
            await widget.repository.refreshOrganizerPage(0);
          } on Object {
            // The selected Space has already been reprojected.
          }
        }
        if (revision != _contextRevision) return true;
        final refreshed = await widget.repository.read(
          ObjectiveDepth.dossier,
          widget.id,
          spaceSlug: spaceSlug,
        );
        final newParent = _text(
          _map(refreshed?.payload['parent_project'])['id'],
        );
        for (final parentId in {oldParent, newParent}) {
          if (revision != _contextRevision) return true;
          if (parentId.isEmpty) continue;
          try {
            await widget.repository.refresh(
              ObjectiveDepth.project,
              parentId,
              spaceSlug: spaceSlug,
            );
          } on Object {
            // The Dossier mutation is already confirmed; a hidden or
            // unreachable Project must not turn it into a second mutation.
          }
        }
      } on Object {
        if (mounted && revision == _contextRevision) {
          _notice(
            'Action confirmée ; actualisez vos données pour voir le nouvel état.',
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
        _notice('Action non confirmée. Vérifiez les droits et la connexion.');
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
    String explanation, {
    String action = 'Confirmer',
  }) async =>
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

  Future<String?> _choose(
    String heading,
    List<Map<String, dynamic>> options, {
    bool allowNone = false,
    String noneLabel = 'Aucun',
  }) async {
    if (options.isEmpty && !allowNone) {
      _notice('Aucun choix disponible selon vos autorisations.');
      return null;
    }
    return showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (sheet) => SafeArea(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxHeight: 520),
          child: ListView(
            shrinkWrap: true,
            children: [
              ListTile(
                title: Text(heading),
                subtitle: const Text(
                  'Seules les options autorisées sont proposées.',
                ),
              ),
              if (allowNone)
                ListTile(
                  leading: const Icon(Icons.folder_off_outlined),
                  title: Text(noneLabel),
                  onTap: () => Navigator.pop(sheet, '__none__'),
                ),
              for (final option in options)
                ListTile(
                  leading: const Icon(Icons.chevron_right_rounded),
                  title: Text(_text(option['label'])),
                  onTap: () => Navigator.pop(sheet, _text(option['id'])),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _edit(Map<String, dynamic> payload) async {
    final objective = _map(payload['objective']);
    final title = TextEditingController(text: _text(objective['title']));
    final description = TextEditingController(
      text: _text(objective['description']),
    );
    final form = GlobalKey<FormState>();
    DateTime? deadline = _parse(payload['deadline']);
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialog) => StatefulBuilder(
        builder: (dialog, update) => AlertDialog(
          title: const Text('Modifier le Dossier'),
          content: Form(
            key: form,
            child: SizedBox(
              width: 430,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextFormField(
                      controller: title,
                      maxLength: 220,
                      decoration: const InputDecoration(
                        labelText: 'Objectif du Dossier',
                        border: OutlineInputBorder(),
                      ),
                      validator: (v) => v == null || v.trim().isEmpty
                          ? 'Objectif obligatoire.'
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
                    const SizedBox(height: 12),
                    MakoloActionButton(
                      label: deadline == null
                          ? 'Échéance facultative'
                          : 'Échéance : ${_dateLabel(dialog, deadline!)}',
                      onPressed: () async {
                        final result = await showDatePicker(
                          context: dialog,
                          initialDate: deadline ?? DateTime.now(),
                          firstDate: DateTime(1900),
                          lastDate: DateTime(2100),
                        );
                        if (result != null) update(() => deadline = result);
                      },
                      appearance: MakoloActionAppearance.secondary,
                      icon: Icons.calendar_today_outlined,
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
              label: 'Enregistrer',
              onPressed: () {
                if (!(form.currentState?.validate() ?? false)) return;
                Navigator.pop(dialog, {
                  'title': title.text.trim(),
                  'description': description.text.trim(),
                  'deadline': deadline == null ? null : _iso(deadline),
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
    if (result != null && mounted) await _command('edit', result, edit: true);
  }

  Future<void> _link(Map<String, dynamic> payload) async {
    final candidates = _map(payload['candidates']);
    final selected = await _choose(
      'Lier une démarche existante',
      _rows(candidates['journeys']),
    );
    if (selected != null && mounted) {
      await _command('link_journey', {'journey_id': selected});
    }
  }

  Future<void> _unlinkJourney(Map<String, dynamic> row) async {
    final approved = await _confirm(
      'Retirer cette démarche ?',
      'La Journey conservera sa propre identité, son statut et son histoire.',
      action: 'Retirer le lien',
    );
    if (approved) {
      await _command('unlink_journey', {'journey_id': row['id']});
    }
  }

  Future<void> _newDependency(Map<String, dynamic> payload) async {
    final choices = _rows(payload['visible_journeys'])
        .map((row) => {'id': row['link_id'], 'label': row['label']})
        .toList();
    if (choices.length < 2) {
      _notice(
        'Il faut au moins deux démarches visibles pour définir une dépendance.',
      );
      return;
    }
    final required = await _choose('Démarche requise (prérequis)', choices);
    if (required == null || !mounted) return;
    final dependent = await _choose(
      'Démarche dépendante',
      choices.where((row) => row['id'] != required).toList(),
    );
    if (dependent == null || !mounted) return;
    final approved = await _confirm(
      'Créer cette dépendance ?',
      'La démarche dépendante devra attendre la démarche requise.',
    );
    if (approved) {
      await _command('add_dependency', {
        'required_link_id': required,
        'dependent_link_id': dependent,
      });
    }
  }

  Future<void> _dependencyAction(
    Map<String, dynamic> row,
    String action,
  ) async {
    final id = row['id'];
    if (action == 'remove') {
      final yes = await _confirm(
        'Retirer le prérequis ?',
        'La relation disparaîtra, sans supprimer les Journeys.',
      );
      if (yes) await _command('remove_dependency', {'dependency_id': id});
    } else {
      final input = TextEditingController();
      final form = GlobalKey<FormState>();
      final reason = await showDialog<String>(
        context: context,
        builder: (dialog) => AlertDialog(
          title: const Text('Lever le prérequis'),
          content: Form(
            key: form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'La levée conserve l’historique de la dépendance ; '
                  'elle ne termine pas la Journey requise.',
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: input,
                  maxLength: 280,
                  decoration: const InputDecoration(
                    labelText: 'Raison de la levée',
                    border: OutlineInputBorder(),
                  ),
                  validator: (v) => v == null || v.trim().isEmpty
                      ? 'Une raison est obligatoire.'
                      : null,
                ),
              ],
            ),
          ),
          actions: [
            MakoloActionButton(
              label: 'Annuler',
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => Navigator.pop(dialog),
            ),
            MakoloActionButton(
              label: 'Lever',
              onPressed: () {
                if (form.currentState?.validate() ?? false) {
                  Navigator.pop(dialog, input.text.trim());
                }
              },
              appearance: MakoloActionAppearance.primary,
            ),
          ],
        ),
      );
      input.dispose();
      if (reason != null && mounted) {
        await _command('waive_dependency', {
          'dependency_id': id,
          'reason': reason,
        });
      }
    }
  }

  Future<void> _projectAction(Map<String, dynamic> payload) async {
    final candidates = _map(payload['candidates']);
    final result = await _choose(
      'Projet du Dossier',
      _rows(candidates['projects']),
      allowNone: true,
      noneLabel: 'Dossier indépendant — détacher',
    );
    if (result == null || !mounted) return;
    final yes = await _confirm(
      'Modifier le rattachement ?',
      'Le Dossier et les Journeys conserveront leur identité.',
      action: 'Confirmer',
    );
    if (yes) {
      await _command('project_set', {
        'project_id': result == '__none__' ? null : result,
      });
    }
  }

  Future<void> _lifecycle(Map<String, dynamic> payload) async {
    final allowed = payload['allowed_transitions'] is List
        ? payload['allowed_transitions'] as List
        : const [];
    final selected = await _choose('Nouvel état autorisé', [
      for (final value in allowed)
        {'id': '$value', 'label': _humanState(value)},
    ]);
    if (selected == null || !mounted) return;
    final yes = await _confirm(
      'Changer l’état du Dossier ?',
      'Les démarches liées conserveront leur propre cycle de vie.',
    );
    if (yes) await _command('lifecycle', {'lifecycle': selected});
  }

  Future<void> _assign(Map<String, dynamic> payload) async {
    final selected = await _choose(
      'Désigner un responsable de coordination',
      _rows(_map(payload['candidates'])['assignees']),
    );
    if (selected == null || !mounted) return;
    await _command('assignment_add', {'assignee_id': selected});
  }

  Future<void> _grant(Map<String, dynamic> payload) async {
    final candidates = _map(payload['candidates']);
    final profile = await _choose(
      'Collaborateur autorisé',
      _rows(candidates['mandate_profiles']),
    );
    if (profile == null || !mounted) return;
    final role = await _choose('Rôle Dossier', _rows(candidates['roles']));
    if (role == null || !mounted) return;
    final yes = await _confirm(
      'Accorder cette autorité ?',
      'Ce mandat concerne le Dossier, pas automatiquement ses Journeys.',
    );
    if (yes) {
      await _command('mandate_grant', {'profile_id': profile, 'role_id': role});
    }
  }

  Future<void> _removeAssignment(Map<String, dynamic> row) async {
    final yes = await _confirm(
      'Retirer la responsabilité ?',
      'Les mandats de cette personne ne sont pas modifiés.',
    );
    if (yes) await _command('assignment_remove', {'assignment_id': row['id']});
  }

  Future<void> _revoke(Map<String, dynamic> row) async {
    final yes = await _confirm(
      'Révoquer le mandat ?',
      'L’autorité sur ce Dossier sera retirée.',
    );
    if (yes) await _command('mandate_revoke', {'mandate_id': row['id']});
  }

  Widget _linkAction(Map<String, dynamic> data) {
    return Tooltip(
      message: 'Lier une démarche',
      child: FilledButton.tonalIcon(
        onPressed: _canMutate && _cap(data, 'dossier.journey.link')
            ? () => _link(data)
            : null,
        icon: const Icon(Icons.add_link_rounded, size: 18),
        label: const Text('Lier'),
        style: FilledButton.styleFrom(
          minimumSize: const Size(0, 36),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          visualDensity: VisualDensity.compact,
          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
      ),
    );
  }

  /// Owner actions belong in the top AppBar, not between Dossier sections.
  Widget _dossierMenu(Map<String, dynamic> data) {
    final menu = [
      if (_cap(data, 'dossier.edit')) 'edit',
      if (_cap(data, 'dossier.dependency.add')) 'dependency',
      if (_cap(data, 'dossier.project.manage')) 'project',
      if (_cap(data, 'dossier.lifecycle')) 'lifecycle',
    ];
    if (menu.isEmpty) return const SizedBox.shrink();
    return PopupMenuButton<String>(
      tooltip: 'Actions du Dossier',
      enabled: _canMutate,
      icon: const Icon(Icons.more_horiz_rounded),
      onSelected: (action) {
        switch (action) {
          case 'edit':
            _edit(data);
          case 'dependency':
            _newDependency(data);
          case 'project':
            _projectAction(data);
          case 'lifecycle':
            _lifecycle(data);
        }
      },
      itemBuilder: (_) => [
        if (menu.contains('edit'))
          const PopupMenuItem(value: 'edit', child: Text('Modifier')),
        if (menu.contains('dependency'))
          const PopupMenuItem(
            value: 'dependency',
            child: Text('Ajouter un prérequis'),
          ),
        if (menu.contains('project'))
          const PopupMenuItem(
            value: 'project',
            child: Text('Rattachement au Projet'),
          ),
        if (menu.contains('lifecycle'))
          const PopupMenuItem(
            value: 'lifecycle',
            child: Text('Changer l’état'),
          ),
      ],
    );
  }

  /// Keep view icons attached to Démarches, never in a separate footer.
  Widget _journeysHeading(Map<String, dynamic> data) {
    final showViews =
        _mode != _DossierMode.overview ||
        _rows(data['visible_journeys']).isNotEmpty ||
        _rows(data['visible_dependencies']).isNotEmpty;
    final canLink =
        _cap(data, 'dossier.journey.link') &&
        (_mode == _DossierMode.overview || _mode == _DossierMode.list);
    final theme = Theme.of(context);
    Widget heading() => Row(
      children: [
        Icon(Icons.route_outlined, color: theme.colorScheme.primary, size: 21),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            'Démarches',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        if (canLink) _linkAction(data),
      ],
    );
    return LayoutBuilder(
      builder: (context, constraints) {
        if (!showViews) return heading();
        if (constraints.maxWidth >= 560) {
          return Row(
            children: [
              Expanded(child: heading()),
              const SizedBox(width: 12),
              SizedBox(width: 224, child: _tabs()),
            ],
          );
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            heading(),
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerRight,
              child: SizedBox(width: 224, child: _tabs()),
            ),
          ],
        );
      },
    );
  }

  Widget _header(Map<String, dynamic> data) {
    final objective = _map(data['objective']);
    final parent = _map(data['parent_project']);
    final readiness = _map(data['readiness']);
    final owner = _map(data['owner']);
    final deadline = _parse(data['deadline']);
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (parent.isNotEmpty && widget.onOpenProject != null)
          MakoloActionButton(
            label: widget.sourceProjectId == _text(parent['id'])
                ? 'Retour au Projet · ${_text(parent['title'])}'
                : 'Ouvrir le Projet · ${_text(parent['title'])}',
            onPressed: () {
              if (widget.sourceProjectId == _text(parent['id']) &&
                  widget.onReturnToProject != null) {
                widget.onReturnToProject!();
              } else {
                widget.onOpenProject!(_text(parent['id']));
              }
            },
            appearance: MakoloActionAppearance.quiet,
            icon: widget.sourceProjectId == _text(parent['id'])
                ? Icons.arrow_back_rounded
                : Icons.folder_special_outlined,
          ),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 53,
              height: 53,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(15),
                color: theme.colorScheme.primary.withValues(alpha: .085),
              ),
              child: Icon(
                Icons.folder_open_outlined,
                color: theme.colorScheme.primary,
                size: 28,
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _text(objective['title']),
                    style: theme.textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        if (_text(owner['label']).isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: InkWell(
              borderRadius: BorderRadius.circular(8),
              onTap: owner['kind'] == 'space' && _text(owner['slug']).isNotEmpty
                  ? (widget.onOpenOwnerSpace == null
                        ? null
                        : () => widget.onOpenOwnerSpace!(_text(owner['slug'])))
                  : null,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Row(
                  children: [
                    Icon(
                      owner['kind'] == 'space'
                          ? Icons.groups_outlined
                          : Icons.person_outline_rounded,
                      size: 18,
                      color: theme.colorScheme.primary,
                    ),
                    const SizedBox(width: 7),
                    Expanded(
                      child: Text(
                        'Porteur · ' + _text(owner['label']),
                        style: theme.textTheme.bodySmall,
                      ),
                    ),
                    if (owner['kind'] == 'space' &&
                        widget.onOpenOwnerSpace != null)
                      const Icon(Icons.chevron_right_rounded, size: 18),
                  ],
                ),
              ),
            ),
          ),
        if (_text(objective['description']).isNotEmpty) ...[
          const SizedBox(height: 12),
          Text(
            _text(objective['description']),
            style: theme.textTheme.bodyMedium,
          ),
        ],
        const SizedBox(height: 12),
        Wrap(
          spacing: 7,
          runSpacing: 7,
          children: [
            Chip(label: Text(_humanState(_map(data['state'])['code']))),
            if (deadline != null)
              Chip(label: Text('Échéance · ${_dateLabel(context, deadline)}')),
            if (_text(readiness['state']).isNotEmpty &&
                _text(readiness['label']).isNotEmpty)
              Chip(label: Text(_text(readiness['label']))),
            if (readiness['partial'] == true)
              const Chip(label: Text('Vue partielle')),
          ],
        ),
        if (widget.conversations != null && widget.onOpenConversation != null)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: ConversationContextAction(
              repository: widget.conversations!,
              kind: 'dossier',
              contextId: widget.id,
              onOpen: widget.onOpenConversation!,
            ),
          ),
      ],
    );
  }

  Widget _tabs() => ObjectiveWorkspaceViewSwitcher<_DossierMode>(
    selected: _mode,
    options: const [
      ObjectiveViewOption(
        _DossierMode.overview,
        Icons.dashboard_outlined,
        'Vue d’ensemble',
      ),
      ObjectiveViewOption(_DossierMode.list, Icons.list_rounded, 'Liste'),
      ObjectiveViewOption(
        _DossierMode.timeline,
        Icons.calendar_month_outlined,
        'Chronologie',
      ),
      ObjectiveViewOption(
        _DossierMode.dependencies,
        Icons.account_tree_outlined,
        'Dépendances',
      ),
    ],
    onSelected: _selectMode,
  );

  Widget _journeyTile(Map<String, dynamic> row, {bool compact = false}) {
    final readiness = _text(row['readiness_label']);
    final id = _text(row['id']);
    final scheme = Theme.of(context).colorScheme;
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 9),
      shape: RoundedRectangleBorder(
        side: BorderSide(color: scheme.outlineVariant),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 6),
        child: Row(
          children: [
            Icon(Icons.route_outlined, color: scheme.primary),
            const SizedBox(width: 9),
            Expanded(
              child: ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text(
                  _text(row['label']),
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                subtitle: Text(
                  [
                    _humanState(row['state']),
                    if (readiness.isNotEmpty) 'Situation : $readiness',
                    if (row['hidden_dependency'] == true)
                      'Conditions partielles',
                    if (!compact &&
                        _text(_map(row['next_action'])['label']).isNotEmpty)
                      _text(_map(row['next_action'])['label']),
                  ].join(' · '),
                ),
                onTap: () => widget.onOpenJourney(id),
              ),
            ),
            if (_cap(row, 'unlink'))
              PopupMenuButton<String>(
                enabled: _canMutate,
                tooltip: 'Gérer la démarche',
                itemBuilder: (_) => [
                  const PopupMenuItem(
                    value: 'unlink',
                    child: Text('Retirer du Dossier'),
                  ),
                ],
                onSelected: (_) => _unlinkJourney(row),
              )
            else
              MakoloIconActionButton(
                tooltip: 'Ouvrir la démarche',
                icon: Icons.chevron_right_rounded,
                onPressed: () => widget.onOpenJourney(id),
              ),
          ],
        ),
      ),
    );
  }

  Widget _metric(String count, String title) => Container(
    constraints: const BoxConstraints(minWidth: 96),
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
    decoration: BoxDecoration(
      border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
      borderRadius: BorderRadius.circular(14),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          count,
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w800,
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
        const SizedBox(height: 6),
        Text(title, style: Theme.of(context).textTheme.labelSmall),
      ],
    ),
  );

  /// One compact surface, with the canonical people page as the full list.
  /// Assignments do not convey Mandates, and the preview only shows
  /// Profiles visible to the active viewer.
  Widget _collaboration(Map<String, dynamic> data) {
    final assignments = _rows(data['assignments']);
    final mandates = _rows(data['mandates']);
    final canAssign = _cap(data, 'dossier.assignment.manage');
    final canGrant = _cap(data, 'dossier.authority.manage');
    if (assignments.isEmpty && mandates.isEmpty && !canAssign && !canGrant) {
      return const SizedBox.shrink();
    }
    final preview = _map(data['people_preview']);
    final hasPreview = data['people_preview'] is Map;
    // Older local snapshots keep visible names, but cannot infer
    // additional people or a Profile ID from a display label.
    final people = hasPreview
        ? _rows(preview['people'])
        : [
            ...assignments.map(
              (item) => {
                'label': item['label'],
                'profile_id': item['profile_id'],
              },
            ),
            ...mandates.map(
              (item) => {
                'label': item['profile'],
                'profile_id': item['profile_id'],
              },
            ),
          ].take(4).toList();
    final remaining = hasPreview && preview['remaining'] is num
        ? (preview['remaining'] as num).toInt()
        : 0;
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Card(
        elevation: 0,
        shape: RoundedRectangleBorder(
          side: BorderSide(color: scheme.outlineVariant),
          borderRadius: BorderRadius.circular(18),
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 7, 12, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(
                  Icons.people_outline_rounded,
                  color: scheme.primary,
                ),
                title: const Text(
                  'Personnes et responsabilités',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
                subtitle: Text(
                  people.isEmpty
                      ? 'Aucune personne visible'
                      : 'Voir les personnes et leurs rôles',
                ),
                trailing: widget.onOpenPeople == null
                    ? null
                    : const Icon(Icons.chevron_right_rounded),
                onTap: widget.onOpenPeople,
              ),
              if (people.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(left: 5, top: 1),
                  child: Row(
                    children: [
                      for (final person in people.take(4))
                        Padding(
                          padding: const EdgeInsets.only(right: 5),
                          child: Tooltip(
                            message: _text(person['label']),
                            child: InkWell(
                              customBorder: const CircleBorder(),
                              onTap:
                                  _text(person['profile_id']).isEmpty ||
                                      _text(person['profile_url']).isEmpty
                                  ? null
                                  : _text(person['profile_view']) == 'self'
                                  ? widget.onOpenMyPassport
                                  : widget.onOpenPerson == null
                                  ? null
                                  : () => widget.onOpenPerson!(
                                      _text(person['profile_id']),
                                    ),
                              child: CircleAvatar(
                                radius: 18,
                                backgroundColor: scheme.primaryContainer,
                                child: Text(
                                  _text(person['label']).isEmpty
                                      ? '•'
                                      : _text(person['label'])
                                            .substring(0, 1)
                                            .toUpperCase(),
                                  style: TextStyle(
                                    color: scheme.onPrimaryContainer,
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      if (remaining > 0)
                        Tooltip(
                          message: 'Voir les autres personnes',
                          child: InkWell(
                            customBorder: const CircleBorder(),
                            onTap: widget.onOpenPeople,
                            child: CircleAvatar(
                              radius: 18,
                              child: Text(
                                '+' + remaining.toString(),
                                style: const TextStyle(fontSize: 11),
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              if (canAssign || canGrant)
                Padding(
                  padding: const EdgeInsets.only(top: 10),
                  child: Wrap(
                    spacing: 7,
                    runSpacing: 3,
                    children: [
                      if (canAssign)
                        TextButton.icon(
                          onPressed: _canMutate ? () => _assign(data) : null,
                          icon: const Icon(Icons.person_add_alt_1_outlined),
                          label: const Text('Coordination'),
                        ),
                      if (canGrant)
                        TextButton.icon(
                          onPressed: _canMutate ? () => _grant(data) : null,
                          icon: const Icon(Icons.shield_outlined),
                          label: const Text('Gérer les accès'),
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

  Widget _overview(Map<String, dynamic> data) {
    final items = _rows(data['visible_journeys']);
    final dependencies = _rows(data['visible_dependencies']);
    final readiness = _map(data['readiness']);
    final next = _map(readiness['next_action']);
    final nextId = _text(next['journey_id']);
    final completed = items
        .where(
          (item) => [
            'fulfilled',
            'completed',
            'complete',
          ].contains(_text(item['state'])),
        )
        .length;
    final requiringAction = items
        .where((item) => item['readiness_state'] == 'action_required')
        .length;
    final complete =
        data['visible_journeys_complete'] == true &&
        readiness['partial'] != true;
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (_text(next['label']).isNotEmpty)
          Card(
            elevation: 0,
            color: scheme.primaryContainer.withValues(alpha: .45),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(17),
            ),
            child: ListTile(
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 14,
                vertical: 9,
              ),
              leading: Icon(Icons.bolt_rounded, color: scheme.primary),
              title: const Text(
                'À faire maintenant',
                style: TextStyle(fontWeight: FontWeight.w800),
              ),
              subtitle: Text(_text(next['label'])),
              trailing: nextId.isNotEmpty
                  ? const Icon(Icons.arrow_forward_rounded)
                  : null,
              onTap: nextId.isNotEmpty
                  ? () => widget.onOpenJourney(nextId)
                  : null,
            ),
          ),
        const SizedBox(height: 10),
        _controls(data),
        _collaboration(data),
        const SizedBox(height: 12),
        Row(
          children: [
            Icon(Icons.route_outlined, color: scheme.primary),
            const SizedBox(width: 9),
            Expanded(
              child: Text(
                'Démarches',
                style: Theme.of(context).textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
            ),
            if (_cap(data, 'dossier.journey.link') && items.isNotEmpty)
              IconButton(
                tooltip: 'Lier une démarche',
                icon: const Icon(Icons.add_link_rounded),
                onPressed: _canMutate ? () => _link(data) : null,
              ),
            if (items.isNotEmpty)
              TextButton.icon(
                onPressed: () => _selectMode(_DossierMode.list),
                iconAlignment: IconAlignment.end,
                icon: const Icon(Icons.chevron_right_rounded),
                label: const Text('Tout voir'),
              ),
          ],
        ),
        if (items.isNotEmpty) ...[
          if (complete) ...[
            Text(
              completed.toString() +
                  ' sur ' +
                  items.length.toString() +
                  ' démarches visibles terminées',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(
                value: completed / items.length,
                minHeight: 7,
                backgroundColor: scheme.primaryContainer,
              ),
            ),
            const SizedBox(height: 12),
          ] else
            const Padding(
              padding: EdgeInsets.only(bottom: 12),
              child: Text('Démarches visibles · données partielles'),
            ),
          if (completed > 0 || requiringAction > 0)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Wrap(
                spacing: 7,
                runSpacing: 4,
                children: [
                  if (requiringAction > 0)
                    ActionChip(
                      avatar: const Icon(Icons.bolt_rounded, size: 17),
                      label: Text(requiringAction.toString() + ' à traiter'),
                      onPressed: () {
                        setState(() => _filter = 'action');
                        _selectMode(_DossierMode.list);
                      },
                    ),
                  if (completed > 0)
                    ActionChip(
                      avatar: const Icon(Icons.check_circle_outline, size: 17),
                      label: Text(completed.toString() + ' terminée(s)'),
                      onPressed: () {
                        setState(() => _filter = 'fulfilled');
                        _selectMode(_DossierMode.list);
                      },
                    ),
                ],
              ),
            ),
          for (final item in items.take(3)) _journeyTile(item, compact: true),
        ] else ...[
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text(
              !complete
                  ? 'Aucune démarche disponible dans les données acquises.'
                  : 'Aucune démarche visible.',
            ),
          ),
          if (_cap(data, 'dossier.journey.link'))
            TextButton.icon(
              onPressed: _canMutate ? () => _link(data) : null,
              icon: const Icon(Icons.add_link_rounded),
              label: const Text('Lier une première démarche'),
            ),
        ],
        if (dependencies.isNotEmpty) ...[
          const SizedBox(height: 9),
          Card(
            elevation: 0,
            shape: RoundedRectangleBorder(
              side: BorderSide(color: scheme.outlineVariant),
              borderRadius: BorderRadius.circular(16),
            ),
            child: ExpansionTile(
              key: const PageStorageKey<String>('dossier-conditions-preview'),
              shape: const Border(),
              collapsedShape: const Border(),
              leading: Icon(Icons.account_tree_outlined, color: scheme.primary),
              title: const Text(
                'Conditions et dépendances',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              subtitle: Text(
                dependencies.length.toString() + ' relation(s) visible(s)',
              ),
              children: [
                for (final dep in dependencies.take(3))
                  ListTile(
                    dense: true,
                    leading: Icon(
                      _text(dep['state']) == 'waived'
                          ? Icons.remove_circle_outline
                          : dep['satisfied'] == true
                          ? Icons.check_circle_outline
                          : Icons.radio_button_unchecked,
                    ),
                    title: Text(_text(dep['required_label'])),
                    subtitle: Text(
                      _text(dep['state']) == 'waived'
                          ? 'Condition levée'
                          : dep['satisfied'] == true
                          ? 'Satisfaite'
                          : _text(dep['state']) == 'active'
                          ? 'À satisfaire'
                          : 'État non précisé',
                    ),
                  ),
                ListTile(
                  title: const Text('Explorer les dépendances'),
                  trailing: const Icon(Icons.arrow_forward_rounded),
                  onTap: () => _selectMode(_DossierMode.dependencies),
                ),
              ],
            ),
          ),
        ],
        if (items.isNotEmpty || dependencies.isNotEmpty) ...[
          const SizedBox(height: 20),
          Text(
            'Explorer le Dossier',
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 10),
          _tabs(),
        ],
        const SizedBox(height: 12),
        _dossierInformation(data),
        // No fabricated resources, proofs, payments or activity stream.
        // Any future contextual card must come from its canonical owner.
      ],
    );
  }

  Widget _dossierInformation(Map<String, dynamic> data) {
    final created = _parse(data['created_at']);
    final updated = _parse(data['updated_at']);
    if (created == null && updated == null) {
      return const SizedBox.shrink();
    }
    return ExpansionTile(
      key: const PageStorageKey<String>('dossier-information'),
      leading: const Icon(Icons.info_outline_rounded),
      title: const Text(
        'Informations du Dossier',
        style: TextStyle(fontWeight: FontWeight.w700),
      ),
      shape: const Border(),
      collapsedShape: const Border(),
      children: [
        if (created != null)
          ListTile(
            dense: true,
            leading: const Icon(Icons.add_circle_outline_rounded),
            title: const Text('Créé le'),
            subtitle: Text(_dateLabel(context, created.toLocal())),
          ),
        if (updated != null && updated != created)
          ListTile(
            dense: true,
            leading: const Icon(Icons.update_rounded),
            title: const Text('Mis à jour le'),
            subtitle: Text(_dateLabel(context, updated.toLocal())),
          ),
      ],
    );
  }

  Widget _empty(String message) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 14),
    child: Text(message, style: Theme.of(context).textTheme.bodyMedium),
  );

  static String _fold(String input) {
    const accented = 'àâäáãåçéèêëíìîïñóòôöõúùûüýÿ';
    const plain = 'aaaaaaceeeeiiiinooooouuuuyy';
    return input.trim().toLowerCase().split('').map((letter) {
      final index = accented.indexOf(letter);
      return index < 0 ? letter : plain[index];
    }).join();
  }

  List<Map<String, dynamic>> _filtered(
    List<Map<String, dynamic>> raw,
    Map<String, dynamic> dossier,
  ) {
    final term = _fold(_search.text);
    final nextAction = _map(_map(dossier['readiness'])['next_action']);
    final next = raw.where((r) {
      if (term.isNotEmpty && !_fold(_text(r['label'])).contains(term)) {
        return false;
      }
      return switch (_filter) {
        'action' => r['readiness_state'] == 'action_required',
        'waiting' => r['readiness_state'] == 'waiting',
        'blocked' => r['readiness_state'] == 'blocked',
        'fulfilled' => r['state'] == 'fulfilled',
        'undated' => _undated(r),
        'mine' => nextAction['journey_id'] == r['id'],
        _ => true,
      };
    }).toList();
    next.sort((a, b) {
      final first = switch (_sort) {
        _ListSort.name => _fold(_text(a['label'])),
        _ListSort.state => _text(a['state']),
        _ListSort.action =>
          a['readiness_state'] == 'action_required' ? '0' : '1',
        _ListSort.created => _text(a['created_at']),
        _ListSort.started => _text(a['started_at']),
        _ListSort.fulfilled => _text(a['fulfilled_at']),
        _ListSort.expiry => _text(a['expires_at']),
        _ => _text(a['updated_at']),
      };
      final second = switch (_sort) {
        _ListSort.name => _fold(_text(b['label'])),
        _ListSort.state => _text(b['state']),
        _ListSort.action =>
          b['readiness_state'] == 'action_required' ? '0' : '1',
        _ListSort.created => _text(b['created_at']),
        _ListSort.started => _text(b['started_at']),
        _ListSort.fulfilled => _text(b['fulfilled_at']),
        _ListSort.expiry => _text(b['expires_at']),
        _ => _text(b['updated_at']),
      };
      if (first.isEmpty != second.isEmpty) return first.isEmpty ? 1 : -1;
      if (_sort == _ListSort.recent ||
          _sort == _ListSort.created ||
          _sort == _ListSort.fulfilled) {
        return second.compareTo(first);
      }
      return first.compareTo(second);
    });
    return next;
  }

  Widget _popup(
    String title,
    String selected,
    Map<String, String> options,
    ValueChanged<String> onChange,
  ) => PopupMenuButton<String>(
    tooltip: title,
    initialValue: selected,
    onSelected: onChange,
    icon: Icon(
      title == 'Tri' ? Icons.sort_rounded : Icons.filter_alt_outlined,
      color: selected == 'all' || (title == 'Tri' && selected == 'recent')
          ? Theme.of(context).colorScheme.onSurfaceVariant
          : Theme.of(context).colorScheme.primary,
    ),
    itemBuilder: (_) => [
      for (final option in options.entries)
        CheckedPopupMenuItem<String>(
          value: option.key,
          checked: option.key == selected,
          child: Text(option.value),
        ),
    ],
  );

  Widget _journeyList(Map<String, dynamic> data) {
    final all = _rows(data['visible_journeys']);
    final items = _filtered(all, data);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          controller: _search,
          decoration: InputDecoration(
            prefixIcon: const Icon(Icons.search_rounded),
            hintText: 'Rechercher une démarche',
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
        const SizedBox(height: 10),
        Wrap(
          spacing: 7,
          runSpacing: 7,
          children: [
            _popup('Situation', _filter, const {
              'all': 'Toutes',
              'action': 'Action requise',
              'waiting': 'En attente',
              'blocked': 'Bloquées',
              'fulfilled': 'Réalisées',
              'undated': 'Sans date de parcours',
              'mine': 'Prochaine intervention personnelle',
            }, (v) => setState(() => _filter = v)),
            _popup(
              'Tri',
              _sort.name,
              const {
                'recent': 'Modification récente',
                'name': 'Nom',
                'state': 'État',
                'action': 'Action utile',
                'created': 'Date de création',
                'started': 'Date de début',
                'fulfilled': 'Date de réalisation',
                'expiry': 'Expiration indiquée',
              },
              (v) => setState(
                () =>
                    _sort = _ListSort.values.firstWhere((row) => row.name == v),
              ),
            ),
            ObjectiveFilterReset(
              active:
                  _search.text.trim().isNotEmpty ||
                  _filter != 'all' ||
                  _sort != _ListSort.recent,
              onClear: () {
                _search.clear();
                setState(() {
                  _filter = 'all';
                  _sort = _ListSort.recent;
                });
              },
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (items.isNotEmpty &&
            (_search.text.trim().isNotEmpty || _filter != 'all'))
          Text(
            '${items.length} résultat${items.length > 1 ? 's' : ''}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        if (items.isNotEmpty) const SizedBox(height: 10),
        if (items.isEmpty)
          _empty(
            all.isEmpty
                ? 'Aucune démarche visible liée à ce Dossier.'
                : 'Aucune démarche chargée ne correspond à ces critères.',
          )
        else
          for (final row in items) _journeyTile(row),
      ],
    );
  }

  static const _momentFields = <(String, String, bool)>[
    ('created_at', 'Démarche créée', false),
    ('submitted_at', 'Soumise', true),
    ('confirmed_at', 'Confirmée', true),
    ('started_at', 'Commencée', true),
    ('fulfilled_at', 'Réalisée', true),
    ('expires_at', 'Expiration indiquée', true),
  ];
  bool _undated(Map<String, dynamic> row) => !_momentFields
      .where((item) => item.$3)
      .any((field) => _parse(row[field.$1]) != null);

  Widget _timeline(Map<String, dynamic> data) {
    final journeys = _rows(data['visible_journeys']);
    final events = <_JourneyMoment>[];
    for (final row in journeys) {
      for (final field in _momentFields) {
        final stamp = _parse(row[field.$1]);
        if (stamp != null) {
          events.add(_JourneyMoment(row, stamp, field.$2));
        }
      }
    }
    events.sort((a, b) => a.when.compareTo(b.when));
    final undated = journeys.where(_undated).toList();
    final today = DateTime.now();
    final widgets = <Widget>[];
    var previousGroup = '';
    var todayInserted = false;
    for (final event in events) {
      final local = event.when.toLocal();
      var key = '';
      var caption = '';
      switch (_timeScale) {
        case _TimeScale.week:
          final monday = DateTime(
            local.year,
            local.month,
            local.day,
          ).subtract(Duration(days: local.weekday - 1));
          key = 'week-${monday.toIso8601String()}';
          caption = 'Semaine du ${_dateLabel(context, monday)}';
          break;
        case _TimeScale.month:
          key = 'month-${local.year}-${local.month}';
          caption = MaterialLocalizations.of(context).formatMonthYear(local);
          break;
        case _TimeScale.quarter:
          final quarter = ((local.month - 1) ~/ 3) + 1;
          key = 'quarter-${local.year}-$quarter';
          caption = 'Trimestre $quarter · ${local.year}';
          break;
      }
      if (key != previousGroup) {
        widgets.add(
          Padding(
            padding: const EdgeInsets.fromLTRB(9, 19, 9, 9),
            child: Text(
              caption,
              style: Theme.of(context).textTheme.titleSmall
                  ?.copyWith(fontWeight: FontWeight.w800),
            ),
          ),
        );
        previousGroup = key;
      }
      if (!todayInserted && !event.when.isBefore(today)) {
        widgets.add(_todayMarker(today));
        todayInserted = true;
      }
      widgets.add(_momentTile(event));
    }
    if (!todayInserted) widgets.add(_todayMarker(today));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Chronologie',
          style: Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 8),
        const Text(
          'Ce sont des faits temporels de Journey, pas un ordre causal. '
          'Une création ne constitue pas une date prévue.',
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 7,
          runSpacing: 7,
          children: [
            _popup(
              'Échelle',
              _timeScale.name,
              const {
                'week': 'Semaine',
                'month': 'Mois',
                'quarter': 'Trimestre',
              },
              (v) => setState(
                () => _timeScale = _TimeScale.values.firstWhere(
                  (row) => row.name == v,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 15),
        if (events.isEmpty)
          _empty('Aucun jalon temporel connu.')
        else
          ...widgets,
        if (undated.isNotEmpty) ...[
          const SizedBox(height: 20),
          Text(
            'Sans autre date de parcours',
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          for (final row in undated) _journeyTile(row, compact: true),
        ],
      ],
    );
  }

  Widget _todayMarker(DateTime today) => Container(
    margin: const EdgeInsets.symmetric(vertical: 10),
    padding: const EdgeInsets.all(11),
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(10),
      color: Theme.of(context).colorScheme.primary.withValues(alpha: .08),
    ),
    child: Text(
      'Aujourd’hui · ${_dateLabel(context, today)}',
      style: TextStyle(
        fontWeight: FontWeight.w700,
        color: Theme.of(context).colorScheme.primary,
      ),
    ),
  );
  Widget _momentTile(_JourneyMoment moment) => IntrinsicHeight(
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          width: 3,
          color: Theme.of(context).colorScheme.outlineVariant,
        ),
        const SizedBox(width: 13),
        Expanded(
          child: ListTile(
            leading: const Icon(Icons.circle, size: 13),
            title: Text(
              moment.label,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            subtitle: Text(
              '${_instantLabel(context, moment.when)} · '
              '${_text(moment.row['label'])}',
            ),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => widget.onOpenJourney(_text(moment.row['id'])),
          ),
        ),
      ],
    ),
  );

  void _graphZoom(double factor) {
    final value = _transform.value.clone();
    value.scaleByDouble(factor, factor, 1.0, 1.0);
    _transform.value = value;
  }

  Widget _dependencyView(Map<String, dynamic> data) {
    final journeys = _rows(data['visible_journeys']);
    final deps = _rows(data['visible_dependencies']);
    final model = _GraphLayout.build(journeys, deps);
    final byId = {for (final row in journeys) _text(row['id']): row};
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Graphe des dépendances',
          style: Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 8),
        const Text(
          'Chaque flèche va du prérequis à la démarche dépendante. '
          'Le déplacement du dessin ne modifie aucune relation métier.',
        ),
        if (data['graph_partial'] == true)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 13),
            child: Text(
              'Vue potentiellement partielle : certaines conditions '
              'ne sont pas visibles selon vos autorisations.',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        const SizedBox(height: 14),
        if (deps.isEmpty)
          _empty('Aucune dépendance visible définie.')
        else ...[
          Wrap(
            spacing: 7,
            runSpacing: 7,
            children: [
              MakoloActionButton(
                label: 'Zoom +',
                onPressed: () => _graphZoom(1.2),
                appearance: MakoloActionAppearance.secondary,
                icon: Icons.zoom_in_rounded,
              ),
              MakoloActionButton(
                label: 'Zoom −',
                onPressed: () => _graphZoom(1 / 1.2),
                appearance: MakoloActionAppearance.secondary,
                icon: Icons.zoom_out_rounded,
              ),
              MakoloActionButton(
                label: 'Recentrer',
                onPressed: () => _transform.value = Matrix4.identity(),
                appearance: MakoloActionAppearance.quiet,
                icon: Icons.center_focus_strong_outlined,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            height: 390,
            clipBehavior: Clip.hardEdge,
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              border: Border.all(
                color: Theme.of(context).colorScheme.outlineVariant,
              ),
              borderRadius: BorderRadius.circular(16),
            ),
            child: InteractiveViewer(
              transformationController: _transform,
              constrained: false,
              minScale: .45,
              maxScale: 3,
              boundaryMargin: const EdgeInsets.all(500),
              child: SizedBox(
                width: model.size.width,
                height: model.size.height,
                child: Stack(
                  children: [
                    CustomPaint(
                      size: model.size,
                      painter: _GraphPainter(
                        positions: model.positions,
                        edges: deps,
                        color: Theme.of(context).colorScheme.outline,
                      ),
                    ),
                    for (final dep in deps)
                      if (model.positions.containsKey(
                            _text(dep['required_journey_id']),
                          ) &&
                          model.positions.containsKey(
                            _text(dep['dependent_journey_id']),
                          ))
                        _graphEdgeTap(dep, model, byId),
                    for (final row in journeys)
                      if (model.positions.containsKey(_text(row['id'])))
                        Positioned(
                          left: model.positions[_text(row['id'])]!.dx,
                          top: model.positions[_text(row['id'])]!.dy,
                          child: SizedBox(
                            width: 196,
                            height: 76,
                            child: Card(
                              elevation: 0,
                              margin: EdgeInsets.zero,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                                side: BorderSide(
                                  color:
                                      row['readiness_state'] ==
                                          'action_required'
                                      ? Theme.of(context).colorScheme.primary
                                      : Theme.of(context)
                                            .colorScheme
                                            .outlineVariant,
                                ),
                              ),
                              child: InkWell(
                                onTap: () =>
                                    widget.onOpenJourney(_text(row['id'])),
                                child: Semantics(
                                  button: true,
                                  label:
                                      'Ouvrir la démarche ${_text(row['label'])}',
                                  child: Padding(
                                    padding: const EdgeInsets.all(9),
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          _text(row['label']),
                                          maxLines: 2,
                                          overflow: TextOverflow.ellipsis,
                                          style: const TextStyle(
                                            fontSize: 12,
                                            fontWeight: FontWeight.w700,
                                          ),
                                        ),
                                        const Spacer(),
                                        Text(
                                          _text(row['readiness_label'])
                                                  .isNotEmpty
                                              ? _text(row['readiness_label'])
                                              : _humanState(row['state']),
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: Theme.of(context)
                                              .textTheme
                                              .labelSmall,
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                  ],
                ),
              ),
            ),
          ),
        ],
        const SizedBox(height: 23),
        Text(
          'Liste accessible des prérequis',
          style: Theme.of(context).textTheme.titleMedium
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 9),
        for (final dep in deps)
          if (byId.containsKey(_text(dep['required_journey_id'])) &&
              byId.containsKey(_text(dep['dependent_journey_id'])))
            _dependencyTile(dep, byId),
      ],
    );
  }

  Widget _graphEdgeTap(
    Map<String, dynamic> dependency,
    _GraphLayout graph,
    Map<String, Map<String, dynamic>> byId,
  ) {
    final required = graph.positions[_text(dependency['required_journey_id'])]!;
    final dependent =
        graph.positions[_text(dependency['dependent_journey_id'])]!;
    final mid = Offset(
      (required.dx + dependent.dx + 196) / 2,
      (required.dy + dependent.dy + 76) / 2,
    );
    return Positioned(
      left: mid.dx - 24,
      top: mid.dy - 24,
      child: Tooltip(
        message: 'Voir le prérequis',
        child: Semantics(
          button: true,
          label: 'Consulter le prérequis entre deux démarches',
          child: InkWell(
            onTap: () => _explainDependency(dependency, byId),
            child: const SizedBox(
              width: 48,
              height: 48,
              child: Center(child: Icon(Icons.info_outline_rounded, size: 18)),
            ),
          ),
        ),
      ),
    );
  }

  void _explainDependency(
    Map<String, dynamic> dependency,
    Map<String, Map<String, dynamic>> byId,
  ) {
    final required = byId[_text(dependency['required_journey_id'])];
    final dependent = byId[_text(dependency['dependent_journey_id'])];
    if (required == null || dependent == null) return;
    showModalBottomSheet<void>(
      context: context,
      builder: (sheet) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Prérequis explicite',
                style: Theme.of(sheet).textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              Text(
                '${_text(required['label'])} est requis avant '
                '${_text(dependent['label'])}.',
              ),
              const SizedBox(height: 10),
              Text(
                dependency['state'] == 'waived'
                    ? 'Prérequis levé'
                    : dependency['satisfied'] == true
                    ? 'Prérequis satisfait'
                    : 'Prérequis à satisfaire',
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _dependencyTile(
    Map<String, dynamic> dep,
    Map<String, Map<String, dynamic>> byId,
  ) {
    final required = byId[_text(dep['required_journey_id'])]!;
    final dependent = byId[_text(dep['dependent_journey_id'])]!;
    return Card(
      elevation: 0,
      child: Padding(
        padding: const EdgeInsets.all(13),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${_text(required['label'])} → ${_text(dependent['label'])}',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            Text(
              dep['state'] == 'waived'
                  ? 'Prérequis levé'
                  : dep['satisfied'] == true
                  ? 'Prérequis satisfait'
                  : 'Prérequis à satisfaire',
            ),
            if (_cap(dep, 'remove') || _cap(dep, 'waive'))
              Wrap(
                spacing: 6,
                runSpacing: 7,
                children: [
                  if (_cap(dep, 'remove'))
                    MakoloActionButton(
                      label: 'Retirer le lien',
                      onPressed: _canMutate
                          ? () => _dependencyAction(dep, 'remove')
                          : null,
                      appearance: MakoloActionAppearance.danger,
                    ),
                  if (_cap(dep, 'waive'))
                    MakoloActionButton(
                      label: 'Lever le prérequis',
                      onPressed: _canMutate
                          ? () => _dependencyAction(dep, 'waive')
                          : null,
                      appearance: MakoloActionAppearance.danger,
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Dossier'),
      actions: [
        MakoloIconActionButton(
          tooltip: 'Actualiser',
          icon: Icons.refresh_rounded,
          onPressed: _refreshing ? null : _refresh,
        ),
      ],
    ),
    body: StreamBuilder<OwnerSourceState>(
      key: ValueKey<String>(
        'dossier-owner:${widget.id}:${_spaceSlug ?? 'personal'}',
      ),
      stream: _owner,
      initialData: OwnerSourceState.unknown,
      builder: (context, ownerSnapshot) {
        final owner = ownerSnapshot.data ?? OwnerSourceState.unknown;
        return StreamBuilder<StoredProjection?>(
          key: ValueKey<String>(
            'dossier-detail:${widget.id}:${_spaceSlug ?? 'personal'}',
          ),
          stream: _detail,
          builder: (context, detailSnapshot) {
            if (owner.invalidated) {
              return const Center(
                child: Text(
                  'Ce Dossier n’est plus accessible dans ce contexte.',
                ),
              );
            }
            final snapshot = detailSnapshot.data;
            if (snapshot == null) {
              return Center(
                child: _refreshing
                    ? const CircularProgressIndicator.adaptive()
                    : MakoloActionButton(
                        label: _failed ? 'Réessayer' : 'Charger ce Dossier',
                        onPressed: _refresh,
                        appearance: MakoloActionAppearance.quiet,
                      ),
              );
            }
            final data = snapshot.payload;
            return RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(
                controller: _pageScroll,
                key: PageStorageKey<String>(
                  'dossier-workspace-scroll:${_spaceSlug ?? 'personal'}',
                ),
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(16, 13, 16, 49),
                children: [
                  Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 950),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          _header(data),
                          const SizedBox(height: 12),
                          if (_mode == _DossierMode.overview)
                            _overview(data)
                          else ...[
                            _controls(data),
                            const SizedBox(height: 10),
                            _tabs(),
                            const SizedBox(height: 12),
                            if (_mode == _DossierMode.list)
                              _journeyList(data)
                            else if (_mode == _DossierMode.timeline)
                              _timeline(data)
                            else
                              _dependencyView(data),
                          ],
                          if (_busy)
                            const Padding(
                              padding: EdgeInsets.all(10),
                              child: LinearProgressIndicator(),
                            ),
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
}

class _JourneyMoment {
  const _JourneyMoment(this.row, this.when, this.label);
  final Map<String, dynamic> row;
  final DateTime when;
  final String label;
}

class _GraphLayout {
  const _GraphLayout(this.positions, this.size);
  final Map<String, Offset> positions;
  final Size size;

  static _GraphLayout build(
    List<Map<String, dynamic>> journeys,
    List<Map<String, dynamic>> dependencies,
  ) {
    final incoming = <String, List<String>>{
      for (final row in journeys) _text(row['id']): <String>[],
    };
    for (final dep in dependencies) {
      if (dep['state'] != 'active') continue;
      final target = _text(dep['dependent_journey_id']);
      final required = _text(dep['required_journey_id']);
      if (incoming.containsKey(target) && incoming.containsKey(required)) {
        incoming[target]!.add(required);
      }
    }
    final depths = <String, int>{};
    int depth(String id, Set<String> seen) {
      if (depths.containsKey(id)) return depths[id]!;
      if (seen.contains(id)) return 0;
      final next = {...seen, id};
      final value =
          incoming[id]?.fold<int>(
            0,
            (maxDepth, previous) =>
                math.max(maxDepth, 1 + depth(previous, next)),
          ) ??
          0;
      depths[id] = math.min(10, value);
      return depths[id]!;
    }

    final layers = <int, List<Map<String, dynamic>>>{};
    for (final row in journeys) {
      final layer = depth(_text(row['id']), {});
      layers.putIfAbsent(layer, () => []).add(row);
    }
    final positions = <String, Offset>{};
    for (final entry in layers.entries) {
      entry.value.sort(
        (a, b) => _text(a['label']).compareTo(_text(b['label'])),
      );
      for (var index = 0; index < entry.value.length; index++) {
        positions[_text(entry.value[index]['id'])] = Offset(
          34 + entry.key * 255.0,
          32 + index * 115.0,
        );
      }
    }
    final maxLayer = layers.isEmpty ? 0 : layers.keys.reduce(math.max);
    final maxRows = layers.values.fold<int>(
      1,
      (maxRows, group) => math.max(maxRows, group.length),
    );
    return _GraphLayout(
      positions,
      Size(
        math.max(450.0, (maxLayer + 1) * 255 + 34.0),
        math.max(310.0, maxRows * 115 + 50.0),
      ),
    );
  }
}

class _GraphPainter extends CustomPainter {
  _GraphPainter({
    required this.positions,
    required this.edges,
    required this.color,
  });
  final Map<String, Offset> positions;
  final List<Map<String, dynamic>> edges;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    for (final edge in edges) {
      final from = positions[_text(edge['required_journey_id'])];
      final to = positions[_text(edge['dependent_journey_id'])];
      if (from == null || to == null) continue;
      final origin = Offset(from.dx + 196, from.dy + 38);
      final target = Offset(to.dx - 6, to.dy + 38);
      final line = Paint()
        ..color = color.withValues(alpha: edge['state'] == 'waived' ? .45 : .8)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.1;
      final path = Path()
        ..moveTo(origin.dx, origin.dy)
        ..cubicTo(
          origin.dx + 40,
          origin.dy,
          target.dx - 40,
          target.dy,
          target.dx,
          target.dy,
        );
      canvas.drawPath(path, line);
      final theta = math.atan2(target.dy - origin.dy, target.dx - origin.dx);
      final arrow = Path()
        ..moveTo(target.dx, target.dy)
        ..lineTo(
          target.dx - 11 * math.cos(theta - .5),
          target.dy - 11 * math.sin(theta - .5),
        )
        ..moveTo(target.dx, target.dy)
        ..lineTo(
          target.dx - 11 * math.cos(theta + .5),
          target.dy - 11 * math.sin(theta + .5),
        );
      canvas.drawPath(arrow, line);
    }
  }

  @override
  bool shouldRepaint(covariant _GraphPainter old) =>
      old.edges != edges || old.positions != positions || old.color != color;
}
