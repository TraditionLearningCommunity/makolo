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
  bool _sending = false;
  String? _reference;
  String? _error;
  String? _audienceId;
  String? _exchangeTargetId;

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
  }

  void _edited() {
    _reference = null;
    if (_error != null && mounted) setState(() => _error = null);
  }

  @override
  void didUpdateWidget(covariant ConversationComposer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository ||
        oldWidget.conversationId != widget.conversationId) {
      _reference = null;
      _drafts.clear();
      _text.clear();
      _error = null;
      _audienceId = widget.capabilities['default_audience_id']?.toString();
      _exchangeTargetId = widget.capabilities['default_exchange_point_id']?.toString();
    } else if (oldWidget.capabilities['default_audience_id'] !=
        widget.capabilities['default_audience_id']) {
      _audienceId = widget.capabilities['default_audience_id']?.toString();
    }
  }

  @override
  void dispose() {
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
    if (widget.capabilities['text_mode'] == 'exchange_select' &&
        _exchangeTargetId == null) {
      setState(() => _error = 'Choisissez un échange.');
      return;
    }
    if (_needsAudience && _audienceId == null &&
        widget.capabilities['text_mode'] == 'information') {
      setState(() => _error = 'Choisissez les destinataires.');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      _reference ??= _newConversationReference();
      final published = await widget.repository.compose(
        conversationId: widget.conversationId,
        clientReference: _reference!,
        mode: 'text',
        body: body,
        pointId: widget.capabilities['text_mode'] == 'exchange' ||
                widget.capabilities['text_mode'] == 'exchange_select'
            ? _exchangeTargetId
            : null,
        audienceId: _audienceId,
        representedSpaceId: _representedSpace,
      );
      if (!mounted) return;
      _text.clear();
      _reference = null;
      widget.onPublished(published);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Envoi non confirmé. Réessayer ou modifier.');
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _openPointEditor(String kind) async {
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
        initialDraft: _drafts[kind],
        onDraftChanged: (draft) => _drafts[kind] = draft,
        onPublished: (id) {
          _drafts.remove(kind);
          Navigator.of(sheetContext).pop();
          widget.onPublished(id);
        },
      ),
    );
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
        onPublished: (id) {
          Navigator.of(sheetContext).pop();
          widget.onPublished(id);
        },
      ),
    );
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

  @override
  Widget build(BuildContext context) {
    final canCreate = widget.capabilities['can_create'] == true;
    final textMode = widget.capabilities['text_mode']?.toString();
    final kinds = _kinds;
    final mediaKinds = (widget.capabilities['media_kinds'] as List?)
        ?.map((item) => item.toString()).toSet() ?? <String>{};
    final canForm = widget.capabilities['can_form'] == true;
    if (textMode == null && !canCreate && mediaKinds.isEmpty && !canForm) {
      return const SizedBox.shrink();
    }
    final secondary = [
      for (final kind in const ['question', 'request', 'exchange', 'information'])
        if (kinds.contains(kind)) kind,
    ];
    final audienceRows = _audienceRows(widget.capabilities);
    return Padding(
      key: const Key('conversation-composer'),
      padding: const EdgeInsets.fromLTRB(20, 28, 20, 32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Divider(),
          const SizedBox(height: 12),
          if (textMode != null) ...[
            if (textMode == 'exchange_select')
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: DropdownButtonFormField<String>(
                  value: _exchangeTargetId,
                  decoration: const InputDecoration(
                    labelText: 'Échange',
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    for (final item in _audienceRows({
                      'audiences': widget.capabilities['exchange_targets'],
                    }))
                      DropdownMenuItem<String>(
                        value: item['id']?.toString(),
                        child: Text(item['title']?.toString() ?? 'Échange'),
                      ),
                  ],
                  onChanged: _sending ? null : (value) => setState(() {
                    _exchangeTargetId = value;
                    _reference = null;
                  }),
                ),
              ),
            if (_needsAudience && textMode == 'information')
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: DropdownButtonFormField<String>(
                  value: _audienceId,
                  decoration: const InputDecoration(
                    labelText: 'Destinataires',
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    for (final row in audienceRows)
                      DropdownMenuItem<String>(
                        value: row['id']?.toString(),
                        child: Text(row['label']?.toString() ?? 'Destinataires'),
                      ),
                  ],
                  onChanged: _sending ? null : (value) => setState(() {
                    _audienceId = value;
                    _reference = null;
                  }),
                ),
              ),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('conversation-compose-text'),
                    controller: _text,
                    focusNode: _focus,
                    minLines: 2,
                    maxLines: 6,
                    maxLength: 5000,
                    textCapitalization: TextCapitalization.sentences,
                    decoration: const InputDecoration(
                      hintText: 'Écrire…',
                      border: OutlineInputBorder(),
                      counterText: '',
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  key: const Key('conversation-compose-send'),
                  onPressed: _sending ? null : _sendText,
                  tooltip: 'Envoyer',
                  icon: _sending
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.arrow_upward_rounded),
                ),
              ],
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
          if (canCreate || canForm || mediaKinds.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                if (mediaKinds.contains('voice'))
                  TextButton.icon(
                    key: const Key('conversation-compose-voice'),
                    onPressed: () => _openMedia('voice'),
                    icon: const Icon(Icons.mic_none_rounded),
                    label: const Text('Vocal'),
                  ),
                if (canForm)
                  TextButton.icon(
                    key: const Key('conversation-compose-form'),
                    onPressed: _openForm,
                    icon: const Icon(Icons.list_alt_rounded),
                    label: const Text('Formulaire'),
                  ),
                if (kinds.contains('poll'))
                  TextButton.icon(
                    onPressed: () => _openPointEditor('poll'),
                    icon: const Icon(Icons.poll_outlined),
                    label: const Text('Sondage'),
                  ),
                if (kinds.contains('confirmation'))
                  TextButton.icon(
                    onPressed: () => _openPointEditor('confirmation'),
                    icon: const Icon(Icons.check_circle_outline_rounded),
                    label: const Text('Confirmer'),
                  ),
                if (secondary.isNotEmpty ||
                    mediaKinds.contains('image') ||
                    mediaKinds.contains('file'))
                  PopupMenuButton<String>(
                    tooltip: 'Plus',
                    icon: const Icon(Icons.add_circle_outline_rounded),
                    onSelected: (value) {
                      if (value.startsWith('media:')) {
                        _openMedia(value.substring(6));
                      } else {
                        _openPointEditor(value);
                      }
                    },
                    itemBuilder: (context) => [
                      if (mediaKinds.contains('image')) ...[
                        const PopupMenuItem(
                          value: 'media:photo', child: Text('Photo'),
                        ),
                        const PopupMenuItem(
                          value: 'media:camera', child: Text('Caméra'),
                        ),
                      ],
                      if (mediaKinds.contains('file'))
                        const PopupMenuItem(
                          value: 'media:document', child: Text('Document'),
                        ),
                      for (final kind in secondary)
                        PopupMenuItem(
                          value: kind,
                          child: Text(switch (kind) {
                            'question' => 'Question',
                            'request' => 'Demande',
                            'exchange' => 'Nouvel échange',
                            _ => 'Information',
                          }),
                        ),
                    ],
                  ),
              ],
            ),
          ],
        ],
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
    this.initialDraft,
    this.representedSpaceId,
  });

  final _PointDraft? initialDraft;
  final ValueChanged<_PointDraft> onDraftChanged;
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
    widget.onDraftChanged(_PointDraft(
      title: _title.text,
      body: _body.text,
      options: _options.text,
      audienceId: _audienceId,
      reference: _reference,
    ));
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
        (options.length < 2 || options.toSet().length != options.length)) {
      setState(() => _error = 'Prévoyez au moins deux choix différents.');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      _reference ??= _newConversationReference();
      _saveDraft();
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
    } on Object {
      if (mounted) {
        setState(() => _error = 'Publication non confirmée. Réessayer ou modifier.');
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
      'confirmation' => 'Confirmer',
      'question' => 'Question',
      'request' => 'Demande',
      'exchange' => 'Nouvel échange',
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
                  labelText: kind == 'poll' ? 'Question' : 'Sujet',
                  border: const OutlineInputBorder(),
                ),
              ),
            if (kind == 'information' || kind == 'request')
              TextField(
                key: const Key('conversation-compose-body'),
                controller: _body,
                autofocus: kind == 'information',
                minLines: 2,
                maxLines: 5,
                maxLength: 5000,
                decoration: const InputDecoration(
                  labelText: 'Texte',
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
                child: Text(_sending ? 'Publication…' : 'Publier'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
