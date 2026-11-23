import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/presentation/search/load_more_on_scroll.dart';

void main() {
  Future<void> pumpList(
    WidgetTester tester, {
    required bool hasMore,
    required bool loading,
    required VoidCallback loadMore,
  }) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: LoadMoreOnScroll(
            hasMore: hasMore,
            loading: loading,
            loadMore: loadMore,
            child: ListView(
              children: [
                for (var i = 0; i < 30; i++)
                  SizedBox(height: 80, child: Text('Élément $i')),
              ],
            ),
          ),
        ),
      ),
    );
  }

  testWidgets('does not page when no further page is available', (
    tester,
  ) async {
    var calls = 0;
    await pumpList(
      tester,
      hasMore: false,
      loading: false,
      loadMore: () => calls++,
    );
    await tester.drag(find.byType(ListView), const Offset(0, -2200));
    await tester.pumpAndSettle();
    expect(calls, 0);
  });

  testWidgets('does not page while another server page is loading', (
    tester,
  ) async {
    var calls = 0;
    await pumpList(
      tester,
      hasMore: true,
      loading: true,
      loadMore: () => calls++,
    );
    await tester.drag(find.byType(ListView), const Offset(0, -2200));
    await tester.pumpAndSettle();
    expect(calls, 0);
  });

  testWidgets('requests the next page when scrolling close to the end', (
    tester,
  ) async {
    var calls = 0;
    await pumpList(
      tester,
      hasMore: true,
      loading: false,
      loadMore: () => calls++,
    );
    await tester.drag(find.byType(ListView), const Offset(0, -2200));
    await tester.pumpAndSettle();
    expect(calls, greaterThan(0));
  });
}
