import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/mark/mark_dictation_capture.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'missing system recognizer never pretends that dictation worked',
    (tester) async {
      const channel = MethodChannel('makolo/test_dictation_unavailable');
      final messenger =
          TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
      messenger.setMockMethodCallHandler(channel, (call) async {
        if (call.method == 'available') return false;
        return null;
      });
      addTearDown(() => messenger.setMockMethodCallHandler(channel, null));
      String? suppliedText;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkDictationCapture(
              channel: channel,
              onText: (text) => suppliedText = text,
              onClose: () {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.textContaining('La dictée n’est pas disponible ici'),
        findsOneWidget,
      );
      expect(find.text('Commencer'), findsOneWidget);
      expect(suppliedText, isNull);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
