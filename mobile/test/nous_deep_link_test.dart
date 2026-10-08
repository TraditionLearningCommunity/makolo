import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/navigation/deep_link_resolver.dart';
import 'package:makolo_mobile/navigation/destination.dart';

void main() {
  const resolver = DeepLinkResolver();

  test('Nous owner handoffs use the server-provided route', () {
    const target = StructuredDestination(
      kind: 'space_us_team',
      id: 'space-x',
      link: '/space/space-x/us/team',
    );

    expect(resolver.resolve(target), '/space/space-x/us/team');
  });

  test('unknown or linkless Nous depths are refused', () {
    expect(
      resolver.resolve(
        const StructuredDestination(kind: 'space_us_settings', id: 'space-x'),
      ),
      isNull,
    );
    expect(
      resolver.resolve(
        const StructuredDestination(kind: 'space_us_team', id: 'space-x'),
      ),
      isNull,
    );
  });
}
