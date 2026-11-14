import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/continuity/conversation_compression.dart';

void main() {
  ConversationThreadItem<int> item(int id, {bool visible = false}) =>
      ConversationThreadItem(
        id: 'point-$id',
        value: id,
        keepVisible: visible,
      );

  test('900 chronological contributions fold around only relevant Points', () {
    final state = ConversationCompressionState();
    final source = [
      for (var i = 1; i <= 900; i++)
        item(i, visible: {61, 62, 201}.contains(i)),
    ];
    final result = state.project(source);
    expect(
      result.map((segment) => segment.items.length).toList(),
      [60, 1, 1, 138, 1, 699],
    );
    expect(
      result.expand((segment) => segment.items.map((item) => item.id)).toList(),
      source.map((item) => item.id).toList(),
    );
    expect(result.where((segment) => !segment.foldable).length, 3);
  });

  test('open segment survives prepend and does not mutate unread metadata', () {
    final state = ConversationCompressionState();
    final source = [item(2), item(3), item(4, visible: true), item(5), item(6)];
    var result = state.project(source);
    state.expand(result.first);
    result = state.project([item(1), ...source]);
    expect(result.first.expanded, isTrue);
    expect(result[2].expanded, isFalse);
    state.collapse(result.first);
    expect(state.project([item(1), ...source]).first.expanded, isFalse);
    expect(source.first.keepVisible, isFalse);
  });

  test('only the same authorized owner facts determine visibility', () {
    final owner = <String, dynamic>{
      'kind': 'question',
      'response_mode': 'free_text',
      'attention_reason': 'respond',
      'can_respond': true,
      'response_window_open': true,
    };
    expect(
      conversationPointNeedsVisibility(
        point: owner,
        ownerAttentionReason: 'respond',
        hasPendingIntent: false,
        editing: false,
        focused: false,
      ),
      isTrue,
    );
    expect(
      conversationPointNeedsVisibility(
        point: {
          'kind': 'information',
          'response_mode': 'none',
          'attention_reason': 'information',
          'unread': true,
        },
        ownerAttentionReason: 'information',
        hasPendingIntent: false,
        editing: false,
        focused: false,
      ),
      isFalse,
    );
    expect(
      conversationPointNeedsVisibility(
        point: owner,
        ownerAttentionReason: null,
        hasPendingIntent: true,
        editing: false,
        focused: false,
      ),
      isTrue,
    );
  });

  test('separate Profile scopes must clear local expansion', () {
    final state = ConversationCompressionState();
    final source = [item(1), item(2), item(3)];
    state.expand(state.project(source).first);
    expect(state.project(source).first.expanded, isTrue);
    state.clear();
    expect(state.project(source).first.expanded, isFalse);
  });
}
