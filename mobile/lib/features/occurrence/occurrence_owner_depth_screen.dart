import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../network/api_error.dart';

/// Owner-backed L5 depth. The day-of catalog is revalidated on every open,
/// refresh and before mutations. It is never a separate offline permission.
class OccurrenceOwnerDepthScreen extends StatefulWidget {
  const OccurrenceOwnerDepthScreen({
    super.key,
    required this.runtime,
    required this.occurrenceId,
    required this.kind,
    this.actorSpaceId,
  });

  final AppRuntime runtime;
  final String occurrenceId;
  final String kind;
  final String? actorSpaceId;

  @override
  State<OccurrenceOwnerDepthScreen> createState() =>
      _OccurrenceOwnerDepthScreenState();
}

class _OccurrenceOwnerDepthScreenState extends State<OccurrenceOwnerDepthScreen>
    with WidgetsBindingObserver {
  Object? _payload;
  Map<String, dynamic>? _depth;
  bool _busy = false;
  bool _denied = false;
  int _epoch = 0;

  static const _readKinds = {
    'my_queue',
    'my_placement',
    'my_checkpoints',
    'readiness',
    'operator_queue',
    'operator_placement',
    'operator_checkpoints',
    'capacity',
    'commerce',
    'finance',
    'places',
  };

  bool get _actorValid {
    final actor = widget.runtime.actorContext?.value;
    final expected = widget.actorSpaceId;
    return expected == null
        ? actor is! SpaceActorContext
        : actor is SpaceActorContext && actor.space.id == expected;
  }

  String get _root => 'api/v1/operations/occurrences/${widget.occurrenceId}';

  String? get _ownerReadPath => switch (widget.kind) {
    'my_queue' => '$_root/queues/me/',
    'my_placement' => '$_root/placements/me/',
    'my_checkpoints' => '$_root/checkpoints/me/',
    'operator_queue' => '$_root/queues/',
    'operator_placement' => '$_root/placement-plans/',
    'operator_checkpoints' => '$_root/checkpoints/',
    'readiness' => '$_root/readiness/',
    'capacity' ||
    'finance' ||
    'commerce' ||
    'places' => '$_root/experience/insights/${widget.kind}/',
    _ => null,
  };

  String get _experiencePath =>
      '$_root/experience/day-of/'
      '${widget.actorSpaceId == null ? '' : '?actor_space=${widget.actorSpaceId}'}';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    widget.runtime.actorContext?.addListener(_onActorChanged);
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant OccurrenceOwnerDepthScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(_onActorChanged);
      widget.runtime.actorContext?.addListener(_onActorChanged);
    }
    if (oldWidget.runtime != widget.runtime ||
        oldWidget.occurrenceId != widget.occurrenceId ||
        oldWidget.kind != widget.kind ||
        oldWidget.actorSpaceId != widget.actorSpaceId) {
      _onActorChanged();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _epoch++;
      _busy = false;
      unawaited(_load());
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      _epoch++;
      if (mounted) {
        setState(() {
          _payload = null;
          _depth = null;
          _busy = false;
        });
      }
    }
  }

  void _onActorChanged() {
    _epoch++;
    if (!mounted) return;
    setState(() {
      _payload = null;
      _depth = null;
      _busy = false;
      _denied = false;
    });
    if (_actorValid) unawaited(_load());
  }

  @override
  void dispose() {
    _epoch++;
    WidgetsBinding.instance.removeObserver(this);
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    super.dispose();
  }

  Future<void> _load() async {
    if (_busy || !_actorValid) return;
    final stamp = ++_epoch;
    setState(() {
      _busy = true;
      _denied = false;
      _depth = null;
      _payload = null;
    });
    try {
      final api = widget.runtime.api;
      final expected = _ownerReadPath;
      if (api == null ||
          !_readKinds.contains(widget.kind) ||
          expected == null) {
        throw StateError('Cette profondeur n’est pas disponible');
      }
      final canonical = (await api.get(_experiencePath)).jsonObject();
      final data = canonical['data'];
      if (data is! Map ||
          data['identity'] is! Map ||
          (data['identity'] as Map)['id']?.toString() != widget.occurrenceId ||
          data['depths'] is! List) {
        throw const FormatException('Contexte Jour J incohérent');
      }
      final matches = (data['depths'] as List)
          .whereType<Map>()
          .where(
            (item) =>
                item['kind'] == widget.kind &&
                item['read_path'] == '/$expected',
          )
          .toList();
      if (matches.length != 1) {
        throw const FormatException('Profondeur non autorisée');
      }
      final response = await api.get(expected);
      final decoded = jsonDecode(response.body);
      if (decoded is! List && decoded is! Map) {
        throw const FormatException('Réponse propriétaire invalide');
      }
      if (decoded is Map &&
          decoded['identity'] is Map &&
          (decoded['identity'] as Map)['id']?.toString() !=
              widget.occurrenceId) {
        throw const FormatException('Mauvaise Occurrence');
      }
      if (!mounted || stamp != _epoch || !_actorValid) return;
      setState(() {
        _depth = Map<String, dynamic>.from(matches.first);
        _payload = decoded;
      });
    } on Object catch (error) {
      if (!mounted || stamp != _epoch) return;
      setState(() {
        _payload = null;
        _depth = null;
        _denied =
            error is MakoloApiError &&
            const {401, 403, 404}.contains(error.statusCode);
      });
    } finally {
      if (mounted && stamp == _epoch) setState(() => _busy = false);
    }
  }

  Future<void> _operate({
    required String path,
    required String method,
    required String label,
    Map<String, dynamic>? body,
  }) async {
    if (_busy || !_actorValid || _depth == null) return;
    if (widget.kind != 'my_queue' && _depth!['can_manage'] != true) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(label),
        content: const Text(
          'Cette opération modifie l’état réel. '
          'Confirmer son exécution auprès du propriétaire ?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Confirmer'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted || !_actorValid) return;
    final stamp = ++_epoch;
    setState(() => _busy = true);
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Service indisponible');
      // Every mutation rechecks the canonical capability and owner permission.
      final envelope = (await api.get(_experiencePath)).jsonObject();
      final data = envelope['data'];
      if (data is! Map ||
          data['depths'] is! List ||
          !(data['depths'] as List).whereType<Map>().any(
            (item) =>
                item['kind'] == widget.kind &&
                item['read_path'] == '/${_ownerReadPath!}',
          )) {
        throw StateError('Mandat ou contexte retiré');
      }
      if (!_actorValid) throw StateError('Acteur modifié');
      final currentDepth = (data['depths'] as List).whereType<Map>().firstWhere(
        (item) => item['kind'] == widget.kind,
      );
      if (widget.kind != 'my_queue' && currentDepth['can_manage'] != true) {
        throw StateError('Droit de modification retiré');
      }
      if (method == 'POST') {
        await api.post(path, body: body);
      } else if (method == 'PATCH') {
        await api.patch(path, body: body);
      } else if (method == 'DELETE') {
        await api.delete(path);
      } else {
        throw StateError('Méthode refusée');
      }
      if (!mounted || stamp != _epoch || !_actorValid) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Résultat confirmé par le propriétaire.')),
      );
    } on Object {
      if (!mounted || stamp != _epoch) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Action non confirmée. Actualisez avant de réessayer.'),
        ),
      );
    } finally {
      if (mounted && stamp == _epoch) setState(() => _busy = false);
    }
    if (mounted && _actorValid) await _load();
  }

  static Map<String, dynamic> _map(Object? value) =>
      value is Map ? Map<String, dynamic>.from(value) : {};
  static List<Map<String, dynamic>> _rows(Object? value) =>
      value is List ? value.whereType<Map>().map(_map).toList() : [];
  static String _text(Object? value) => value?.toString() ?? 'À vérifier';
  static String _summary(Object? value) {
    if (value is Map) {
      return value.entries
          .where(
            (entry) =>
                entry.value != null &&
                !const {
                  'id',
                  'token',
                  'credential',
                  'credential_token',
                  'secret',
                  'email',
                  'payer_email',
                  'metadata',
                }.contains(entry.key.toString()),
          )
          .map(
            (entry) =>
                '${_fieldLabel(entry.key.toString())} : ${_summary(entry.value)}',
          )
          .join(' · ');
    }
    if (value is List) return value.map(_summary).join(' · ');
    return _text(value);
  }

  static String _fieldLabel(String key) => switch (key) {
    'status' || 'state' => 'État',
    'quantity' || 'count' => 'Nombre',
    'counts' => 'Situation de la file',
    'available' => 'Disponible',
    'total' => 'Total',
    'held' => 'Réservé provisoirement',
    'committed' => 'Confirmé',
    'currency' => 'Devise',
    'amount' => 'Montant',
    'unit_price' => 'Prix unitaire',
    'required' => 'Obligatoire',
    'active' => 'Actif',
    'position' => 'Position',
    'source' => 'Source',
    'eligibility_policy' => 'Condition d’admission',
    'checkpoint_id' => 'Checkpoint',
    _ => key.replaceAll('_', ' '),
  };

  Widget _row(BuildContext context, Map<String, dynamic> data) {
    final label = _text(
      data['label'] ?? data['name'] ?? data['key'] ?? data['id'],
    );
    final entries = data.entries.where(
      (entry) =>
          !const {
            'id',
            'key',
            'label',
            'name',
            'units',
            'assignments',
          }.contains(entry.key) &&
          entry.value != null,
    );
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: Theme.of(context).textTheme.titleMedium),
            for (final entry in entries)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  '${_fieldLabel(entry.key)} : ${_summary(entry.value)}',
                ),
              ),
            if (widget.kind == 'operator_queue' &&
                _depth?['can_manage'] == true &&
                data['id'] != null) ...[
              const SizedBox(height: 8),
              FilledButton.tonal(
                onPressed: _busy
                    ? null
                    : () => _operate(
                        path: 'api/v1/operations/queues/${data['id']}/call/',
                        method: 'POST',
                        label: 'Appeler la prochaine personne',
                      ),
                child: const Text('Appeler la suite'),
              ),
              Wrap(
                spacing: 6,
                children: [
                  for (final action in ['pause', 'resume', 'close'])
                    OutlinedButton(
                      onPressed: _busy
                          ? null
                          : () => _operate(
                              path:
                                  'api/v1/operations/queues/${data['id']}/status/',
                              method: 'PATCH',
                              body: {'action': action},
                              label: 'Changer la file : $action',
                            ),
                      child: Text(action),
                    ),
                ],
              ),
            ],
            if (widget.kind == 'operator_checkpoints' &&
                _depth?['can_manage'] == true &&
                data['id'] != null)
              Wrap(
                spacing: 6,
                children: [
                  for (final action in ['open', 'pause', 'resume', 'close'])
                    OutlinedButton(
                      onPressed: _busy
                          ? null
                          : () => _operate(
                              path:
                                  'api/v1/operations/checkpoints/${data['id']}/status/',
                              method: 'PATCH',
                              body: {'action': action},
                              label: 'Checkpoint : $action',
                            ),
                      child: Text(action),
                    ),
                ],
              ),
            if (widget.kind == 'my_queue' &&
                data['id'] != null &&
                const {'waiting', 'called'}.contains(data['status']))
              OutlinedButton(
                onPressed: _busy
                    ? null
                    : () => _operate(
                        path:
                            'api/v1/operations/queue-entries/${data['id']}/me/cancel/',
                        method: 'POST',
                        label: 'Quitter cette file',
                      ),
                child: const Text('Quitter la file'),
              ),
            if (widget.kind == 'operator_placement' &&
                _depth?['can_manage'] == true)
              for (final unit in _rows(data['units'])) ...[
                const Divider(),
                Text(
                  '${_text(unit['label'])} · ${_text(unit['kind'])}',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                for (final assignment in _rows(unit['assignments']))
                  Row(
                    children: [
                      Expanded(
                        child: Text('Attribution ${_text(assignment['id'])}'),
                      ),
                      TextButton(
                        onPressed: _busy
                            ? null
                            : () => _operate(
                                path:
                                    'api/v1/operations/placement-assignments/${assignment['id']}/',
                                method: 'DELETE',
                                label: 'Retirer cette attribution',
                              ),
                        child: const Text('Retirer'),
                      ),
                    ],
                  ),
                const SizedBox(height: 4),
                OutlinedButton(
                  onPressed: _busy || unit['id'] == null
                      ? null
                      : () => _assignPlacement(
                          planId: _text(data['id']),
                          unitId: _text(unit['id']),
                        ),
                  child: const Text('Attribuer cette place'),
                ),
              ],
          ],
        ),
      ),
    );
  }

  Future<void> _assignPlacement({
    required String planId,
    required String unitId,
  }) async {
    final controller = TextEditingController();
    var kind = 'profile_id';
    try {
      final selected = await showDialog<Map<String, String>>(
        context: context,
        builder: (dialogContext) => StatefulBuilder(
          builder: (context, update) => AlertDialog(
            title: const Text('Attribuer une place'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButton<String>(
                  value: kind,
                  items: const [
                    DropdownMenuItem(
                      value: 'profile_id',
                      child: Text('Profil Makolo'),
                    ),
                    DropdownMenuItem(
                      value: 'external_beneficiary_id',
                      child: Text('Bénéficiaire externe'),
                    ),
                  ],
                  onChanged: (value) {
                    if (value != null) update(() => kind = value);
                  },
                ),
                TextField(
                  controller: controller,
                  decoration: const InputDecoration(
                    labelText: 'Identifiant du bénéficiaire',
                  ),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Annuler'),
              ),
              FilledButton(
                onPressed: () {
                  final id = controller.text.trim();
                  if (id.isNotEmpty) Navigator.pop(dialogContext, {kind: id});
                },
                child: const Text('Continuer'),
              ),
            ],
          ),
        ),
      );
      if (selected == null || !mounted) return;
      await _operate(
        path: 'api/v1/operations/placement-plans/$planId/assignments/',
        method: 'POST',
        label: 'Confirmer cette attribution',
        body: {'unit_id': unitId, ...selected},
      );
    } finally {
      controller.dispose();
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = _payload;
    final depth = _depth;
    final data = _map(current);
    final ownerData = _map(data['data']);
    final payload = ownerData.isNotEmpty ? ownerData : data;
    final lists = <Map<String, dynamic>>[
      if (current is List) ..._rows(current),
      if (current is Map) ..._rows(payload['entries']),
      if (current is Map) ..._rows(payload['offers']),
      if (current is Map) ..._rows(payload['order_counts']),
      if (current is Map) ..._rows(payload['obligations']),
      if (current is Map) ..._rows(payload['payments']),
    ];
    return Scaffold(
      appBar: AppBar(
        title: Text(depth?['label']?.toString() ?? 'Opération'),
        actions: [
          IconButton(
            tooltip: 'Actualiser et vérifier les mandats',
            onPressed: _busy ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: !_actorValid || _denied
          ? const Center(
              child: Text('Ce contenu est privé ou votre mandat a été retiré.'),
            )
          : _busy && current == null
          ? const Center(child: CircularProgressIndicator())
          : depth == null
          ? Center(
              child: TextButton(
                onPressed: _load,
                child: const Text('Vérifier à nouveau'),
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  depth['source']?.toString() ?? 'Propriétaire métier',
                  style: Theme.of(context).textTheme.labelMedium,
                ),
                const SizedBox(height: 12),
                if (_busy) const LinearProgressIndicator(),
                if (lists.isEmpty && payload.isEmpty)
                  const Card(
                    child: Padding(
                      padding: EdgeInsets.all(20),
                      child: Text(
                        'Aucun fait disponible auprès du propriétaire.',
                      ),
                    ),
                  ),
                if (lists.isEmpty && payload.isNotEmpty) _row(context, payload),
                for (final item in lists) ...[
                  _row(context, item),
                  const SizedBox(height: 8),
                ],
              ],
            ),
    );
  }
}
