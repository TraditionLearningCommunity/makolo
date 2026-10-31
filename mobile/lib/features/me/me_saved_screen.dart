import 'package:flutter/material.dart';

import '../../network/makolo_api_client.dart';
import '../../presentation/possibilities/discovery_save_icon.dart';
import '../../repositories/personal_repository.dart';
import '../../sync/projection_contract.dart';
import 'me_local_preview.dart';

/// Full owner-backed saved collection; the Moi root presents only three rows.
class MeSavedScreen extends StatefulWidget {
  const MeSavedScreen({
    super.key,
    required this.api,
    required this.personal,
    required this.onOpen,
    required this.onDiscover,
  });
  final MakoloApiClient api;
  final PersonalRepository personal;
  final ValueChanged<String> onOpen;
  final VoidCallback onDiscover;

  @override
  State<MeSavedScreen> createState() => _MeSavedScreenState();
}

class _MeSavedScreenState extends State<MeSavedScreen> {
  static const _savedProjectionKind = 'personal.me.preview';
  static const _savedResourceKey = 'considerations:bookmarks:known';
  final _scroll = ScrollController();
  final _rows = <Map<String, dynamic>>[];
  int _offset = 0;
  bool _hasMore = true, _loading = false, _failed = false;
  bool _hasKnownCollection = false;
  String? _removing;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_checkEnd);
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    try {
      final saved = await widget.personal.store.readProjection(
        _savedProjectionKind,
        resourceKey: _savedResourceKey,
      );
      final payload = saved?.payload;
      final actor = payload?['actor'];
      final items = payload?['items'];
      if (mounted &&
          actor is Map &&
          actor['type'] == 'profile' &&
          actor['id']?.toString() == widget.personal.store.profileId &&
          items is List &&
          payload?['next_offset'] is int &&
          payload?['has_more'] is bool) {
        final known = items
            .whereType<Map>()
            .map(
              (row) => row.map((key, value) => MapEntry(key.toString(), value)),
            )
            .where((row) => row['id'] != null && row['activity'] is Map)
            .toList();
        setState(() {
          _rows
            ..clear()
            ..addAll(known);
          _offset = payload!['next_offset'] as int;
          _hasMore = payload['has_more'] as bool;
          _hasKnownCollection = true;
        });
      } else {
        await _restoreRootPreview();
      }
    } on Object {
      // Missing owner collection does not become an authoritative empty list.
    }
    if (mounted) await _next(reset: true);
  }

  Future<void> _restoreRootPreview() async {
    try {
      final snapshot = await widget.personal.store.readProjection(
        'personal.me',
      );
      final local = MeLocalPreview.forProfile(
        snapshot,
        widget.personal.store.profileId,
      );
      final bookmarks = local?.collection('considerations', 'bookmarks');
      if (mounted && bookmarks != null) {
        final cached = (bookmarks['items'] as List)
            .whereType<Map<String, dynamic>>()
            .toList();
        setState(() {
          _rows
            ..clear()
            ..addAll(cached);
          _offset = bookmarks['next_offset'] is int
              ? bookmarks['next_offset'] as int
              : cached.length;
          _hasMore = bookmarks['has_more'] == true;
          _hasKnownCollection = true;
        });
      }
    } on Object {
      // A missing or malformed local preview is not an empty collection.
    }
  }

  Future<void> _retainKnownCollection() async {
    await widget.personal.store.putProjection(
      kind: _savedProjectionKind,
      resourceKey: _savedResourceKey,
      schemaVersion: 1,
      payload: {
        'actor': {'type': 'profile', 'id': widget.personal.store.profileId},
        'family': 'bookmarks',
        'items': _rows,
        'next_offset': _offset,
        'has_more': _hasMore,
      },
    );
  }

  void _checkEnd() {
    if (_scroll.hasClients && _scroll.position.extentAfter < 480) _next();
  }

  Future<void> _next({bool reset = false}) async {
    if (_loading || (!reset && !_hasMore) || (!reset && _failed)) return;
    setState(() {
      _loading = true;
      _failed = false;
    });
    final offset = reset ? 0 : _offset;
    try {
      final uri = Uri(
        path: 'api/v1/me/preview/considerations/',
        queryParameters: {
          'family': 'bookmarks',
          'offset': '$offset',
          'limit': '24',
        },
      );
      final response = await widget.api.get(uri.toString());
      final data = ProjectionEnvelope.parse(
        response.jsonObject(),
        expectedProjection: 'personal.me.preview',
      ).data;
      final part = data['collection'];
      final actor = data['actor'];
      if (actor is! Map ||
          actor['type'] != 'profile' ||
          actor['id']?.toString() != widget.personal.store.profileId ||
          data['family'] != 'bookmarks' ||
          data['offset'] != offset ||
          part is! Map ||
          part['items'] is! List ||
          part['has_more'] is! bool ||
          part['next_offset'] is! int ||
          part['next_offset'] < offset ||
          (part['has_more'] == true && (part['items'] as List).isEmpty)) {
        throw const FormatException('Invalid saved collection');
      }
      if (!mounted) return;
      final known = <String>{
        for (final row in reset ? <Map<String, dynamic>>[] : _rows)
          if (row['id'] != null) row['id'].toString(),
      };
      final nextRows = <Map<String, dynamic>>[];
      for (final raw in part['items'] as List) {
        if (raw is! Map || raw['id'] == null) continue;
        if (known.add(raw['id'].toString())) {
          nextRows.add(raw.map((k, v) => MapEntry(k.toString(), v)));
        }
      }
      setState(() {
        if (reset) _rows.clear();
        _rows.addAll(nextRows);
        _offset = part['next_offset'] as int;
        _hasMore = part['has_more'] as bool;
        _loading = false;
        _hasKnownCollection = true;
      });
      try {
        await _retainKnownCollection();
      } on Object {
        // Valid server data is still displayed; persistence can reconcile later.
      }
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _checkEnd();
      });
    } on Object {
      if (mounted)
        setState(() {
          _loading = false;
          _failed = true;
        });
    }
  }

  Future<void> _remove(String activityId) async {
    if (_removing != null) return;
    setState(() => _removing = activityId);
    try {
      await widget.api.delete(
        'api/v1/discovery/items/activity/${Uri.encodeComponent(activityId)}/saved/',
      );
      if (!mounted) return;
      // The server confirmed removal. Preserve other known rows if refresh
      // fails; do not replace the entire offline collection with an error.
      setState(() {
        _rows.removeWhere(
          (row) =>
              row['activity'] is Map &&
              (row['activity'] as Map)['id']?.toString() == activityId,
        );
        _offset = 0;
        _hasMore = true;
        _failed = false;
        _removing = null;
      });
      try {
        await _retainKnownCollection();
      } on Object {
        // The owner confirmed removal. The next sync remains authoritative.
      }
      try {
        await widget.personal.reflectMeBookmarkRemoved(activityId: activityId);
      } on Object {
        // The owner already confirmed removal; never report it as failed
        // because the read-model reflection could not be written.
      }
      await _next(reset: true);
      // Invalidate the single personal read model, not a duplicate save store.
      try {
        final root = await widget.api.get('api/v1/me/');
        final envelope = ProjectionEnvelope.parse(
          root.jsonObject(),
          expectedProjection: 'personal.me',
        );
        if (envelope.data['actor'] is Map &&
            (envelope.data['actor'] as Map)['id']?.toString() ==
                widget.personal.store.profileId) {
          await widget.personal.store.putProjection(
            kind: 'personal.me',
            schemaVersion: envelope.schemaVersion,
            payload: envelope.data,
            receivedAt: DateTime.now().toUtc(),
            sourceGeneratedAt: envelope.generatedAt,
          );
        }
      } on Object {
        // The server mutation succeeded; normal sync will refresh Moi.
      }
    } on Object {
      if (mounted) {
        setState(() => _removing = null);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Impossible de retirer cet élément.')),
        );
      }
    }
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Mes enregistrements'),
      actions: [
        IconButton(
          tooltip: 'Découvrir d’autres possibilités',
          onPressed: widget.onDiscover,
          icon: const Icon(Icons.add_rounded),
        ),
      ],
    ),
    body: RefreshIndicator(
      onRefresh: () => _next(reset: true),
      child: ListView(
        controller: _scroll,
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
        children: [
          for (final row in _rows)
            if (row['activity'] is Map &&
                (row['activity'] as Map)['id'] != null)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: DiscoveryOrbitIcon(
                  saved: true,
                  color: Theme.of(context).colorScheme.primary,
                ),
                title: Text(
                  (row['activity'] as Map)['title']?.toString() ?? '',
                ),
                trailing: IconButton(
                  tooltip: 'Retirer des enregistrements',
                  onPressed:
                      _removing == (row['activity'] as Map)['id'].toString()
                      ? null
                      : () =>
                            _remove((row['activity'] as Map)['id'].toString()),
                  icon: DiscoveryOrbitIcon(
                    saved: false,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ),
                onTap: () =>
                    widget.onOpen((row['activity'] as Map)['id'].toString()),
              ),
          if (!_loading && !_failed && !_hasMore)
            Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 20),
                child: Text(
                  _rows.isEmpty && _hasKnownCollection
                      ? 'Aucun enregistrement pour le moment.'
                      : 'Vous avez tout exploré',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            ),
        ],
      ),
    ),
  );
}
