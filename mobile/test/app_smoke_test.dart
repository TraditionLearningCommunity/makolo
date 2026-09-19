import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/main.dart';

void main() {
  testWidgets('phase 0 exposes the five canonical anchors', (tester) async {
    await tester.pumpWidget(const MakoloApp());
    expect(find.text('Maintenant'), findsWidgets);
    expect(find.text('Découvrir'), findsOneWidget);
    expect(find.text('Makolo'), findsOneWidget);
    expect(find.text('En cours'), findsOneWidget);
    expect(find.text('Moi'), findsOneWidget);
  });
}
