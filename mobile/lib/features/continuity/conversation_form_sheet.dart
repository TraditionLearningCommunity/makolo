import '../../platform/media/native_media_picker.dart';

import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'conversation_repository.dart';

String _newFormReference() =>
    'mobile-form-${DateTime.now().microsecondsSinceEpoch}-'
    '${Random.secure().nextInt(0x7fffffff).toRadixString(16)}';

class ConversationFormSheet extends StatefulWidget {
  const ConversationFormSheet({
    super.key,
    required this.repository,
    required this.conversationId,
    required this.capabilities,
    required this.onPublished,
    this.onQueued,
    this.representedSpaceId,
  });

  final ConversationRepository repository;
  final String conversationId;
  final Map<String, dynamic> capabilities;
  final ValueChanged<String> onPublished;
  final VoidCallback? onQueued;
  final String? representedSpaceId;

  @override
  State<ConversationFormSheet> createState() => _ConversationFormSheetState();
}

class _ConversationFormSheetState extends State<ConversationFormSheet> {
  final _title = TextEditingController();
  late final List<TextEditingController> _questionControllers;
  String? _selectedVersionId;
  String? _selectedAudienceId;
  String? _reference;
  String? _error;
  String? _mediaPath;
  String? _mediaName;
  String? _mediaKind;
  bool _newTemplate = false;
  bool _sending = false;
  bool _restoring = false;
  bool _submitted = false;
  Timer? _draftTimer;
  Future<void> _draftWrites = Future<void>.value();

  List<Map<String, dynamic>> get _forms {
    final raw = widget.capabilities['form_options'];
    if (raw is! List) return const [];
    return [
      for (final row in raw)
        if (row is Map)
          row.map((key, value) => MapEntry(key.toString(), value)),
    ];
  }

  List<Map<String, dynamic>> get _audiences {
    final raw = widget.capabilities['audiences'];
    if (raw is! List) return const [];
    return [
      for (final row in raw)
        if (row is Map)
          row.map((key, value) => MapEntry(key.toString(), value)),
    ];
  }

  String? get _representedSpace =>
      widget.representedSpaceId != null &&
          widget.representedSpaceId ==
              widget.capabilities['representable_space_id']?.toString()
      ? widget.representedSpaceId
      : null;

  @override
  void initState() {
    super.initState();
    _newTemplate = _forms.isEmpty;
    _selectedAudienceId = widget.capabilities['default_audience_id']
        ?.toString();
    _questionControllers = [TextEditingController()];
    _title.addListener(_edited);
    for (final controller in _questionControllers) {
      controller.addListener(_edited);
    }
    unawaited(_restore());
  }

  Future<void> _restore() async {
    final delivery = widget.repository.delivery;
    if (delivery == null) return;
    Map<String, dynamic>? data;
    try {
      data = await delivery.readDraft(
        conversationId: widget.conversationId,
        kind: 'form',
      );
    } on Object {
      return;
    }
    if (!mounted ||
        data == null ||
        _title.text.isNotEmpty ||
        _questionControllers.any((item) => item.text.isNotEmpty)) {
      return;
    }
    _restoring = true;
    _title.text = data['title']?.toString() ?? '';
    final savedQuestions = data['questions'];
    final values = savedQuestions is List
        ? savedQuestions.map((item) => item.toString()).toList()
        : (savedQuestions?.toString() ?? '')
              .split('\n')
              .where((item) => item.trim().isNotEmpty)
              .toList();
    for (final controller in _questionControllers) {
      controller.removeListener(_edited);
      controller.dispose();
    }
    _questionControllers
      ..clear()
      ..addAll(
        (values.isEmpty ? <String>[''] : values).map(
          (value) => TextEditingController(text: value),
        ),
      );
    for (final controller in _questionControllers) {
      controller.addListener(_edited);
    }
    _selectedVersionId = data['form_version_id']?.toString();
    _selectedAudienceId =
        data['audience_id']?.toString() ?? _selectedAudienceId;
    _newTemplate = data['new_template'] == true;
    _restoring = false;
    setState(() {});
  }

  void _saveDraft() {
    final delivery = widget.repository.delivery;
    if (delivery == null) return;
    final payload = <String, dynamic>{
      'title': _title.text,
      'questions': _questionControllers.map((item) => item.text).toList(),
      'new_template': _newTemplate,
      if (_selectedVersionId != null) 'form_version_id': _selectedVersionId,
      if (_selectedAudienceId != null) 'audience_id': _selectedAudienceId,
    };
    _draftWrites = _draftWrites
        .catchError((Object _) {})
        .then(
          (_) async => delivery.saveDraft(
            conversationId: widget.conversationId,
            kind: 'form',
            payload: payload,
          ),
        );
  }

  void _edited() {
    if (_restoring) return;
    _reference = null;
    _draftTimer?.cancel();
    _draftTimer = Timer(const Duration(milliseconds: 350), _saveDraft);
    if (_error != null && mounted) setState(() => _error = null);
  }

  @override
  void dispose() {
    _draftTimer?.cancel();
    if (!_submitted &&
        (_title.text.isNotEmpty ||
            _questionControllers.any((item) => item.text.isNotEmpty))) {
      _saveDraft();
    }
    _title.removeListener(_edited);
    _title.dispose();
    for (final controller in _questionControllers) {
      controller.removeListener(_edited);
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _chooseMedia(String mode) async {
    if (_sending) return;
    try {
      String? path;
      String? name;
      final String kind;
      if (mode == 'photo') {
        final image = await NativeMediaPicker.pickImage(
          camera: false,
          quality: 90,
          maxWidth: 2200,
        );
        path = image?.path;
        name = image?.name;
        kind = 'image';
      } else {
        final file = await NativeMediaPicker.pickDocument(const [
          'pdf',
          'txt',
          'doc',
          'docx',
        ]);
        path = file?.path;
        name = file?.name;
        kind = 'file';
      }
      if (!mounted || path == null || name == null) return;
      setState(() {
        _mediaPath = path;
        _mediaName = name;
        _mediaKind = kind;
        _error = null;
      });
    } on Object {
      if (mounted) setState(() => _error = 'Pièce indisponible.');
    }
  }

  Future<void> _publish() async {
    if (_sending || _submitted) return;
    final title = _title.text.trim();
    if (title.isEmpty) {
      setState(() => _error = 'Précisez l’objet du formulaire.');
      return;
    }
    if (widget.capabilities['audience_selection_required'] == true &&
        _selectedAudienceId == null) {
      setState(() => _error = 'Choisissez les destinataires.');
      return;
    }
    final questions = _newTemplate
        ? _questionControllers
              .map((item) => item.text.trim())
              .where((value) => value.isNotEmpty)
              .toList(growable: false)
        : <String>[];
    if (_newTemplate &&
        (questions.isEmpty ||
            questions.length > 8 ||
            questions.toSet().length != questions.length)) {
      setState(
        () => _error = 'Ajoutez entre une et huit questions distinctes.',
      );
      return;
    }
    if (!_newTemplate && _selectedVersionId == null) {
      setState(() => _error = 'Choisissez un formulaire.');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      _draftTimer?.cancel();
      _saveDraft();
      await _draftWrites;
      final delivery = widget.repository.delivery;
      if (delivery != null) {
        await delivery.queue(
          conversationId: widget.conversationId,
          mode: _mediaPath == null ? 'form' : 'media',
          pointKind: _mediaPath == null ? null : 'form_request',
          title: title,
          formVersionId: _newTemplate ? null : _selectedVersionId,
          questions: _newTemplate ? questions : null,
          filePath: _mediaPath,
          filename: _mediaName,
          mediaKind: _mediaKind,
          audienceId: _selectedAudienceId,
          representedSpaceId: _representedSpace,
        );
        try {
          await delivery.clearDraft(
            conversationId: widget.conversationId,
            kind: 'form',
          );
        } on Object {
          // The owner operation is already durably queued.
        }
        _submitted = true;
        if (mounted) widget.onQueued?.call();
      } else {
        if (_mediaPath != null) {
          setState(() => _error = 'Pièce indisponible sans stockage local.');
          return;
        }
        _reference ??= _newFormReference();
        final id = await widget.repository.publishForm(
          conversationId: widget.conversationId,
          title: title,
          clientReference: _reference!,
          formVersionId: _newTemplate ? null : _selectedVersionId,
          questions: _newTemplate ? questions : null,
          audienceId: _selectedAudienceId,
          representedSpaceId: _representedSpace,
        );
        _submitted = true;
        if (mounted) widget.onPublished(id);
      }
    } on Object {
      if (mounted) {
        setState(() => _error = 'Envoi non conservé. Réessayer.');
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final forms = _forms;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          20,
          8,
          20,
          MediaQuery.viewInsetsOf(context).bottom + 24,
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Formulaire', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 16),
              if (forms.isNotEmpty) ...[
                Wrap(
                  spacing: 8,
                  children: [
                    ChoiceChip(
                      label: const Text('Disponible'),
                      selected: !_newTemplate,
                      onSelected: _sending
                          ? null
                          : (_) => setState(() {
                              _newTemplate = false;
                              _reference = null;
                              _error = null;
                              _saveDraft();
                            }),
                    ),
                    ChoiceChip(
                      label: const Text('Nouveau'),
                      selected: _newTemplate,
                      onSelected: _sending
                          ? null
                          : (_) => setState(() {
                              _newTemplate = true;
                              _reference = null;
                              _error = null;
                            }),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
              ],
              if (!_newTemplate)
                DropdownButtonFormField<String>(
                  initialValue: _selectedVersionId,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Formulaire',
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    for (final form in forms)
                      DropdownMenuItem(
                        value: form['id']?.toString(),
                        child: Text(form['title']?.toString() ?? 'Formulaire'),
                      ),
                  ],
                  onChanged: _sending
                      ? null
                      : (value) {
                          final selected = forms.where(
                            (form) => form['id']?.toString() == value,
                          );
                          setState(() {
                            _selectedVersionId = value;
                            _title.text = selected.isEmpty
                                ? ''
                                : selected.first['title']?.toString() ?? '';
                            _reference = null;
                            _saveDraft();
                          });
                        },
                ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('conversation-form-title'),
                controller: _title,
                readOnly: _sending,
                maxLength: 220,
                textCapitalization: TextCapitalization.sentences,
                decoration: InputDecoration(
                  labelText: _newTemplate ? 'Objet' : 'Objet de la demande',
                  border: const OutlineInputBorder(),
                ),
              ),
              if (_newTemplate) ...[
                const SizedBox(height: 8),
                Text(
                  'Questions',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                for (
                  var index = 0;
                  index < _questionControllers.length;
                  index++
                )
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: TextField(
                            key: Key('conversation-form-question-$index'),
                            controller: _questionControllers[index],
                            readOnly: _sending,
                            minLines: 1,
                            maxLines: 3,
                            maxLength: 220,
                            decoration: InputDecoration(
                              labelText: 'Question ${index + 1}',
                              border: const OutlineInputBorder(),
                              counterText: '',
                            ),
                          ),
                        ),
                        IconButton(
                          tooltip: 'Supprimer cette question',
                          onPressed:
                              _sending || _questionControllers.length <= 1
                              ? null
                              : () => setState(() {
                                  final removed = _questionControllers.removeAt(
                                    index,
                                  );
                                  removed.removeListener(_edited);
                                  removed.dispose();
                                  _edited();
                                }),
                          icon: const Icon(Icons.remove_circle_outline),
                        ),
                      ],
                    ),
                  ),
                Align(
                  alignment: Alignment.centerLeft,
                  child: MakoloActionButton(
                    label: 'Ajouter une question',
                    onPressed: _sending || _questionControllers.length >= 8
                        ? null
                        : () => setState(() {
                            final controller = TextEditingController();
                            controller.addListener(_edited);
                            _questionControllers.add(controller);
                            _edited();
                          }),
                    icon: Icons.add_rounded,
                    appearance: MakoloActionAppearance.quiet,
                  ),
                ),
              ],
              if ((widget.capabilities['media_kinds'] as List?)?.isNotEmpty ==
                  true) ...[
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  children: [
                    if ((widget.capabilities['media_kinds'] as List).contains(
                      'image',
                    ))
                      MakoloActionButton(
                        label: 'Photo',
                        onPressed: _sending
                            ? null
                            : () => _chooseMedia('photo'),
                        icon: Icons.image_outlined,
                        appearance: MakoloActionAppearance.secondary,
                      ),
                    if ((widget.capabilities['media_kinds'] as List).contains(
                      'file',
                    ))
                      MakoloActionButton(
                        label: 'Document',
                        onPressed: _sending
                            ? null
                            : () => _chooseMedia('document'),
                        icon: Icons.attach_file_outlined,
                        appearance: MakoloActionAppearance.secondary,
                      ),
                  ],
                ),
                if (_mediaName != null)
                  ListTile(
                    dense: true,
                    leading: const Icon(Icons.attachment_rounded),
                    title: Text(
                      _mediaName!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    trailing: MakoloIconActionButton(
                      tooltip: 'Retirer cette pièce',
                      icon: Icons.close_rounded,
                      onPressed: _sending
                          ? null
                          : () => setState(() {
                              _mediaPath = null;
                              _mediaName = null;
                              _mediaKind = null;
                            }),
                    ),
                  ),
              ],
              if (widget.capabilities['audience_selection_required'] ==
                  true) ...[
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _selectedAudienceId,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Destinataires',
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    for (final audience in _audiences)
                      DropdownMenuItem(
                        value: audience['id']?.toString(),
                        child: Text(
                          audience['label']?.toString() ?? 'Audience',
                        ),
                      ),
                  ],
                  onChanged: _sending
                      ? null
                      : (value) => setState(() {
                          _selectedAudienceId = value;
                          _reference = null;
                          _saveDraft();
                        }),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: 10),
                Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              const SizedBox(height: 16),
              Align(
                alignment: Alignment.centerRight,
                child: MakoloActionButton(
                  key: const Key('conversation-form-publish'),
                  label: _sending
                      ? 'Envoi…'
                      : _submitted
                      ? 'Conservé'
                      : 'Envoyer',
                  onPressed: _sending || _submitted ? null : _publish,
                  appearance: MakoloActionAppearance.primary,
                  icon: Icons.send_rounded,
                  phase: _sending
                      ? MakoloActionPhase.processing
                      : _submitted
                      ? MakoloActionPhase.confirmed
                      : _error != null
                      ? MakoloActionPhase.failed
                      : MakoloActionPhase.available,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
