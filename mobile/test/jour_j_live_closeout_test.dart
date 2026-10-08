import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/navigation/deep_link_resolver.dart';
import 'package:makolo_mobile/navigation/destination.dart';

void main() {
  test('Jour J and Live ingress preserve the requested actor depth', () {
    const resolver = DeepLinkResolver();

    expect(
      resolver.resolve(
        const StructuredDestination(kind: 'occurrence_day_of', id: 'occ-1'),
      ),
      '/occurrences/occ-1/day-of',
    );
    expect(
      resolver.resolve(
        const StructuredDestination(kind: 'occurrence_live', id: 'occ-1'),
      ),
      '/occurrences/occ-1/live',
    );
    expect(
      resolver.resolve(
        const StructuredDestination(
          kind: 'space_occurrence_day_of',
          id: 'occ-2',
        ),
      ),
      '/space/occurrences/occ-2/day-of',
    );
    expect(
      resolver.resolve(
        const StructuredDestination(kind: 'space_occurrence_live', id: 'occ-2'),
      ),
      '/space/occurrences/occ-2/live',
    );
  });
}
