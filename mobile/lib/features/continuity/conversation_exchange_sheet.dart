import 'dart:math';

import 'package:flutter/material.dart';

import 'conversation_media_group.dart';
import 'conversation_media_sheet.dart';
import 'conversation_repository.dart';

String _exchangeReference() =>
    'mobile-exchange-${DateTime.now().microsecondsSinceEpoch}-${Random.secure().nextInt(0x7fffffff).toRadixString(16)}';

List<Map<String, dynamic>> _entries(Object? raw) {
  if (raw is! List) return const [];
  return [
    for (final item in raw)
      if (item is Map)
        item.map((key, value) => MapEntry(key.toString(), value)),
  ];
}

/// A single Point Exchange depth, read by its owner and filtered by audiences.
class ConversationExchangeSheet extends StatefulWidget {
  const ConversationExchangeSheet({
    super.key,
    required this.repository,
    required this.conversationId,
    required this.pointId,
    required this.title,
    required this.canRespond,
    required this.capabilities,
    required this.onPublished,
    this.representedSpaceId,
  });

  final ConversationRepository repository;
  final String conversationId;
  final String pointId;
  final String title;
  final bool canRespond;
  final Map<String, dynamic> capabilities;
  final ValueChanged<String> onPublished;
  final String? representedSpaceId;

  @override
  State<ConversationExchangeSheet> createState() =>
      _ConversationExchangeSheetState();
}

class _ConversationExchangeSheetState extends State<ConversationExchangeSheet> {
  final _body = TextEditingController();
  final List<Map<String, dynamic>> _rows = [];
  String? _cursor;
  String? _reference;
  String? _error;
  bool _loading = false;
  bool _loaded = false;
  bool _sending = false;

  @override
  void initState() {
    super.initState();
    _body.addListener(() {
      _reference = null;
      if (_error != null && mounted) setState(() => _error = null);
    });
    _load();
  }

  @override
  void dispose() {
    _body.dispose();
    super.dispose();
  }

  Future<void> _load({bool reset = false}) async {
    if (_loading) return;
    if (reset) {
      _cursor = null;
      _rows.clear();
      _loaded = false;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final page = await widget.repository.exchangeEntries(
        pointId: widget.pointId,
        cursor: _cursor,
      );
      if (!mounted) return;
      setState(() {
        final seen = _rows.map((item) => item['id']?.toString()).toSet();
        for (final item in _entries(page['results'])) {
          if (seen.add(item['id']?.toString())) _rows.add(item);
        }
        _cursor = page['next_cursor']?.toString();
        _loaded = true;
      });
    } on Object {
      if (mounted) {
        setState(
          () => _error = 'Discussion indisponible. Votre saisie est conservée.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _send() async {
    if (_sending || !widget.canRespond || _body.text.trim().isEmpty) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      _reference ??= _exchangeReference();
      final published = await widget.repository.compose(
        conversationId: widget.conversationId,
        clientReference: _reference!,
        mode: 'text',
        pointId: widget.pointId,
        body: _body.text.trim(),
        representedSpaceId:
            widget.representedSpaceId ==
                widget.capabilities['representable_space_id']?.toString()
            ? widget.representedSpaceId
            : null,
      );
      if (!mounted) return;
      _body.clear();
      _reference = null;
      widget.onPublished(published);
      await _load(reset: true);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Envoi non confirmé. Réessayer ou modifier.');
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _attach(String mode) async {
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (sheetContext) => ConversationMediaSheet(
        mode: mode,
        lockedPointId: widget.pointId,
        repository: widget.repository,
        conversationId: widget.conversationId,
        capabilities: widget.capabilities,
        representedSpaceId: widget.representedSpaceId,
        onPublished: (pointId) {
          Navigator.of(sheetContext).pop();
          widget.onPublished(pointId);
          _load(reset: true);
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final media =
        (widget.capabilities['media_kinds'] as List?)
            ?.map((item) => item.toString())
            .toSet() ??
        <String>{};
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: Scaffold(
          appBar: AppBar(
            title: Text(widget.title.isEmpty ? 'Discussion' : widget.title),
          ),
          body: Column(
            children: [
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (_loading && !_loaded)
                      const Center(child: CircularProgressIndicator()),
                    if (!_loading && _loaded && _rows.isEmpty)
                      const Text('Aucun message pour le moment.'),
                    for (final row in _rows) ...[
                      if (row['own'] == true)
                        Text(
                          'Vous',
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        child: Text(row['body']?.toString() ?? ''),
                      ),
                      if (_entries(row['attachments']).isNotEmpty)
                        ConversationMediaGroup(
                          key: ValueKey('exchange-media-${row['id']}'),
                          repository: widget.repository,
                          attachments: _entries(row['attachments']),
                        ),
                      const Divider(height: 25),
                    ],
                    if (_cursor != null)
                      TextButton(
                        onPressed: _loading ? null : _load,
                        child: Text(_loading ? 'Chargement…' : 'Voir la suite'),
                      ),
                  ],
                ),
              ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.all(8),
                  child: Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              if (widget.canRespond)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      if (media.isNotEmpty)
                        PopupMenuButton<String>(
                          tooltip: 'Joindre',
                          icon: const Icon(Icons.add_circle_outline_rounded),
                          onSelected: _attach,
                          itemBuilder: (context) => [
                            if (media.contains('voice'))
                              const PopupMenuItem(
                                value: 'voice',
                                child: Text('Vocal'),
                              ),
                            if (media.contains('image')) ...[
                              const PopupMenuItem(
                                value: 'photo',
                                child: Text('Photo'),
                              ),
                              const PopupMenuItem(
                                value: 'camera',
                                child: Text('Caméra'),
                              ),
                            ],
                            if (media.contains('file'))
                              const PopupMenuItem(
                                value: 'document',
                                child: Text('Document'),
                              ),
                          ],
                        ),
                      Expanded(
                        child: TextField(
                          key: const Key('conversation-exchange-input'),
                          controller: _body,
                          minLines: 1,
                          maxLines: 4,
                          maxLength: 5000,
                          decoration: const InputDecoration(
                            hintText: 'Écrire un message…',
                            border: OutlineInputBorder(),
                            counterText: '',
                          ),
                        ),
                      ),
                      IconButton.filled(
                        key: const Key('conversation-exchange-send'),
                        onPressed: _sending ? null : _send,
                        icon: _sending
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.arrow_upward_rounded),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
