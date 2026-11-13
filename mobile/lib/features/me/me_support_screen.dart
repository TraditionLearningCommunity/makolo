import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';

import 'appuis_dashboard.dart';

import '../../app/runtime/app_runtime.dart';
import '../../app/runtime/actor_context.dart';
import '../../network/api_error.dart';
import '../../sync/sync_status.dart';
import '../../sync/owner_source_state.dart';

/// Shared Profile/Space composition of owner-backed Recognition, Loyalty and
/// Partners. There is no Appuis domain, no inferred right and no local spending.
class MeSupportScreen extends StatefulWidget {
  const MeSupportScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  State<MeSupportScreen> createState() => _MeSupportScreenState();
}

class _MeSupportScreenState extends State<MeSupportScreen> {
  static const families = ['recognition', 'loyalty', 'partners'];
  final Map<String, Map<String, dynamic>> _snapshots = {};
  final Map<String, String> _errors = {};
  final Map<String, String> _pendingKeys = {};
  late ActorContext _actor;
  int _generation = 0;
  bool _loading = true;
  bool _busy = false;
  bool _denied = false;
  StreamSubscription<OwnerSourceState>? _personalSource;

  String get _scope => _actor is SpaceActorContext
      ? 'space:${(_actor as SpaceActorContext).space.id}'
      : 'personal';
  bool get _space => _actor is SpaceActorContext;

  @override
  void initState() {
    super.initState();
    _actor = widget.runtime.actorContext?.value ?? const PersonalActorContext();
    widget.runtime.actorContext?.addListener(_actorChanged);
    _bindPersonalSource();
    unawaited(_load());
  }

  @override
  void dispose() {
    _generation++;
    widget.runtime.actorContext?.removeListener(_actorChanged);
    unawaited(_personalSource?.cancel());
    super.dispose();
  }

  void _actorChanged() {
    final next =
        widget.runtime.actorContext?.value ?? const PersonalActorContext();
    if (next == _actor) return;
    _actor = next;
    _generation++;
    _snapshots.clear();
    _errors.clear();
    _pendingKeys.clear();
    _denied = false;
    setState(() => _loading = true);
    unawaited(_load());
  }

  void _bindPersonalSource() {
    final personal = widget.runtime.personal;
    if (personal == null) return;
    _personalSource = personal.watchMeSource().listen((source) {
      if (!mounted || _space) return;
      if (source.invalidated) {
        _generation++;
        _denied = true;
        _snapshots.clear();
        _pendingKeys.clear();
        setState(() {});
        final store = widget.runtime.store;
        if (store != null) {
          for (final family in families) {
            unawaited(
              store.deleteProjection(
                'appuis.$family',
                resourceKey: 'personal',
              ),
            );
          }
        }
      } else if (_denied) {
        _denied = false;
        unawaited(_load());
      }
    });
  }

  @override
  void didUpdateWidget(covariant MeSupportScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime != widget.runtime) {
      oldWidget.runtime.actorContext?.removeListener(_actorChanged);
      unawaited(_personalSource?.cancel());
      widget.runtime.actorContext?.addListener(_actorChanged);
      _bindPersonalSource();
      _generation++;
      _actor =
          widget.runtime.actorContext?.value ?? const PersonalActorContext();
      _snapshots.clear();
      _denied = false;
      unawaited(_load());
    }
  }

  bool _current(int generation, ActorContext actor) =>
      mounted &&
      generation == _generation &&
      _actor == actor &&
      (widget.runtime.actorContext?.value ?? const PersonalActorContext()) ==
          actor;

  String _path(String family, ActorContext actor) {
    if (actor is SpaceActorContext) {
      final space = actor.space;
      return switch (family) {
        'recognition' => 'api/v1/recognition/spaces/${space.id}/',
        'loyalty' =>
          'api/v1/loyalty/organizations/${Uri.encodeComponent(space.slug)}/',
        'partners' =>
          'api/v1/partners/partners/?organization=${Uri.encodeQueryComponent(space.id)}',
        _ => throw ArgumentError.value(family),
      };
    }
    return switch (family) {
      'recognition' => 'api/v1/recognition/me/',
      'loyalty' => 'api/v1/loyalty/me/',
      'partners' => 'api/v1/me/partners/',
      _ => throw ArgumentError.value(family),
    };
  }

  Future<void> _load() async {
    final generation = ++_generation;
    final actor = _actor;
    final store = widget.runtime.store;
    if (_denied || store == null || widget.runtime.api == null) {
      if (_current(generation, actor)) setState(() => _loading = false);
      return;
    }
    if (actor is SpaceActorContext) {
      final workspace = widget.runtime.space;
      final authorized =
          workspace != null &&
          await workspace.hasAcquiredSpaceContext(actor.space);
      if (!mounted || !_current(generation, actor)) return;
      if (!authorized) {
        for (final family in families) {
          await store.deleteProjection('appuis.$family', resourceKey: _scope);
        }
        if (mounted && _current(generation, actor)) {
          setState(() {
            _denied = true;
            _loading = false;
          });
        }
        return;
      }
    }
    for (final family in families) {
      try {
        final saved = await store.readProjection(
          'appuis.$family',
          resourceKey: _scope,
        );
        if (!mounted || !_current(generation, actor)) return;
        if (saved != null) _snapshots[family] = saved.payload;
      } on Object {
        // The other family snapshots remain available.
      }
    }
    if (_current(generation, actor)) setState(() => _loading = false);
    await _refresh();
  }

  Future<void> _refresh() async {
    final actor = _actor;
    final generation = _generation;
    final api = widget.runtime.api;
    final store = widget.runtime.store;
    if (_denied ||
        _busy ||
        api == null ||
        store == null ||
        !_current(generation, actor)) {
      return;
    }
    setState(() => _busy = true);
    try {
      for (final family in families) {
        if (!_current(generation, actor)) break;
        try {
          final response = await api.get(_path(family, actor));
          if (!mounted || !_current(generation, actor)) return;
          final decoded = jsonDecode(response.body);
          final body = family == 'partners' && !_space && decoded is Map
              ? decoded['data']
              : decoded;
          if (body is! Map && body is! List) {
            throw const FormatException('Invalid owner projection');
          }
          final payload = body is List
              ? <String, dynamic>{'relationships': body}
              : Map<String, dynamic>.from(body as Map);
          if (family == 'partners') {
            await _includePartnerActivity(payload, actor, generation);
          }
          if (!mounted || !_current(generation, actor)) return;
          await store.putProjection(
            kind: 'appuis.$family',
            resourceKey: _scope,
            schemaVersion: 1,
            payload: _cacheSafe(payload),
            lastVerifiedOnlineAt: DateTime.now().toUtc(),
            freshnessPolicyId: 'swr',
          );
          if (!mounted || !_current(generation, actor)) return;
          setState(() {
            _snapshots[family] = payload;
            _errors.remove(family);
          });
        } on MakoloApiError catch (error) {
          if (!mounted || !_current(generation, actor)) return;
          if (error.statusCode == 401 ||
              error.statusCode == 403 ||
              error.statusCode == 404) {
            await store.deleteProjection(
              'appuis.$family',
              resourceKey: _scope,
            );
            if (!mounted || !_current(generation, actor)) return;
            setState(() {
              _snapshots.remove(family);
              if (error.statusCode == 404) {
                _errors.remove(family);
              } else {
                _errors[family] = 'Accès retiré ou non autorisé.';
              }
            });
          } else {
            setState(
              () => _errors[family] = 'Actualisation impossible. Les informations connues restent visibles.',
            );
          }
        } on Object {
          if (mounted && _current(generation, actor)) {
            setState(
              () => _errors[family] = 'Actualisation impossible. Les informations connues restent visibles.',
            );
          }
        }
      }
    } finally {
      if (_current(generation, actor)) setState(() => _busy = false);
    }
  }

  /// Voucher codes are private owner secrets; do not persist their raw value
  /// in the general-purpose projection snapshot (online reads remain intact).
  static Map<String, dynamic> _cacheSafe(Map<String, dynamic> payload) {
    Object? clean(Object? value) {
      if (value is List) return value.map(clean).toList(growable: false);
      if (value is Map) {
        return <String, dynamic>{
          for (final entry in value.entries)
            if (entry.key != 'benefit_code' && entry.key != 'promotion_code')
              entry.key.toString(): clean(entry.value),
        };
      }
      return value;
    }

    return clean(payload) as Map<String, dynamic>;
  }

  /// Owner datasets stay separate, filtered by this actor's Partner IDs.
  Future<void> _includePartnerActivity(
    Map<String, dynamic> payload,
    ActorContext actor,
    int generation,
  ) async {
    final api = widget.runtime.api;
    if (api == null) return;
    final ids = _rows(payload['relationships'])
        .map((row) => _text(row['id']))
        .where((id) => id.isNotEmpty)
        .toSet();
    if (ids.isEmpty) return;
    final organization = actor is SpaceActorContext
        ? '?organization=${Uri.encodeQueryComponent(actor.space.id)}'
        : '';
    for (final family in ['codes', 'commissions', 'payouts']) {
      if (!mounted || !_current(generation, actor)) return;
      try {
        final response = await api.get(
          'api/v1/partners/$family/$organization',
        );
        if (!mounted || !_current(generation, actor)) return;
        final decoded = jsonDecode(response.body);
        if (decoded is! List) continue;
        payload[family] = decoded
            .whereType<Map>()
            .map(_map)
            .where((row) => ids.contains(_text(row['partner'])))
            .toList(growable: false);
      } on Object {
        // No optional failure can invalidate the established relation.
      }
    }
    final campaigns = _rows(payload['codes'])
        .map((row) => _text(row['campaign']))
        .where((id) => id.isNotEmpty)
        .toSet();
    if (campaigns.isNotEmpty && _current(generation, actor)) {
      try {
        final response = await api.get(
          'api/v1/partners/campaigns/$organization',
        );
        final decoded = jsonDecode(response.body);
        if (decoded is List && _current(generation, actor)) {
          payload['campaigns'] = decoded
              .whereType<Map>()
              .map(_map)
              .where((row) => campaigns.contains(_text(row['id'])))
              .toList(growable: false);
        }
      } on Object {
        // Keep the valid owner rows already acquired.
      }
    }
  }

  static Map<String, dynamic> _map(Object? value) => value is Map
      ? value.map((key, value) => MapEntry(key.toString(), value))
      : {};
  static List<Map<String, dynamic>> _rows(Object? value) {
    final entries = value is Map ? value['items'] : value;
    return entries is List
        ? entries.whereType<Map>().map(_map).toList(growable: false)
        : const [];
  }

  static String _text(Object? value) => value == null ? '' : value.toString();
  static String _label(Map<String, dynamic> row) {
    final achievement = _map(row['achievement']);
    final reward = _map(row['reward']);
    for (final value in [
      row['name'],
      row['code'],
      row['reward_name'],
      row['display_name'],
      row['program_name'],
      row['plan_name'],
      achievement['name'],
      reward['name'],
      row['description'],
    ]) {
      if (_text(value).isNotEmpty) return _text(value);
    }
    return 'Élément disponible';
  }

  String? _action(Map<String, dynamic> row, String family, String name) {
    if (family != 'recognition' && family != 'loyalty') return null;
    if (SyncStatusScope.maybeOf(context)?.state == SyncVisualState.offline) {
      return null;
    }
    if (row['capabilities'] is! List ||
        !(row['capabilities'] as List).contains(name)) {
      return null;
    }
    final raw = _map(row['links'])[name];
    if (raw is! String) return null;
    final uri = Uri.tryParse(raw);
    if (uri == null ||
        uri.hasScheme ||
        uri.hasAuthority ||
        uri.hasQuery ||
        uri.hasFragment ||
        uri.pathSegments.contains('..')) {
      return null;
    }
    if (!uri.path.startsWith('/api/v1/$family/') ||
        !uri.path.endsWith('/')) {
      return null;
    }
    if (family == 'recognition') {
      if (_space) {
        final id = (_actor as SpaceActorContext).space.id;
        if (!uri.path.startsWith('/api/v1/recognition/spaces/$id/')) {
          return null;
        }
      } else if (uri.path.contains('/spaces/')) {
        return null;
      }
    }
    return uri.path.substring(1);
  }

  Future<void> _execute(
    Map<String, dynamic> row,
    String family,
    String action,
  ) async {
    final path = _action(row, family, action);
    if (path == null || _busy) return;
    final generation = _generation;
    final actor = _actor;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialog) => AlertDialog(
        title: Text(
          action == 'redeem'
              ? 'Utiliser cet avantage ?'
              : action == 'cancel'
              ? 'Annuler cette adhésion ?'
              : 'Confirmer la réponse ?',
        ),
        content: Text(_label(row)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialog, false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialog, true),
            child: const Text('Confirmer'),
          ),
        ],
      ),
    );
    if (confirmed != true || !_current(generation, actor)) return;
    final api = widget.runtime.api;
    if (api == null) return;
    final operation = '$family:${_text(row['id'])}:$action';
    final key = _pendingKeys.putIfAbsent(operation, () {
      final random = Random.secure();
      return List<int>.generate(
        16,
        (_) => random.nextInt(256),
      ).map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    });
    setState(() => _busy = true);
    try {
      await api.post(
        path,
        body: action == 'redeem' ? {'idempotency_key': key} : {},
      );
      if (!mounted || !_current(generation, actor)) return;
      _pendingKeys.remove(operation);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Réponse confirmée par le serveur.')),
      );
    } on MakoloApiError catch (error) {
      if (mounted && _current(generation, actor)) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.message)));
      }
    } on Object {
      if (mounted && _current(generation, actor)) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Résultat non confirmé. Vérifiez avant de réessayer.',
            ),
          ),
        );
      }
    } finally {
      if (mounted && _current(generation, actor)) {
        setState(() => _busy = false);
        unawaited(_refresh());
      }
    }
  }

  /// A family is an entry point, not an endless list. Detail stays folded
  /// until the participant explicitly wants it.
  @override
  Widget build(BuildContext context) {
    final offline =
        SyncStatusScope.maybeOf(context)?.state == SyncVisualState.offline;
    final hasRows = AppuisViewData.available(_snapshots, _space).isNotEmpty;
    return Scaffold(
      appBar: AppBar(
        title: Text(_space ? 'Nos appuis' : 'Mes appuis'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            icon: const Icon(Icons.refresh_outlined),
            onPressed: offline || _busy ? null : _refresh,
          ),
        ],
      ),
      body: _denied
          ? const Center(child: Text('Ces appuis ne sont plus accessibles.'))
          : _loading && !hasRows
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: offline ? () async {} : _refresh,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                children: [
                  if (offline)
                    const Padding(
                      padding: EdgeInsets.only(bottom: 16),
                      child: Text(
                        'Données conservées sur cet appareil. '
                        'Les droits seront revérifiés à la reconnexion.',
                      ),
                    ),
                  AppuisDashboard(
                    key: ValueKey('appuis:' + _scope),
                    snapshots: _snapshots,
                    space: _space,
                    actorKey: _scope,
                    busy: _busy,
                    onAction: _execute,
                    allowed: (row, family, action) =>
                        _action(row, family, action) != null,
                  ),
                  for (final family in families) ...[
                    if (_errors[family] case final error?)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Text(
                          error,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ),
                  ],
                  if (!hasRows && !_busy && _errors.isEmpty)
                    const Center(
                      child: Padding(
                        padding: EdgeInsets.symmetric(vertical: 24),
                        child: Text('Aucun appui disponible pour le moment.'),
                      ),
                    ),
                ],
              ),
            ),
    );
  }
}
