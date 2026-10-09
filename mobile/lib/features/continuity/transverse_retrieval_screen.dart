import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../features/space/space_repository.dart';
import '../../network/api_error.dart';

/// One secondary retrieval surface: Search for an active actor or Space History.
/// Search responses stay ephemeral; offline evidence comes only from owner snapshots.
class TransverseRetrievalScreen extends StatefulWidget {
  const TransverseRetrievalScreen({
    super.key,
    required this.runtime,
    this.spaceActor,
    this.history = false,
    this.initialQuery = '',
  });

  final AppRuntime runtime;
  final SpaceActorContext? spaceActor;
  final bool history;
  final String initialQuery;

  @override
  State<TransverseRetrievalScreen> createState() =>
      _TransverseRetrievalScreenState();
}

class _TransverseRetrievalScreenState extends State<TransverseRetrievalScreen> {
  late final TextEditingController _query;
  List<Map<String, dynamic>> _local = [];
  List<Map<String, dynamic>> _remote = [];
  bool _loading = false;
  bool _failed = false;
  bool _revoked = false;
  int _offset = 0;
  bool _more = false;
  int _version = 0;
  int? _selected;
  String _historyKind = 'all';
  DateTime? _startDate;
  DateTime? _endDate;

  bool get _isSpace => widget.spaceActor != null;
  bool get _actorValid =>
      !_isSpace || widget.runtime.actorContext?.value == widget.spaceActor;
  String get _title => widget.history ? 'Historique' : 'Recherche';

  @override
  void initState() {
    super.initState();
    _query = TextEditingController(text: widget.initialQuery);
    widget.runtime.actorContext?.addListener(_onActorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      unawaited(_submit());
    });
  }

  @override
  void didUpdateWidget(covariant TransverseRetrievalScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(_onActorChanged);
      widget.runtime.actorContext?.addListener(_onActorChanged);
    }
    if (oldWidget.runtime.store != widget.runtime.store ||
        oldWidget.spaceActor != widget.spaceActor ||
        oldWidget.runtime.session?.profileId !=
            widget.runtime.session?.profileId) {
      _version++;
      _local = [];
      _remote = [];
      _more = false;
      _offset = 0;
      _selected = null;
      _failed = false;
      _revoked = false;
      _query.text = widget.initialQuery;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(_submit());
      });
    }
  }

  void _onActorChanged() {
    _version++;
    if (!mounted) return;
    setState(() {
      _local = [];
      _remote = [];
      _revoked = !_actorValid;
      _selected = null;
    });
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    _query.dispose();
    super.dispose();
  }

  String _path(String query, int offset) {
    final actor = widget.spaceActor;
    final base = actor == null
        ? 'api/v1/me/search/'
        : 'api/v1/organizations/workspaces/'
              '${Uri.encodeComponent(actor.space.slug)}/'
              '${widget.history ? 'history' : 'search'}/';
    return Uri(
      path: base,
      queryParameters: {
        if (query.isNotEmpty) 'q': query,
        if (widget.history && _isSpace) 'kind': _historyKind,
        if (widget.history && _startDate != null)
          'from': _dateString(_startDate!),
        if (widget.history && _endDate != null)
          'to': _dateString(_endDate!),
        'limit': '24',
        'offset': '$offset',
        if (actor != null && !actor.perspective.isAll)
          'responsibility': actor.perspective.id!,
      },
    ).toString();
  }

  String _dateString(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';

  String _spaceCachePrefix(SpaceActorContext actor) =>
      '${actor.space.id}:${SpaceSyncKeys.perspectiveKey(actor.perspective)}:';

  String _spaceCacheQueryPrefix(SpaceActorContext actor, String query) =>
      '${_spaceCachePrefix(actor)}${Uri.encodeComponent(query)}:'
      '${_historyKind}:'
      '${_startDate == null ? '-' : _dateString(_startDate!)}:'
      '${_endDate == null ? '-' : _dateString(_endDate!)}:';

  String _spaceCacheKey(SpaceActorContext actor, String query, int offset) =>
      '${_spaceCacheQueryPrefix(actor, query)}$offset';

  Future<List<Map<String, dynamic>>> _cachedRows(String query) async {
    final store = widget.runtime.store;
    if (store == null || !_actorValid) return [];
    final rows = <Map<String, dynamic>>[];
    if (!_isSpace) {
      if (widget.history) return [];
      final pages = await store.readProjections('personal.history');
      for (final page in pages) {
        final items = page.payload['items'];
        if (items is! List) continue;
        for (final value in items) {
          if (value is! Map) continue;
          final item = Map<String, dynamic>.from(value);
          final source = item['source'];
          if (source is! Map) continue;
          rows.add({
            'source': source,
            'title': item['title'],
            'human_type': 'Historique',
            'relation': item['outcome'] is Map
                ? (item['outcome'] as Map)['label']
                : null,
            'historical': true,
          });
        }
      }
      final resources = await store.readProjections('personal.me.resources');
      for (final snapshot in resources) {
        final documents = snapshot.payload['documents'];
        if (documents is! Map || documents['items'] is! List) continue;
        for (final value in documents['items'] as List) {
          if (value is! Map) continue;
          final item = Map<String, dynamic>.from(value);
          final id = item['id']?.toString();
          if (id == null) continue;
          rows.add({
            'source': {'kind': 'personal_asset', 'id': id},
            'title': item['title'],
            'human_type': 'Document',
            'relation': 'Ma ressource',
            'historical': false,
          });
        }
      }
    } else {
      final actor = widget.spaceActor!;
      if (widget.history) {
        final snapshots = await store.readProjections('space.history');
        final prefix = _spaceCacheQueryPrefix(actor, query);
        for (final page in snapshots) {
          if (!page.resourceKey.startsWith(prefix)) continue;
          final values = page.payload['items'];
          if (values is! List) continue;
          for (final value in values.whereType<Map>()) {
            final item = Map<String, dynamic>.from(value);
            final source = item['source'];
            if (source is! Map) continue;
            rows.add({
              'source': source,
              'title': item['title'],
              'human_type': 'Séance passée',
              'relation': (item['outcome'] is Map)
                  ? (item['outcome'] as Map)['label']
                  : 'Historique',
              'historical': true,
            });
          }
        }
      }
      final repository = widget.runtime.space;
      if (repository == null) return [];
      if (widget.history) {
        // Only the explicit Space History owner projection has defensible
        // historical dates. Work's completed items are not another History.
        final normalized = query.toLowerCase();
        return _deduplicate(rows.where((row) =>
          normalized.isEmpty ||
          (row['title']?.toString().toLowerCase() ?? '')
              .contains(normalized)).toList());
      }
      final source = repository.workSource(actor.space, actor.perspective);
      final state = await repository.readSource(source);
      if (state.invalidated) return [];
      final cached = await store.readProjection(
        SpaceProjectionKind.work.wireValue,
        resourceKey: SpaceSyncKeys.resourceKey(
          actor.space.id,
          perspective: actor.perspective,
        ),
      );
      final sections = cached?.payload['sections'];
      if (sections is Map) {
        for (final entry in sections.entries) {
          if (widget.history && entry.key != 'completed') continue;
          final section = entry.value;
          if (section is! Map || section['items'] is! List) continue;
          for (final value in section['items'] as List) {
            if (value is! Map) continue;
            final item = Map<String, dynamic>.from(value);
            final owner = item['source'];
            if (owner is! Map) continue;
            if (widget.history) {
              if (owner['kind'] != 'occurrence' ||
                  item['state'] != 'completed') {
                continue;
              }
            }
            rows.add({
              'source': owner,
              'title': item['title'],
              'human_type': item['kind'] ?? 'Activité',
              'relation': 'Données synchronisées',
              'historical': widget.history,
            });
          }
        }
      }
      if (!widget.history && actor.perspective.isAll) {
        final source = repository.relationshipsSource(actor.space);
        final status = await repository.readSource(source);
        if (!status.invalidated) {
          final cached = await store.readProjection(
            SpaceProjectionKind.relationships.wireValue,
            resourceKey: SpaceSyncKeys.resourceKey(actor.space.id),
          );
          final sections = cached?.payload['sections'];
          if (sections is Map) {
            for (final section in sections.values) {
              if (section is! Map || section['items'] is! List) continue;
              for (final value in section['items'] as List) {
                if (value is! Map) continue;
                final item = Map<String, dynamic>.from(value);
                final profile = item['profile'];
                final label = profile is Map ? profile['name'] : null;
                final id = item['id']?.toString();
                if (id == null) continue;
                rows.add({
                  'source': {'kind': item['kind'], 'id': id},
                  'title': label ?? item['name'] ??
                      item['label'] ?? item['owner_identity'],
                  'human_type': item['relation_type'] ?? 'Relation',
                  'relation': item['relation_type'] ?? 'Relation',
                  'historical': false,
                });
              }
            }
          }
        }
      }
    }
    if (!widget.history && query.isEmpty) return [];
    final normalized = query.toLowerCase();
    final filtered = rows.where((row) {
      final text = (row['title'] ?? '').toString().toLowerCase();
      return normalized.isEmpty || text.contains(normalized);
    });
    return _deduplicate(filtered.toList());
  }

  List<Map<String, dynamic>> _deduplicate(List<Map<String, dynamic>> rows) {
    final seen = <String>{};
    return rows.where((row) {
      final source = row['source'];
      if (source is! Map) return false;
      final key = '${source['kind']}:${source['id']}:'
          '${row['relation'] ?? ''}';
      return seen.add(key);
    }).toList();
  }

  Future<void> _submit({bool more = false}) async {
    if (!_actorValid) return;
    final query = _query.text.trim();
    final version = ++_version;
    if (!more) {
      final local = await _cachedRows(query);
      if (!mounted || version != _version || !_actorValid) return;
      setState(() {
        _local = local;
        _remote = [];
        _offset = 0;
        _more = false;
        _failed = false;
        _revoked = false;
        _selected = null;
      });
    }
    if (query.isEmpty && !widget.history) return;
    final api = widget.runtime.api;
    if (api == null) {
      if (mounted) setState(() => _failed = true);
      return;
    }
    final nextOffset = more ? _offset : 0;
    setState(() => _loading = true);
    try {
      final response = await api.get(_path(query, nextOffset));
      final json = response.jsonObject();
      final payload = _isSpace ? json : json['data'];
      if (payload is! Map) throw const FormatException('Invalid retrieval');
      if (_isSpace) {
        final actor = payload['actor_context'];
        if (actor is! Map ||
            actor['kind'] != 'space' ||
            actor['id'] != widget.spaceActor!.space.id) {
          throw const FormatException('Unexpected Space actor context');
        }
      }
      final list = payload['items'];
      final page = payload['page'];
      if (list is! List || page is! Map) {
        throw const FormatException('Invalid owner projection');
      }
      final items = list.whereType<Map>().map(
        (value) => Map<String, dynamic>.from(value),
      ).toList();
      if (!mounted || !_actorValid || version != _version) return;
      final store = widget.runtime.store;
      if (widget.history && _isSpace && store != null) {
        final actor = widget.spaceActor!;
        if (!more) {
          final previous = await store.readProjections('space.history');
          for (final page in previous) {
            if (page.resourceKey.startsWith(_spaceCachePrefix(actor))) {
              await store.deleteProjection(
                'space.history', resourceKey: page.resourceKey,
              );
            }
          }
        }
        await store.putProjection(
          kind: 'space.history',
          resourceKey: _spaceCacheKey(actor, query, nextOffset),
          schemaVersion: 1,
          payload: Map<String, dynamic>.from(payload),
        );
      }
      if (!mounted || !_actorValid || version != _version) return;
      setState(() {
        _remote = _deduplicate(more ? [..._remote, ...items] : items);
        // A current owner result replaces previously synchronized snippets.
        // Missing items after a successful fetch must not linger as visible.
        _local = [];
        _offset = nextOffset + items.length;
        _more = page['has_more'] == true && items.isNotEmpty;
        _failed = false;
      });
    } on MakoloApiError catch (error) {
      if (!mounted || version != _version) return;
      final denied = {401, 403, 404}.contains(error.statusCode);
      if (denied && _isSpace) {
        final store = widget.runtime.store;
        if (store != null) {
          final cached = await store.readProjections('space.history');
          for (final page in cached) {
            if (page.resourceKey.startsWith(
              _spaceCachePrefix(widget.spaceActor!),
            )) {
              await store.deleteProjection(
                'space.history', resourceKey: page.resourceKey,
              );
            }
          }
          final actor = widget.spaceActor!;
          await store.deleteProjection(
            SpaceProjectionKind.work.wireValue,
            resourceKey: SpaceSyncKeys.resourceKey(
              actor.space.id,
              perspective: actor.perspective,
            ),
          );
          await store.deleteProjection(
            SpaceProjectionKind.relationships.wireValue,
            resourceKey: SpaceSyncKeys.resourceKey(actor.space.id),
          );
        }
      }
      setState(() {
        _failed = true;
        if (denied) {
          _revoked = true;
          _local = [];
          _remote = [];
        }
      });
    } on Object {
      if (mounted && version == _version) setState(() => _failed = true);
    } finally {
      if (mounted && version == _version) setState(() => _loading = false);
    }
  }

  static const _spaceKinds = <String>{
    'activity', 'occurrence', 'commerce_order',
    'team_member', 'group', 'crm_contact', 'audience', 'partner',
  };

  bool _canOpen(Map<String, dynamic> item) {
    final source = item['source'];
    if (source is! Map || source['id'] == null) return false;
    final kind = source['kind']?.toString();
    if (_isSpace) return _spaceKinds.contains(kind);
    return {
      'journey', 'access', 'personal_asset', 'group', 'commerce_order',
    }.contains(kind);
  }

  void _open(Map<String, dynamic> item) {
    if (!_actorValid || !_canOpen(item)) return;
    final source = item['source'] as Map;
    final id = Uri.encodeComponent(source['id'].toString());
    final kind = source['kind'].toString();
    if (_isSpace) {
      context.push(
        '/space/${Uri.encodeComponent(widget.spaceActor!.space.slug)}'
        '/retrieval/${Uri.encodeComponent(kind)}/$id',
      );
    } else {
      final path = switch (kind) {
        'journey' => '/journeys/$id',
        'access' => '/accesses/$id',
        'personal_asset' => '/me/resources/$id',
        'group' => '/groups/$id',
        'commerce_order' => '/me/orders/$id',
        _ => null,
      };
      if (path != null) context.push(path);
    }
  }

  @override
  Widget build(BuildContext context) {
    final rows = _remote.isEmpty && (_failed || _loading)
        ? _local
        : _remote;
    final viewport = MediaQuery.sizeOf(context);
    final large = viewport.width >= 900 &&
        MediaQuery.textScalerOf(context).scale(16) < 25.6;
    final selected = _selected != null && _selected! < rows.length
        ? rows[_selected!]
        : null;
    return Scaffold(
      appBar: AppBar(title: Text(
        _isSpace ? '$_title · ${widget.spaceActor!.space.slug}' : _title,
      )),
      body: !_actorValid || _revoked
          ? const Center(child: Text(
              'Ce contexte n’est plus autorisé. Retournez à votre Espace.',
            ))
          : Row(
              children: [
                Expanded(
                  flex: 3,
                  child: ListView(
                    key: const PageStorageKey('transverse-retrieval-results'),
                    padding: const EdgeInsets.all(20),
                    children: [
                      TextField(
                        controller: _query,
                        maxLength: 120,
                        textInputAction: TextInputAction.search,
                        decoration: InputDecoration(
                          labelText: widget.history
                              ? 'Rechercher dans le passé'
                              : 'Retrouver une réalité connue',
                          suffixIcon: IconButton(
                            tooltip: 'Lancer la recherche',
                            icon: const Icon(Icons.search),
                            onPressed: () => _submit(),
                          ),
                        ),
                        onSubmitted: (_) => _submit(),
                      ),
                      if (_failed)
                        const Text(
                          'Actualisation indisponible. Les résultats locaux, '
                          's’ils existent, peuvent être incomplets.',
                        ),
                      if (_loading) const LinearProgressIndicator(),
                      if (_isSpace)
                        Text(
                          'Contexte : ${widget.spaceActor!.space.slug}. '
                          'Seules les sources autorisées et couvertes sont consultées.',
                        ),
                      if (widget.history && _isSpace) ...[
                        const SizedBox(height: 12),
                        DropdownButtonFormField<String>(
                          initialValue: _historyKind,
                          isExpanded: true,
                          decoration: const InputDecoration(
                            labelText: 'Type de passé',
                          ),
                          items: const [
                            DropdownMenuItem(value: 'all', child: Text('Tout')),
                            DropdownMenuItem(
                              value: 'occurrence', child: Text('Séances passées'),
                            ),
                            DropdownMenuItem(
                              value: 'commerce_order',
                              child: Text('Commandes annulées'),
                            ),
                          ],
                          onChanged: (value) {
                            if (value == null) return;
                            setState(() => _historyKind = value);
                            unawaited(_submit());
                          },
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            OutlinedButton(
                              onPressed: () async {
                                final date = await showDatePicker(
                                  context: context,
                                  initialDate: _startDate ?? DateTime.now(),
                                  firstDate: DateTime(2000),
                                  lastDate: DateTime.now(),
                                );
                                if (!mounted || date == null) return;
                                setState(() => _startDate = date);
                                unawaited(_submit());
                              },
                              child: Text(_startDate == null
                                  ? 'Depuis'
                                  : 'Depuis ${_dateString(_startDate!)}'),
                            ),
                            OutlinedButton(
                              onPressed: () async {
                                final date = await showDatePicker(
                                  context: context,
                                  initialDate: _endDate ?? DateTime.now(),
                                  firstDate: DateTime(2000),
                                  lastDate: DateTime.now(),
                                );
                                if (!mounted || date == null) return;
                                setState(() => _endDate = date);
                                unawaited(_submit());
                              },
                              child: Text(_endDate == null
                                  ? 'Jusqu’au'
                                  : 'Jusqu’au ${_dateString(_endDate!)}'),
                            ),
                            if (_startDate != null || _endDate != null)
                              TextButton(
                                onPressed: () {
                                  setState(() {
                                    _startDate = null;
                                    _endDate = null;
                                  });
                                  unawaited(_submit());
                                },
                                child: const Text('Effacer la période'),
                              ),
                          ],
                        ),
                      ],
                      const SizedBox(height: 12),
                      if (rows.isEmpty && !_loading)
                        Text(_query.text.trim().isEmpty && !widget.history
                            ? 'Saisissez ce que vous souhaitez retrouver.'
                            : 'Aucun résultat visible dans ce contexte.'),
                      for (var index = 0; index < rows.length; index++)
                        ListTile(
                          key: ValueKey('retrieval-$index'),
                          title: Text(rows[index]['title']?.toString() ??
                              'Élément'),
                          subtitle: Text([
                            rows[index]['human_type']?.toString() ?? 'Réel',
                            rows[index]['relation']?.toString() ?? '',
                            if (rows[index]['historical'] == true)
                              'Historique',
                          ].where((label) => label.isNotEmpty).join(' · ')),
                          trailing: _canOpen(rows[index])
                              ? const Icon(Icons.chevron_right)
                              : null,
                          onTap: large
                              ? () => setState(() => _selected = index)
                              : _canOpen(rows[index])
                                  ? () => _open(rows[index])
                                  : null,
                        ),
                      if (_more)
                        OutlinedButton(
                          onPressed: _loading
                              ? null
                              : () => _submit(more: true),
                          child: const Text('Afficher la suite'),
                        ),
                      const SizedBox(height: 16),
                      Text(
                        'Couverture partielle. Hors connexion : seuls les '
                        'éléments disponibles sur cet appareil sont consultables.',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                if (large && selected != null) ...[
                  const VerticalDivider(width: 1),
                  Expanded(
                    flex: 2,
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            selected['title']?.toString() ?? 'Élément',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          const SizedBox(height: 12),
                          Text(selected['relation']?.toString() ?? ''),
                          if (_canOpen(selected))
                            TextButton(
                              onPressed: () => _open(selected),
                              child: const Text('Ouvrir chez le propriétaire'),
                            ),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ),
    );
  }
}
