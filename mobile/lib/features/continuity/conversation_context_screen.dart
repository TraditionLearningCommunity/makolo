import 'package:flutter/material.dart';

import '../../design/behavior_states.dart';
import 'conversation_repository.dart';

/// Existing Conversations only. The owner decides access; no conversation is
/// created or authorized by this navigation surface.
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
  final void Function(String id) onOpen;

  @override
  State<ConversationContextScreen> createState() =>
      _ConversationContextScreenState();
}

class _ConversationContextScreenState extends State<ConversationContextScreen> {
  late Future<List<Map<String, dynamic>>> _results;
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
    _results = widget.repository.conversationsForContext(
      kind: widget.kind,
      id: widget.contextId,
    );
  }

  void _retry() => setState(_load);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Conversations')),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _results,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return MakoloErrorState(
              message: 'Impossible d’ouvrir cette conversation.',
              onRetry: _retry,
            );
          }
          if (!snapshot.hasData) {
            return const MakoloLoadingState();
          }
          final conversations = snapshot.data!;
          if (conversations.isEmpty) {
            return const MakoloEmptyState(
              title: 'Aucune conversation accessible ici',
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
}

/// Only offers a contextual entry when the owner confirms a visible existing
/// Conversation. It cannot imply a contact right or create a direct chat.
class ConversationContextAction extends StatefulWidget {
  const ConversationContextAction({
    super.key,
    required this.repository,
    required this.kind,
    required this.contextId,
    required this.onOpen,
  });

  final ConversationRepository repository;
  final String kind;
  final String contextId;
  final void Function(String id) onOpen;

  @override
  State<ConversationContextAction> createState() =>
      _ConversationContextActionState();
}

class _ConversationContextActionState extends State<ConversationContextAction> {
  late Future<List<Map<String, dynamic>>> _results;

  @override
  void initState() {
    super.initState();
    _results = _load();
  }

  @override
  void didUpdateWidget(covariant ConversationContextAction oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository ||
        oldWidget.kind != widget.kind ||
        oldWidget.contextId != widget.contextId) {
      _results = _load();
    }
  }

  Future<List<Map<String, dynamic>>> _load() =>
      widget.repository.conversationsForContext(
        kind: widget.kind,
        id: widget.contextId,
      );

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: _results,
      builder: (context, snapshot) {
        if (!snapshot.hasData || snapshot.data!.isEmpty) {
          return const SizedBox.shrink();
        }
        final conversations = snapshot.data!;
        return TextButton.icon(
          onPressed: () {
            if (conversations.length == 1) {
              final id = conversations.first['id']?.toString();
              if (id != null) widget.onOpen(id);
            } else {
              // Multiple context Conversations must be selected, not guessed.
              showModalBottomSheet<void>(
                context: context,
                builder: (sheetContext) => SafeArea(
                  child: ListView(
                    shrinkWrap: true,
                    children: [
                      for (final row in conversations)
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
          },
          icon: const Icon(Icons.forum_outlined),
          label: const Text('Échanger'),
        );
      },
    );
  }
}
