import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/data/local/profile_store.dart';
import 'package:makolo_mobile/features/continuity/objective_organizer_data.dart';

StoredProjection page({
  required DateTime received,
  required int offset,
  required List<Map<String, dynamic>> entries,
  bool hasMore = false,
  String actor = 'current',
}) => StoredProjection(
  kind: 'objective.organizer.collection',
  schemaVersion: 1,
  receivedAt: received,
  payload: {
    'actor': {'type': 'profile', 'id': actor},
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
}
