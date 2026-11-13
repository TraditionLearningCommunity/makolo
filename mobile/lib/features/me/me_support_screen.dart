import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';
import '../../app/runtime/actor_context.dart';
import '../../data/local/profile_store.dart';
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
  bool _showAllPrograms = false;
  StreamSubscription<OwnerSourceState>? _personalSource;

  String get _scope => _actor is SpaceActorContext
      ? 'space:' + (_actor as SpaceActorContext).space.id
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
    _showAllPrograms = false;
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
                'appuis.' + family,
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
        'recognition' => 'api/v1/recognition/spaces/' + space.id + '/',
        'loyalty' =>
          'api/v1/loyalty/organizations/' +
              Uri.encodeComponent(space.slug) +
              '/',
        'partners' =>
          'api/v1/partners/partners/?organization=' +
              Uri.encodeQueryComponent(space.id),
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
      if (!_current(generation, actor)) return;
      if (!authorized) {
        for (final family in families) {
          await store.deleteProjection('appuis.' + family, resourceKey: _scope);
        }
        if (_current(generation, actor)) {
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
          'appuis.' + family,
          resourceKey: _scope,
        );
        if (!_current(generation, actor)) return;
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
        !_current(generation, actor))
      return;
    setState(() => _busy = true);
    try {
      for (final family in families) {
        if (!_current(generation, actor)) break;
        try {
          final response = await api.get(_path(family, actor));
          if (!_current(generation, actor)) return;
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
          if (!_current(generation, actor)) return;
          await store.putProjection(
            kind: 'appuis.' + family,
            resourceKey: _scope,
            schemaVersion: 1,
            payload: _cacheSafe(payload),
            lastVerifiedOnlineAt: DateTime.now().toUtc(),
            freshnessPolicyId: 'swr',
          );
          if (!_current(generation, actor)) return;
          setState(() {
            _snapshots[family] = payload;
            _errors.remove(family);
          });
        } on MakoloApiError catch (error) {
          if (!_current(generation, actor)) return;
          if (error.statusCode == 401 ||
              error.statusCode == 403 ||
              error.statusCode == 404) {
            await store.deleteProjection(
              'appuis.' + family,
              resourceKey: _scope,
            );
            if (!_current(generation, actor)) return;
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
          if (_current(generation, actor)) {
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
        ? '?organization=' + Uri.encodeQueryComponent(actor.space.id)
        : '';
    for (final family in ['codes', 'commissions', 'payouts']) {
      if (!_current(generation, actor)) return;
      try {
        final response = await api.get(
          'api/v1/partners/' + family + '/' + organization,
        );
        if (!_current(generation, actor)) return;
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
          'api/v1/partners/campaigns/' + organization,
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
        !(row['capabilities'] as List).contains(name))
      return null;
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
    if (!uri.path.startsWith('/api/v1/' + family + '/') ||
        !uri.path.endsWith('/'))
      return null;
    if (family == 'recognition') {
      if (_space) {
        final id = (_actor as SpaceActorContext).space.id;
        if (!uri.path.startsWith('/api/v1/recognition/spaces/' + id + '/'))
          return null;
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
    final operation = family + ':' + _text(row['id']) + ':' + action;
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
      if (!_current(generation, actor)) return;
      _pendingKeys.remove(operation);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Réponse confirmée par le serveur.')),
      );
    } on MakoloApiError catch (error) {
      if (_current(generation, actor)) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.message)));
      }
    } on Object {
      if (_current(generation, actor)) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Résultat non confirmé. Vérifiez avant de réessayer.',
            ),
          ),
        );
      }
    } finally {
      if (_current(generation, actor)) {
        setState(() => _busy = false);
        unawaited(_refresh());
      }
    }
  }


  /// A family is an entry point, not an endless list. Detail stays folded
  /// until the participant explicitly wants it.
  Widget _section(
    String family,
    String title,
    Object? source, {
    String Function(Map<String, dynamic>)? details,
    bool actions = false,
    IconData icon = Icons.list_alt_outlined,
  }) {
    final rows = _rows(source);
    if (rows.isEmpty) return const SizedBox.shrink();
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        key: PageStorageKey<String>('appuis:' + _scope + ':' + family + ':' + title),
        leading: Icon(icon, color: Theme.of(context).colorScheme.primary),
        title: Text(title, style: Theme.of(context).textTheme.titleSmall),
        subtitle: Text(rows.length == 1 ? '1 élément' : rows.length.toString() + ' éléments'),
        children: [
          for (final row in rows)
            ListTile(
              dense: true,
              title: Text(_label(row), maxLines: 2, overflow: TextOverflow.ellipsis),
              subtitle: () {
                final detail = details?.call(row) ??
                    _text(row['status_label'] ?? row['description'] ??
                        row['status'] ?? row['created_at']);
                return detail.trim().isEmpty ? null : Text(
                  detail, maxLines: 2, overflow: TextOverflow.ellipsis,
                );
              }(),
              trailing: actions ? Wrap(
                spacing: 0,
                children: [
                  for (final command in ['accept', 'decline', 'redeem', 'cancel'])
                    if (_action(row, family, command) != null)
                      TextButton(
                        onPressed: _busy ? null : () => _execute(row, family, command),
                        child: Text(switch (command) {
                          'accept' => 'Accepter',
                          'decline' => 'Refuser',
                          'cancel' => 'Annuler',
                          _ => 'Utiliser',
                        }),
                      ),
                ],
              ) : null,
            ),
        ],
      ),
    );
  }

  static bool _positive(Object? value) {
    if (value is num) return value > 0;
    return (num.tryParse(_text(value).replaceAll(',', '.')) ?? 0) > 0;
  }

  static String _programId(Map<String, dynamic> row) {
    final program = row['program'];
    return _text(program is Map ? program['id'] : program);
  }

  Widget _heading(String label, IconData symbol) => Padding(
    padding: const EdgeInsets.fromLTRB(4, 18, 4, 12),
    child: Row(children: [
      Icon(symbol, size: 22, color: Theme.of(context).colorScheme.primary),
      const SizedBox(width: 10),
      Expanded(child: Text(label,
          style: Theme.of(context).textTheme.titleLarge)),
    ]),
  );

  /// One card per Loyalty program, even when the owner has several rows.
  /// A zero balance is not promoted to a metric. Details are on demand.
  Widget _personalLoyalty(Map<String, dynamic> data) {
    final accounts = _rows(data['accounts']);
    final memberships = _rows(data['memberships']);
    final rewards = _rows(data['available_rewards']);
    final history = _rows(data['rewards']);
    final keys = <String>{};
    for (final row in [...accounts, ...memberships, ...rewards]) {
      final id = _programId(row);
      if (id.isNotEmpty) keys.add(id);
    }
    final cards = <Widget>[];
    for (final id in keys) {
      final owned = accounts.where((row) => _programId(row) == id).toList();
      final joined = memberships.where((row) => _programId(row) == id).toList();
      final available = rewards.where((row) => _programId(row) == id).toList();
      final account = owned.isNotEmpty ? owned.first : <String, dynamic>{};
      final membership = joined.isNotEmpty ? joined.first : <String, dynamic>{};
      final reward = available.isNotEmpty ? available.first : <String, dynamic>{};
      final organization = _text(account['organization_name'] ??
          membership['organization_name'] ??
          _map(reward['organization'])['name']);
      final programName = _text(account['program_name']);
      final balance = account['points_balance'];
      final tier = _text(_map(account['current_tier'])['name']);
      final unit = _text(account['points_name']);
      final details = [
        if (_positive(balance))
          _text(balance) + (unit.isEmpty ? ' points' : ' ' + unit),
        if (tier.isNotEmpty) tier,
        if (available.isNotEmpty)
          available.length.toString() + ' avantage' +
              (available.length == 1 ? '' : 's') + ' disponible' +
              (available.length == 1 ? '' : 's'),
      ];
      cards.add(Card(
        margin: const EdgeInsets.only(bottom: 10),
        clipBehavior: Clip.antiAlias,
        child: ExpansionTile(
          key: PageStorageKey<String>('loyalty:' + _scope + ':' + id),
          leading: CircleAvatar(
            backgroundColor: Theme.of(context).colorScheme.primaryContainer,
            child: Icon(Icons.card_giftcard_outlined,
                color: Theme.of(context).colorScheme.onPrimaryContainer),
          ),
          title: Text(programName.isNotEmpty ? programName :
              (organization.isEmpty ? 'Programme de fidélité' : organization),
              maxLines: 2, overflow: TextOverflow.ellipsis),
          subtitle: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (programName.isNotEmpty && organization.isNotEmpty)
                Text(organization, maxLines: 1, overflow: TextOverflow.ellipsis),
              if (details.isNotEmpty)
                Text(details.join(' · '), maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.primary,
                    )),
            ],
          ),
          children: [
            for (final row in joined)
              ListTile(
                dense: true,
                leading: const Icon(Icons.verified_outlined),
                title: Text(_text(row['plan_name']).isEmpty
                    ? 'Adhésion' : _text(row['plan_name'])),
                subtitle: Text(_text(row['status'])),
                trailing: _action(row, 'loyalty', 'cancel') == null
                    ? null : TextButton(
                      onPressed: _busy ? null :
                          () => _execute(row, 'loyalty', 'cancel'),
                      child: const Text('Annuler'),
                    ),
              ),
            for (final row in available)
              ListTile(
                dense: true,
                leading: const Icon(Icons.redeem_outlined),
                title: Text(_label(row)),
                subtitle: _positive(row['points_cost'])
                    ? Text(_text(row['points_cost']) + ' ' +
                        _text(row['points_name'])) : null,
                trailing: _action(row, 'loyalty', 'redeem') == null
                    ? null : TextButton(
                      onPressed: _busy ? null :
                          () => _execute(row, 'loyalty', 'redeem'),
                      child: const Text('Utiliser'),
                    ),
              ),
            for (final row in owned)
              for (final movement in _rows(row['recent_activity']))
                ListTile(
                  dense: true,
                  leading: const Icon(Icons.history_outlined),
                  title: Text(_text(movement['description']).isEmpty
                      ? 'Mouvement' : _text(movement['description'])),
                  trailing: _positive(movement['points_delta'])
                      ? Text('+' + _text(movement['points_delta'])) : null,
                ),
          ],
        ),
      ));
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (cards.isNotEmpty) _heading('Fidélité', Icons.loyalty_outlined),
      ...(_showAllPrograms ? cards : cards.take(3)),
      if (cards.length > 3)
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            icon: Icon(_showAllPrograms
                ? Icons.expand_less_rounded : Icons.expand_more_rounded),
            onPressed: () => setState(() {
              _showAllPrograms = !_showAllPrograms;
            }),
            label: Text(_showAllPrograms ? 'Voir moins' :
                'Voir les ' + cards.length.toString() + ' programmes'),
          ),
        ),
      _section('loyalty', 'Récompenses obtenues', history,
          icon: Icons.workspace_premium_outlined),
    ]);
  }

  Widget _family(String family, Map<String, dynamic> data) {
    final account = _map(data['account']);
    final program = _map(data['program']);
    final relationships = _rows(data['relationships']);
    if (family == 'loyalty' && !_space) {
      return _personalLoyalty(data);
    }
    if (family == 'recognition') {
      final credits = _map(data['summary'])['available_credits'];
      final visible = account.isNotEmpty ||
          _rows(data['incoming']).isNotEmpty ||
          _rows(data['benefits_received']).isNotEmpty ||
          _rows(data['achievements']).isNotEmpty;
      if (!visible) return const SizedBox.shrink();
      return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        _heading('Reconnaissance', Icons.workspace_premium_outlined),
        if (_positive(credits))
          Card(child: ListTile(
            leading: const Icon(Icons.stars_outlined),
            title: Text(_text(credits) + ' crédits disponibles'),
          )),
        _section(family, 'Réponses attendues', data['incoming'],
            actions: true, icon: Icons.mark_email_unread_outlined),
        _section(family, 'Récompenses', data['rewards'],
            details: (row) => _positive(row['points_cost'])
                ? _text(row['points_cost']) + ' crédits' : '',
            actions: true, icon: Icons.redeem_outlined),
        _section(family, 'Contributions reconnues', data['achievements'],
            icon: Icons.military_tech_outlined),
        _section(family, 'Avantages reçus', data['benefits_received'],
            icon: Icons.card_giftcard_outlined),
        _section(family, 'Utilisations', data['redemptions'],
            icon: Icons.check_circle_outline),
        _section(family, 'Mouvements', data['recent_activity'],
            icon: Icons.history_outlined),
      ]);
    }
    if (family == 'loyalty') {
      if (program.isEmpty) return const SizedBox.shrink();
      return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        _heading('Fidélité', Icons.loyalty_outlined),
        Card(child: ListTile(
          leading: const Icon(Icons.storefront_outlined),
          title: Text(_text(program['name'])),
          subtitle: const Text('Programme de cet Espace'),
        )),
        _section(family, 'Niveaux', program['tiers'], icon: Icons.layers_outlined),
        _section(family, 'Formules', program['membership_plans'],
            icon: Icons.card_membership_outlined),
        _section(family, 'Avantages proposés', program['rewards'],
            icon: Icons.redeem_outlined),
      ]);
    }
    if (relationships.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _heading('Partenariats', Icons.handshake_outlined),
      _section(family, 'Relations', relationships,
          icon: Icons.people_outline),
      _section(family, 'Campagnes', data['campaigns'],
          icon: Icons.campaign_outlined),
      _section(family, 'Codes de parrainage', data['codes'],
          icon: Icons.qr_code_outlined),
      _section(family, 'Commissions', data['commissions'],
          icon: Icons.receipt_long_outlined),
      _section(family, 'Versements', data['payouts'],
          icon: Icons.payments_outlined),
    ]);
  }

  bool _hasVisible(String family, Map<String, dynamic> data) {
    if (family == 'recognition') {
      return _map(data['account']).isNotEmpty ||
          _rows(data['incoming']).isNotEmpty ||
          _rows(data['benefits_received']).isNotEmpty ||
          _rows(data['achievements']).isNotEmpty;
    }
    if (family == 'loyalty') {
      return _space ? _map(data['program']).isNotEmpty :
          _rows(data['accounts']).isNotEmpty ||
          _rows(data['memberships']).isNotEmpty ||
          _rows(data['available_rewards']).isNotEmpty ||
          _rows(data['rewards']).isNotEmpty;
    }
    return _rows(data['relationships']).isNotEmpty;
  }

  @override
  Widget build(BuildContext context) {
    final offline =
        SyncStatusScope.maybeOf(context)?.state == SyncVisualState.offline;
    final hasRows = families.any((family) =>
        _snapshots[family] != null &&
        _hasVisible(family, _snapshots[family]!));
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
                  for (final family in families) ...[
                    if (_snapshots[family] case final data?)
                      _family(family, data),
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
                  if (!hasRows && !_busy)
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
