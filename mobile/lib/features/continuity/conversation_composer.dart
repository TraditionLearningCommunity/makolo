import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';

import 'conversation_repository.dart';
import 'conversation_form_sheet.dart';
import 'conversation_media_sheet.dart';

String _newConversationReference() {
  final random = Random.secure();
  return 'mobile-c3-${DateTime.now().microsecondsSinceEpoch}-'
      '${random.nextInt(0x7fffffff).toRadixString(16)}';
}

List<Map<String, dynamic>> _audienceRows(Map<String, dynamic> capabilities) {
  final rows = capabilities['audiences'];
  if (rows is! List) return const [];
  return [
    for (final row in rows)
      if (row is Map)
        row.map((key, value) => MapEntry(key.toString(), value)),
  ];
}

class _PointDraft {
  const _PointDraft({
    required this.title,
    required this.body,
    required this.options,
    this.audienceId,
    this.reference,
  });

  final String title;
  final String body;
  final String options;
  final String? audienceId;
  final String? reference;

  Map<String, dynamic> toPayload() => {
    'title': title,
    'body': body,
    'options': options,
    if (audienceId != null) 'audience_id': audienceId,
  };

  factory _PointDraft.fromPayload(Map<String, dynamic> payload) => _PointDraft(
    title: payload['title']?.toString() ?? '',
    body: payload['body']?.toString() ?? '',
    options: payload['options']?.toString() ?? '',
    audienceId: payload['audience_id']?.toString(),
  );
}

class ConversationComposer extends StatefulWidget {
  const ConversationComposer({
    super.key,
    required this.repository,
    required this.conversationId,
    required this.capabilities,
    required this.onPublished,
    this.representedSpaceId,
  });

  final ConversationRepository repository;
  final String conversationId;
  final Map<String, dynamic> capabilities;
  final String? representedSpaceId;
  final ValueChanged<String> onPublished;

  @override
  State<ConversationComposer> createState() => _ConversationComposerState();
}

class _ConversationComposerState extends State<ConversationComposer> {
  final TextEditingController _text = TextEditingController();
  final FocusNode _focus = FocusNode();
  final Map<String, _PointDraft> _drafts = {};
  Timer? _draftTimer;
  Future<void> _draftWrites = Future<void>.value();
  bool _editingProgrammatically = false;
  bool _sending = false;
  String? _reference;
  String? _error;
  String? _audienceId;
  String? _exchangeTargetId;
  String _selectedType = 'information';

  String? get _representedSpace => widget.representedSpaceId != null &&
          widget.representedSpaceId ==
              widget.capabilities['representable_space_id']?.toString()
      ? widget.representedSpaceId
      : null;

  @override
  void initState() {
    super.initState();
    _audienceId = widget.capabilities['default_audience_id']?.toString();
    _exchangeTargetId = widget.capabilities['default_exchange_point_id']?.toString();
    _text.addListener(_edited);
    unawaited(_restoreDraft());
  }

  Future<void> _restoreDraft() async {
    final delivery = widget.repository.delivery;
    if (delivery == null) return;
    final repository = widget.repository;
    final conversationId = widget.conversationId;
    try {
      final draft = await delivery.readDraft(
        conversationId: conversationId, kind: 'information',
      );
      if (!mounted || repository != widget.repository ||
          conversationId != widget.conversationId ||
          _text.text.isNotEmpty || draft == null) return;
      _editingProgrammatically = true;
      _text.text = draft['body']?.toString() ?? '';
      _editingProgrammatically = false;
    } on Object {
      // A missing local draft must not block composing.
    }
  }

  void _persistDraft(String content) {
    final delivery = widget.repository.delivery;
    if (delivery == null) return;
    final conversationId = widget.conversationId;
    _draftWrites = _draftWrites.catchError((Object _) {}).then((_) async {
      await delivery.saveDraft(
        conversationId: conversationId,
        kind: 'information',
        payload: {'body': content},
      );
    });
  }

  void _edited() {
    if (_editingProgrammatically) return;
    _reference = null;
    _draftTimer?.cancel();
    _draftTimer = Timer(const Duration(milliseconds: 350), () {
      _persistDraft(_text.text);
    });
    if (_error != null && mounted) setState(() => _error = null);
  }

  @override
  void didUpdateWidget(covariant ConversationComposer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository ||
        oldWidget.conversationId != widget.conversationId) {
      _draftTimer?.cancel();
      _editingProgrammatically = true;
      _text.clear();
      _editingProgrammatically = false;
      _reference = null;
      _drafts.clear();
      _error = null;
      _selectedType = 'information';
      _audienceId = widget.capabilities['default_audience_id']?.toString();
      _exchangeTargetId = widget.capabilities['default_exchange_point_id']?.toString();
      unawaited(_restoreDraft());
    } else if (oldWidget.capabilities['default_audience_id'] !=
        widget.capabilities['default_audience_id']) {
      _audienceId = widget.capabilities['default_audience_id']?.toString();
    }
  }

  @override
  void dispose() {
    _draftTimer?.cancel();
    if (_text.text.isNotEmpty) _persistDraft(_text.text);
    _text.removeListener(_edited);
    _text.dispose();
    _focus.dispose();
    super.dispose();
  }

  bool get _needsAudience =>
      widget.capabilities['audience_selection_required'] == true;
  List<String> get _kinds {
    final kinds = widget.capabilities['allowed_kinds'];
    return kinds is List ? kinds.map((item) => item.toString()).toList() : [];
  }

  Future<void> _sendText() async {
    final body = _text.text.trim();
    if (body.isEmpty || _sending) return;
    final mode = widget.capabilities['text_mode']?.toString();
    if (mode == 'exchange_select' && _exchangeTargetId == null) {
      setState(() => _error = 'Choisissez une conversation à laquelle répondre.');
      return;
    }
    if (_needsAudience && _audienceId == null && mode == 'information') {
      setState(() => _error = 'Choisissez les destinataires.');
      return;
    }
    setState(() { _sending = true; _error = null; });
    try {
      final delivery = widget.repository.delivery;
      final pointId = mode == 'exchange' || mode == 'exchange_select'
          ? _exchangeTargetId : null;
      if (delivery != null) {
        _draftTimer?.cancel();
        await delivery.queue(
          conversationId: widget.conversationId,
          mode: 'text',
          body: body,
          pointId: pointId,
          audienceId: _audienceId,
          representedSpaceId: _representedSpace,
        );
        // The Outbox is durable; network confirmation will arrive separately.
        if (!mounted) return;
        _editingProgrammatically = true;
        _text.clear();
        _editingProgrammatically = false;
        await _draftWrites.catchError((Object _) {});
        await delivery.clearDraft(
          conversationId: widget.conversationId, kind: 'information',
        );
      } else {
        _reference ??= _newConversationReference();
        final sent = await widget.repository.compose(
          conversationId: widget.conversationId,
          clientReference: _reference!,
          mode: 'text',
          body: body,
          pointId: pointId,
          audienceId: _audienceId,
          representedSpaceId: _representedSpace,
        );
        if (!mounted) return;
        _editingProgrammatically = true;
        _text.clear();
        _editingProgrammatically = false;
        widget.onPublished(sent);
      }
      _reference = null;
      _focus.unfocus();
    } on Object {
      if (mounted) {
        setState(() => _error = 'Envoi non conservé. Réessayer.');
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _openPointEditor(String kind) async {
    _PointDraft? draft = _drafts[kind];
    final delivery = widget.repository.delivery;
    if (delivery != null) {
      try {
        final stored = await delivery.readDraft(
          conversationId: widget.conversationId, kind: kind,
        );
        if (stored != null) draft = _PointDraft.fromPayload(stored);
      } on Object {
        // Keep the in-memory draft when local read is temporarily unavailable.
      }
    }
    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      useSafeArea: true,
      builder: (sheetContext) => _ComposePointSheet(
        kind: kind,
        repository: widget.repository,
        conversationId: widget.conversationId,
        capabilities: widget.capabilities,
        representedSpaceId: widget.representedSpaceId,
        initialDraft: draft,
        onDraftChanged: (next) async {
          _drafts[kind] = next;
          if (delivery != null) {
            await delivery.saveDraft(
              conversationId: widget.conversationId,
              kind: kind,
              payload: next.toPayload(),
            );
          }
        },
        onQueued: () {
          _drafts.remove(kind);
          Navigator.of(sheetContext).pop();
        },
        onPublished: (id) {
          _drafts.remove(kind);
          Navigator.of(sheetContext).pop();
          widget.onPublished(id);
        },
      ),
    );
    if (mounted) setState(() => _selectedType = 'information');
  }

  Future<void> _openForm() async {
    await showModalBottomSheet<void>(
      context: context, isScrollControlled: true,
      useSafeArea: true, showDragHandle: true,
      builder: (sheetContext) => ConversationFormSheet(
        repository: widget.repository,
        conversationId: widget.conversationId,
        capabilities: widget.capabilities,
        representedSpaceId: widget.representedSpaceId,
        onQueued: () => Navigator.of(sheetContext).pop(),
        onPublished: (id) {
          Navigator.of(sheetContext).pop();
          widget.onPublished(id);
        },
      ),
    );
    if (mounted) setState(() => _selectedType = 'information');
  }

  Future<void> _openMedia(String mode) async {
    await showModalBottomSheet<void>(
      context: context, isScrollControlled: true,
      useSafeArea: true, showDragHandle: true,
      builder: (sheetContext) => ConversationMediaSheet(
        mode: mode,
        repository: widget.repository,
        conversationId: widget.conversationId,
        capabilities: widget.capabilities,
        representedSpaceId: widget.representedSpaceId,
        onPublished: (id) {
          Navigator.of(sheetContext).pop();
          widget.onPublished(id);
        },
      ),
    );
  }

  Future<void> _selectType() async {
    final kinds = _kinds;
    final canForm = widget.capabilities['can_form'] == true;
    final entries = <(String, String, IconData)>[
      if (widget.capabilities['text_mode'] != null ||
          kinds.contains('information'))
        ('information', 'Information', Icons.chat_bubble_outline_rounded),
      if (kinds.contains('question'))
        ('question', 'Question', Icons.help_outline_rounded),
      if (kinds.contains('request'))
        ('request', 'Demande', Icons.assignment_outlined),
      if (canForm) ('form', 'Formulaire', Icons.article_outlined),
      if (kinds.contains('poll')) ('poll', 'Sondage', Icons.poll_outlined),
      if (kinds.contains('confirmation'))
        ('confirmation', 'Confirmation', Icons.task_alt_rounded),
    ];
    final chosen = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      useSafeArea: true,
      builder: (sheetContext) => SafeArea(
        top: false,
        child: ListView(
          shrinkWrap: true,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 6, 20, 12),
              child: Text('Type', style: Theme.of(sheetContext).textTheme.titleLarge),
            ),
            for (final (id, label, icon) in entries)
              ListTile(
                key: Key('conversation-type-$id'),
                leading: Icon(icon),
                title: Text(label),
                selected: id == _selectedType,
                trailing: id == _selectedType
                    ? const Icon(Icons.check_rounded)
                    : null,
                onTap: () => Navigator.of(sheetContext).pop(id),
              ),
          ],
        ),
      ),
    );
    if (!mounted || chosen == null) return;
    setState(() => _selectedType = chosen);
    if (chosen == 'form') {
      await _openForm();
    } else if (chosen != 'information') {
      await _openPointEditor(chosen);
    }
  }

  @override
  Widget build(BuildContext context) {
    final textMode = widget.capabilities['text_mode']?.toString();
    final kinds = _kinds;
    final mediaKinds = (widget.capabilities['media_kinds'] as List?)
            ?.map((item) => item.toString()).toSet() ?? <String>{};
    final canForm = widget.capabilities['can_form'] == true;
    if (textMode == null && kinds.isEmpty &&
        mediaKinds.isEmpty && !canForm) {
      return const SizedBox.shrink();
    }
    final scheme = Theme.of(context).colorScheme;
    final audiences = _audienceRows(widget.capabilities);
    return Material(
      key: const Key('conversation-composer'),
      elevation: 3,
      color: scheme.surface,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (textMode == 'exchange_select' &&
                _exchangeTargetId == null)
              TextButton.icon(
                onPressed: _sending ? null : () async {
                  final selection = await showModalBottomSheet<String>(
                    context: context, showDragHandle: true,
                    builder: (sheetContext) => ListView(
                      shrinkWrap: true,
                      children: [
                        for (final target in _audienceRows({
                          'audiences': widget.capabilities['exchange_targets'],
                        }))
                          ListTile(
                            title: Text(target['title']?.toString() ?? 'Sujet'),
                            onTap: () => Navigator.pop(
                                sheetContext, target['id']?.toString()),
                          ),
                      ],
                    ),
                  );
                  if (selection != null && mounted) {
                    setState(() => _exchangeTargetId = selection);
                  }
                },
                icon: const Icon(Icons.forum_outlined),
                label: const Text('Choisir le sujet'),
              ),
            if (_needsAudience && textMode == 'information')
              DropdownButtonFormField<String>(
                value: _audienceId,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Destinataires', isDense: true,
                  border: OutlineInputBorder(),
                ),
                items: [
                  for (final audience in audiences)
                    DropdownMenuItem(
                      value: audience['id']?.toString(),
                      child: Text(audience['label']?.toString() ?? 'Destinataires'),
                    ),
                ],
                onChanged: _sending ? null : (value) => setState(() {
                  _audienceId = value;
                  _reference = null;
                }),
              ),
            if (textMode != null) ...[
              Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Expanded(
                    child: TextField(
                      key: const Key('conversation-compose-text'),
                      controller: _text,
                      focusNode: _focus,
                      minLines: 1,
                      maxLines: 4,
                      maxLength: 5000,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: InputDecoration(
                        hintText: 'Écrire quelque chose…',
                        isDense: true,
                        counterText: '',
                        filled: true,
                        fillColor: scheme.surfaceContainerLow,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(20),
                          borderSide: BorderSide.none,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 6),
                  IconButton.filled(
                    key: const Key('conversation-compose-send'),
                    onPressed: _sending ? null : _sendText,
                    tooltip: 'Envoyer',
                    icon: _sending
                        ? const SizedBox(
                            width: 18, height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.arrow_upward_rounded),
                  ),
                ],
              ),
            ],
            Row(
              children: [
                TextButton.icon(
                  key: const Key('conversation-compose-type'),
                  onPressed: _sending ? null : _selectType,
                  icon: const Icon(Icons.tune_rounded, size: 19),
                  label: Text('Type · ${_selectedType == 'information'
                      ? 'Information'
                      : _selectedType == 'form'
                      ? 'Formulaire'
                      : _selectedType == 'poll'
                      ? 'Sondage'
                      : _selectedType == 'request'
                      ? 'Demande'
                      : _selectedType == 'confirmation'
                      ? 'Confirmation'
                      : 'Question'}'),
                ),
                const Spacer(),
                if (mediaKinds.contains('voice'))
                  IconButton(
                    key: const Key('conversation-compose-voice'),
                    tooltip: 'Note vocale',
                    onPressed: _sending ? null : () => _openMedia('voice'),
                    icon: const Icon(Icons.mic_none_rounded),
                  ),
                if (mediaKinds.contains('image') ||
                    mediaKinds.contains('file'))
                  PopupMenuButton<String>(
                    key: const Key('conversation-compose-attachment'),
                    tooltip: 'Joindre',
                    icon: const Icon(Icons.attach_file_rounded),
                    onSelected: (value) => _openMedia(value),
                    itemBuilder: (context) => [
                      if (mediaKinds.contains('image')) ...[
                        const PopupMenuItem(
                          value: 'photo', child: Text('Photo'),
                        ),
                        const PopupMenuItem(
                          value: 'camera', child: Text('Caméra'),
                        ),
                      ],
                      if (mediaKinds.contains('file'))
                        const PopupMenuItem(
                          value: 'document', child: Text('Document'),
                        ),
                    ],
                  ),
              ],
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  _error!,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: scheme.error,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _ComposePointSheet extends StatefulWidget {
  const _ComposePointSheet({
    required this.kind,
    required this.repository,
    required this.conversationId,
    required this.capabilities,
    required this.onPublished,
    required this.onDraftChanged,
    required this.onQueued,
    this.initialDraft,
    this.representedSpaceId,
  });

  final _PointDraft? initialDraft;
  final Future<void> Function(_PointDraft) onDraftChanged;
  final VoidCallback onQueued;
  final String kind;
  final ConversationRepository repository;
  final String conversationId;
  final Map<String, dynamic> capabilities;
  final String? representedSpaceId;
  final ValueChanged<String> onPublished;

  @override
  State<_ComposePointSheet> createState() => _ComposePointSheetState();
}

class _ComposePointSheetState extends State<_ComposePointSheet> {
  late final TextEditingController _title;
  late final TextEditingController _body;
  late final TextEditingController _options;
  String? _reference;
  String? _audienceId;
  String? _error;
  bool _sending = false;
  Future<void> _draftWrites = Future<void>.value();

  String? get _representedSpace => widget.representedSpaceId != null &&
          widget.representedSpaceId ==
              widget.capabilities['representable_space_id']?.toString()
      ? widget.representedSpaceId
      : null;

  @override
  void initState() {
    super.initState();
    final draft = widget.initialDraft;
    _title = TextEditingController(text: draft?.title ?? '');
    _body = TextEditingController(text: draft?.body ?? '');
    _options = TextEditingController(text: draft?.options ?? '\n');
    _reference = draft?.reference;
    _audienceId = draft?.audienceId ??
        widget.capabilities['default_audience_id']?.toString();
    _title.addListener(_changed);
    _body.addListener(_changed);
    _options.addListener(_changed);
  }

  void _saveDraft() {
    final draft = _PointDraft(
      title: _title.text,
      body: _body.text,
      options: _options.text,
      audienceId: _audienceId,
      reference: _reference,
    );
    _draftWrites = _draftWrites.catchError((Object _) {}).then(
      (_) => widget.onDraftChanged(draft),
    );
  }

  void _changed() {
    _reference = null;
    _saveDraft();
    if (_error != null && mounted) setState(() => _error = null);
  }

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    _options.dispose();
    super.dispose();
  }

  Future<void> _publish() async {
    if (_sending) return;
    final kind = widget.kind;
    final title = _title.text.trim();
    final body = _body.text.trim();
    if (kind != 'information' && title.isEmpty) {
      setState(() => _error = 'Précisez le sujet.');
      return;
    }
    if (kind == 'information' && body.isEmpty) {
      setState(() => _error = 'Écrivez le texte.');
      return;
    }
    if (widget.capabilities['audience_selection_required'] == true &&
        _audienceId == null) {
      setState(() => _error = 'Choisissez les destinataires.');
      return;
    }
    final options = kind == 'poll'
        ? _options.text.split('\n')
            .map((item) => item.trim())
            .where((item) => item.isNotEmpty)
            .toList(growable: false)
        : <String>[];
    if (kind == 'poll' &&
        (options.length < 2 || options.length > 12 ||
            options.toSet().length != options.length)) {
      setState(() => _error = 'Prévoyez entre 2 et 12 choix différents.');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      _saveDraft();
      await _draftWrites;
      final delivery = widget.repository.delivery;
      if (delivery != null) {
        await delivery.queue(
          conversationId: widget.conversationId,
          mode: 'point',
          kind: kind,
          title: title,
          body: body,
          options: options,
          audienceId: _audienceId,
          representedSpaceId: _representedSpace,
        );
        await delivery.clearDraft(
          conversationId: widget.conversationId, kind: kind,
        );
        if (mounted) widget.onQueued();
      } else {
        _reference ??= _newConversationReference();
        final published = await widget.repository.compose(
          conversationId: widget.conversationId,
          mode: 'point',
          kind: kind,
          title: title,
          body: body,
          options: options,
          audienceId: _audienceId,
          representedSpaceId: _representedSpace,
          clientReference: _reference!,
        );
        if (mounted) widget.onPublished(published);
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
    final kind = widget.kind;
    final audiences = _audienceRows(widget.capabilities);
    final title = switch (kind) {
      'poll' => 'Sondage',
      'confirmation' => 'Confirmation',
      'question' => 'Question',
      'request' => 'Demande',
      'exchange' => 'Échange',
      _ => 'Information',
    };
    return Padding(
      padding: EdgeInsets.fromLTRB(
        20, 6, 20, MediaQuery.viewInsetsOf(context).bottom + 24,
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 16),
            if (kind != 'information')
              TextField(
                key: const Key('conversation-compose-title'),
                controller: _title,
                autofocus: true,
                maxLength: 220,
                decoration: InputDecoration(
                  labelText: kind == 'poll' || kind == 'question'
                      ? 'Question'
                      : kind == 'confirmation'
                      ? 'À confirmer'
                      : 'Sujet',
                  border: const OutlineInputBorder(),
                ),
              ),
            if (kind == 'information' || kind == 'request' ||
                kind == 'question' || kind == 'confirmation' ||
                kind == 'poll')
              TextField(
                key: const Key('conversation-compose-body'),
                controller: _body,
                autofocus: kind == 'information',
                minLines: 2,
                maxLines: 5,
                maxLength: 5000,
                decoration: InputDecoration(
                  labelText: kind == 'information'
                      ? 'Texte'
                      : 'Précisions (facultatif)',
                  border: OutlineInputBorder(),
                ),
              ),
            if (kind == 'poll')
              TextField(
                key: const Key('conversation-compose-options'),
                controller: _options,
                minLines: 3,
                maxLines: 5,
                decoration: const InputDecoration(
                  labelText: 'Choix · un par ligne',
                  border: OutlineInputBorder(),
                ),
              ),
            if (widget.capabilities['audience_selection_required'] == true)
              DropdownButtonFormField<String>(
                value: _audienceId,
                decoration: const InputDecoration(
                  labelText: 'Destinataires',
                  border: OutlineInputBorder(),
                ),
                items: [
                  for (final audience in audiences)
                    DropdownMenuItem<String>(
                      value: audience['id']?.toString(),
                      child: Text(audience['label']?.toString() ?? 'Audience'),
                    ),
                ],
                onChanged: _sending ? null : (value) => setState(() {
                  _audienceId = value;
                  _reference = null;
                  _saveDraft();
                }),
              ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
            const SizedBox(height: 16),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton(
                key: const Key('conversation-compose-publish'),
                onPressed: _sending ? null : _publish,
                child: Text(_sending ? 'Envoi…' : 'Envoyer'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
