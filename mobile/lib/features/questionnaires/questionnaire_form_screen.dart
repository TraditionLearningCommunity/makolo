import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/behavior_states.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../repositories/draft_repository.dart';
import '../../sync/outbox/outbox_processor.dart';
import '../../sync/outbox/outbox_repository.dart';
import 'questionnaire_repository.dart';
import 'questionnaire_submit_coordinator.dart';

class QuestionnaireFormScreen extends StatefulWidget {
  const QuestionnaireFormScreen({
    super.key,
    required this.requestId,
    required this.journeyId,
    required this.links,
    required this.repository,
    required this.drafts,
    required this.outbox,
    required this.submitCoordinator,
    this.outboxProcessor,
  });

  final String requestId;
  final String journeyId;
  final QuestionnaireOwnerLinks links;
  final QuestionnaireRepository repository;
  final DraftRepository drafts;
  final OutboxRepository outbox;
  final QuestionnaireSubmitCoordinator submitCoordinator;
  final OutboxProcessor? outboxProcessor;

  @override
  State<QuestionnaireFormScreen> createState() =>
      _QuestionnaireFormScreenState();
}

class _QuestionnaireFormScreenState extends State<QuestionnaireFormScreen> {
  Timer? _autosave;
  Map<String, dynamic> _answers = <String, dynamic>{};
  Map<String, dynamic> _serverErrors = <String, dynamic>{};
  bool _initializedAnswers = false;
  bool _refreshing = false;
  bool _savingDraft = false;

  String get _draftId => 'questionnaire:${widget.requestId}';

  @override
  void initState() {
    super.initState();
    unawaited(_prepare());
  }

  Future<void> _prepare() async {
    final draft = await widget.drafts.read(
      owner: QuestionnaireSubmitCoordinator.owner,
      resourceKind: QuestionnaireSubmitCoordinator.resourceKind,
      resourceId: widget.requestId,
    );
    final local = await widget.repository.readParsed(widget.requestId);
    if (!mounted) return;
    _applyInitial(local, draft);
    unawaited(_refresh());
  }

  void _applyInitial(
    QuestionnaireRequestDetail? owner,
    StoredLocalDraft? draft,
  ) {
    if (_initializedAnswers) return;
    final draftAnswers = draft?.payload['answers'];
    final draftErrors = draft?.payload['server_errors'];
    setState(() {
      if (draftAnswers is Map) {
        _answers = draftAnswers.map(
          (key, value) => MapEntry(key.toString(), value),
        );
      } else if (owner != null) {
        _answers = Map<String, dynamic>.from(owner.answers);
      }
      if (draftErrors is Map) {
        _serverErrors = draftErrors.map(
          (key, value) => MapEntry(key.toString(), value),
        );
      }
      _initializedAnswers = true;
    });
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refresh(
        requestId: widget.requestId,
        detailPath: widget.links.detail,
      );
    } on Object {
      // Local content and draft remain authoritative for device-owned work.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  void _changed(String key, Object? value) {
    setState(() {
      _answers[key] = value;
      _serverErrors.remove(key);
      _serverErrors.remove('_form');
    });
    _autosave?.cancel();
    _autosave = Timer(const Duration(milliseconds: 450), () {
      unawaited(_persistDraft());
    });
  }

  Future<void> _persistDraft() async {
    if (_savingDraft) return;
    _savingDraft = true;
    try {
      await widget.drafts.saveLocal(
        draftId: _draftId,
        owner: QuestionnaireSubmitCoordinator.owner,
        resourceKind: QuestionnaireSubmitCoordinator.resourceKind,
        resourceId: widget.requestId,
        payload: <String, dynamic>{
          'answers': _answers,
          if (_serverErrors.isNotEmpty) 'server_errors': _serverErrors,
          'base_observed_at': DateTime.now().toUtc().toIso8601String(),
        },
      );
    } finally {
      _savingDraft = false;
      if (mounted) setState(() {});
    }
  }

  Future<void> _submit(QuestionnaireRequestDetail detail) async {
    final validation = _validate(detail);
    if (validation.isNotEmpty) {
      setState(() => _serverErrors = validation);
      return;
    }
    await _persistDraft();
    final created = await widget.submitCoordinator.enqueue(
      requestId: widget.requestId,
      journeyId: widget.journeyId,
      answers: Map<String, dynamic>.from(_answers),
      links: widget.links,
    );
    if (created) {
      await widget.outboxProcessor?.run();
    }
  }

  Map<String, dynamic> _validate(QuestionnaireRequestDetail detail) {
    final errors = <String, dynamic>{};
    for (final question in detail.questions) {
      final value = _answers[question.key];
      final missing =
          value == null || value == '' || (value is List && value.isEmpty);
      if (question.required && missing) {
        errors[question.key] = 'Ce champ est obligatoire.';
        continue;
      }
      if (missing) continue;
      if (value is String) {
        if (question.minLength != null && value.length < question.minLength!) {
          errors[question.key] = 'Minimum ${question.minLength} caractères.';
        }
        if (question.maxLength != null && value.length > question.maxLength!) {
          errors[question.key] = 'Maximum ${question.maxLength} caractères.';
        }
      }
    }
    return errors;
  }

  @override
  void dispose() {
    _autosave?.cancel();
    if (_initializedAnswers) {
      unawaited(_persistDraft());
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      stream: widget.repository.watchDetail(widget.requestId),
      builder: (context, snapshot) {
        final projection = snapshot.data;
        QuestionnaireRequestDetail? detail;
        if (projection != null) {
          try {
            detail = QuestionnaireRequestDetail.fromPayload(projection.payload);
          } on FormatException {
            detail = null;
          }
        }

        if (!_initializedAnswers && detail != null) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) _applyInitial(detail, null);
          });
        }

        return StreamBuilder<List<OutboxResourceOperation>>(
          stream: widget.outbox.watchResource(
            operationKind: QuestionnaireSubmitCoordinator.operationKind,
            resourceId: widget.requestId,
          ),
          initialData: const [],
          builder: (context, operationsSnapshot) {
            final operation = operationsSnapshot.data?.isNotEmpty == true
                ? operationsSnapshot.data!.first
                : null;
            final commit = _commitCue(operation);

            return Scaffold(
              appBar: AppBar(
                title: Text(detail?.title ?? 'Formulaire'),
                actions: [
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              body: detail == null
                  ? (_refreshing
                        ? const MakoloLoadingState(
                            label: 'Chargement du formulaire…',
                          )
                        : MakoloErrorState(
                            message: 'Ce formulaire n’est pas disponible sur cet appareil.',
                            preservedMessage: 'Votre brouillon local, s’il existe, est conservé.',
                            onRetry: _refresh,
                          ))
                  : _FormContent(
                      detail: detail,
                      answers: _answers,
                      errors: _serverErrors,
                      commit: commit,
                      refreshing: _refreshing,
                      canSubmit:
                          widget.links.canSubmit &&
                          !detail.isSubmitted &&
                          !_operationActive(operation),
                      onChanged: _changed,
                      onSubmit: () => _submit(detail!),
                    ),
            );
          },
        );
      },
    );
  }

  bool _operationActive(OutboxResourceOperation? operation) {
    if (operation == null) return false;
    return operation.state == OutboxState.queued.wireValue ||
        operation.state == OutboxState.inFlight.wireValue ||
        operation.state == OutboxState.awaitingConfirmation.wireValue;
  }

  MakoloCommitCue _commitCue(OutboxResourceOperation? operation) {
    if (operation == null) {
      return _initializedAnswers
          ? MakoloCommitCue.savedOnDevice
          : MakoloCommitCue.none;
    }
    return switch (operation.state) {
      'queued' || 'in_flight' => MakoloCommitCue.pending,
      'awaiting_confirmation' => MakoloCommitCue.awaitingConfirmation,
      'confirmed' => MakoloCommitCue.confirmed,
      'conflict' => MakoloCommitCue.conflict,
      'failed' => MakoloCommitCue.failed,
      _ => MakoloCommitCue.none,
    };
  }
}

class _FormContent extends StatelessWidget {
  const _FormContent({
    required this.detail,
    required this.answers,
    required this.errors,
    required this.commit,
    required this.refreshing,
    required this.canSubmit,
    required this.onChanged,
    required this.onSubmit,
  });

  final QuestionnaireRequestDetail detail;
  final Map<String, dynamic> answers;
  final Map<String, dynamic> errors;
  final MakoloCommitCue commit;
  final bool refreshing;
  final bool canSubmit;
  final void Function(String key, Object? value) onChanged;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(MakoloSpacing.inner),
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      children: [
        if (detail.description != null) ...[
          Text(
            detail.description!,
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          const SizedBox(height: MakoloSpacing.lg),
        ],
        if (refreshing) ...[
          const MakoloRefreshIndicator(label: 'Vérification du formulaire…'),
          const SizedBox(height: MakoloSpacing.md),
        ],
        MakoloCommitIndicator(commit: commit),
        if (errors['_form'] != null) ...[
          const SizedBox(height: MakoloSpacing.md),
          InlineMessage(message: errors['_form'].toString()),
        ],
        const SizedBox(height: MakoloSpacing.lg),
        for (final question in detail.questions) ...[
          _QuestionField(
            question: question,
            value: answers[question.key],
            error: errors[question.key]?.toString(),
            onChanged: (value) => onChanged(question.key, value),
          ),
          const SizedBox(height: MakoloSpacing.inner),
        ],
        FilledButton.icon(
          onPressed: canSubmit ? onSubmit : null,
          icon: const Icon(Icons.check_rounded),
          label: Text(detail.isSubmitted ? 'Déjà soumis' : 'Soumettre'),
        ),
        if (!canSubmit && !detail.isSubmitted) ...[
          const SizedBox(height: MakoloSpacing.sm),
          Text(
            'La soumission reste sous l’autorité du serveur et sera confirmée à distance.',
            style: Theme.of(context).textTheme.bodySmall,
            textAlign: TextAlign.center,
          ),
        ],
      ],
    );
  }
}

class _QuestionField extends StatelessWidget {
  const _QuestionField({
    required this.question,
    required this.value,
    required this.onChanged,
    this.error,
  });

  final QuestionnaireQuestion question;
  final Object? value;
  final ValueChanged<Object?> onChanged;
  final String? error;

  String get _label => question.label + (question.required ? ' *' : '');

  @override
  Widget build(BuildContext context) {
    switch (question.type) {
      case QuestionnaireQuestionType.shortText:
      case QuestionnaireQuestionType.longText:
        return TextFormField(
          key: ValueKey(question.key),
          initialValue: value?.toString() ?? '',
          minLines: question.type == QuestionnaireQuestionType.longText ? 4 : 1,
          maxLines: question.type == QuestionnaireQuestionType.longText ? 8 : 1,
          maxLength: question.maxLength,
          textInputAction: question.type == QuestionnaireQuestionType.longText
              ? TextInputAction.newline
              : TextInputAction.next,
          decoration: InputDecoration(
            labelText: _label,
            helperText: question.helpText,
            errorText: error,
          ),
          onChanged: onChanged,
        );
      case QuestionnaireQuestionType.number:
        return TextFormField(
          key: ValueKey(question.key),
          initialValue: value?.toString() ?? '',
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          textInputAction: TextInputAction.next,
          decoration: InputDecoration(
            labelText: _label,
            helperText: question.helpText,
            errorText: error,
          ),
          onChanged: onChanged,
        );
      case QuestionnaireQuestionType.boolean:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(_label),
              subtitle: question.helpText == null
                  ? null
                  : Text(question.helpText!),
              value: value == true,
              onChanged: onChanged,
            ),
            if (error != null)
              Text(
                error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        );
      case QuestionnaireQuestionType.singleChoice:
        return _ChoiceField(
          question: question,
          selected: value is String ? <String>{value as String} : const {},
          error: error,
          multiple: false,
          onChanged: (selected) =>
              onChanged(selected.isEmpty ? null : selected.first),
        );
      case QuestionnaireQuestionType.multipleChoice:
        final selected = value is List
            ? (value as List).map((item) => item.toString()).toSet()
            : <String>{};
        return _ChoiceField(
          question: question,
          selected: selected,
          error: error,
          multiple: true,
          onChanged: (items) => onChanged(items.toList(growable: false)),
        );
      case QuestionnaireQuestionType.date:
        return _DateField(
          question: question,
          value: value?.toString(),
          error: error,
          onChanged: onChanged,
        );
    }
  }
}

class _ChoiceField extends StatelessWidget {
  const _ChoiceField({
    required this.question,
    required this.selected,
    required this.multiple,
    required this.onChanged,
    this.error,
  });

  final QuestionnaireQuestion question;
  final Set<String> selected;
  final bool multiple;
  final ValueChanged<Set<String>> onChanged;
  final String? error;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: question.label,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            question.label + (question.required ? ' *' : ''),
            style: Theme.of(context).textTheme.titleLarge,
          ),
          if (question.helpText != null) Text(question.helpText!),
          const SizedBox(height: MakoloSpacing.sm),
          for (final choice in question.choices)
            if (multiple)
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(choice),
                value: selected.contains(choice),
                onChanged: (checked) {
                  final next = Set<String>.from(selected);
                  if (checked == true) {
                    next.add(choice);
                  } else {
                    next.remove(choice);
                  }
                  onChanged(next);
                },
              )
            else
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(
                  selected.contains(choice)
                      ? Icons.radio_button_checked_rounded
                      : Icons.radio_button_unchecked_rounded,
                ),
                title: Text(choice),
                selected: selected.contains(choice),
                onTap: () => onChanged(<String>{choice}),
              ),
          if (error != null)
            Text(
              error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
        ],
      ),
    );
  }
}

class _DateField extends StatelessWidget {
  const _DateField({
    required this.question,
    required this.value,
    required this.onChanged,
    this.error,
  });

  final QuestionnaireQuestion question;
  final String? value;
  final ValueChanged<Object?> onChanged;
  final String? error;

  @override
  Widget build(BuildContext context) {
    final parsed = value == null ? null : DateTime.tryParse(value!);
    final label = parsed == null
        ? 'Choisir une date'
        : MaterialLocalizations.of(context).formatMediumDate(parsed.toLocal());
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          question.label + (question.required ? ' *' : ''),
          style: Theme.of(context).textTheme.titleLarge,
        ),
        if (question.helpText != null) Text(question.helpText!),
        const SizedBox(height: MakoloSpacing.sm),
        OutlinedButton.icon(
          onPressed: () async {
            final picked = await showDatePicker(
              context: context,
              initialDate: parsed ?? DateTime.now(),
              firstDate: DateTime(1900),
              lastDate: DateTime(2200),
            );
            if (picked != null) {
              final iso = picked.toIso8601String().split('T').first;
              onChanged(iso);
            }
          },
          icon: const Icon(Icons.calendar_today_outlined),
          label: Text(label),
        ),
        if (error != null)
          Text(
            error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
      ],
    );
  }
}
