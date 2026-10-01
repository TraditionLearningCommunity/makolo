import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/environment.dart';
import 'package:makolo_mobile/platform/maps/makolo_map_view.dart';

void main() {
  const viewport = MapViewport(center: MapCoordinate(-11.66, 27.47));

  testWidgets('disabled maps expose an explicit fallback state', (
    tester,
  ) async {
    await tester.pumpWidget(
      Directionality(
        textDirection: TextDirection.ltr,
        child: ConfiguredMakoloMapView(
          config: const MakoloMapsConfig(enabled: false, style: null),
          initialViewport: viewport,
          fallbackBuilder: (_, state, _) => Text(state.name),
        ),
      ),
    );

    expect(find.text('disabled'), findsOneWidget);
  });

  testWidgets('enabled maps without a style fail recoverably', (tester) async {
    var retries = 0;
    await tester.pumpWidget(
      Directionality(
        textDirection: TextDirection.ltr,
        child: ConfiguredMakoloMapView(
          config: const MakoloMapsConfig(enabled: true, style: null),
          initialViewport: viewport,
          fallbackBuilder: (_, state, retry) {
            return GestureDetector(
              onTap: () {
                retries += 1;
                retry();
              },
              child: Text(state.name),
            );
          },
        ),
      ),
    );

    expect(find.text('error'), findsOneWidget);
    await tester.tap(find.text('error'));
    await tester.pump();
    expect(retries, 1);
    expect(find.text('error'), findsOneWidget);
  });
}
