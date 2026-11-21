/// Pure client presentation. Input order, permissions and read facts belong
/// to the owners and are never changed by folding a chronological range.
class ConversationThreadItem<T> {
  const ConversationThreadItem({
    required this.id,
    required this.value,
    required this.keepVisible,
    this.publishedAt,
  });

  final String id;
  final T value;
  final bool keepVisible;
  final DateTime? publishedAt;
}

class ConversationThreadSegment<T> {
  const ConversationThreadSegment({
    required this.id,
    required this.items,
    required this.foldable,
    required this.expanded,
  });

  final String id;
  final List<ConversationThreadItem<T>> items;
  final bool foldable;
  final bool expanded;
}

/// Keeps expansion anchored to owner IDs, not page numbers or list offsets.
/// The caller creates one state per Profile/Conversation and discards it when
/// that scope changes. An unknown page is not an empty or completed range.
class ConversationCompressionState {
  final Set<String> _expandedIds = <String>{};

  void expand<T>(ConversationThreadSegment<T> segment) {
    _expandedIds.addAll(segment.items.map((item) => item.id));
  }

  void collapse<T>(ConversationThreadSegment<T> segment) {
    _expandedIds.removeAll(segment.items.map((item) => item.id));
  }

  void clear() => _expandedIds.clear();

  List<ConversationThreadSegment<T>> project<T>(
    Iterable<ConversationThreadItem<T>> orderedItems,
  ) {
    final result = <ConversationThreadSegment<T>>[];
    final run = <ConversationThreadItem<T>>[];
    final seen = <String>{};

    void flush() {
      if (run.isEmpty) return;
      final items = List<ConversationThreadItem<T>>.unmodifiable(run);
      result.add(
        ConversationThreadSegment<T>(
          id: 'range:${items.first.id}',
          items: items,
          foldable: items.length > 1,
          expanded:
              items.length == 1 ||
              items.any((item) => _expandedIds.contains(item.id)),
        ),
      );
      run.clear();
    }

    for (final item in orderedItems) {
      // Invalid or repeated identities cannot form reliable visual anchors.
      // A duplicated owner ID is one contribution, not a second message.
      if (item.id.isEmpty || !seen.add(item.id)) continue;
      if (item.keepVisible) {
        flush();
        result.add(
          ConversationThreadSegment<T>(
            id: 'item:${item.id}',
            items: List<ConversationThreadItem<T>>.unmodifiable([item]),
            foldable: false,
            expanded: true,
          ),
        );
      } else {
        run.add(item);
      }
    }
    flush();
    return List<ConversationThreadSegment<T>>.unmodifiable(result);
  }
}

/// Decisions use already-authorized owner facts. Unread status intentionally
/// does not make ordinary chatter mandatory. A missing interactive contract
/// stays visible rather than silently hiding a potentially necessary action.
bool conversationPointNeedsVisibility({
  required Map<String, dynamic> point,
  required String? ownerAttentionReason,
  required bool hasPendingIntent,
  required bool editing,
  required bool focused,
  String? representedSpaceId,
}) {
  if (hasPendingIntent || editing || focused) return true;
  final reason = ownerAttentionReason ?? point['attention_reason']?.toString();
  if (const {
    'respond',
    'acknowledge',
    'form',
    'resolve',
    'result',
    'upcoming',
  }.contains(reason)) {
    return true;
  }
  if (point['can_acknowledge'] == true && point['acknowledged'] != true) {
    return true;
  }
  if (point['kind'] == 'form_request') {
    final request = point['form_request'];
    if (request is Map && request['can_respond'] == true) return true;
  }
  final mode = point['response_mode']?.toString();
  final interactive = mode != null && mode != 'none';
  // Explicit null is a known owner decision. Absent fields in an older local
  // projection are not evidence that nothing needs the viewer's attention.
  if (interactive && !point.containsKey('attention_reason') && reason == null) {
    final allowed = representedSpaceId == null
        ? point['can_respond']
        : point['response_window_open'];
    if (allowed != false) return true;
  }
  return false;
}
