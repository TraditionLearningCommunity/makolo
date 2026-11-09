import '../../design/makolo_patterns.dart';

import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/surface_states.dart';
import '../../repositories/draft_repository.dart';
import '../../sync/outbox/outbox_processor.dart';
import '../../sync/outbox/outbox_repository.dart';
import 'questionnaire_repository.dart';
import '../continuity/conversation_media_group.dart';
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
  bool _submitting = false;
  bool _draftDirty = false;
  bool _submittedLocally = false;
  int _draftRevision = 0;
  Future<void> _draftWrites = Future<void>.value();

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
    if (_submitting) return;
    setState(() {
      _answers[key] = value;
      _serverErrors.remove(key);
      _serverErrors.remove('_form');
      _draftDirty = true;
      _submittedLocally = false;
      _draftRevision++;
    });
    _autosave?.cancel();
    _autosave = Timer(const Duration(milliseconds: 450), () {
      unawaited(_persistDraft().catchError((Object _) {}));
    });
  }

  Future<void> _persistDraft() {
    // A quick submit must wait for a preceding autosave instead of
    // returning early and racing the atomic draft + owner intent.
    final answers = Map<String, dynamic>.from(_answers);
    final errors = Map<String, dynamic>.from(_serverErrors);
    final revision = _draftRevision;
    final write = _draftWrites.then(
      (_) => widget.drafts.saveLocal(
        draftId: _draftId,
        owner: QuestionnaireSubmitCoordinator.owner,
        resourceKind: QuestionnaireSubmitCoordinator.resourceKind,
        resourceId: widget.requestId,
        payload: <String, dynamic>{
          'answers': answers,
          if (errors.isNotEmpty) 'server_errors': errors,
          'base_observed_at': DateTime.now().toUtc().toIso8601String(),
        },
      ),
    );
    _draftWrites = write.then<void>(
      (_) {},
      onError: (Object _, StackTrace _) {},
    );
    return write.then((_) {
      if (_draftRevision == revision) _draftDirty = false;
    });
  }

  Future<void> _submit(QuestionnaireRequestDetail detail) async {
    if (_submitting) return;
    final validation = _validate(detail);
    if (validation.isNotEmpty) {
      setState(() => _serverErrors = validation);
      return;
    }
    _autosave?.cancel();
    final answers = Map<String, dynamic>.from(_answers);
    setState(() => _submitting = true);
    try {
      await _persistDraft();
      final created = await widget.submitCoordinator.enqueue(
        requestId: widget.requestId,
        journeyId: widget.journeyId,
        answers: answers,
        links: widget.links,
      );
      if (created) {
        _submittedLocally = true;
        await widget.outboxProcessor?.run();
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
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
    if (_initializedAnswers && _draftDirty && !_submittedLocally) {
      unawaited(_persistDraft().catchError((Object _) {}));
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
                      repository: widget.repository,
                      detail: detail,
                      answers: _answers,
                      errors: _serverErrors,
                      commit: commit,
                      retryScheduled: operation?.retryScheduled ?? false,
                      refreshing: _refreshing,
                      canEdit: !_submitting,
                      canSubmit:
                          widget.links.canSubmit &&
                          !detail.isSubmitted &&
                          !_submitting &&
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
    return operation.retryScheduled ||
        operation.state == OutboxState.queued.wireValue ||
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
    required this.repository,
    required this.detail,
    required this.answers,
    required this.errors,
    required this.commit,
    required this.retryScheduled,
    required this.refreshing,
    required this.canEdit,
    required this.canSubmit,
    required this.onChanged,
    required this.onSubmit,
  });

  final QuestionnaireRepository repository;
  final QuestionnaireRequestDetail detail;
  final Map<String, dynamic> answers;
  final Map<String, dynamic> errors;
  final MakoloCommitCue commit;
  final bool retryScheduled;
  final bool refreshing;
  final bool canEdit;
  final bool canSubmit;
  final void Function(String key, Object? value) onChanged;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return MakoloReadingWidth(
      child: ListView(
        padding: const EdgeInsets.all(MakoloSpacing.inner),
        keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
        children: [
          MakoloCard(
            child: MakoloStatusMetadataAction(
              title: detail.required
                  ? 'Formulaire requis'
                  : 'Formulaire complémentaire',
              subtitle: detail.description,
              status: MakoloStatus(label: _requestStateLabel(detail)),
              metadata: [
                MakoloMetadataItem('Version ${detail.version}'),
                if (detail.dueAt != null)
                  MakoloMetadataItem(
                    'Échéance ${MaterialLocalizations.of(context).formatMediumDate(detail.dueAt!.toLocal())}',
                    icon: Icons.event_outlined,
                  ),
                if (detail.submittedAt != null)
                  MakoloMetadataItem(
                    'Soumis ${MaterialLocalizations.of(context).formatMediumDate(detail.submittedAt!.toLocal())}',
                    icon: Icons.check_circle_outline_rounded,
                  ),
              ],
            ),
          ),
          const SizedBox(height: MakoloSpacing.lg),
          if (detail.description != null) ...[
            Text(
              detail.description!,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            const SizedBox(height: MakoloSpacing.lg),
          ],
          if (detail.media.isNotEmpty) ...[
            ConversationMediaGroup(
              download: repository.downloadMedia,
              attachments: detail.media.map((item) => item.toViewerMap())
                  .toList(growable: false),
            ),
            const SizedBox(height: MakoloSpacing.md),
          ],
          if (refreshing) ...[
            const MakoloRefreshIndicator(label: 'Vérification du formulaire…'),
            const SizedBox(height: MakoloSpacing.md),
          ],
          MakoloCommitIndicator(commit: commit),
          if (retryScheduled) ...[
            const SizedBox(height: MakoloSpacing.sm),
            const InlineMessage(
              message:
                  'L’envoi a été interrompu. Une nouvelle tentative '
                  'est prévue avec la même intention ; aucune seconde '
                  'soumission n’est nécessaire.',
            ),
          ],
          if (errors['_form'] != null) ...[
            const SizedBox(height: MakoloSpacing.md),
            InlineMessage(message: errors['_form'].toString()),
          ],
          const SizedBox(height: MakoloSpacing.lg),
          for (final question in detail.questions) ...[
            _QuestionField(
              repository: repository,
              question: question,
              value: answers[question.key],
              error: errors[question.key]?.toString(),
              enabled:
                  canEdit &&
                  !retryScheduled &&
                  !detail.isSubmitted &&
                  commit != MakoloCommitCue.pending &&
                  commit != MakoloCommitCue.awaitingConfirmation,
              onChanged: (value) => onChanged(question.key, value),
            ),
            if (question.media.isNotEmpty &&
                question.type != QuestionnaireQuestionType.singleChoice &&
                question.type != QuestionnaireQuestionType.multipleChoice)
              ConversationMediaGroup(
                download: repository.downloadMedia,
                attachments: question.media
                    .map((item) => item.toViewerMap()).toList(growable: false),
              ),
            const SizedBox(height: MakoloSpacing.inner),
          ],
          FilledButton.icon(
            onPressed: canSubmit ? onSubmit : null,
            icon: const Icon(Icons.check_rounded),
            label: Text(detail.isSubmitted ? 'Déjà soumis' : 'Soumettre'),
          ),
          if (!canSubmit &&
              !detail.isSubmitted &&
              commit == MakoloCommitCue.none) ...[
            const SizedBox(height: MakoloSpacing.sm),
            Text(
              'L’envoi de ce formulaire n’est pas disponible pour le moment.',
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
          ],
        ],
      ),
    );
  }
}

class _QuestionField extends StatelessWidget {
  const _QuestionField({
    required this.repository,
    required this.question,
    required this.value,
    required this.onChanged,
    required this.enabled,
    this.error,
  });

  final QuestionnaireRepository repository;
  final QuestionnaireQuestion question;
  final Object? value;
  final ValueChanged<Object?> onChanged;
  final bool enabled;
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
          enabled: enabled,
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
          enabled: enabled,
          textInputAction: TextInputAction.next,
          decoration: InputDecoration(
            labelText: _label,
            helperText: question.helpText,
            errorText: error,
          ),
          onChanged: onChanged,
        );
      case QuestionnaireQuestionType.boolean:
        return Semantics(
          container: true,
          label: _label,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(_label, style: Theme.of(context).textTheme.titleLarge),
              if (question.helpText != null) Text(question.helpText!),
              const SizedBox(height: MakoloSpacing.sm),
              SegmentedButton<bool>(
                segments: const [
                  ButtonSegment<bool>(value: true, label: Text('Oui')),
                  ButtonSegment<bool>(value: false, label: Text('Non')),
                ],
                selected: value is bool
                    ? <bool>{value as bool}
                    : const <bool>{},
                emptySelectionAllowed: true,
                onSelectionChanged: enabled
                    ? (selected) =>
                          onChanged(selected.isEmpty ? null : selected.first)
                    : null,
              ),
              if (error != null)
                Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
            ],
          ),
        );
      case QuestionnaireQuestionType.singleChoice:
        return _ChoiceField(
          repository: repository,
          question: question,
          selected: value is String ? <String>{value as String} : const {},
          error: error,
          enabled: enabled,
          multiple: false,
          onChanged: (selected) =>
              onChanged(selected.isEmpty ? null : selected.first),
        );
      case QuestionnaireQuestionType.multipleChoice:
        final selected = value is List
            ? (value as List).map((item) => item.toString()).toSet()
            : <String>{};
        return _ChoiceField(
          repository: repository,
          question: question,
          selected: selected,
          error: error,
          enabled: enabled,
          multiple: true,
          onChanged: (items) => onChanged(items.toList(growable: false)),
        );
      case QuestionnaireQuestionType.date:
        return _DateField(
          question: question,
          value: value?.toString(),
          error: error,
          enabled: enabled,
          onChanged: onChanged,
        );
    }
  }
}

class _ChoiceField extends StatelessWidget {
  const _ChoiceField({
    required this.repository,
    required this.question,
    required this.selected,
    required this.multiple,
    required this.onChanged,
    required this.enabled,
    this.error,
  });

  final QuestionnaireRepository repository;
  final QuestionnaireQuestion question;
  final Set<String> selected;
  final bool multiple;
  final ValueChanged<Set<String>> onChanged;
  final bool enabled;
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
          if (question.media.isNotEmpty)
            ConversationMediaGroup(
              download: repository.downloadMedia,
              attachments: question.media
                  .map((item) => item.toViewerMap()).toList(growable: false),
            ),
          const SizedBox(height: MakoloSpacing.sm),
          for (var index = 0; index < question.choices.length; index++) ...[
            _ChoiceMediaItem(
              key: ValueKey('questionnaire-choice-${question.key}-$index'),
              repository: repository,
              question: question,
              choice: question.choices[index],
              index: index,
              multiple: multiple,
              selected: selected.contains(question.choices[index]),
              enabled: enabled,
              onTap: (checked) {
                final value = question.choices[index];
                if (multiple) {
                  final next = Set<String>.from(selected);
                  if (checked) { next.add(value); } else { next.remove(value); }
                  onChanged(next);
                } else {
                  onChanged(<String>{value});
                }
              },
            ),
          ],
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

class _ChoiceMediaItem extends StatelessWidget {
  const _ChoiceMediaItem({
    super.key,
    required this.repository,
    required this.question,
    required this.choice,
    required this.index,
    required this.multiple,
    required this.selected,
    required this.enabled,
    required this.onTap,
  });

  final QuestionnaireRepository repository;
  final QuestionnaireQuestion question;
  final String choice;
  final int index;
  final bool multiple;
  final bool selected;
  final bool enabled;
  final ValueChanged<bool> onTap;

  @override
  Widget build(BuildContext context) {
    final media = question.choiceMedia[index] ?? const <QuestionnaireMedia>[];
    return Padding(
      padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
      child: DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          color: Theme.of(context).colorScheme.surfaceContainerLow,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (multiple)
              CheckboxListTile(
                contentPadding: const EdgeInsets.symmetric(horizontal: 8),
                title: Text(choice),
                value: selected,
                onChanged: enabled ? (checked) => onTap(checked == true) : null,
              )
            else
              ListTile(
                contentPadding: const EdgeInsets.symmetric(horizontal: 8),
                leading: Icon(selected
                    ? Icons.radio_button_checked_rounded
                    : Icons.radio_button_unchecked_rounded),
                title: Text(choice),
                selected: selected,
                enabled: enabled,
                onTap: enabled ? () => onTap(true) : null,
              ),
            if (media.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
                child: ConversationMediaGroup(
                  download: repository.downloadMedia,
                  attachments: media.map((item) => item.toViewerMap())
                      .toList(growable: false),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _DateField extends StatelessWidget {
  const _DateField({
    required this.question,
    required this.value,
    required this.onChanged,
    required this.enabled,
    this.error,
  });

  final QuestionnaireQuestion question;
  final String? value;
  final ValueChanged<Object?> onChanged;
  final bool enabled;
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
          onPressed: enabled
              ? () async {
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
                }
              : null,
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

String _requestStateLabel(QuestionnaireRequestDetail detail) {
  if (detail.isSubmitted) return 'Confirmé';
  return switch (detail.status) {
    'requested' => 'À remplir',
    'cancelled' => 'Annulé',
    'completed' => 'Confirmé',
    _ => detail.status.replaceAll('_', ' '),
  };
}
