import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../design/action_controls.dart';
import '../../network/api_error.dart';
import '../questionnaires/questionnaire_form_screen.dart';
import 'journey_artifact_repository.dart';

/// A Journey with a Space beneficiary is not a personal /me Journey and not
/// the provider's Space Service Case. Each access uses the current mandate.
class SpaceBeneficiaryJourneyScreen extends StatefulWidget {
  const SpaceBeneficiaryJourneyScreen({
    super.key,
    required this.runtime,
    required this.space,
    required this.journeyId,
  });

  final AppRuntime runtime;
  final SpaceActorIdentity space;
  final String journeyId;

  @override
  State<SpaceBeneficiaryJourneyScreen> createState() =>
      _SpaceBeneficiaryJourneyScreenState();
}

class _SpaceBeneficiaryJourneyScreenState
    extends State<SpaceBeneficiaryJourneyScreen> {
  late SpaceBeneficiaryJourneyRepository _repository;
  bool _busy = false;
  bool _denied = false;
  String? _error;
  int _epoch = 0;

  bool get _actorValid {
    final value = widget.runtime.actorContext?.value;
    return value is SpaceActorContext && value.space == widget.space;
  }

  @override
  void initState() {
    super.initState();
    _repository = _open();
    widget.runtime.actorContext?.addListener(_onActorChange);
    unawaited(_refresh());
  }

  SpaceBeneficiaryJourneyRepository _open() =>
      SpaceBeneficiaryJourneyRepository(
        database: widget.runtime.database!,
        store: widget.runtime.store!,
        profileId: widget.runtime.session!.profileId,
        sync: widget.runtime.sync,
      );

  @override
  void didUpdateWidget(covariant SpaceBeneficiaryJourneyScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(_onActorChange);
      widget.runtime.actorContext?.addListener(_onActorChange);
    }
    if (oldWidget.runtime != widget.runtime ||
        oldWidget.space != widget.space ||
        oldWidget.journeyId != widget.journeyId) {
      _epoch++;
      _repository = _open();
      _denied = false;
      unawaited(_refresh());
    }
  }

  @override
  void dispose() {
    _epoch++;
    widget.runtime.actorContext?.removeListener(_onActorChange);
    super.dispose();
  }

  void _onActorChange() {
    if (!mounted) return;
    setState(() {
      _denied = !_actorValid;
      _error = null;
    });
    if (_actorValid) unawaited(_refresh());
  }

  Future<void> _refresh() async {
    if (_busy || !_actorValid) return;
    final revision = ++_epoch;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await _repository.refresh(widget.space, widget.journeyId);
      if (mounted && revision == _epoch && _actorValid) {
        setState(() => _denied = false);
      }
    } on MakoloApiError catch (error) {
      if (!mounted || revision != _epoch) return;
      if (error.statusCode == 403 || error.statusCode == 404) {
        await _repository.store.deleteProjection(
          SpaceBeneficiaryJourneyRepository.projectionKind,
          resourceKey: SpaceBeneficiaryJourneyRepository.resourceKey(
            widget.space,
            widget.journeyId,
          ),
        );
        if (mounted) setState(() => _denied = true);
      } else {
        setState(
          () => _error = 'La synchronisation a échoué. Les données locales sont conservées.',
        );
      }
    } on Object {
      if (mounted && revision == _epoch) {
        setState(
          () => _error =
              'Les informations récentes sont momentanément indisponibles.',
        );
      }
    } finally {
      if (mounted && revision == _epoch) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Demande de cet Espace'),
      actions: [
        IconButton(
          tooltip: 'Actualiser',
          onPressed: _actorValid && !_busy ? _refresh : null,
          icon: const Icon(Icons.refresh_rounded),
        ),
      ],
    ),
    body: !_actorValid || _denied
        ? const Center(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Text(
                'Cette demande n’est plus accessible avec le contexte sélectionné.',
              ),
            ),
          )
        : StreamBuilder<StoredProjection?>(
            stream: _repository.watch(widget.space, widget.journeyId),
            builder: (context, snapshot) {
              final raw = snapshot.data?.payload;
              final state = _row(raw?['state']);
              final representation = _row(raw?['representation']);
              final service = _row(raw?['service_request']);
              final opportunity = _row(service['opportunity']);
              final result = _row(raw?['service_result']);
              final capabilities = _row(raw?['capabilities']);
              final forms = _rows(raw?['forms']);
              final requirements = _rows(raw?['requirements']);
              final steps = _rows(raw?['steps']);
              final links = _row(raw?['links']);
              return ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  if (_busy) const LinearProgressIndicator(),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: Text(_error!),
                    ),
                  if (raw == null)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 28),
                      child: Text(
                        'Cette demande n’est pas encore disponible localement.',
                      ),
                    )
                  else ...[
                    Text(
                      representation['title']?.toString() ?? 'Demande',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 4),
                    Text('Pour ${widget.space.slug}'),
                    const SizedBox(height: 8),
                    Text(state['label']?.toString() ?? 'État non connu'),
                    if (service['objective'] is String &&
                        (service['objective'] as String).trim().isNotEmpty) ...[
                      const SizedBox(height: 16),
                      Text(
                        'Votre objectif',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(service['objective'] as String),
                    ],
                    if (opportunity['title'] is String) ...[
                      const SizedBox(height: 16),
                      Text(
                        'Opportunité concernée',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(opportunity['title'] as String),
                      if (opportunity['publication_state'] != 'published')
                        const Text(
                          'La référence est conservée, mais l’opportunité n’est plus publiée.',
                        ),
                    ],
                    if (result['label'] is String) ...[
                      const SizedBox(height: 16),
                      Text(
                        'Réponse de l’organisme',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(result['label'] as String),
                    ],
                    if (steps.isNotEmpty) ...[
                      const SizedBox(height: 20),
                      Text(
                        'Progression de la demande',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      for (final step in steps)
                        ListTile(
                          title: Text(step['title']?.toString() ?? 'Étape'),
                          subtitle: Text(step['status']?.toString() ?? ''),
                        ),
                    ],
                    if (requirements.isNotEmpty) ...[
                      const SizedBox(height: 16),
                      Text(
                        'Conditions',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      for (final requirement in requirements)
                        ListTile(
                          leading: const Icon(Icons.fact_check_outlined),
                          title: Text(
                            requirement['label']?.toString() ?? 'Condition',
                          ),
                          subtitle: Text(
                            requirement['state']?.toString() ?? '',
                          ),
                          onTap: () {
                            final link = requirement['link'];
                            if (link is String && link.isNotEmpty) {
                              _openDetail(context, link);
                            }
                          },
                        ),
                    ],
                    if (forms.isNotEmpty) ...[
                      const SizedBox(height: 16),
                      Text(
                        'Formulaires',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      for (final form in forms)
                        ListTile(
                          leading: const Icon(Icons.description_outlined),
                          title: Text(
                            form['title']?.toString() ?? 'Formulaire',
                          ),
                          subtitle: Text(form['status']?.toString() ?? ''),
                          onTap: form['link'] is String
                              ? () => context.push(
                                  '/space/${Uri.encodeComponent(widget.space.slug)}/beneficiary/journeys/${widget.journeyId}/forms/${form['id']}',
                                )
                              : null,
                        ),
                    ],
                    const SizedBox(height: 16),
                    if (capabilities['answer_intake'] == true)
                      MakoloActionButton(
                        label: 'Préparer et envoyer la demande',
                        appearance: MakoloActionAppearance.primary,
                        icon: Icons.edit_document,
                        onPressed: () => context.push(
                          '/space/${Uri.encodeComponent(widget.space.slug)}/beneficiary/journeys/${widget.journeyId}/intake',
                        ),
                      ),
                    if (links['artifacts'] is String)
                      MakoloActionButton(
                        label: 'Pièces de cette demande',
                        icon: Icons.attach_file_rounded,
                        onPressed: () => context.push(
                          '/space/${Uri.encodeComponent(widget.space.slug)}/beneficiary/journeys/${widget.journeyId}/artifacts',
                        ),
                      ),
                    if (links['resources'] is String)
                      MakoloActionButton(
                        label: 'Ressources pour se préparer',
                        icon: Icons.menu_book_outlined,
                        onPressed: () => context.push(
                          '/space/${Uri.encodeComponent(widget.space.slug)}/beneficiary/journeys/${widget.journeyId}/resources',
                        ),
                      ),
                  ],
                ],
              );
            },
          ),
  );

  void _openDetail(BuildContext context, String link) {
    final id = Uri.tryParse(link)?.pathSegments
        .lastWhere((piece) => piece.isNotEmpty, orElse: () => '');
    if (id != null && id.isNotEmpty) {
      context.push(
        '/space/${Uri.encodeComponent(widget.space.slug)}/beneficiary/journeys/${widget.journeyId}/requirements/$id',
      );
    }
  }
}

Map<String, dynamic> _row(Object? value) =>
    value is Map ? Map<String, dynamic>.from(value) : const {};

List<Map<String, dynamic>> _rows(Object? value) => value is List
    ? value
          .whereType<Map>()
          .map((row) => Map<String, dynamic>.from(row))
          .toList()
    : const [];

/// The owner keeps the actual Intake answers and submission state. A local
/// draft is an intention; neither offline storage nor a tap is a confirmation.
class SpaceBeneficiaryIntakeScreen extends StatefulWidget {
  const SpaceBeneficiaryIntakeScreen({
    super.key,
    required this.runtime,
    required this.space,
    required this.journeyId,
  });

  final AppRuntime runtime;
  final SpaceActorIdentity space;
  final String journeyId;

  @override
  State<SpaceBeneficiaryIntakeScreen> createState() =>
      _SpaceBeneficiaryIntakeScreenState();
}

class _SpaceBeneficiaryIntakeScreenState
    extends State<SpaceBeneficiaryIntakeScreen> {
  Map<String, dynamic>? _owner;
  final Map<String, dynamic> _answers = {};
  final Map<String, TextEditingController> _textFields = {};
  bool _loading = true;
  bool _sending = false;
  String? _error;
  int _epoch = 0;

  String get _draftKey =>
      'space-service-intake:${widget.runtime.session?.profileId}:${widget.space.id}:${widget.journeyId}';

  String get _path =>
      'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.space.slug)}/beneficiary/journeys/${widget.journeyId}/intake/';

  bool get _actorValid {
    final value = widget.runtime.actorContext?.value;
    return value is SpaceActorContext && value.space == widget.space;
  }

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_onActorChange);
    unawaited(_load());
  }

  @override
  void dispose() {
    _epoch++;
    widget.runtime.actorContext?.removeListener(_onActorChange);
    for (final field in _textFields.values) {
      field.dispose();
    }
    super.dispose();
  }

  void _onActorChange() {
    if (!mounted) return;
    setState(() {
      _owner = null;
      _error = null;
    });
    if (_actorValid) unawaited(_load());
  }

  Future<void> _load() async {
    if (!_actorValid) return;
    final epoch = ++_epoch;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final local = await widget.runtime.interactions?.read(_draftKey);
      final serialized = local?['answers'];
      final restored = serialized is String ? jsonDecode(serialized) : null;
      final response = await widget.runtime.api!.get(_path);
      final payload = response.jsonObject();
      if (payload['journey_id'] != widget.journeyId ||
          payload['questions'] is! List) {
        throw const FormatException('Incorrect Services Intake owner');
      }
      if (!mounted || epoch != _epoch || !_actorValid) return;
      final questions = _rows(payload['questions']);
      setState(() {
        _owner = payload;
        _answers.clear();
        for (final question in questions) {
          final id = question['id']?.toString();
          if (id != null && question['value'] != null) {
            _answers[id] = question['value'];
          }
        }
        if (restored is Map) {
          for (final entry in restored.entries) {
            if (entry.key is String &&
                questions.any((question) => question['id'] == entry.key)) {
              _answers[entry.key as String] = entry.value;
            }
          }
        }
        for (final field in _textFields.values) {
          field.dispose();
        }
        _textFields.clear();
        for (final question in questions) {
          final id = question['id']?.toString();
          if (id == null) continue;
          if (const {'short_text', 'long_text'}.contains(question['type'])) {
            _textFields[id] = TextEditingController(
              text: _answers[id]?.toString() ?? '',
            );
          }
        }
        _loading = false;
      });
    } on Object {
      if (mounted && epoch == _epoch) {
        setState(() {
          _loading = false;
          _error = 'Les questions ne sont pas accessibles actuellement.';
        });
      }
    }
  }

  void _edit(String id, dynamic value) {
    setState(() => _answers[id] = value);
    unawaited(_saveDraft());
  }

  Future<void> _saveDraft() async {
    try {
      await widget.runtime.interactions?.save(_draftKey, {
        'answers': jsonEncode(_answers),
      });
    } on Object {
      // Keep the unsent answers in memory without claiming a saved draft.
    }
  }

  Future<void> _submit(bool confirm) async {
    if (_sending || !_actorValid || _owner?['can_edit'] != true) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await _saveDraft();
      final response = await widget.runtime.api!.post(
        _path,
        body: {'answers': _answers, 'submit': confirm},
      );
      final data = response.jsonObject();
      if (data['journey_id'] != widget.journeyId) {
        throw const FormatException('Owner confirmation mismatch');
      }
      if (!mounted || !_actorValid) return;
      setState(() {
        _owner = data;
        _error = confirm
            ? 'La demande a été reçue. Son état est défini par le Service.'
            : 'Réponses enregistrées par le Service.';
      });
      await widget.runtime.interactions?.clear(_draftKey);
      if (confirm && mounted) Navigator.of(context).pop();
    } on Object {
      if (mounted) {
        setState(() {
          _error =
              'Aucune confirmation reçue. Votre brouillon reste disponible.';
        });
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final editable = _actorValid && _owner?['can_edit'] == true;
    final questions = _rows(_owner?['questions']);
    return Scaffold(
      appBar: AppBar(title: const Text('Préparer la demande')),
      body: !_actorValid
          ? const Center(child: Text('Cet Espace n’est plus sélectionné.'))
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                if (_loading) const LinearProgressIndicator(),
                if (_error != null) Text(_error!),
                if (!_loading && _owner == null)
                  MakoloActionButton(
                    label: 'Réessayer',
                    onPressed: _load,
                    icon: Icons.refresh_rounded,
                  ),
                if (_owner != null) ...[
                  if (!editable)
                    const Text('Les réponses ne sont plus modifiables.'),
                  for (final question in questions) ...[
                    const SizedBox(height: 16),
                    Text(
                      '${question['label'] ?? 'Question'}${question['required'] == true ? ' *' : ''}',
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    _question(question, editable),
                  ],
                  const SizedBox(height: 20),
                  if (editable) ...[
                    MakoloActionButton(
                      label: 'Enregistrer les réponses',
                      onPressed: _sending ? null : () => _submit(false),
                      busy: _sending,
                    ),
                    const SizedBox(height: 8),
                    MakoloActionButton(
                      label: 'Envoyer la demande',
                      appearance: MakoloActionAppearance.primary,
                      icon: Icons.send_outlined,
                      onPressed: _sending ? null : () => _submit(true),
                      busy: _sending,
                    ),
                  ],
                ],
              ],
            ),
    );
  }

  Widget _question(Map<String, dynamic> question, bool enabled) {
    final id = question['id']?.toString() ?? '';
    final type = question['type']?.toString() ?? '';
    final value = _answers[id];
    final choices = question['options'] is List
        ? (question['options'] as List).map((item) => item.toString()).toList()
        : <String>[];
    if (type == 'boolean') {
      return SwitchListTile(
        title: Text(value == true ? 'Oui' : 'Non'),
        value: value == true,
        onChanged: enabled ? (selected) => _edit(id, selected) : null,
      );
    }
    if (type == 'date') {
      return MakoloActionButton(
        label: value?.toString() ?? 'Choisir une date',
        icon: Icons.event_outlined,
        onPressed: enabled
            ? () async {
                final selected = await showDatePicker(
                  context: context,
                  initialDate: DateTime.now(),
                  firstDate: DateTime(1900),
                  lastDate: DateTime(2200),
                );
                if (selected != null) {
                  _edit(
                    id,
                    '${selected.year.toString().padLeft(4, '0')}-${selected.month.toString().padLeft(2, '0')}-${selected.day.toString().padLeft(2, '0')}',
                  );
                }
              }
            : null,
      );
    }
    if (type == 'single_choice') {
      return DropdownButtonFormField<String>(
        initialValue: choices.contains(value) ? value as String : null,
        items: choices
            .map(
              (choice) => DropdownMenuItem(value: choice, child: Text(choice)),
            )
            .toList(),
        onChanged: enabled ? (choice) => _edit(id, choice) : null,
      );
    }
    if (type == 'multiple_choice') {
      final selected = value is List
          ? value.map((item) => item.toString()).toSet()
          : <String>{};
      return Column(
        children: [
          for (final choice in choices)
            CheckboxListTile(
              title: Text(choice),
              value: selected.contains(choice),
              onChanged: enabled
                  ? (checked) {
                      final next = Set<String>.from(selected);
                      if (checked == true) {
                        next.add(choice);
                      } else {
                        next.remove(choice);
                      }
                      _edit(id, next.toList());
                    }
                  : null,
            ),
        ],
      );
    }
    return TextField(
      controller: _textFields[id],
      enabled: enabled,
      maxLines: type == 'long_text' ? 5 : 1,
      maxLength: type == 'short_text' ? 500 : null,
      onChanged: (text) => _edit(id, text),
    );
  }
}

/// Small owner-only read depth. No local Requirement satisfaction is computed.
class SpaceBeneficiaryRequirementScreen extends StatefulWidget {
  const SpaceBeneficiaryRequirementScreen({
    super.key,
    required this.runtime,
    required this.space,
    required this.journeyId,
    required this.assessmentId,
  });

  final AppRuntime runtime;
  final SpaceActorIdentity space;
  final String journeyId;
  final String assessmentId;

  @override
  State<SpaceBeneficiaryRequirementScreen> createState() =>
      _SpaceBeneficiaryRequirementScreenState();
}

class _SpaceBeneficiaryRequirementScreenState
    extends State<SpaceBeneficiaryRequirementScreen> {
  Map<String, dynamic>? _details;
  String? _error;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<void> _load() async {
    final actor = widget.runtime.actorContext?.value;
    if (actor is! SpaceActorContext || actor.space != widget.space) return;
    try {
      final response = await widget.runtime.api!.get(
        'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.space.slug)}/beneficiary/journeys/${widget.journeyId}/requirements/${widget.assessmentId}/',
      );
      if (!mounted) return;
      setState(() {
        _details = response.jsonObject();
        _error = null;
      });
    } on Object {
      if (mounted)
        setState(() => _error = 'Condition actuellement indisponible.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final actor = widget.runtime.actorContext?.value;
    final allowed = actor is SpaceActorContext && actor.space == widget.space;
    final requirement = _row(_details?['requirement']);
    return Scaffold(
      appBar: AppBar(title: const Text('Condition de la demande')),
      body: !allowed
          ? const Center(child: Text('Contexte Espace différent.'))
          : Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (_error != null) Text(_error!),
                  if (_details == null) const LinearProgressIndicator(),
                  if (_details != null) ...[
                    Text(
                      requirement['title']?.toString() ?? 'Condition',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 12),
                    Text(requirement['status']?.toString() ?? ''),
                    const SizedBox(height: 12),
                    const Text(
                      'Avoir un document ne signifie pas que la condition est validée.',
                    ),
                  ],
                ],
              ),
            ),
    );
  }
}
