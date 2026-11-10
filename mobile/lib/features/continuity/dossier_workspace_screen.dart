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
import 'objective_context_banner.dart';
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
    super.dispose();
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  bool get _offline =>
      SyncStatusScope.maybeOf(context)?.state == SyncVisualState.offline;
  bool get _canMutate => widget.api != null && !_busy && !_offline;
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
      if (cached == null ||
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
        await widget.repository.refreshOrganizerPage(0);
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
      'Désigner un responsable',
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

  Widget _controls(Map<String, dynamic> data) => Wrap(
    spacing: 9,
    runSpacing: 9,
    children: [
      if (_cap(data, 'dossier.journey.link'))
        MakoloActionButton(
          label: 'Lier une démarche',
          onPressed: _canMutate ? () => _link(data) : null,
          icon: Icons.link_rounded,
          appearance: MakoloActionAppearance.primary,
        ),
      if (_cap(data, 'dossier.dependency.add'))
        MakoloActionButton(
          label: 'Ajouter un prérequis',
          onPressed: _canMutate ? () => _newDependency(data) : null,
          icon: Icons.account_tree_outlined,
          appearance: MakoloActionAppearance.secondary,
        ),
      if (_cap(data, 'dossier.project.manage'))
        MakoloActionButton(
          label: 'Rattachement',
          onPressed: _canMutate ? () => _projectAction(data) : null,
          icon: Icons.drive_file_move_outlined,
          appearance: MakoloActionAppearance.secondary,
        ),
      if (_cap(data, 'dossier.lifecycle'))
        MakoloActionButton(
          label: 'Changer l’état',
          onPressed: _canMutate ? () => _lifecycle(data) : null,
          icon: Icons.change_circle_outlined,
          appearance: MakoloActionAppearance.secondary,
        ),
      if (_cap(data, 'dossier.assignment.manage'))
        MakoloActionButton(
          label: 'Responsabilité',
          onPressed: _canMutate ? () => _assign(data) : null,
          icon: Icons.person_add_alt_outlined,
          appearance: MakoloActionAppearance.secondary,
        ),
      if (_cap(data, 'dossier.authority.manage'))
        MakoloActionButton(
          label: 'Mandat',
          onPressed: _canMutate ? () => _grant(data) : null,
          icon: Icons.shield_outlined,
          appearance: MakoloActionAppearance.secondary,
        ),
    ],
  );

  Widget _header(Map<String, dynamic> data) {
    final objective = _map(data['objective']);
    final parent = _map(data['parent_project']);
    final readiness = _map(data['readiness']);
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
                    _text(_map(data['owner'])['label']),
                    style: theme.textTheme.labelMedium?.copyWith(
                      color: theme.colorScheme.primary,
                      letterSpacing: .5,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _text(objective['title']),
                    style: theme.textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            ),
            if (_cap(data, 'dossier.edit'))
              MakoloIconActionButton(
                tooltip: 'Modifier le Dossier',
                onPressed: _canMutate ? () => _edit(data) : null,
                icon: Icons.edit_outlined,
              ),
          ],
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
            Chip(
              label: Text(
                _text(readiness['label']).isNotEmpty
                    ? _text(readiness['label'])
                    : 'Situation à confirmer',
              ),
            ),
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

  Widget _tabs() => LayoutBuilder(
    builder: (context, bounds) {
      final buttons = [
        (_DossierMode.overview, 'Vue d’ensemble', Icons.dashboard_outlined),
        (_DossierMode.list, 'Liste', Icons.list_rounded),
        (_DossierMode.timeline, 'Chronologie', Icons.calendar_month_outlined),
        (_DossierMode.dependencies, 'Dépendances', Icons.account_tree_outlined),
      ];
      if (bounds.maxWidth < 650) {
        return Wrap(
          spacing: 7,
          runSpacing: 7,
          children: [
            for (final (mode, label, icon) in buttons)
              ChoiceChip(
                selected: _mode == mode,
                label: Text(label),
                avatar: Icon(icon, size: 16),
                onSelected: (_) => setState(() => _mode = mode),
              ),
          ],
        );
      }
      return SegmentedButton<_DossierMode>(
        showSelectedIcon: false,
        selected: {_mode},
        segments: const [
          ButtonSegment(
            value: _DossierMode.overview,
            label: Text('Vue d’ensemble'),
            icon: Icon(Icons.dashboard_outlined),
          ),
          ButtonSegment(
            value: _DossierMode.list,
            label: Text('Liste'),
            icon: Icon(Icons.list),
          ),
          ButtonSegment(
            value: _DossierMode.timeline,
            label: Text('Chronologie'),
            icon: Icon(Icons.calendar_month_outlined),
          ),
          ButtonSegment(
            value: _DossierMode.dependencies,
            label: Text('Dépendances'),
            icon: Icon(Icons.account_tree_outlined),
          ),
        ],
        onSelectionChanged: (values) => setState(() => _mode = values.first),
      );
    },
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
    constraints: const BoxConstraints(minWidth: 125),
    padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 14),
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

  Widget _collaboration(Map<String, dynamic> data) {
    final assignments = _rows(data['assignments']);
    final mandates = _rows(data['mandates']);
    if (assignments.isEmpty && mandates.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 19),
        Text(
          'Personnes et responsabilités',
          style: Theme.of(context).textTheme.titleMedium
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        for (final row in assignments)
          ListTile(
            leading: const Icon(Icons.person_outline_rounded),
            title: Text(_text(row['label'])),
            subtitle: const Text('Responsabilité opérationnelle'),
            trailing: _cap(row, 'remove')
                ? MakoloIconActionButton(
                    tooltip: 'Retirer la responsabilité',
                    icon: Icons.person_remove_outlined,
                    onPressed: _canMutate ? () => _removeAssignment(row) : null,
                  )
                : null,
          ),
        for (final row in mandates)
          ListTile(
            leading: const Icon(Icons.shield_outlined),
            title: Text(_text(row['profile'])),
            subtitle: Text('Mandat · ${_text(row['role'])}'),
            trailing: _cap(row, 'revoke')
                ? MakoloIconActionButton(
                    tooltip: 'Révoquer ce mandat',
                    icon: Icons.shield_outlined,
                    onPressed: _canMutate ? () => _revoke(row) : null,
                  )
                : null,
          ),
        Text(
          'Responsabilité et autorité restent distinctes ; '
          'elles ne créent aucun droit automatique sur les Journeys.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }

  Widget _overview(Map<String, dynamic> data) {
    final items = _rows(data['visible_journeys']);
    final deps = _rows(data['visible_dependencies']);
    final readiness = _map(data['readiness']);
    final next = _map(readiness['next_action']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Vue d’ensemble',
          style: Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 7),
        const Text(
          'Ce qui avance, ce qui attend et la prochaine intervention utile.',
        ),
        const SizedBox(height: 16),
        Card(
          elevation: 0,
          color: Theme.of(context).colorScheme.primary.withValues(alpha: .065),
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  _text(readiness['label']).isNotEmpty
                      ? _text(readiness['label'])
                      : 'Situation non disponible',
                  style: Theme.of(context).textTheme.titleMedium
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 8),
                Text(
                  next.isNotEmpty
                      ? 'Prochaine intervention : ${_text(next['label'])}'
                      : readiness['partial'] == true
                      ? 'La situation collective est partielle.'
                      : 'Aucune intervention personnelle explicitement signalée.',
                ),
                if (next['journey_id'] != null)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: MakoloActionButton(
                      label: 'Voir la démarche',
                      onPressed: () =>
                          widget.onOpenJourney(_text(next['journey_id'])),
                      appearance: MakoloActionAppearance.quiet,
                      icon: Icons.arrow_forward_rounded,
                    ),
                  ),
                if (_text(readiness['hidden_signal']).isNotEmpty)
                  Text(
                    _text(readiness['hidden_signal']),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 9,
          runSpacing: 9,
          children: [
            _metric('${items.length}', 'Démarches visibles'),
            _metric(
              '${items.where((r) => r['state'] == 'fulfilled').length}',
              'Réalisées',
            ),
            _metric(
              '${items.where((r) => r['readiness_state'] == 'action_required').length}',
              'Action requise',
            ),
            _metric(
              '${deps.where((r) => r['state'] == 'active').length}',
              'Prérequis visibles actifs',
            ),
          ],
        ),
        const SizedBox(height: 21),
        Text(
          'Démarches du Dossier',
          style: Theme.of(context).textTheme.titleMedium
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 11),
        if (items.isEmpty)
          _empty('Aucune démarche visible liée.')
        else
          for (final row in items.take(7)) _journeyTile(row, compact: true),
        if (items.length > 7)
          MakoloActionButton(
            label: 'Voir toutes les démarches',
            onPressed: () => setState(() => _mode = _DossierMode.list),
            appearance: MakoloActionAppearance.quiet,
            icon: Icons.list_rounded,
          ),
        _collaboration(data),
      ],
    );
  }

  Widget _empty(String message) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 28),
    child: Column(
      children: [
        Icon(
          Icons.folder_open_outlined,
          size: 39,
          color: Theme.of(context).colorScheme.primary,
        ),
        const SizedBox(height: 12),
        Text(
          message,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium,
        ),
      ],
    ),
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
    itemBuilder: (_) => [
      for (final option in options.entries)
        PopupMenuItem(value: option.key, child: Text(option.value)),
    ],
    child: Chip(
      avatar: const Icon(Icons.keyboard_arrow_down_rounded, size: 16),
      label: Text(options[selected] ?? title),
    ),
  );

  Widget _journeyList(Map<String, dynamic> data) {
    final all = _rows(data['visible_journeys']);
    final items = _filtered(all, data);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Toutes les démarches',
          style: Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 7),
        const Text('Recherche et classement locaux des démarches acquises.'),
        const SizedBox(height: 14),
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
              active: _search.text.trim().isNotEmpty ||
                  _filter != 'all' || _sort != _ListSort.recent,
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
        Text(
          _search.text.trim().isNotEmpty || _filter != 'all'
              ? '${items.length} '
                    '${items.length == 1 ? 'résultat' : 'résultats'} '
                    'parmi les démarches chargées'
              : '${items.length} '
                    '${items.length == 1 ? 'démarche chargée' : 'démarches chargées'}',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 12),
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
      left: mid.dx - 12,
      top: mid.dy - 12,
      child: Tooltip(
        message: 'Voir le prérequis',
        child: Semantics(
          button: true,
          label: 'Consulter le prérequis entre deux démarches',
          child: InkWell(
            onTap: () => _explainDependency(dependency, byId),
            child: const SizedBox(
              width: 26,
              height: 26,
              child: Icon(Icons.info_outline_rounded, size: 17),
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
                          ObjectiveContextBanner(payload: data),
                          const SizedBox(height: 12),
                          _header(data),
                          if (_offline)
                            const Padding(
                              padding: EdgeInsets.only(top: 8),
                              child: Text(
                                'Mode hors ligne · données locales acquises.',
                              ),
                            ),
                          const SizedBox(height: 18),
                          _controls(data),
                          const SizedBox(height: 23),
                          _tabs(),
                          const SizedBox(height: 22),
                          if (_mode == _DossierMode.overview)
                            _overview(data)
                          else if (_mode == _DossierMode.list)
                            _journeyList(data)
                          else if (_mode == _DossierMode.timeline)
                            _timeline(data)
                          else
                            _dependencyView(data),
                          if (_busy)
                            const Padding(
                              padding: EdgeInsets.all(10),
                              child: LinearProgressIndicator(),
                            ),
                          if (_failed)
                            MakoloActionButton(
                              label: 'Actualisation impossible · Réessayer',
                              onPressed: _refresh,
                              appearance: MakoloActionAppearance.quiet,
                              icon: Icons.refresh_rounded,
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
