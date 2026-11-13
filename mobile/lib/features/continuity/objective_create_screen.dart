import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/actor_context_controller.dart';
import '../../network/makolo_api_client.dart';
import '../../network/api_error.dart';
import '../../repositories/draft_repository.dart';
import 'objective_creation_draft.dart';
import 'objective_repository.dart';

/// Owner-backed creation; an offline form is not a confirmed Project/Dossier.
class ObjectiveCreateScreen extends StatefulWidget {
  const ObjectiveCreateScreen({
    super.key,
    required this.kind,
    required this.api,
    required this.repository,
    required this.drafts,
    required this.onCreated,
    this.onReview,
    this.spaceActor,
    this.actorContext,
  });

  final String kind;
  final MakoloApiClient api;
  final ObjectiveRepository repository;
  final DraftRepository drafts;
  final ValueChanged<String> onCreated;
  final VoidCallback? onReview;
  final SpaceActorIdentity? spaceActor;
  final ActorContextController? actorContext;

  @override
  State<ObjectiveCreateScreen> createState() => _ObjectiveCreateScreenState();
}

class _ObjectiveCreateScreenState extends State<ObjectiveCreateScreen> {
  final _form = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _description = TextEditingController();
  late ObjectiveCreationDraft _draft;
  Timer? _autosave;
  DateTime? _start, _end, _deadline;
  bool _restoring = true;
  bool _restoreFailed = false;
  bool _draftSaveFailed = false;
  bool _attempted = false;
  bool _submitting = false;
  String? _error;
  String? _confirmedId;
  String? _confirmedSpaceSlug;
  String? _confirmedKind;
  ObjectiveRepository? _confirmedRepository;

  bool get _isProject => widget.kind == 'project';
  bool get _actorValid {
    final owner = widget.spaceActor;
    final selected = widget.actorContext?.value;
    if (owner == null) return selected is! SpaceActorContext;
    return selected is SpaceActorContext && selected.space == owner;
  }

  void _onActorChanged() {
    if (mounted) setState(() {});
  }

  @override
  void initState() {
    super.initState();
    _draft = ObjectiveCreationDraft(
      repository: widget.drafts,
      profileId: widget.repository.profileId,
      kind: widget.kind,
      spaceId: widget.spaceActor?.id,
    );
    widget.actorContext?.addListener(_onActorChanged);
    _title.addListener(_scheduleDraft);
    _description.addListener(_scheduleDraft);
    unawaited(_restoreDraft());
  }

  @override
  void dispose() {
    _autosave?.cancel();
    if (!_restoring &&
        !_attempted &&
        !_submitting &&
        _confirmedId == null &&
        (_title.text.isNotEmpty ||
            _description.text.isNotEmpty ||
            _start != null ||
            _end != null ||
            _deadline != null)) {
      unawaited(_draft.save(_snapshot('editing')).catchError((Object _) {}));
    }
    widget.actorContext?.removeListener(_onActorChanged);
    _title.removeListener(_scheduleDraft);
    _description.removeListener(_scheduleDraft);
    _title.dispose();
    _description.dispose();
    super.dispose();
  }

  String? _iso(DateTime? date) => date == null
      ? null
      : '${date.year.toString().padLeft(4, '0')}-'
            '${date.month.toString().padLeft(2, '0')}-'
            '${date.day.toString().padLeft(2, '0')}';

  String _human(DateTime? value) {
    if (value == null) return 'Facultatif';
    return '${value.day.toString().padLeft(2, '0')}/'
        '${value.month.toString().padLeft(2, '0')}/${value.year}';
  }

  Future<void> _chooseDate(String field) async {
    final current = switch (field) {
      'start' => _start,
      'end' => _end,
      _ => _deadline,
    };
    final now = DateTime.now();
    final date = await showDatePicker(
      context: context,
      initialDate: current ?? now,
      firstDate: DateTime(1900),
      lastDate: DateTime(2100),
      helpText: 'Choisir une date',
    );
    if (date == null || !mounted) return;
    setState(() {
      switch (field) {
        case 'start':
          _start = date;
          break;
        case 'end':
          _end = date;
          break;
        default:
          _deadline = date;
          break;
      }
    });
  }

  Widget _dateField(String field, String label, DateTime? value) => ListTile(
    contentPadding: EdgeInsets.zero,
    dense: true,
    title: Text(label),
    subtitle: value == null ? null : Text(_human(value)),
    trailing: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        MakoloIconActionButton(
          tooltip: 'Choisir : $label',
          onPressed: _submitting ? null : () => _chooseDate(field),
          icon: Icons.calendar_today_outlined,
        ),
        if (value != null)
          MakoloIconActionButton(
            tooltip: 'Effacer : $label',
            onPressed: _submitting
                ? null
                : () => setState(() {
                    switch (field) {
                      case 'start':
                        _start = null;
                        break;
                      case 'end':
                        _end = null;
                        break;
                      default:
                        _deadline = null;
                        break;
                    }
                  }),
            icon: Icons.close_rounded,
          ),
      ],
    ),
  );

  Future<void> _submit() async {
    if (_submitting ||
        !_actorValid ||
        !(_form.currentState?.validate() ?? false))
      return;
    if (_isProject &&
        _start != null &&
        _end != null &&
        _start!.isAfter(_end!)) {
      setState(() => _error = 'La fin ne peut pas précéder le début.');
      return;
    }
    final submittedKind = widget.kind;
    final submittedSpaceSlug = widget.spaceActor?.slug;
    final submittedRepository = widget.repository;
    final submittedApi = widget.api;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final result = await submittedApi.post(
        'api/v1/objectives/${submittedKind == 'project' ? 'projects' : 'dossiers'}/'
        '${ObjectiveRepository.contextQuery(submittedSpaceSlug)}',
        body: {
          'title': _title.text.trim(),
          'description': _description.text.trim(),
          if (_isProject && _start != null) 'starts_on': _iso(_start),
          if (_isProject && _end != null) 'ends_on': _iso(_end),
          if (!_isProject && _deadline != null) 'deadline': _iso(_deadline),
        },
      );
      final id = result.jsonObject()['id']?.toString();
      if (id == null || id.isEmpty) {
        throw const FormatException('Invalid Objectives owner response');
      }
      // Keep the owner's confirmed identity even if the active actor changes
      // while the list is revalidating. Otherwise the result disappears and
      // the human may repeat a mutation that already succeeded.
      if (mounted) {
        setState(() {
          _confirmedId = id;
          _confirmedSpaceSlug = submittedSpaceSlug;
          _confirmedKind = submittedKind;
          _confirmedRepository = submittedRepository;
        });
      }
      // The mutation is confirmed. The parent list is now revalidated.
      try {
        await submittedRepository.refreshOrganizerPage(
          0,
          spaceSlug: submittedSpaceSlug,
        );
        if (submittedSpaceSlug != null) {
          try {
            await submittedRepository.refreshOrganizerPage(0);
          } on Object {
            // Refreshing Moi is secondary to the confirmed Space creation.
          }
        }
      } on Object {
        // The new detail still opens; the organizer can retry its refresh.
      }
      if (mounted &&
          _actorValid &&
          widget.kind == submittedKind &&
          widget.spaceActor?.slug == submittedSpaceSlug &&
          identical(widget.repository, submittedRepository)) {
        widget.onCreated(id);
      }
    } on Object {
      if (mounted) {
        setState(
          () => _error = _confirmedId == null
              ? 'Création non confirmée. Vérifiez votre connexion et les informations saisies.'
              : 'Création confirmée, mais ouverture indisponible.',
        );
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final confirmedId = _confirmedId;
    if (confirmedId != null) {
      final owner = _confirmedSpaceSlug;
      return Scaffold(
        appBar: AppBar(title: const Text('Création confirmée')),
        body: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 480),
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.check_circle_outline_rounded, size: 42),
                    const SizedBox(height: 12),
                    Text(
                      'La réalisation a été créée.',
                      style: Theme.of(context).textTheme.titleLarge,
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      owner == null
                          ? 'Elle appartient à votre Profil.'
                          : 'Elle appartient à l’Espace $owner.',
                      textAlign: TextAlign.center,
                    ),
                    if (!_actorValid) ...[
                      const SizedBox(height: 8),
                      const Text(
                        'Le contexte actif a changé. Revenez au contexte '
                        'de création pour ouvrir cette réalisation.',
                        textAlign: TextAlign.center,
                      ),
                    ],
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      Text(
                        _error!,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ],
                    const SizedBox(height: 18),
                    MakoloActionButton(
                      label: 'Ouvrir la réalisation',
                      onPressed:
                          !_actorValid ||
                              _submitting ||
                              widget.kind != _confirmedKind ||
                              widget.spaceActor?.slug != _confirmedSpaceSlug ||
                              !identical(
                                widget.repository,
                                _confirmedRepository,
                              )
                          ? null
                          : () => widget.onCreated(confirmedId),
                      appearance: MakoloActionAppearance.primary,
                      icon: Icons.open_in_new_rounded,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    }
    if (!_actorValid) {
      return const Scaffold(
        body: Center(child: Text('La création doit être rouverte.')),
      );
    }
    final project = _isProject;
    final title = project ? 'Créer un projet' : 'Créer un dossier';
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 600),
            child: Form(
              key: _form,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(18, 14, 18, 24),
                children: [
                  TextFormField(
                    controller: _title,
                    autofocus: true,
                    maxLength: 220,
                    enabled: !_submitting,
                    textCapitalization: TextCapitalization.sentences,
                    decoration: InputDecoration(
                      labelText: project
                          ? 'Nom du projet'
                          : 'Objectif du dossier',
                      border: const OutlineInputBorder(),
                    ),
                    validator: (value) => value == null || value.trim().isEmpty
                        ? 'Ce titre est obligatoire.'
                        : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _description,
                    maxLines: 4,
                    enabled: !_submitting,
                    decoration: const InputDecoration(
                      labelText: 'Description (facultative)',
                      border: OutlineInputBorder(),
                      alignLabelWithHint: true,
                    ),
                  ),
                  const SizedBox(height: 20),
                  if (project) ...[
                    _dateField('start', 'Début de l’horizon', _start),
                    _dateField('end', 'Fin de l’horizon', _end),
                  ] else
                    _dateField('deadline', 'Échéance', _deadline),
                  const SizedBox(height: 24),
                  if (_error != null) ...[
                    Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                    const SizedBox(height: 12),
                  ],
                  MakoloActionButton(
                    label: _submitting ? 'Confirmation…' : title,
                    onPressed: _submitting ? null : _submit,
                    busy: _submitting,
                    icon: Icons.check_rounded,
                    appearance: MakoloActionAppearance.primary,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
