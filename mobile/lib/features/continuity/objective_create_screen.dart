import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/actor_context_controller.dart';
import '../../network/makolo_api_client.dart';
import 'objective_repository.dart';

/// Owner-backed creation; an offline form is not a confirmed Project/Dossier.
class ObjectiveCreateScreen extends StatefulWidget {
  const ObjectiveCreateScreen({
    super.key,
    required this.kind,
    required this.api,
    required this.repository,
    required this.onCreated,
    this.spaceActor,
    this.actorContext,
  });

  final String kind;
  final MakoloApiClient api;
  final ObjectiveRepository repository;
  final ValueChanged<String> onCreated;
  final SpaceActorIdentity? spaceActor;
  final ActorContextController? actorContext;

  @override
  State<ObjectiveCreateScreen> createState() => _ObjectiveCreateScreenState();
}

class _ObjectiveCreateScreenState extends State<ObjectiveCreateScreen> {
  final _form = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _description = TextEditingController();
  DateTime? _start, _end, _deadline;
  bool _submitting = false;
  String? _error;

  bool get _isProject => widget.kind == 'project';
  bool get _actorValid {
    final owner = widget.spaceActor;
    if (owner == null) return true;
    final selected = widget.actorContext?.value;
    return selected is SpaceActorContext && selected.space == owner;
  }

  void _onActorChanged() {
    if (mounted) setState(() {});
  }

  @override
  void initState() {
    super.initState();
    widget.actorContext?.addListener(_onActorChanged);
  }

  @override
  void dispose() {
    widget.actorContext?.removeListener(_onActorChanged);
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
    if (value == null) return 'Non renseignée';
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

  Widget _dateField(String field, String label, DateTime? value) => Row(
    children: [
      Expanded(child: Text('$label : ${_human(value)}')),
      MakoloActionButton(
        label: 'Choisir',
        appearance: MakoloActionAppearance.quiet,
        onPressed: _submitting ? null : () => _chooseDate(field),
        icon: Icons.calendar_today_outlined,
      ),
      if (value != null)
        MakoloIconActionButton(
          tooltip: 'Effacer la date',
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
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final result = await widget.api.post(
        'api/v1/objectives/${_isProject ? 'projects' : 'dossiers'}/'
        '${ObjectiveRepository.contextQuery(widget.spaceActor?.slug)}',
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
      // The mutation is confirmed. The parent list is now revalidated.
      try {
        await widget.repository.refreshOrganizerPage(
          0,
          spaceSlug: widget.spaceActor?.slug,
        );
        if (widget.spaceActor != null) {
          try {
            await widget.repository.refreshOrganizerPage(0);
          } on Object {
            // Refreshing Moi is secondary to the confirmed Space creation.
          }
        }
      } on Object {
        // The new detail still opens; the organizer can retry its refresh.
      }
      if (mounted && _actorValid) widget.onCreated(id);
    } on Object {
      if (mounted) {
        setState(
          () => _error = 'Création non confirmée. Vérifiez votre connexion et les informations saisies.',
        );
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_actorValid) {
      return const Scaffold(
        body: Center(child: Text('Cet Espace n’est plus le contexte actif.')),
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
