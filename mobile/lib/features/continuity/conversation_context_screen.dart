import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../design/behavior_states.dart';
import 'conversation_repository.dart';

List<Map<String, dynamic>> _contextRows(Map<String, dynamic> response) {
  final raw = response['results'];
  if (raw is! List) return const [];
  return [
    for (final row in raw)
      if (row is Map) row.map((key, value) => MapEntry(key.toString(), value)),
  ];
}

/// The owner decides both visibility and whether opening a missing context is
/// authorized. Neither membership nor public Profile creates contact rights.
class ConversationContextScreen extends StatefulWidget {
  const ConversationContextScreen({
    super.key,
    required this.repository,
    required this.kind,
    required this.contextId,
    required this.onOpen,
  });

  final ConversationRepository repository;
  final String kind;
  final String contextId;
  final ValueChanged<String> onOpen;

  @override
  State<ConversationContextScreen> createState() =>
      _ConversationContextScreenState();
}

class _ConversationContextScreenState extends State<ConversationContextScreen> {
  late Future<Map<String, dynamic>> _future;
  bool _busy = false;
  String? _error;
  String? _openedId;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant ConversationContextScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository ||
        oldWidget.kind != widget.kind ||
        oldWidget.contextId != widget.contextId) {
      _openedId = null;
      _load();
    }
  }

  void _load() {
    _future = widget.repository.contextDecision(
      kind: widget.kind,
      id: widget.contextId,
    );
  }

  void _retry() => setState(() {
    _error = null;
    _load();
  });

  Future<void> _ensure() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final id = await widget.repository.ensureContext(
        kind: widget.kind,
        id: widget.contextId,
      );
      if (mounted) widget.onOpen(id);
    } on Object {
      if (mounted) setState(() => _error = 'Ouverture non confirmée.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Conversations')),
    body: FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return MakoloErrorState(
            message: 'Conversation indisponible.',
            onRetry: _retry,
          );
        }
        if (!snapshot.hasData) return const MakoloLoadingState();
        final conversations = _contextRows(snapshot.data!);
        if (conversations.isEmpty) {
          if (snapshot.data!['can_ensure'] != true) {
            return const MakoloEmptyState(
              title: 'Aucune conversation accessible ici',
            );
          }
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                MakoloActionButton(
                  label: _busy ? 'Ouverture…' : 'Échanger',
                  onPressed: _busy ? null : _ensure,
                  appearance: MakoloActionAppearance.primary,
                  busy: _busy,
                ),
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(_error!),
                  ),
              ],
            ),
          );
        }
        if (conversations.length == 1) {
          final id = conversations.first['id']?.toString();
          if (id != null && _openedId != id) {
            _openedId = id;
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted) widget.onOpen(id);
            });
          }
          return const MakoloLoadingState();
        }
        return ListView.separated(
          itemCount: conversations.length,
          separatorBuilder: (_, _) => const Divider(height: 1),
          itemBuilder: (context, index) {
            final row = conversations[index];
            final id = row['id']?.toString();
            return ListTile(
              title: Text(row['title']?.toString() ?? 'Conversation'),
              subtitle: row['purpose'] == null
                  ? null
                  : Text(row['purpose'].toString()),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: id == null ? null : () => widget.onOpen(id),
            );
          },
        );
      },
    ),
  );
}

class ConversationContextAction extends StatefulWidget {
  const ConversationContextAction({
    super.key,
    required this.repository,
    required this.kind,
    required this.contextId,
    required this.onOpen,
    this.iconOnly = false,
  });

  final ConversationRepository repository;
  final String kind;
  final String contextId;
  final ValueChanged<String> onOpen;
  final bool iconOnly;

  @override
  State<ConversationContextAction> createState() =>
      _ConversationContextActionState();
}

class _ConversationContextActionState extends State<ConversationContextAction> {
  late Future<Map<String, dynamic>> _future;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant ConversationContextAction oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository ||
        oldWidget.kind != widget.kind ||
        oldWidget.contextId != widget.contextId) {
      _load();
    }
  }

  void _load() {
    _future = widget.repository.contextDecision(
      kind: widget.kind,
      id: widget.contextId,
    );
  }

  Future<void> _ensure() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final id = await widget.repository.ensureContext(
        kind: widget.kind,
        id: widget.contextId,
      );
      if (mounted) widget.onOpen(id);
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Ouverture non confirmée.')),
        );
        setState(_load);
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _openRows(List<Map<String, dynamic>> rows) {
    if (rows.length == 1) {
      final id = rows.first['id']?.toString();
      if (id != null) widget.onOpen(id);
      return;
    }
    if (rows.isEmpty) {
      _ensure();
      return;
    }
    showModalBottomSheet<void>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            for (final row in rows)
              ListTile(
                title: Text(row['title']?.toString() ?? 'Conversation'),
                onTap: () {
                  Navigator.of(sheetContext).pop();
                  final id = row['id']?.toString();
                  if (id != null) widget.onOpen(id);
                },
              ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Map<String, dynamic>>(
    future: _future,
    builder: (context, snapshot) {
      if (!snapshot.hasData) return const SizedBox.shrink();
      final rows = _contextRows(snapshot.data!);
      final canEnsure = snapshot.data!['can_ensure'] == true;
      if (rows.isEmpty && !canEnsure) return const SizedBox.shrink();
      final VoidCallback? open = _busy ? null : () => _openRows(rows);
      if (widget.iconOnly) {
        return IconButton(
          tooltip: 'Conversation de cette démarche',
          onPressed: open,
          icon: const Icon(Icons.forum_outlined),
        );
      }
      return TextButton.icon(
        onPressed: open,
        icon: const Icon(Icons.forum_outlined),
        label: Text(_busy ? 'Ouverture…' : 'Échanger'),
      );
    },
  );
}
