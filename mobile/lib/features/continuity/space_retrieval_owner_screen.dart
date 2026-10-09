import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';

/// Owner-backed Space N3. A search result is never an authorization grant:
/// every opening re-reads the source using the current account and actor.
class SpaceRetrievalOwnerScreen extends StatefulWidget {
  const SpaceRetrievalOwnerScreen({
    super.key,
    required this.runtime,
    required this.spaceActor,
    required this.kind,
    required this.id,
  });

  final AppRuntime runtime;
  final SpaceActorContext spaceActor;
  final String kind;
  final String id;

  @override
  State<SpaceRetrievalOwnerScreen> createState() =>
      _SpaceRetrievalOwnerScreenState();
}

class _SpaceRetrievalOwnerScreenState extends State<SpaceRetrievalOwnerScreen> {
  late Future<Map<String, dynamic>> _result;

  bool get _actorValid =>
      widget.runtime.actorContext?.value == widget.spaceActor;

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_onActorChanged);
    _result = _readOwner();
  }

  void _onActorChanged() {
    if (!mounted) return;
    setState(() {
      // A return to this Space also forces owner revalidation.
      _result = _readOwner();
    });
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant SpaceRetrievalOwnerScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(_onActorChanged);
      widget.runtime.actorContext?.addListener(_onActorChanged);
    }
    if (oldWidget.runtime != widget.runtime ||
        oldWidget.spaceActor != widget.spaceActor ||
        oldWidget.kind != widget.kind ||
        oldWidget.id != widget.id) {
      _result = _readOwner();
    }
  }

  String get _spacePath =>
      'api/v1/organizations/workspaces/'
      '${Uri.encodeComponent(widget.spaceActor.space.slug)}/';

  Future<Map<String, dynamic>> _readOwner() async {
    if (!_actorValid) throw StateError('Space actor context changed');
    final api = widget.runtime.api;
    if (api == null) throw StateError('Owner API unavailable');
    final kind = widget.kind;
    final id = Uri.encodeComponent(widget.id);
    final data = switch (kind) {
      'activity' || 'occurrence' => await _readActivityOwner(api, kind, id),
      'commerce_order' => await _readOrderOwner(api, id),
      'team_member' ||
      'group' ||
      'crm_contact' ||
      'audience' ||
      'partner' => await _readRelationshipOwner(api, kind, id),
      _ => throw const FormatException('Unknown owner'),
    };
    if (!_actorValid) throw StateError('Space actor context changed');
    return data;
  }

  Future<Map<String, dynamic>> _readActivityOwner(
    dynamic api,
    String kind,
    String id,
  ) async {
    final path = kind == 'activity'
        ? 'api/v1/activities/$id/'
        : 'api/v1/occurrences/$id/';
    final envelope = (await api.get(path)).jsonObject();
    final data = envelope['data'];
    if (data is! Map) throw const FormatException('Missing owner data');
    final payload = Map<String, dynamic>.from(data);
    final identity = payload['identity'];
    if (identity is! Map ||
        identity['kind'] != kind ||
        identity['id'] != widget.id) {
      throw const FormatException('Owner identity mismatch');
    }
    Map ownerData = payload;
    if (kind == 'occurrence') {
      final activity = payload['activity'];
      if (activity is! Map || activity['id'] == null) {
        throw const FormatException('Occurrence activity is missing');
      }
      final ownerEnvelope = (await api.get(
        'api/v1/activities/${Uri.encodeComponent(activity['id'].toString())}/',
      )).jsonObject();
      if (ownerEnvelope['data'] is! Map) {
        throw const FormatException('Activity owner unavailable');
      }
      ownerData = ownerEnvelope['data'] as Map;
    }
    final owner = ownerData['owner'];
    if (owner is! Map ||
        owner['kind'] != 'space' ||
        owner['id'] != widget.spaceActor.space.id) {
      throw const FormatException('Result belongs to another actor');
    }
    final representation = payload['representation'];
    final title = kind == 'activity'
        ? (representation is Map ? representation['title'] : null)
        : (payload['activity'] is Map
              ? (payload['activity'] as Map)['title']
              : null);
    final status = payload['state'];
    final place = payload['place'];
    return {
      'title': title ?? 'Élément',
      'type': kind == 'activity' ? 'Activité' : 'Séance',
      'status': status is Map ? status['code'] : null,
      'summary': representation is Map ? representation['summary'] : null,
      'place': place is Map ? (place['name'] ?? place['locality']) : null,
      'timing': payload['timing'],
    };
  }

  Future<Map<String, dynamic>> _readRelationshipOwner(
    dynamic api,
    String kind,
    String id,
  ) async {
    final path = Uri(
      path: '${_spacePath}relationships/',
      queryParameters: {'kind': kind, 'id': id},
    ).toString();
    final payload = (await api.get(path)).jsonObject();
    final selection = payload['selection'];
    if (selection is! Map ||
        selection['kind'] != kind ||
        selection['id'] != widget.id) {
      throw const FormatException('Relation unavailable in Space scope');
    }
    final profile = selection['profile'];
    return {
      'title':
          (profile is Map ? profile['name'] : null) ??
          selection['name'] ??
          selection['label'] ??
          selection['owner_identity'] ??
          'Relation',
      'type': selection['relation_type'] ?? 'Relation',
      'status': selection['status'],
      'summary': selection['owner_identity'],
    };
  }

  Future<Map<String, dynamic>> _readOrderOwner(dynamic api, String id) async {
    final perspective = widget.spaceActor.perspective;
    final path = Uri(
      path: '${_spacePath}commerce/orders/$id/',
      queryParameters: perspective.isAll
          ? null
          : {'responsibility': perspective.id!},
    ).toString();
    final payload = (await api.get(path)).jsonObject();
    final actor = payload['actor_context'];
    if (actor is! Map ||
        actor['kind'] != 'space' ||
        actor['id'] != widget.spaceActor.space.id ||
        payload['kind'] != 'commerce_order' ||
        payload['id'] != widget.id) {
      throw const FormatException('Order owner does not match context');
    }
    final activity = payload['activity'];
    return {
      'title': payload['title'],
      'type': 'Commande',
      'status': payload['status'],
      'summary': activity is Map ? activity['title'] : null,
      'timing': payload['cancelled_at'],
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Détail de mon Espace')),
      body: !_actorValid
          ? const Center(
              child: Text('Revenez à l’Espace autorisé pour ce détail.'),
            )
          : FutureBuilder<Map<String, dynamic>>(
              future: _result,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (!snapshot.hasData) {
                  return Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text(
                          'Le propriétaire ne rend plus ce détail accessible '
                          'dans le contexte courant.',
                        ),
                        TextButton(
                          onPressed: () =>
                              setState(() => _result = _readOwner()),
                          child: const Text('Actualiser'),
                        ),
                      ],
                    ),
                  );
                }
                final data = snapshot.data!;
                return ListView(
                  padding: const EdgeInsets.all(24),
                  children: [
                    Text(
                      data['type']?.toString() ?? 'Élément',
                      style: Theme.of(context).textTheme.labelLarge,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      data['title']?.toString() ?? 'Détail',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    for (final key in ['status', 'summary', 'place', 'timing'])
                      if (data[key] != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 14),
                          child: Text(data[key].toString()),
                        ),
                  ],
                );
              },
            ),
    );
  }
}
