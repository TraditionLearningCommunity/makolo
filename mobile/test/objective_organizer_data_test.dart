import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/objective_organizer_data.dart';

StoredProjection page({
  required DateTime received,
  required int offset,
  required List<Map<String, dynamic>> entries,
  bool hasMore = false,
  String actor = 'current',
  String? spaceSlug,
}) => StoredProjection(
  kind: 'objective.organizer.collection',
  schemaVersion: 1,
  receivedAt: received,
  payload: {
    'actor': {'type': 'profile', 'id': actor},
    'actor_context': spaceSlug == null
        ? {'kind': 'personal'}
        : {
            'kind': 'space',
            'space': {'slug': spaceSlug},
          },
    'items': entries,
    'page': {
      'offset': offset,
      'limit': 50,
      'next_offset': offset + 50,
      'has_more': hasMore,
    },
  },
);

Map<String, dynamic> item(String kind, String id, {String? parent}) => {
  'kind': kind,
  'id': id,
  'title': '$kind $id',
  'state': 'active',
  'relation': 'mine',
  if (kind == 'dossier') 'project_id': parent,
  if (kind == 'journey') 'dossier_ids': parent == null ? [] : [parent],
};

void main() {
  final t0 = DateTime.utc(2026, 11, 8, 8);
  final t1 = DateTime.utc(2026, 11, 8, 9);

  test('a current organizer first page can be empty and still acquired', () {
    final state = OrganizerPage.read([
      page(received: t0, offset: 0, entries: []),
    ], 'current');
    expect(state.hasFirst, isTrue);
    expect(state.entries, isEmpty);
    expect(state.hasMore, isFalse);
  });

  test(
    'mixed canonical identities and parent references survive local read',
    () {
      final state = OrganizerPage.read([
        page(
          received: t0,
          offset: 0,
          entries: [
            item('project', 'p'),
            item('dossier', 'd', parent: 'p'),
            item('journey', 'j', parent: 'd'),
          ],
        ),
      ], 'current');
      expect(state.entries.map((e) => e.kind).toList(), [
        'project',
        'dossier',
        'journey',
      ]);
      expect(state.entries[1].projectId, 'p');
      expect(state.entries[2].dossierIds, ['d']);
    },
  );

  test(
    'older continuation cannot restore removed authorized relationships',
    () {
      final first = page(
        received: t1,
        offset: 0,
        hasMore: true,
        entries: [item('project', 'new')],
      );
      final previous = page(
        received: t0,
        offset: 50,
        entries: [item('dossier', 'old')],
      );
      final state = OrganizerPage.read([previous, first], 'current');
      expect(state.entries.map((e) => e.id).toList(), ['new']);
      expect(state.hasMore, isTrue);
      expect(state.nextOffset, 50);
    },
  );

  test('contiguous pages from same acquisition are combined', () {
    final first = page(
      received: t0,
      offset: 0,
      hasMore: true,
      entries: [item('project', 'p')],
    );
    final second = page(
      received: t1,
      offset: 50,
      entries: [item('dossier', 'd')],
    );
    final state = OrganizerPage.read([second, first], 'current');
    expect(state.entries.map((e) => e.id).toList(), ['p', 'd']);
    expect(state.hasMore, isFalse);
  });

  test('Space organizer windows cannot mix the Profile or other Spaces', () {
    final personal = page(
      received: t0,
      offset: 0,
      entries: [item('dossier', 'personal')],
    );
    final firstA = page(
      received: t0,
      offset: 0,
      hasMore: true,
      spaceSlug: 'space-a',
      entries: [item('project', 'a')],
    );
    final secondA = page(
      received: t1,
      offset: 50,
      spaceSlug: 'space-a',
      entries: [item('dossier', 'a-dossier', parent: 'a')],
    );
    final firstB = page(
      received: t1,
      offset: 0,
      spaceSlug: 'space-b',
      entries: [item('project', 'b')],
    );
    final all = [firstB, secondA, personal, firstA];
    final mine = OrganizerPage.read(all, 'current');
    final a = OrganizerPage.read(all, 'current', spaceSlug: 'space-a');
    final b = OrganizerPage.read(all, 'current', spaceSlug: 'space-b');
    expect(mine.entries.map((e) => e.id), ['personal']);
    expect(a.entries.map((e) => e.id), ['a', 'a-dossier']);
    expect(a.entries.last.projectId, 'a');
    expect(b.entries.map((e) => e.id), ['b']);
    expect(a.hasFirst, isTrue);
    expect(b.hasMore, isFalse);
  });

  test('Another Profile cannot enter an authorized Space window', () {
    final other = page(
      received: t0,
      offset: 0,
      entries: [item('dossier', 'secret')],
      actor: 'other',
      spaceSlug: 'space-a',
    );
    final scoped = OrganizerPage.read(
      [other], 'current', spaceSlug: 'space-a',
    );
    expect(scoped.hasFirst, isFalse);
    expect(scoped.entries, isEmpty);
  });

  test('another Profile cannot enter this organizer collection', () {
    final other = page(
      received: t0,
      offset: 0,
      entries: [item('project', 'private')],
      actor: 'other',
    );
    final state = OrganizerPage.read([other], 'current');
    expect(state.hasFirst, isFalse);
    expect(state.entries, isEmpty);
  });
  test('large explorer graph renders each shared Journey only once', () {
    final raw = <Map<String, dynamic>>[];
    for (var p = 0; p < 6; p++) {
      raw.add(item('project', 'p$p'));
      for (var d = 0; d < 4; d++) {
        raw.add(item('dossier', 'd$p-$d', parent: 'p$p'));
      }
    }
    raw.add(item('dossier', 'independent'));
    raw.add({
      ...item('journey', 'shared'),
      'dossier_ids': ['d0-0', 'd0-1', 'd1-0'],
    });
    raw.add(item('journey', 'ordinary', parent: 'd2-0'));
    final entries = raw.map(OrganizerEntry.fromMap).toList();
    final hierarchy = OrganizerHierarchy(entries);
    final visited = <String>[];
    void walk(OrganizerEntry node) {
      visited.add(node.key);
      for (final child in hierarchy.childrenOf(node)) {
        walk(child);
      }
    }

    for (final root in hierarchy.roots) {
      walk(root);
    }
    expect(visited.length, entries.length);
    expect(visited.toSet().length, entries.length);
    expect(
      hierarchy.childrenOf(hierarchy.byKey['dossier:d0-0']!).map((e) => e.id),
      contains('shared'),
    );
    expect(
      hierarchy.childrenOf(hierarchy.byKey['dossier:d0-1']!).map((e) => e.id),
      isNot(contains('shared')),
    );
    expect(
      hierarchy.additionalSharedLinks(hierarchy.byKey['dossier:d0-1']!),
      1,
    );
    expect(
      hierarchy.additionalSharedLinks(hierarchy.byKey['dossier:d1-0']!),
      1,
    );
    expect(hierarchy.roots.map((e) => e.key), contains('dossier:independent'));
    expect(entries.singleWhere((e) => e.id == 'shared').dossierIds, [
      'd0-0',
      'd0-1',
      'd1-0',
    ]);
  });

  test('empty Dossier stays present without fabricated Journey children', () {
    final project = OrganizerEntry.fromMap(item('project', 'p'));
    final dossier = OrganizerEntry.fromMap(item('dossier', 'd', parent: 'p'));
    final tree = OrganizerHierarchy([project, dossier]);
    expect(tree.childrenOf(project).map((row) => row.id), ['d']);
    expect(tree.childrenOf(dossier), isEmpty);
    expect(tree.roots.map((row) => row.key), ['project:p']);
  });

  test('missing parents are roots but are not reclassified independent', () {
    final dossier = OrganizerEntry.fromMap(
      item('dossier', 'd', parent: 'project-not-loaded'),
    );
    final journey = OrganizerEntry.fromMap({
      ...item('journey', 'j'),
      'dossier_ids': ['dossier-not-loaded'],
    });
    final hierarchy = OrganizerHierarchy([dossier, journey]);
    expect(
      hierarchy.roots.map((e) => e.key),
      containsAll(['dossier:d', 'journey:j']),
    );
    expect(dossier.isIndependent, isFalse);
    expect(journey.isIndependent, isFalse);
  });

  test('count labels are grammatical and never invent a total', () {
    final projects = [OrganizerEntry.fromMap(item('project', 'p'))];
    final journeys = [
      OrganizerEntry.fromMap(item('journey', 'a')),
      OrganizerEntry.fromMap(item('journey', 'b')),
    ];
    expect(organizerCountLabel(projects), '1 projet');
    expect(organizerCountLabel(journeys), '2 démarches');
    expect(organizerCountLabel([...projects, ...journeys]), '3 éléments');
    expect(organizerCountLabel(journeys, filtered: true), '2 résultats');
    expect(organizerCountLabel(projects, filtered: true), '1 résultat');
    expect(
      organizerCountLabel(journeys, partial: true),
      '2 démarches chargées',
    );
    expect(organizerCountLabel([], filtered: true), '0 résultats');
    expect(
      organizerSharedLinksLabel(1),
      '1 démarche également liée, présentée dans un autre dossier',
    );
    expect(
      organizerSharedLinksLabel(2),
      '2 démarches également liées, présentées dans un autre dossier',
    );
    expect(
      organizerMoreChildrenLabel(projects.first, 1),
      'Et 1 autre dossier chargé',
    );
    expect(
      organizerMoreChildrenLabel(projects.first, 3),
      'Et 3 autres dossiers chargés',
    );
    expect(
      organizerMoreChildrenLabel(
        OrganizerEntry.fromMap(item('dossier', 'd')),
        2,
      ),
      'Et 2 autres démarches chargées',
    );
  });
}
