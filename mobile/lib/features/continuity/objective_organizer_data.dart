import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';

enum OrganizerMode { cards, list, explorer }
enum OrganizerSort { name, created, updated, deadline, start }

class OrganizerEntry {
  const OrganizerEntry({
    required this.kind, required this.id, required this.title,
    required this.state, required this.relation,
    this.description = '', this.space, this.projectId,
    this.dossierIds = const [], this.created, this.updated,
    this.deadline, this.start,
  });

  final String kind, id, title, state, relation, description;
  final String? space, projectId;
  final List<String> dossierIds;
  final DateTime? created, updated, deadline, start;

  String get key => '$kind:$id';
  String get kindLabel => switch (kind) {
    'project' => 'Projet',
    'dossier' => 'Dossier',
    _ => 'Démarche',
  };
  IconData get icon => switch (kind) {
    'project' => Icons.folder_special_outlined,
    'dossier' => Icons.folder_outlined,
    _ => Icons.route_outlined,
  };
  bool get isIndependent => kind == 'project' ||
      (kind == 'dossier' && projectId == null) ||
      (kind == 'journey' && dossierIds.isEmpty);

  String get humanState => switch (state) {
    'draft' => 'En préparation',
    'active' || 'in_progress' => 'En cours',
    'fulfilled' || 'completed' => 'Terminé',
    'cancelled' => 'Annulé',
    'archived' => 'Archivé',
    'expired' => 'Expirée',
    'pending_approval' => 'Approbation attendue',
    'pending_payment' => 'Paiement attendu',
    'submitted' => 'Soumise',
    'rejected' => 'Refusée',
    'confirmed' => 'Confirmée',
    'approved' => 'Approuvée',
    _ => 'État indisponible',
  };

  DateTime? dateFor(OrganizerSort criterion) => switch (criterion) {
    OrganizerSort.created => created,
    OrganizerSort.updated => updated,
    OrganizerSort.deadline => deadline,
    OrganizerSort.start => start,
    OrganizerSort.name => null,
  };

  String? get displayDate {
    final value = deadline ?? start;
    if (value == null) return null;
    final stamp = '${value.day.toString().padLeft(2, '0')}/'
        '${value.month.toString().padLeft(2, '0')}/${value.year}';
    return '${deadline != null ? 'Échéance' : 'Début'} : $stamp';
  }

  static DateTime? _date(Object? value) =>
      value == null ? null : DateTime.tryParse(value.toString());

  factory OrganizerEntry.fromMap(Map row) {
    final space = row['space'];
    final ids = row['dossier_ids'];
    return OrganizerEntry(
      kind: row['kind'].toString(),
      id: row['id'].toString(),
      title: row['title'].toString(),
      description: row['description']?.toString() ?? '',
      state: row['state']?.toString() ?? '',
      relation: row['relation']?.toString() ?? '',
      space: space is Map ? space['name']?.toString() : null,
      projectId: row['project_id']?.toString(),
      dossierIds: ids is List ? ids.map((id) => id.toString()).toList() : const [],
      created: _date(row['created_at']),
      updated: _date(row['updated_at']),
      deadline: _date(row['deadline'] ?? row['ends_on']),
      start: _date(row['starts_on'] ?? row['started_at']),
    );
  }
}

/// Local pages are identity-checked and only consumed while contiguous.
class OrganizerPage {
  const OrganizerPage({
    required this.entries, required this.hasFirst,
    required this.hasMore, required this.nextOffset,
  });
  final List<OrganizerEntry> entries;
  final bool hasFirst, hasMore;
  final int nextOffset;

  factory OrganizerPage.read(List<StoredProjection> projections, String profileId) {
    final pages = projections.toList()..sort((a, b) => _offset(a).compareTo(_offset(b)));
    final result = <OrganizerEntry>[];
    final seen = <String>{};
    var expected = 0;
    var hasFirst = false;
    var hasMore = false;
    for (final snapshot in pages) {
      final value = snapshot.payload;
      final actor = value['actor'];
      final pagination = value['page'];
      final entries = value['items'];
      if (actor is! Map || actor['type'] != 'profile' ||
          actor['id']?.toString() != profileId ||
          pagination is! Map || pagination['offset'] != expected ||
          entries is! List) break;
      hasFirst = true;
      for (final raw in entries) {
        if (raw is! Map ||
            !{'project', 'dossier', 'journey'}.contains(raw['kind']) ||
            raw['id'] is! String || raw['title'] is! String) continue;
        final item = OrganizerEntry.fromMap(raw);
        if (seen.add(item.key)) result.add(item);
      }
      hasMore = pagination['has_more'] == true;
      final nextOffset = pagination['next_offset'];
      if (nextOffset is! int || nextOffset <= expected) break;
      expected = nextOffset;
      if (!hasMore) break;
    }
    return OrganizerPage(
      entries: result, hasFirst: hasFirst,
      hasMore: hasMore, nextOffset: expected,
    );
  }

  static int _offset(StoredProjection value) {
    final page = value.payload['page'];
    return page is Map && page['offset'] is int ? page['offset'] as int : 0;
  }
}
