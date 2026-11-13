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
    if (date == null ||
        !mounted ||
        _attempted ||
        _submitting ||
        _restoring ||
        _restoreFailed) {
      return;
    }
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
    _scheduleDraft();
  }

  DateTime? _restoredDate(Object? value) =>
      value is String ? DateTime.tryParse(value) : null;

  Map<String, dynamic> _snapshot(
    String submissionState, {
    String? confirmedId,
  }) => {
    'title': _title.text,
    'description': _description.text,
    'starts_on': _iso(_start),
    'ends_on': _iso(_end),
    'deadline': _iso(_deadline),
    'submission_state': submissionState,
    'confirmed_id': ?confirmedId,
  };

  Future<void> _restoreDraft() async {
    try {
      final stored = await _draft.read();
      if (!mounted) return;
      final data = stored?.payload;
      final state = data?['submission_state'];
      final id = data?['confirmed_id'];
      setState(() {
        if (data != null) {
          _title.text = data['title'] is String ? data['title'] as String : '';
          _description.text = data['description'] is String
              ? data['description'] as String
              : '';
          _start = _restoredDate(data['starts_on']);
          _end = _restoredDate(data['ends_on']);
          _deadline = _restoredDate(data['deadline']);
        }
        _attempted =
            state == 'verification_required' ||
            (state == 'confirmed' && (id is! String || id.isEmpty));
        if (state == 'confirmed' && id is String && id.isNotEmpty) {
          _confirmedId = id;
          _confirmedSpaceSlug = widget.spaceActor?.slug;
          _confirmedKind = widget.kind;
          _confirmedRepository = widget.repository;
        }
        _restoring = false;
        _restoreFailed = false;
        _draftSaveFailed = false;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _restoring = false;
        _restoreFailed = true;
      });
    }
  }

  void _scheduleDraft() {
    if (_restoring || _attempted || _submitting || _confirmedId != null) {
      return;
    }
    _autosave?.cancel();
    _autosave = Timer(const Duration(milliseconds: 350), () {
      final values = _snapshot('editing');
      unawaited(
        _draft
            .save(values)
            .then((_) {
              if (mounted && _draftSaveFailed) {
                setState(() => _draftSaveFailed = false);
              }
            })
            .catchError((Object _) {
              if (mounted) setState(() => _draftSaveFailed = true);
            }),
      );
    });
  }

  Future<void> _retryRestore() async {
    if (_restoring || _submitting) return;
    setState(() => _restoring = true);
    await _restoreDraft();
  }

  Future<void> _resumeAfterReview() async {
    if (!_attempted || _submitting) return;
    final reviewed = await showDialog<bool>(
      context: context,
      builder: (dialog) => AlertDialog(
        title: const Text('Reprendre ?'),
        content: const Text(
          'Vérifiez d’abord dans Mes démarches si la création existe déjà. '
          'Renvoyer pourrait créer un doublon.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialog, false),
            child: const Text('Annuler'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialog, true),
            child: const Text('J’ai vérifié'),
          ),
        ],
      ),
    );
    if (reviewed != true || !mounted || !_actorValid) return;
    try {
      await _draft.save(_snapshot('editing'), verifiedReopen: true);
      if (mounted) {
        setState(() {
          _attempted = false;
          _error = null;
          _draftSaveFailed = false;
        });
      }
    } on Object {
      if (mounted) setState(() => _draftSaveFailed = true);
    }
  }

  Future<void> _startAnother() async {
    if (_confirmedId == null || _submitting) return;
    try {
      await _draft.clear();
    } on Object {
      if (mounted) setState(() => _draftSaveFailed = true);
      return;
    }
    if (!mounted) return;
    _autosave?.cancel();
    setState(() {
      _title.clear();
      _description.clear();
      _start = null;
      _end = null;
      _deadline = null;
      _confirmedId = null;
      _confirmedKind = null;
      _confirmedSpaceSlug = null;
      _confirmedRepository = null;
      _attempted = false;
      _error = null;
      _draftSaveFailed = false;
    });
  }

  Widget _draftMark() {
    final String label;
    final IconData symbol;
    if (_restoring) {
      label = 'Reprise';
      symbol = Icons.hourglass_empty_rounded;
    } else if (_restoreFailed || _draftSaveFailed) {
      label = 'Sauvegarde indisponible';
      symbol = Icons.error_outline_rounded;
    } else if (_attempted) {
      label = 'À vérifier avant de renvoyer';
      symbol = Icons.schedule_outlined;
    } else if (_confirmedId != null) {
      label = 'Création confirmée';
      symbol = Icons.check_circle_outline_rounded;
    } else {
      label = 'Brouillon';
      symbol = Icons.edit_note_rounded;
    }
    return Tooltip(
      message: label,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Icon(
          symbol,
          size: 20,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
          semanticLabel: label,
        ),
      ),
    );
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
          onPressed: _submitting || _restoring || _restoreFailed || _attempted
              ? null
              : () => _chooseDate(field),
          icon: Icons.calendar_today_outlined,
        ),
        if (value != null)
          MakoloIconActionButton(
            tooltip: 'Effacer : $label',
            onPressed: _submitting || _restoring || _restoreFailed || _attempted
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
                    _scheduleDraft();
                  }),
            icon: Icons.close_rounded,
          ),
      ],
    ),
  );

  Future<void> _submit() async {
    if (_submitting ||
        _restoring ||
        _restoreFailed ||
        _attempted ||
        _confirmedId != null ||
        !_actorValid ||
        !(_form.currentState?.validate() ?? false)) {
      return;
    }
    if (_isProject &&
        _start != null &&
        _end != null &&
        _start!.isAfter(_end!)) {
      setState(() => _error = 'La fin ne peut pas précéder le début.');
      return;
    }

    final submittedKind = widget.kind;
    final submittedSpace = widget.spaceActor;
    final submittedSpaceSlug = submittedSpace?.slug;
    final submittedRepository = widget.repository;
    final submittedDraft = _draft;
    final submittedApi = widget.api;
    final values = _snapshot('verification_required');
    _autosave?.cancel();
    setState(() {
      _submitting = true;
      _attempted = true;
      _error = null;
    });

    var requestStarted = false;
    try {
      // This must be durable BEFORE the non-idempotent owner POST. Restoring
      // this state never schedules a replay or silently enables another send.
      await submittedDraft.save(values);
      if (!mounted ||
          !_actorValid ||
          widget.kind != submittedKind ||
          widget.spaceActor != submittedSpace ||
          !identical(widget.repository, submittedRepository)) {
        // Nothing reached Django. Restore the editable draft for that scope.
        await submittedDraft.save({
          ...values,
          'submission_state': 'editing',
        }, verifiedReopen: true);
        if (mounted) setState(() => _attempted = false);
        return;
      }
      requestStarted = true;
      final result = await submittedApi.post(
        'api/v1/objectives/${submittedKind == 'project' ? 'projects' : 'dossiers'}/'
        '${ObjectiveRepository.contextQuery(submittedSpaceSlug)}',
        body: {
          'title': (values['title'] as String).trim(),
          'description': (values['description'] as String).trim(),
          if (submittedKind == 'project' && values['starts_on'] != null)
            'starts_on': values['starts_on'],
          if (submittedKind == 'project' && values['ends_on'] != null)
            'ends_on': values['ends_on'],
          if (submittedKind != 'project' && values['deadline'] != null)
            'deadline': values['deadline'],
        },
      );
      final id = result.jsonObject()['id']?.toString();
      if (id == null || id.isEmpty) {
        throw const FormatException('Invalid Objectives owner response');
      }

      // A confirmed identity survives actor switches, screen disposal and a
      // failed organizer refresh. Persistence failure leaves verification_required
      // on disk (safe), never silently restores an editable duplicate.
      if (mounted) {
        setState(() {
          _confirmedId = id;
          _confirmedSpaceSlug = submittedSpaceSlug;
          _confirmedKind = submittedKind;
          _confirmedRepository = submittedRepository;
          _attempted = false;
          _draftSaveFailed = false;
        });
      }
      try {
        await submittedDraft.save({
          ...values,
          'submission_state': 'confirmed',
          'confirmed_id': id,
        });
      } on Object {
        if (mounted) setState(() => _draftSaveFailed = true);
      }

      try {
        await submittedRepository.refreshOrganizerPage(
          0,
          spaceSlug: submittedSpaceSlug,
        );
        if (submittedSpaceSlug != null) {
          try {
            await submittedRepository.refreshOrganizerPage(0);
          } on Object {
            // Personal collection refresh is secondary to confirmed creation.
          }
        }
      } on Object {
        // The owner-confirmed detail may still be opened directly.
      }
      if (mounted &&
          _actorValid &&
          widget.kind == submittedKind &&
          widget.spaceActor == submittedSpace &&
          identical(widget.repository, submittedRepository)) {
        widget.onCreated(id);
      }
    } on MakoloApiError catch (error) {
      final definitive =
          requestStarted &&
          const {400, 401, 403, 404, 422}.contains(error.statusCode);
      if (definitive) {
        try {
          await submittedDraft.save({
            ...values,
            'submission_state': 'editing',
          }, verifiedReopen: true);
          if (mounted) {
            setState(() {
              _attempted = false;
              _error = 'Vérifiez les informations saisies.';
            });
          }
        } on Object {
          if (mounted) setState(() => _draftSaveFailed = true);
        }
      } else if (!requestStarted && mounted) {
        setState(() {
          _attempted = false;
          _draftSaveFailed = true;
        });
      }
      // After an uncertain send, the saved draft remains À vérifier.
      // Never automatically retry a Project/Dossier creation.
    } on Object {
      if (!requestStarted && mounted) {
        setState(() {
          _attempted = false;
          _draftSaveFailed = true;
        });
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
        appBar: AppBar(
          title: const Text('Création confirmée'),
          actions: [_draftMark()],
        ),
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
                    const SizedBox(height: 8),
                    MakoloActionButton(
                      label: 'Créer un autre',
                      onPressed: !_actorValid || _submitting
                          ? null
                          : _startAnother,
                      appearance: MakoloActionAppearance.quiet,
                      icon: Icons.add_rounded,
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
      appBar: AppBar(title: Text(title), actions: [_draftMark()]),
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
                    enabled:
                        !_submitting &&
                        !_restoring &&
                        !_restoreFailed &&
                        !_attempted,
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
                    enabled:
                        !_submitting &&
                        !_restoring &&
                        !_restoreFailed &&
                        !_attempted,
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
                  if (_restoreFailed)
                    TextButton.icon(
                      onPressed: _retryRestore,
                      icon: const Icon(Icons.refresh_rounded),
                      label: const Text('Réessayer'),
                    ),
                  if (_attempted) ...[
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      child: Row(
                        children: [
                          Icon(
                            Icons.schedule_outlined,
                            size: 18,
                            color: Theme.of(context)
                                .colorScheme
                                .onSurfaceVariant,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'À vérifier',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ),
                    Wrap(
                      spacing: 8,
                      children: [
                        if (widget.onReview != null)
                          TextButton.icon(
                            onPressed: _submitting ? null : widget.onReview,
                            icon: const Icon(Icons.search_rounded),
                            label: const Text('Mes démarches'),
                          ),
                        TextButton.icon(
                          onPressed: _submitting ? null : _resumeAfterReview,
                          icon: const Icon(Icons.edit_note_rounded),
                          label: const Text('Reprendre'),
                        ),
                      ],
                    ),
                  ],
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
                    onPressed:
                        _submitting ||
                            _restoring ||
                            _restoreFailed ||
                            _attempted
                        ? null
                        : _submit,
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
