import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/features/mark/mark_navigation.dart';
import 'package:makolo_mobile/features/mark/mark_repository.dart';

void main() {
  test('known owner handoffs use Flutter routes, never owner API links', () {
    const result = MarkResult(
      state: 'resolved',
      handoff: {'owner': 'access', 'surface': 'access_detail'},
      links: {'detail': '/api/v1/me/accesses/private-identity/'},
      raw: {
        'result': {'kind': 'access', 'id': 'access-id'},
      },
    );
    expect(
      markHandoffRoute(result, const PersonalActorContext()),
      '/accesses/access-id',
    );
  });

  test('personal search retains its text in the owner discovery route', () {
    const result = MarkResult(
      state: 'resolved',
      handoff: {'owner': 'discovery', 'surface': 'discover'},
      raw: {
        'result': {'kind': 'discovery_search', 'query': 'concert à Kinshasa'},
      },
    );
    final path = markHandoffRoute(result, const PersonalActorContext());
    final uri = Uri.parse(path!);
    expect(uri.path, '/discover/search');
    expect(uri.queryParameters['q'], 'concert à Kinshasa');
  });

  test('an unresolved request cannot navigate as a confirmed owner result', () {
    const result = MarkResult(
      state: 'needs_confirmation',
      handoff: {'owner': 'access', 'surface': 'access_detail'},
      raw: {
        'result': {'kind': 'access', 'id': 'access-id'},
      },
    );
    expect(markHandoffRoute(result, const PersonalActorContext()), isNull);
  });

  test('Space team handoff never becomes a personal destination', () {
    const result = MarkResult(
      state: 'resolved',
      handoff: {'owner': 'organizations', 'surface': 'team'},
    );
    final space = SpaceActorContext(
      space: SpaceActorIdentity(id: 'space-id', slug: 'space-slug'),
    );
    expect(markHandoffRoute(result, space), '/space/us');
    expect(markHandoffRoute(result, const PersonalActorContext()), isNull);
  });

  test('Space Jour J and Scanner use Space routes only', () {
    final space = SpaceActorContext(
      space: SpaceActorIdentity(id: 'space-id', slug: 'space-slug'),
    );
    const dayOf = MarkResult(
      state: 'resolved',
      handoff: {'owner': 'operations', 'surface': 'day_of'},
      raw: {
        'result': {
          'identity': {'id': 'occurrence-id'},
        },
      },
    );
    const scanner = MarkResult(
      state: 'resolved',
      handoff: {'owner': 'scanner', 'surface': 'occurrence_context'},
      raw: {
        'result': {
          'identity': {'id': 'occurrence-id'},
        },
      },
    );
    expect(
      markHandoffRoute(dayOf, space),
      '/space/occurrences/occurrence-id/day-of',
    );
    expect(
      markHandoffRoute(scanner, space),
      '/space/occurrences/occurrence-id/scanner',
    );
    expect(markHandoffRoute(scanner, const PersonalActorContext()), isNull);
  });

  test('Space cannot open a destination without a verified occurrence', () {
    final actor = SpaceActorContext(
      space: SpaceActorIdentity(id: 'space-id', slug: 'space-slug'),
    );
    const result = MarkResult(
      state: 'resolved',
      handoff: {'owner': 'operations', 'surface': 'day_of'},
      raw: {
        'result': {'reason': 'missing_occurrence'},
      },
    );
    expect(markHandoffRoute(result, actor), isNull);
  });

  test('clarification selection excludes unknown or incomplete targets', () {
    expect(
      markClarificationSelection({'kind': 'journey', 'id': 'journey-id'}),
      {'kind': 'journey', 'id': 'journey-id'},
    );
    expect(
      markClarificationSelection({'kind': 'permission', 'id': 'injected'}),
      isNull,
    );
    expect(
      markClarificationSelection({'kind': 'discovery_item', 'id': 'item-id'}),
      isNull,
    );
    expect(
      markClarificationSelection({
        'kind': 'discovery_item',
        'id': 'item-id',
        'family': 'activity',
      }),
      {'kind': 'discovery_item', 'id': 'item-id', 'family': 'activity'},
    );
  });
}
