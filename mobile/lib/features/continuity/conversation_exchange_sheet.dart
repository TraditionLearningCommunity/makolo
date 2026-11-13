import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../network/api_error.dart';
import '../../data/files/file_transfer_coordinator.dart';
import 'conversation_local_delivery.dart';
import 'conversation_media_group.dart';
import 'conversation_attachment_viewer.dart';
import 'conversation_media_sheet.dart';
import 'conversation_repository.dart';

String _exchangeReference() =>
    'exchange-${DateTime.now().microsecondsSinceEpoch}-${Random.secure().nextInt(0x7fffffff)}';
List<Map<String, dynamic>> _entries(Object? value) => value is List
    ? [
        for (final row in value)
          if (row is Map) Map<String, dynamic>.from(row),
      ]
    : [];

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

class _ConversationExchangeSheetState extends State<ConversationExchangeSheet>
    with WidgetsBindingObserver {
  final _body = TextEditingController();
  final _search = TextEditingController();
  final _scroll = ScrollController();
  final _viewportKey = GlobalKey();
  List<Map<String, dynamic>> _rows = [];
  List<ConversationOutgoing> _outgoing = [];
  StreamSubscription<List<Map<String, dynamic>>>? _messages;
  StreamSubscription<List<ConversationOutgoing>>? _pending;
  StreamSubscription<Map<String, dynamic>>? _signals;
  Timer? _poll;
  Timer? _typingExpiry;
  Future<void> _draftWrites = Future.value();
  final Map<String, String> _mentions = {};
  final List<Map<String, dynamic>> _references = [];
  Map<String, dynamic>? _reply;
  Map<String, dynamic>? _edit;
  String? _editReference;
  String? _error;
  String? _ephemeral;
  String? _cursor;
  bool _loading = false;
  bool _loaded = false;
  bool _localReadDone = false;
  bool _sending = false;
  bool _revoked = false;
  bool _foreground = true;
  bool _newMessages = false;
  int _limit = 100;
  int _searchGeneration = 0;
  Timer? _searchDebounce;
  String? _searchCursor;
  bool _searchBusy = false;
  String? _searchFreshness;
  final Map<String, Map<String, dynamic>> _searchRows = {};
  List<Map<String, dynamic>>? _focusedContext;
  final Map<String, GlobalKey> _messageKeys = {};
  String? _highlight;
  bool _programmaticScroll = false;

  String get _draftKind => 'exchange:${widget.pointId}';
  ConversationLocalDelivery? get _delivery => widget.repository.delivery;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _body.addListener(_draftChanged);
    _search.addListener(_searchChanged);
    _initialize();
    _restoreDraft();
    _pending = _delivery?.watchOutgoing(widget.conversationId).listen((rows) {
      if (!mounted) return;
      setState(
        () => _outgoing = rows
            .where((row) => row.pointId == widget.pointId)
            .toList(),
      );
      if (_outgoing.any((row) => row.isConfirmed)) unawaited(_refresh());
    });
    _signals = widget.repository.realtime?.signals.listen((signal) {
      if (!mounted) return;
      if (signal['type'] == 'connected') {
        setState(() => _ephemeral = null);
        return;
      }
      if (signal['type'] == 'transport_unavailable' ||
          signal['type'] == 'disconnected') {
        setState(
          () => _ephemeral = 'Temps réel interrompu · Actualisation périodique',
        );
        return;
      }
      if (signal['point_id'] != widget.pointId) return;
      if (signal['code'] == 'access_revoked') {
        setState(() {
          _revoked = true;
          _rows = [];
        });
        return;
      }
      if (signal['type'] == 'typing_changed' ||
          signal['type'] == 'presence_changed') {
        if (signal['profile_id'] == widget.repository.profileId) return;
        _typingExpiry?.cancel();
        setState(
          () => _ephemeral = signal['type'] == 'typing_changed'
              ? 'Une personne écrit…'
              : 'Actif dans cette discussion',
        );
        _typingExpiry = Timer(
          Duration(seconds: signal['ttl'] as int? ?? 5),
          () {
            if (mounted) setState(() => _ephemeral = null);
          },
        );
      }
    });
    // Catch-up remains available when Channels/Redis cannot be reached.
    _poll = Timer.periodic(const Duration(seconds: 20), (_) {
      if (_foreground) unawaited(_refresh());
    });
  }

  Future<void> _initialize() async {
    try {
      final local = await widget.repository.exchangeStore.read(
        widget.pointId,
        limit: _limit,
      );
      if (!mounted) return;
      setState(() {
        _rows = local;
        _loaded = local.isNotEmpty;
        _localReadDone = true;
      });
      _observe();
      await _load();
    } on Object {
      if (mounted) {
        setState(
          () => _error =
              'Lecture locale indisponible. Votre saisie est conservée.',
        );
      }
    }
  }

  void _observe() {
    unawaited(_messages?.cancel());
    _messages = widget.repository
        .watchExchange(widget.pointId, limit: _limit)
        .listen(
          (rows) {
            if (!mounted) return;
            final latest = _rows.isEmpty ? 0 : _rows.last['sequence'] as int;
            setState(() {
              if (_scroll.hasClients &&
                  _scroll.offset > 80 &&
                  rows.any((row) => (row['sequence'] as int) > latest)) {
                _newMessages = true;
              }
              _rows = rows;
              _loaded = true;
            });
          },
          onError: (Object error) {
            if (mounted) {
              setState(() => _error = 'Lecture locale indisponible.');
            }
          },
        );
  }

  Future<void> _restoreDraft() async {
    try {
      final draft = await _delivery?.readDraft(
        conversationId: widget.conversationId,
        kind: _draftKind,
      );
      if (!mounted || _body.text.isNotEmpty || draft == null) return;
      _body.text = draft['body']?.toString() ?? '';
      for (final id in (draft['mention_profile_ids'] as List? ?? const [])) {
        _mentions[id.toString()] = 'Mention';
      }
      _references.addAll(_entries(draft['references']));
      final replyId = draft['reply_to_id'];
      if (replyId is String) {
        setState(() => _reply = {'id': replyId, 'body': 'Réponse citée'});
      }
    } on Object {
      if (mounted) setState(() => _error = 'Brouillon local indisponible.');
    }
  }

  void _draftChanged() {
    if (_edit != null) return;
    final body = _body.text, replyId = _reply?['id'];
    final mentions = _mentions.keys.toList();
    final references = _references
        .map((r) => {'kind': r['kind'], 'id': r['id']})
        .toList();
    _draftWrites = _draftWrites
        .then((_) async {
          await _delivery?.saveDraft(
            conversationId: widget.conversationId,
            kind: _draftKind,
            payload: {
              'body': body,
              'reply_to_id': replyId,
              'mention_profile_ids': mentions,
              'references': references,
            },
          );
        })
        .catchError((Object error) {
          if (mounted) {
            setState(
              () => _error =
                  'Brouillon non sauvegardé. Gardez cette discussion ouverte.',
            );
          }
        });
    widget.repository.realtime?.typing(widget.pointId);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    widget.repository.realtime?.foreground(_foreground);
    if (_foreground) unawaited(_refresh());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _searchDebounce?.cancel();
    _poll?.cancel();
    _typingExpiry?.cancel();
    unawaited(_messages?.cancel());
    unawaited(_pending?.cancel());
    unawaited(_signals?.cancel());
    _body.removeListener(_draftChanged);
    _body.dispose();
    _search.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    if (_revoked || !_foreground || !_localReadDone) return;
    try {
      await widget.repository.refreshExchange(widget.pointId);
      if (mounted) setState(() => _error = null);
    } on MakoloApiError catch (error) {
      if (!mounted) return;
      setState(() {
        if ({401, 403, 404}.contains(error.statusCode)) {
          _revoked = true;
          _rows = [];
        }
        _error = _revoked
            ? 'Cette Discussion n’est plus accessible.'
            : 'Actualisation impossible.';
      });
    } on Object {
      if (mounted) setState(() => _error = 'Actualisation impossible.');
    }
  }

  Future<void> _load() async {
    if (_loading || _revoked) return;
    setState(() => _loading = true);
    try {
      final page = await widget.repository.exchangeEntries(
        pointId: widget.pointId,
        cursor: _cursor,
      );
      if (!mounted) return;
      setState(() {
        if (_focusedContext != null) {
          final merged = {
            for (final row in [
              ..._entries(page['results']),
              ..._focusedContext!,
            ])
              row['id']: row,
          };
          _focusedContext = merged.values.toList()
            ..sort(
              (a, b) => (a['sequence'] as int).compareTo(b['sequence'] as int),
            );
        }
        _cursor = page['next_cursor']?.toString();
        _limit += 50;
      });
      _observe();
      await _refresh();
    } on Object {
      if (mounted) {
        setState(() => _error = 'Impossible d’actualiser les messages.');
      }
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
          _loaded = true;
        });
      }
    }
  }

  Future<void> _send() async {
    if (_sending ||
        _revoked ||
        !widget.canRespond ||
        (_body.text.trim().isEmpty && _references.isEmpty)) {
      return;
    }
    final text = _body.text;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      if (_edit case final edit?) {
        _editReference ??= _exchangeReference();
        await widget.repository.mutateEntry(
          edit['id'].toString(),
          body: text,
          expectedVersion: edit['edit_version'] as int,
          reference: _editReference,
          mentionProfileIds: _mentions.keys.toList(),
        );
        _edit = null;
        _editReference = null;
      } else {
        final delivery = _delivery;
        if (delivery == null) throw StateError('Envoi local indisponible.');
        await _draftWrites;
        await delivery.queue(
          conversationId: widget.conversationId,
          mode: 'text',
          pointId: widget.pointId,
          body: text.trim(),
          replyToId: _reply?['id']?.toString(),
          mentionProfileIds: _mentions.keys.toList(),
          references: _references
              .map((r) => {'kind': r['kind'], 'id': r['id']})
              .toList(),
          representedSpaceId:
              widget.representedSpaceId ==
                  widget.capabilities['representable_space_id']
              ? widget.representedSpaceId
              : null,
        );
      }
      if (!mounted) return;
      if (_body.text == text) {
        _reply = null;
        _mentions.clear();
        _references.clear();
        _body.clear();
      }
      await _refresh();
    } on Object {
      if (mounted) setState(() => _error = 'Envoi non confirmé.');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _action(Map<String, dynamic> row, String action) async {
    if (action == 'copy') {
      await Clipboard.setData(ClipboardData(text: row['body'].toString()));
      return;
    }
    if (action == 'reply') {
      setState(() {
        _reply = row;
        _edit = null;
      });
      _draftChanged();
      return;
    }
    if (action == 'edit') {
      setState(() {
        _edit = row;
        _reply = null;
        _editReference = null;
        _mentions.clear();
        for (final m in _entries(row['mentions'])) {
          _mentions[m['id'].toString()] = m['label'].toString();
        }
        _body.text = row['body'].toString();
      });
      return;
    }
    try {
      if (action == 'delete') {
        final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Supprimer ce message ?'),
            content: const Text('Il sera retiré de cette Discussion.'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Conserver'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Supprimer'),
              ),
            ],
          ),
        );
        if (confirmed != true) return;
        await widget.repository.mutateEntry(row['id'].toString(), remove: true);
      } else {
        final selected = _entries(row['reactions'])
            .any((r) => r['emoji'] == action && r['selected'] == true);
        await widget.repository.mutateEntry(
          row['id'].toString(),
          emoji: action,
          selected: !selected,
          reference: _exchangeReference(),
        );
      }
      await _refresh();
    } on Object {
      if (mounted) {
        setState(
          () => _error =
              'Modification non confirmée. Actualisez avant de réessayer.',
        );
      }
    }
  }

  Future<void> _chooseOption({bool references = false}) async {
    try {
      final options = await widget.repository.exchangeOptions(
        widget.pointId,
        references: references,
      );
      if (!mounted) return;
      final selected = await showModalBottomSheet<Map<String, dynamic>>(
        context: context,
        useSafeArea: true,
        builder: (context) => ListView(
          shrinkWrap: true,
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text(
                references
                    ? 'Joindre une référence'
                    : 'Mentionner une personne',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            if (options.isEmpty)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('Aucun élément accessible dans ce contexte.'),
              ),
            for (final option in options)
              ListTile(
                title: Text(option['label'].toString()),
                onTap: () => Navigator.pop(context, option),
              ),
          ],
        ),
      );
      if (!mounted || selected == null) return;
      setState(() {
        if (references) {
          _references
            ..clear()
            ..add(selected);
        } else {
          _mentions[selected['id'].toString()] = selected['label'].toString();
        }
      });
      _draftChanged();
    } on Object {
      if (mounted) {
        setState(() => _error = 'Sélection indisponible. Réessayez.');
      }
    }
  }

  void _searchChanged() {
    final query = _search.text.trim();
    final generation = ++_searchGeneration;
    _searchDebounce?.cancel();
    _searchCursor = null;
    _searchRows.clear();
    _searchFreshness = null;
    if (query.isEmpty) {
      setState(() {});
      return;
    }
    () async {
      final rows = await widget.repository.exchangeStore.search(
        widget.pointId,
        query,
      );
      if (!mounted || generation != _searchGeneration) return;
      setState(() {
        for (final row in rows) {
          _searchRows[row['id'].toString()] = row;
        }
        _searchFreshness = 'Messages reçus sur cet appareil';
      });
    }().catchError((Object error) {
      if (mounted && generation == _searchGeneration) {
        setState(() => _error = 'Recherche locale indisponible.');
      }
    });
    if (query.length >= 2) {
      _searchDebounce = Timer(
        const Duration(milliseconds: 300),
        () => _remoteSearch(generation),
      );
    }
  }

  Future<void> _remoteSearch(int generation, {bool append = false}) async {
    if (_searchBusy) return;
    setState(() => _searchBusy = true);
    final query = _search.text.trim();
    try {
      final page = await widget.repository.searchExchange(
        widget.pointId,
        query,
        cursor: append ? _searchCursor : null,
      );
      if (!mounted ||
          generation != _searchGeneration ||
          query != _search.text.trim()) {
        return;
      }
      setState(() {
        if (page['local_scope_changed'] == true) _searchRows.clear();
        for (final row in _entries(page['results'])) {
          _searchRows[row['id'].toString()] = row;
        }
        _searchCursor = page['next_cursor']?.toString();
        _searchFreshness = 'Résultats actualisés';
      });
    } on MakoloApiError catch (error) {
      if (mounted && generation == _searchGeneration) {
        if ({401, 403, 404}.contains(error.statusCode)) {
          await widget.repository.exchangeStore.revoke(widget.pointId);
          if (mounted) {
            setState(() {
              _revoked = true;
              _rows = [];
              _searchRows.clear();
              _focusedContext = null;
              _error = 'Cette Discussion n’est plus accessible.';
            });
          }
        } else {
          setState(
            () => _searchFreshness =
                'Réseau indisponible · Résultats locaux conservés',
          );
        }
      }
    } on Object {
      if (mounted && generation == _searchGeneration) {
        setState(
          () => _searchFreshness =
              'Réseau indisponible · Résultats locaux conservés',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _searchBusy = false);
        if (generation != _searchGeneration && _search.text.trim().length >= 2) {
          _searchDebounce = Timer(
            const Duration(milliseconds: 100),
            () => _remoteSearch(_searchGeneration),
          );
        }
      }
    }
  }

  Future<void> _jumpEntry(String id) async {
    final generation = ++_searchGeneration;
    try {
      final page = await widget.repository.locateExchangeEntry(
        widget.pointId,
        id,
      );
      if (!mounted || generation != _searchGeneration) return;
      _programmaticScroll = true;
      _search.removeListener(_searchChanged);
      _search.clear();
      _search.addListener(_searchChanged);
      setState(() {
        _focusedContext = _entries(page['results']);
        _highlight = id;
        _cursor = page['has_more'] == true
            ? page['before_sequence']?.toString()
            : null;
      });
      await WidgetsBinding.instance.endOfFrame;
      if (_scroll.hasClients) _scroll.jumpTo(0);
      // Context is bounded by the owner to 51 rows. Bring a lazily built
      // target into the viewport without fetching any unrelated history.
      for (var attempt = 0; attempt < 55 && mounted; attempt++) {
        final target = _messageKeys[id]?.currentContext;
        if (target != null) {
          await Scrollable.ensureVisible(
            target,
            alignment: .45,
            duration: Duration.zero,
          );
          break;
        }
        if (!_scroll.hasClients) break;
        final next = (_scroll.offset + _scroll.position.viewportDimension * .75)
            .clamp(0.0, _scroll.position.maxScrollExtent)
            .toDouble();
        if (next == _scroll.offset) break;
        _scroll.jumpTo(next);
        await WidgetsBinding.instance.endOfFrame;
      }
      if (mounted) setState(() => _newMessages = true);
    } on Object {
      if (mounted) setState(() => _error = 'Message indisponible.');
    } finally {
      _programmaticScroll = false;
    }
  }

  Future<void> _openReference(String id) async {
    try {
      final reference = await widget.repository.exchangeReference(id);
      if (!mounted) return;
      final open = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(reference['label'].toString()),
          content: Text(
            [
              reference['description'],
              reference['state_label'],
              reference['mode_label'],
              if (reference['version'] != null)
                'Version ${reference['version']}',
              reference['mime_type'],
            ].whereType<String>().join(' · '),
          ),
          actions: [
            if (reference['view_url'] != null)
              TextButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Ouvrir'),
              ),
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Fermer'),
            ),
          ],
        ),
      );
      if (open != true || !mounted) return;
      final mime =
          reference['mime_type']?.toString() ?? 'application/octet-stream';
      final ext =
          {
            'application/pdf': 'pdf',
            'image/jpeg': 'jpg',
            'image/png': 'png',
            'text/plain': 'txt',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                'docx',
          }[mime] ??
          'bin';
      final filename = '${reference['label']}.$ext';
      await showModalBottomSheet<void>(
        context: context,
        useSafeArea: true,
        isScrollControlled: true,
        builder: (context) => FractionallySizedBox(
          heightFactor: .92,
          child: ConversationAttachmentViewer(
            attachment: {
              'id': id,
              'name': filename,
              'mime_type': mime,
              'kind': mime.startsWith('image/') ? 'image' : 'file',
            },
            download:
                ({required String attachmentId, required String filename}) =>
                    widget.repository.downloadEntryReference(
                      referenceId: id,
                      filename: filename,
                    ),
            allowDownload: reference['can_download'] == true,
            allowShare: reference['can_share'] == true,
            authorizeExport: (share) async {
              if (reference['export_warning'] == true) {
                final confirmed = await showDialog<bool>(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Confirmer l’export ?'),
                    content: const Text(
                      'Ce document peut contenir des données personnelles.',
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context, false),
                        child: const Text('Annuler'),
                      ),
                      FilledButton(
                        onPressed: () => Navigator.pop(context, true),
                        child: const Text('Confirmer'),
                      ),
                    ],
                  ),
                );
                if (confirmed != true) throw StateError('Export annulé');
              }
              return widget.repository.downloadEntryReference(
                referenceId: id,
                filename: filename,
                mode: share ? 'system_share' : 'download',
                confirm: true,
              );
            },
          ),
        ),
      );
    } on Object {
      if (mounted) {
        setState(() => _error = 'Cette référence n’est plus accessible.');
      }
    }
  }

  Future<void> _privacy() async {
    final detail = await widget.repository.readDetail(widget.conversationId);
    if (!mounted) return;
    final current =
        (detail?.payload['personal_state'] as Map?)?['share_read_receipts'] !=
        false;
    final selected = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reçus de lecture'),
        content: Text(
          current
              ? 'Vos lectures sont partagées dans cette Conversation.'
              : 'Vos lectures ne sont pas partagées dans cette Conversation.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Conserver'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, !current),
            child: Text(current ? 'Ne plus partager' : 'Partager'),
          ),
        ],
      ),
    );
    if (selected == null) return;
    try {
      await widget.repository.updatePersonalState(
        conversationId: widget.conversationId,
        shareReadReceipts: selected,
      );
    } on Object {
      if (mounted) {
        setState(() => _error = 'Préférence non confirmée. Réessayez.');
      }
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
        onQueued: () {
          Navigator.of(sheetContext).pop();
        },
        onPublished: (pointId) {
          Navigator.of(sheetContext).pop();
          widget.onPublished(pointId);
          unawaited(_refresh());
        },
      ),
    );
  }

  Future<void> _markRead() async {
    if (!_foreground ||
        _revoked ||
        _programmaticScroll ||
        ModalRoute.of(context)?.isCurrent != true) {
      return;
    }
    final viewport = _viewportKey.currentContext?.findRenderObject();
    if (viewport is! RenderBox) return;
    final origin = viewport.localToGlobal(Offset.zero);
    final bounds = origin & viewport.size;
    final visible = <String>{};
    for (final entry in _messageKeys.entries) {
      final node = entry.value.currentContext?.findRenderObject();
      if (node is! RenderBox || !node.attached) continue;
      final top = node.localToGlobal(Offset.zero);
      final box = top & node.size;
      if (box.top >= bounds.top && box.bottom <= bounds.bottom) {
        visible.add(entry.key);
      }
    }
    try {
      await widget.repository.markVisibleExchangeRead(widget.pointId, visible);
    } on Object {
      if (mounted) setState(() => _error = 'Lecture non confirmée.');
    }
  }

  Widget _bubble(Map<String, dynamic> row, {bool showAuthor = true}) {
    final own = row['own'] == true, removed = row['removed'] == true;
    final capabilities = row['capabilities'] as Map? ?? {};
    final quote = row['reply_to'] as Map?;
    final author = row['author'] as Map?;
    final reactions = _entries(row['reactions']);
    final delivery = row['delivery'] as Map?;
    final deliveryLabel =
        delivery?['read_count'] is int && (delivery!['read_count'] as int) > 0
        ? 'Lu (${delivery['read_count']})'
        : delivery?['delivered_count'] is int &&
              (delivery!['delivered_count'] as int) > 0
        ? 'Livré (${delivery['delivered_count']})'
        : 'Confirmé';
    return Align(
      alignment: own ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        key: ValueKey('exchange-message-${row['id']}'),
        margin: const EdgeInsets.symmetric(vertical: 5),
        padding: const EdgeInsets.all(12),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * .82,
        ),
        decoration: BoxDecoration(
          color: own
              ? Theme.of(context).colorScheme.primaryContainer
              : Theme.of(context).colorScheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (showAuthor)
              Text(
                own ? 'Vous' : author?['label']?.toString() ?? '',
                style: Theme.of(context).textTheme.labelSmall,
              ),
            if (row['represented_space'] case final Map space)
              Text(
                space['label'].toString(),
                style: Theme.of(context).textTheme.labelSmall,
              ),
            if (quote != null)
              Container(
                padding: const EdgeInsets.all(8),
                margin: const EdgeInsets.symmetric(vertical: 6),
                decoration: BoxDecoration(
                  border: Border(
                    left: BorderSide(
                      color: Theme.of(context).colorScheme.primary,
                      width: 3,
                    ),
                  ),
                ),
                child: TextButton(
                  onPressed: quote['available'] == false
                      ? null
                      : () => _jumpEntry(quote['id'].toString()),
                  child: Text(
                    quote['available'] == false
                        ? 'Message indisponible'
                        : quote['removed'] == true
                        ? 'Message supprimé'
                        : quote['body']?.toString() ?? 'Réponse citée',
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ),
            SelectableText(
              removed ? 'Message supprimé' : row['body']?.toString() ?? '',
            ),
            if (!removed && _entries(row['attachments']).isNotEmpty)
              ConversationMediaGroup(
                repository: widget.repository,
                attachments: _entries(row['attachments']),
              ),
            for (final mention in _entries(row['mentions']))
              Text(
                '@${mention['label']}',
                style: TextStyle(color: Theme.of(context).colorScheme.primary),
              ),
            for (final ref in _entries(row['references']))
              TextButton(
                onPressed: ref['available'] == true
                    ? () => _openReference(ref['id'].toString())
                    : null,
                child: Text(
                  ref['available'] == true
                      ? ref['label'].toString()
                      : 'Référence inaccessible',
                ),
              ),
            Text(
              '${DateTime.tryParse(row['created_at']?.toString() ?? '')?.toLocal().toString().substring(0, 16) ?? ''}${row['edited_at'] == null ? '' : ' · Modifié'}${own ? ' · $deliveryLabel' : ''}',
              style: Theme.of(context).textTheme.labelSmall,
            ),
            if (reactions.isNotEmpty)
              Wrap(
                children: [
                  for (final reaction in reactions)
                    TextButton(
                      onPressed: capabilities['react'] == true
                          ? () => _action(row, reaction['emoji'].toString())
                          : null,
                      child: Text('${reaction['emoji']} ${reaction['count']}'),
                    ),
                ],
              ),
            if (!removed)
              PopupMenuButton<String>(
                tooltip: 'Actions du message',
                onSelected: (action) => _action(row, action),
                itemBuilder: (_) => [
                  const PopupMenuItem(value: 'copy', child: Text('Copier')),
                  if (capabilities['reply'] == true)
                    const PopupMenuItem(
                      value: 'reply',
                      child: Text('Répondre'),
                    ),
                  if (capabilities['edit'] == true)
                    const PopupMenuItem(value: 'edit', child: Text('Modifier')),
                  if (capabilities['delete'] == true)
                    const PopupMenuItem(
                      value: 'delete',
                      child: Text('Supprimer'),
                    ),
                  if (capabilities['react'] == true)
                    for (final emoji in ['👍', '❤️', '🙏', '✅', '👀', '🎉'])
                      PopupMenuItem(value: emoji, child: Text(emoji)),
                ],
              ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final rows = _focusedContext ?? _rows;
    final references = _rows.map((row) => row['client_reference']).toSet();
    final pending = _outgoing
        .where((row) => !references.contains(row.reference))
        .toList();
    final media =
        (widget.capabilities['media_kinds'] as List?)
            ?.map((v) => v.toString())
            .toSet() ??
        <String>{};
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: Scaffold(
          appBar: AppBar(
            title: Text(widget.title),
            actions: [
              IconButton(
                tooltip: 'Confidentialité des lectures',
                onPressed: _privacy,
                icon: const Icon(Icons.visibility_outlined),
              ),
              IconButton(
                tooltip: 'Actualiser',
                onPressed: _refresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          body: Column(
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: TextField(
                  controller: _search,
                  decoration: const InputDecoration(
                    labelText: 'Rechercher dans les messages',
                    prefixIcon: Icon(Icons.search),
                  ),
                ),
              ),
              if (_search.text.trim().isNotEmpty) ...[
                if (_searchFreshness != null)
                  Text(
                    _searchFreshness!,
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                if (_searchBusy) const LinearProgressIndicator(),
                SizedBox(
                  height: 180,
                  child: ListView(
                    children: [
                      for (final row
                          in (_searchRows.values.toList()..sort(
                            (a, b) => (b['sequence'] as int).compareTo(
                              a['sequence'] as int,
                            ),
                          )))
                        ListTile(
                          title: Text(
                            row['body'].toString(),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                          onTap: () => _jumpEntry(row['id'].toString()),
                        ),
                      if (_searchCursor != null)
                        TextButton(
                          onPressed: _searchBusy
                              ? null
                              : () => _remoteSearch(
                                  _searchGeneration,
                                  append: true,
                                ),
                          child: const Text('Résultats suivants'),
                        ),
                    ],
                  ),
                ),
              ],
              if (_ephemeral != null)
                Text(
                  _ephemeral!,
                  style: Theme.of(context).textTheme.labelSmall,
                ),
              if (_revoked)
                const Expanded(
                  child: Center(
                    child: Text('Cette Discussion n’est plus accessible.'),
                  ),
                )
              else if (!_loaded && _rows.isEmpty)
                const Expanded(
                  child: Center(child: CircularProgressIndicator()),
                )
              else
                Expanded(
                  child: NotificationListener<ScrollNotification>(
                    key: _viewportKey,
                    onNotification: (notification) {
                      if (!_programmaticScroll &&
                          notification is UserScrollNotification) {
                        unawaited(_markRead());
                      }
                      return false;
                    },
                    child: ListView.builder(
                      controller: _scroll,
                      reverse: true,
                      padding: const EdgeInsets.all(12),
                      itemCount: rows.length + pending.length + 1,
                      itemBuilder: (context, index) {
                        if (index < pending.length) {
                          final intent = pending.reversed.elementAt(index);
                          return Align(
                            alignment: Alignment.centerRight,
                            child: Card(
                              child: Padding(
                                padding: const EdgeInsets.all(12),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.end,
                                  children: [
                                    Text(
                                      intent.body.isEmpty
                                          ? intent.filename ?? 'Média'
                                          : intent.body,
                                    ),
                                    if (intent.mediaKind != null &&
                                        _delivery != null)
                                      StreamBuilder<ConversationTransfer?>(
                                        stream: _delivery!.watchTransfer(
                                          intent.reference,
                                        ),
                                        builder: (context, snapshot) {
                                          final transfer = snapshot.data;
                                          if (transfer == null) {
                                            return const SizedBox.shrink();
                                          }
                                          return Column(
                                            children: [
                                              if (transfer.state ==
                                                  FileTransferState
                                                      .transferring) ...[
                                                LinearProgressIndicator(
                                                  value: transfer.total > 0
                                                      ? transfer.transferred /
                                                            transfer.total
                                                      : null,
                                                ),
                                                if (transfer.total > 0)
                                                  Text(
                                                    '${(100 * transfer.transferred / transfer.total).floor()} %',
                                                  ),
                                                TextButton(
                                                  onPressed: () =>
                                                      _delivery!.cancelTransfer(
                                                        intent.reference,
                                                      ),
                                                  child: const Text(
                                                    'Interrompre le transfert',
                                                  ),
                                                ),
                                              ],
                                              if (transfer.state ==
                                                  FileTransferState
                                                      .ownerConfirmationRequired)
                                                const Text('Envoi à vérifier'),
                                            ],
                                          );
                                        },
                                      ),
                                    Text(
                                      intent.isConfirmed
                                          ? 'Envoyé'
                                          : intent.isBlocked
                                          ? 'Envoi à vérifier'
                                          : 'En attente',
                                      style: Theme.of(context)
                                          .textTheme
                                          .labelSmall,
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          );
                        }
                        final messageIndex = index - pending.length;
                        if (messageIndex == rows.length) {
                          return _cursor == null
                              ? const SizedBox.shrink()
                              : TextButton(
                                  onPressed: _loading ? null : _load,
                                  child: Text(
                                    _loading
                                        ? 'Chargement…'
                                        : 'Messages précédents',
                                  ),
                                );
                        }
                        final row = rows[rows.length - 1 - messageIndex];
                        final id = row['id'].toString();
                        final previous = rows.length - 2 - messageIndex >= 0
                            ? rows[rows.length - 2 - messageIndex]
                            : null;
                        final date = DateTime.tryParse(
                          row['created_at'].toString(),
                        )?.toLocal();
                        final priorDate = previous == null
                            ? null
                            : DateTime.tryParse(
                                previous['created_at'].toString(),
                              )?.toLocal();
                        final dayChanged =
                            priorDate == null ||
                            date?.day != priorDate.day ||
                            date?.month != priorDate.month ||
                            date?.year != priorDate.year;
                        return Container(
                          key: _messageKeys.putIfAbsent(id, () => GlobalKey()),
                          decoration: BoxDecoration(
                            border: Border.all(
                              color: id == _highlight
                                  ? Theme.of(context).colorScheme.primary
                                  : Colors.transparent,
                              width: 2,
                            ),
                          ),
                          child: Column(
                            children: [
                              if (dayChanged && date != null)
                                Text(
                                  MaterialLocalizations.of(context)
                                      .formatMediumDate(date),
                                ),
                              _bubble(
                                row,
                                showAuthor:
                                    dayChanged ||
                                    previous == null ||
                                    (previous['author'] as Map?)?['id'] !=
                                        (row['author'] as Map?)?['id'],
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                  ),
                ),
              if (_newMessages)
                TextButton(
                  onPressed: () {
                    _programmaticScroll = true;
                    setState(() {
                      _focusedContext = null;
                      _newMessages = false;
                      _highlight = null;
                    });
                    WidgetsBinding.instance.addPostFrameCallback((_) {
                      if (_scroll.hasClients) _scroll.jumpTo(0);
                      _programmaticScroll = false;
                    });
                  },
                  child: const Text('Nouveaux messages ↓'),
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
              if (!_revoked && widget.canRespond) ...[
                if (_mentions.isNotEmpty || _references.isNotEmpty)
                  Wrap(
                    children: [
                      for (final m in _mentions.entries)
                        InputChip(
                          label: Text('@${m.value}'),
                          onDeleted: () {
                            setState(() => _mentions.remove(m.key));
                            _draftChanged();
                          },
                        ),
                      for (final r in _references.toList())
                        InputChip(
                          label: Text(r['label']?.toString() ?? 'Référence'),
                          onDeleted: () {
                            setState(() => _references.remove(r));
                            _draftChanged();
                          },
                        ),
                    ],
                  ),
                if (_reply != null || _edit != null)
                  ListTile(
                    dense: true,
                    title: Text(
                      _edit == null ? 'Réponse citée' : 'Modifier le message',
                    ),
                    subtitle: Text(
                      (_edit ?? _reply)?['body']?.toString() ?? '',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    trailing: IconButton(
                      tooltip: 'Annuler',
                      onPressed: () {
                        setState(() {
                          _reply = _edit = null;
                          _editReference = null;
                        });
                        _restoreDraft();
                      },
                      icon: const Icon(Icons.close),
                    ),
                  ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      if (media.isNotEmpty)
                        PopupMenuButton<String>(
                          tooltip: 'Joindre',
                          onSelected: _attach,
                          itemBuilder: (_) => [
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
                      IconButton(
                        tooltip: 'Mentionner',
                        onPressed: () => _chooseOption(),
                        icon: const Icon(Icons.alternate_email),
                      ),
                      IconButton(
                        tooltip: 'Référence',
                        onPressed: () => _chooseOption(references: true),
                        icon: const Icon(Icons.link),
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
                        tooltip: 'Envoyer',
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
            ],
          ),
        ),
      ),
    );
  }
}
