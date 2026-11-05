import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';

import 'conversation_repository.dart';

String _newFormReference() => 'mobile-form-${DateTime.now().microsecondsSinceEpoch}-'
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
  final _questions = TextEditingController();
  String? _selectedVersionId;
  String? _selectedAudienceId;
  String? _reference;
  String? _error;
  bool _newTemplate = false;
  bool _sending = false;
  bool _restoring = false;
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
    _selectedAudienceId = widget.capabilities['default_audience_id']?.toString();
    _title.addListener(_edited);
    _questions.addListener(_edited);
    unawaited(_restore());
  }

  Future<void> _restore() async {
    final delivery = widget.repository.delivery;
    if (delivery == null) return;
    final data = await delivery.readDraft(
      conversationId: widget.conversationId,
      kind: 'form',
    );
    if (!mounted || data == null ||
        _title.text.isNotEmpty || _questions.text.isNotEmpty) return;
    _restoring = true;
    _title.text = data['title']?.toString() ?? '';
    _questions.text = data['questions']?.toString() ?? '';
    _selectedVersionId = data['form_version_id']?.toString();
    _selectedAudienceId = data['audience_id']?.toString() ??
        _selectedAudienceId;
    _newTemplate = data['new_template'] == true;
    _restoring = false;
    setState(() {});
  }

  void _saveDraft() {
    final delivery = widget.repository.delivery;
    if (delivery == null) return;
    final payload = <String, dynamic>{
      'title': _title.text,
      'questions': _questions.text,
      'new_template': _newTemplate,
      if (_selectedVersionId != null) 'form_version_id': _selectedVersionId,
      if (_selectedAudienceId != null) 'audience_id': _selectedAudienceId,
    };
    _draftWrites = _draftWrites.catchError((Object _) {}).then((_) async =>
        delivery.saveDraft(
          conversationId: widget.conversationId,
          kind: 'form',
          payload: payload,
        ));
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
    if (_title.text.isNotEmpty || _questions.text.isNotEmpty) _saveDraft();
    _title.removeListener(_edited);
    _questions.removeListener(_edited);
    _title.dispose();
    _questions.dispose();
    super.dispose();
  }

  Future<void> _publish() async {
    if (_sending) return;
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
        ? _questions.text.split('\n')
            .map((value) => value.trim())
            .where((value) => value.isNotEmpty)
            .toList(growable: false)
        : <String>[];
    if (_newTemplate && (questions.isEmpty || questions.length > 8 ||
        questions.toSet().length != questions.length)) {
      setState(() => _error = 'Ajoutez entre une et huit questions distinctes.');
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
          mode: 'form',
          title: title,
          formVersionId: _newTemplate ? null : _selectedVersionId,
          questions: _newTemplate ? questions : null,
          audienceId: _selectedAudienceId,
          representedSpaceId: _representedSpace,
        );
        await delivery.clearDraft(
          conversationId: widget.conversationId, kind: 'form',
        );
        if (mounted) widget.onQueued?.call();
      } else {
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
          20, 8, 20, MediaQuery.viewInsetsOf(context).bottom + 24,
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
                      onSelected: _sending ? null : (_) => setState(() {
                        _newTemplate = false;
                        _reference = null;
                        _error = null;
                        _saveDraft();
                      }),
                    ),
                    ChoiceChip(
                      label: const Text('Nouveau'),
                      selected: _newTemplate,
                      onSelected: _sending ? null : (_) => setState(() {
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
                  value: _selectedVersionId,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Formulaire', border: OutlineInputBorder(),
                  ),
                  items: [
                    for (final form in forms)
                      DropdownMenuItem(
                        value: form['id']?.toString(),
                        child: Text(form['title']?.toString() ?? 'Formulaire'),
                      ),
                  ],
                  onChanged: _sending ? null : (value) {
                    final selected = forms.where(
                      (form) => form['id']?.toString() == value,
                    );
                    setState(() {
                      _selectedVersionId = value;
                      _title.text = selected.isEmpty
                          ? '' : selected.first['title']?.toString() ?? '';
                      _reference = null;
                      _saveDraft();
                    });
                  },
                ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('conversation-form-title'),
                controller: _title,
                maxLength: 220,
                textCapitalization: TextCapitalization.sentences,
                decoration: InputDecoration(
                  labelText: _newTemplate ? 'Objet' : 'Objet de la demande',
                  border: const OutlineInputBorder(),
                ),
              ),
              if (_newTemplate) ...[
                const SizedBox(height: 8),
                TextField(
                  key: const Key('conversation-form-questions'),
                  controller: _questions,
                  minLines: 3,
                  maxLines: 7,
                  decoration: const InputDecoration(
                    labelText: 'Questions · une par ligne',
                    border: OutlineInputBorder(),
                  ),
                ),
              ],
              if (widget.capabilities['audience_selection_required'] == true) ...[
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: _selectedAudienceId,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Destinataires', border: OutlineInputBorder(),
                  ),
                  items: [
                    for (final audience in _audiences)
                      DropdownMenuItem(
                        value: audience['id']?.toString(),
                        child: Text(audience['label']?.toString() ?? 'Audience'),
                      ),
                  ],
                  onChanged: _sending ? null : (value) => setState(() {
                    _selectedAudienceId = value;
                    _reference = null;
                    _saveDraft();
                  }),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: 10),
                Text(_error!, style: TextStyle(
                  color: Theme.of(context).colorScheme.error,
                )),
              ],
              const SizedBox(height: 16),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton(
                  key: const Key('conversation-form-publish'),
                  onPressed: _sending ? null : _publish,
                  child: Text(_sending ? 'Envoi…' : 'Envoyer'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
