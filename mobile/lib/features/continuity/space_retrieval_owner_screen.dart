import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../presentation/contracts/space_presentation.dart';
import '../../presentation/mps/mps_models.dart';
import '../../presentation/mps/mps_native_renderer.dart';

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
      _result = _actorValid
          ? _readOwner()
          : Future.value(const <String, dynamic>{});
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
      'activity' ||
      'occurrence' ||
      'offer' ||
      'journey' ||
      'transport_route' ||
      'vehicle' => await _readWorkOwner(api, kind),
      'commerce_order' => await _readOrderOwner(api, id),
      'payment_obligation' => await _readPayerObligationOwner(api, id),
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

  Future<Map<String, dynamic>> _readWorkOwner(dynamic api, String kind) async {
    final perspective = widget.spaceActor.perspective;
    final path = Uri(
      path: '${_spacePath}work/',
      queryParameters: {
        'kind': kind,
        'id': widget.id,
        if (!perspective.isAll) 'responsibility': perspective.id!,
      },
    ).toString();
    final payload = (await api.get(path)).jsonObject();
    final item = spaceMap(payload['selection']);
    final source = spaceMap(item?['source']);
    final space = spaceMap(payload['space']);
    if (space?['id'] != widget.spaceActor.space.id ||
        source?['kind'] != kind ||
        source?['id'] != widget.id) {
      throw const FormatException(
        'Owner unavailable in current responsibility',
      );
    }
    MpsPresentationPackage? presentation;
    var presentationUnavailable = false;
    final mps = widget.runtime.mps;
    if (kind == 'activity' && mps != null) {
      try {
        await mps.refreshActivity(widget.id, 'public_page');
        if (!_actorValid) throw StateError('Actor changed');
        presentation = await mps.readActivityPackage(widget.id, 'public_page');
      } on Object {
        // Do not expose an older artifact after failed owner revalidation.
        presentationUnavailable = true;
      }
    }
    return {
      'title': item!['title'],
      'type': payload['primary_business_label'],
      'status': item['state'],
      'summary': item['summary'],
      'timing': item['timing'],
      'context': item['context'],
      'presentation': presentation,
      'presentation_unavailable': presentationUnavailable,
      'continuity_facet': item['continuity_facet'],
      'day_of':
          (item['capabilities'] is List &&
          (item['capabilities'] as List).contains('open_day_of')),
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

  Future<Map<String, dynamic>> _readPayerObligationOwner(
    dynamic api,
    String id,
  ) async {
    final perspective = widget.spaceActor.perspective;
    final path = Uri(
      path: '${_spacePath}payment-obligations/$id/',
      queryParameters: perspective.isAll
          ? null
          : {'responsibility': perspective.id!},
    ).toString();
    final payload = (await api.get(path)).jsonObject();
    final space = spaceMap(payload['space']);
    if (space?['id'] != widget.spaceActor.space.id ||
        payload['kind'] != 'payment_obligation' ||
        payload['id'] != widget.id ||
        payload['responsibility'] != (perspective.id ?? 'all')) {
      throw const FormatException(
        'Payment obligation owner is no longer available in this Space',
      );
    }
    return {
      'title': payload['label'],
      'type': 'Obligation financière',
      'status': payload['status'],
      'summary': '${payload['amount']} ${payload['currency']}',
      'timing': payload['due_at'],
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
                final itemContext = spaceMap(data['context']);
                final activity = spaceMap(itemContext?['activity']);
                final activityRoute = spaceOwnerRoute(
                  slug: widget.spaceActor.space.slug,
                  kind: 'activity',
                  id: spaceText(activity?['id']),
                );
                final blockers = spaceMap(
                  data['continuity_facet'],
                )?['blockers'];
                return ListView(
                  padding: const EdgeInsets.all(24),
                  children: [
                    MakoloDetailHeader(
                      title: spaceText(data['title']) ?? 'Détail',
                      eyebrow: spaceText(data['type']),
                      subtitle: spaceText(data['summary']),
                      status: spaceText(data['status']) == null
                          ? null
                          : MakoloStatus(
                              label: spaceStateLabel(data['status'] as String),
                            ),
                    ),
                    for (final key in ['place'])
                      if (data[key] != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 14),
                          child: Text(data[key].toString()),
                        ),
                    for (final line in spaceTimingLines(data['timing']))
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: Text(line),
                      ),
                    if (itemContext?['passenger_capacity'] is num)
                      Text(
                        '${itemContext!['passenger_capacity']} places dans le véhicule',
                      ),
                    if (spaceMap(itemContext?['pricing'])
                        case final Map<String, dynamic> pricing)
                      if (pricing['unit_price'] is String &&
                          pricing['currency'] is String)
                        ListTile(
                          leading: const Icon(Icons.payments_outlined),
                          title: Text(
                            'Prix unitaire : ${pricing['unit_price']} ${pricing['currency']}',
                          ),
                        ),
                    if (spaceText(spaceMap(itemContext?['place'])?['name'])
                        case final String place)
                      ListTile(
                        leading: const Icon(Icons.place_outlined),
                        title: Text(place),
                      ),
                    if (itemContext?['stops'] case final List stops)
                      for (final stop in stops)
                        if (spaceMap(stop)
                            case final Map<String, dynamic> place)
                          ListTile(
                            leading: const Icon(Icons.place_outlined),
                            title: Text(spaceText(place['name']) ?? 'Arrêt'),
                            subtitle: Text(
                              [
                                if (place['boarding_allowed'] == true)
                                  'Embarquement',
                                if (place['alighting_allowed'] == true)
                                  'Descente',
                              ].join(' · '),
                            ),
                          ),
                    if (blockers is List && blockers.isNotEmpty)
                      MakoloAttentionBlock(
                        title: 'Points à examiner',
                        body:
                            '${blockers.length} blocage(s) actif(s) dans cette démarche.',
                      ),
                    if (activityRoute != null)
                      ListTile(
                        title: Text(
                          spaceText(activity?['title']) ?? 'Activité liée',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => context.push(activityRoute),
                      ),
                    if (data['day_of'] == true && widget.kind == 'occurrence')
                      FilledButton.icon(
                        onPressed: () => context.push(
                          '/space/occurrences/${Uri.encodeComponent(widget.id)}/day-of',
                        ),
                        icon: const Icon(Icons.play_circle_outline),
                        label: const Text('Jour J'),
                      ),
                    if (data['presentation']
                        case final MpsPresentationPackage package)
                      if (spaceMap(package.artifact.context['editorial'])
                              ?.isNotEmpty ==
                          true)
                        ExpansionTile(
                          title: const Text('Présentation'),
                          children: [
                            MpsNativeRenderer(
                              package: package,
                              mediaBaseUri: widget.runtime.api?.baseUri,
                              mediaScopeKey:
                                  '${widget.runtime.session?.profileId}:${widget.spaceActor.space.id}:${widget.spaceActor.perspective.id ?? 'all'}',
                            ),
                          ],
                        ),
                    if (data['presentation_unavailable'] == true)
                      const Text(
                        'La présentation associée est indisponible. Actualisez pour réessayer.',
                      ),
                  ],
                );
              },
            ),
    );
  }
}
