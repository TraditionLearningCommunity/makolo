import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';

enum OrganizerMode { cards, list, explorer }

enum OrganizerSort { name, created, updated, deadline, start, completed }

class OrganizerEntry {
  const OrganizerEntry({
    required this.kind,
    required this.id,
    required this.title,
    required this.state,
    required this.relation,
    this.description = '',
    this.space,
    this.projectId,
    this.dossierIds = const [],
    this.created,
    this.updated,
    this.deadline,
    this.start,
    this.completed,
  });

  final String kind, id, title, state, relation, description;
  final String? space, projectId;
  final List<String> dossierIds;
  final DateTime? created, updated, deadline, start, completed;

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
  bool get isIndependent =>
      kind == 'project' ||
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
    OrganizerSort.completed => completed,
    OrganizerSort.name => null,
  };

  String? get displayDate {
    final value = deadline ?? start;
    if (value == null) return null;
    final stamp =
        '${value.day.toString().padLeft(2, '0')}/'
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
      dossierIds: ids is List
          ? ids.map((id) => id.toString()).toList()
          : const [],
      created: _date(row['created_at']),
      updated: _date(row['updated_at']),
      deadline: _date(row['deadline'] ?? row['ends_on']),
      start: _date(row['starts_on'] ?? row['started_at']),
      completed: _date(row['fulfilled_at']),
    );
  }
}

/// Presentation-only tree for the locally acquired, viewer-authorized items.
///
/// A Journey may belong to several Dossiers. Show the Journey once under the
/// first acquired parent (stable by id); keep all canonical dossierIds intact
/// and surface the other associations in the UI instead of cloning the node.
/// Missing parents remain unknown, never inferred to be independent.
class OrganizerHierarchy {
  OrganizerHierarchy(Iterable<OrganizerEntry> entries) {
    final items = entries.toList();
    _byKey = {for (final item in items) item.key: item};
    _projects = items.where((e) => e.kind == 'project').toList();
    _dossiers = items.where((e) => e.kind == 'dossier').toList();
    _journeys = items.where((e) => e.kind == 'journey').toList();
    _primaryDossier = {
      for (final journey in _journeys)
        journey.id: _acquiredParents(journey).isEmpty
            ? null
            : _acquiredParents(journey).first,
    };
  }

  late final Map<String, OrganizerEntry> _byKey;
  late final List<OrganizerEntry> _projects, _dossiers, _journeys;
  late final Map<String, String?> _primaryDossier;

  Map<String, OrganizerEntry> get byKey => _byKey;

  List<String> _acquiredParents(OrganizerEntry journey) =>
      journey.dossierIds
          .toSet()
          .where((id) => _byKey.containsKey('dossier:$id'))
          .toList()
        ..sort();

  List<OrganizerEntry> childrenOf(OrganizerEntry parent) =>
      switch (parent.kind) {
        'project' => _dossiers.where((d) => d.projectId == parent.id).toList(),
        'dossier' =>
          _journeys.where((j) => _primaryDossier[j.id] == parent.id).toList(),
        _ => <OrganizerEntry>[],
      };

  List<OrganizerEntry> get roots => [
    ..._projects,
    ..._dossiers.where(
      (d) =>
          d.projectId == null || !_byKey.containsKey('project:${d.projectId}'),
    ),
    ..._journeys.where((j) => _primaryDossier[j.id] == null),
  ];

  /// Other locally acquired Dossier links that are represented elsewhere.
  int additionalSharedLinks(OrganizerEntry dossier) => _journeys
      .where(
        (j) =>
            j.dossierIds.contains(dossier.id) &&
            _primaryDossier[j.id] != dossier.id &&
            _primaryDossier[j.id] != null,
      )
      .length;

  /// Shared relationships may include authorized parents not yet acquired.
  int get extraLinks => _journeys.fold<int>(
    0,
    (count, journey) =>
        count +
        (journey.dossierIds.toSet().length > 1
            ? journey.dossierIds.toSet().length - 1
            : 0),
  );
}

/// Counts only the loaded collection: never imply that a partial window is
/// the authoritative total of all Projects/Dossiers/Journeys.
String organizerCountLabel(
  Iterable<OrganizerEntry> entries, {
  bool filtered = false,
  bool partial = false,
}) {
  final values = entries.toList();
  final count = values.length;
  final kinds = values.map((e) => e.kind).toSet();
  final type = filtered
      ? count == 1
            ? 'résultat'
            : 'résultats'
      : kinds.length == 1
      ? switch (kinds.first) {
          'project' => count == 1 ? 'projet' : 'projets',
          'dossier' => count == 1 ? 'dossier' : 'dossiers',
          _ => count == 1 ? 'démarche' : 'démarches',
        }
      : count == 1
      ? 'élément'
      : 'éléments';
  final loaded = partial
      ? kinds.length == 1 && kinds.first == 'journey' && !filtered
            ? count == 1
                  ? ' chargée'
                  : ' chargées'
            : count == 1
            ? ' chargé'
            : ' chargés'
      : '';
  return '$count $type$loaded';
}

/// Shared links in the explorer are references, never duplicate nodes.
String organizerSharedLinksLabel(int count) => count == 1
    ? '1 démarche également liée, présentée dans un autre dossier'
    : '$count démarches également liées, présentées dans un autre dossier';

/// Describe only the acquired direct children, with grammatical counts.
String organizerMoreChildrenLabel(OrganizerEntry parent, int count) {
  if (parent.kind == 'project') {
    return count == 1
        ? 'Et 1 autre dossier chargé'
        : 'Et $count autres dossiers chargés';
  }
  return count == 1
      ? 'Et 1 autre démarche chargée'
      : 'Et $count autres démarches chargées';
}

/// Local pages are identity-checked and only consumed while contiguous.
class OrganizerPage {
  const OrganizerPage({
    required this.entries,
    required this.hasFirst,
    required this.hasMore,
    required this.nextOffset,
  });
  final List<OrganizerEntry> entries;
  final bool hasFirst, hasMore;
  final int nextOffset;

  factory OrganizerPage.read(
    List<StoredProjection> projections,
    String profileId, {
    String? spaceSlug,
  }) {
    // The Profile owns the database, not the presentation scope.
    // Do not merge personal and Space windows into one apparent hierarchy.
    final pages = projections.where((snapshot) {
      final lens = snapshot.payload['actor_context'];
      if (spaceSlug == null) {
        return lens is! Map || lens['kind'] != 'space';
      }
      if (lens is! Map || lens['kind'] != 'space') return false;
      final space = lens['space'];
      return space is Map && space['slug'] == spaceSlug;
    }).toList()..sort((a, b) => _offset(a).compareTo(_offset(b)));
    final result = <OrganizerEntry>[];
    final seen = <String>{};
    var expected = 0;
    var hasFirst = false;
    var hasMore = false;
    DateTime? firstReceivedAt;
    for (final snapshot in pages) {
      // A refreshed first page is a new authorized view. Never append
      // continuation pages received before that view: old Dossier/Project
      // relationships or permissions may no longer be visible.
      if (firstReceivedAt != null &&
          snapshot.receivedAt.isBefore(firstReceivedAt)) {
        break;
      }
      final value = snapshot.payload;
      final actor = value['actor'];
      final pagination = value['page'];
      final entries = value['items'];
      if (actor is! Map ||
          actor['type'] != 'profile' ||
          actor['id']?.toString() != profileId ||
          pagination is! Map ||
          pagination['offset'] != expected ||
          entries is! List) {
        break;
      }
      hasFirst = true;
      firstReceivedAt ??= snapshot.receivedAt;
      for (final raw in entries) {
        if (raw is! Map ||
            !{'project', 'dossier', 'journey'}.contains(raw['kind']) ||
            raw['id'] is! String ||
            raw['title'] is! String) {
          continue;
        }
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
      entries: result,
      hasFirst: hasFirst,
      hasMore: hasMore,
      nextOffset: expected,
    );
  }

  static int _offset(StoredProjection value) {
    final page = value.payload['page'];
    return page is Map && page['offset'] is int ? page['offset'] as int : 0;
  }
}
