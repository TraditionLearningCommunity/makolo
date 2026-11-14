import 'dart:async';

import 'package:flutter/material.dart';

/// Direct Recognition spending: no categories-as-pages or synthetic wallet.
///
/// The owner projection already filters rewards; the server revalidates every
/// spend. A disabled withdrawal is only shown with a confirmed value.
class AppuisCreditsUseScreen extends StatefulWidget {
  const AppuisCreditsUseScreen({
    super.key,
    required this.initial,
    required this.space,
    required this.canSpend,
    required this.canUseReward,
    required this.onRedeem,
    required this.onReload,
    this.actorChanges,
    this.actorIsCurrent,
  });

  final Map<String, dynamic> initial;
  final bool space;
  final bool Function() canSpend;
  final bool Function(Map<String, dynamic>) canUseReward;
  final Future<Map<String, dynamic>?> Function(Map<String, dynamic>) onRedeem;
  final Future<Map<String, dynamic>?> Function() onReload;
  final Listenable? actorChanges;
  final bool Function()? actorIsCurrent;

  @override
  State<AppuisCreditsUseScreen> createState() => _AppuisCreditsUseScreenState();
}

class _AppuisCreditsUseScreenState extends State<AppuisCreditsUseScreen> {
  late Map<String, dynamic> _data;
  bool _working = false;
  bool _balanceUnverified = false;

  @override
  void initState() {
    super.initState();
    _data = widget.initial;
    widget.actorChanges?.addListener(_actorChanged);
  }

  @override
  void dispose() {
    widget.actorChanges?.removeListener(_actorChanged);
    super.dispose();
  }

  void _actorChanged() {
    if (widget.actorIsCurrent?.call() == false && mounted) {
      Navigator.of(context).maybePop();
    }
  }

  static Map<String, dynamic> _map(Object? value) => value is Map
      ? value.map((key, val) => MapEntry(key.toString(), val))
      : <String, dynamic>{};

  static List<Map<String, dynamic>> _rows(Object? value) {
    final list = value is Map ? value['items'] : value;
    return list is List
        ? list.whereType<Map>().map(_map).toList(growable: false)
        : const <Map<String, dynamic>>[];
  }

  static String _text(Object? value) => value?.toString() ?? '';

  static bool _positive(Object? value) {
    if (value is num) return value > 0;
    return (num.tryParse(_text(value).replaceAll(',', '.')) ?? 0) > 0;
  }

  bool get _current => widget.actorIsCurrent?.call() ?? true;

  Map<String, dynamic> get _summary => _map(_data['summary']);

  List<Map<String, dynamic>> get _rewards => _rows(_data['rewards'])
      .where(
        (reward) =>
            reward['kind'] != 'payout' && reward['self_eligible'] == true,
      )
      .toList(growable: false);

  Map<String, dynamic> get _money {
    final equivalence = _map(_data['monetary_equivalent']);
    final amount = _text(equivalence['amount']);
    final currency = _text(equivalence['currency']);
    if (currency.length != 3 ||
        !RegExp(r'^[A-Z]{3}$').hasMatch(currency) ||
        !_positive(amount)) {
      return const <String, dynamic>{};
    }
    return equivalence;
  }

  String _category(Map<String, dynamic> reward) =>
      _text(_map(reward['presentation'])['category']);

  String _action(Map<String, dynamic> reward) {
    final label = _text(_map(reward['presentation'])['action']);
    return label == 'Activer' || label == 'Débloquer' || label == 'Utiliser'
        ? label
        : 'Utiliser';
  }

  bool _authorized(Map<String, dynamic> reward) =>
      !_working &&
      _current &&
      widget.canSpend() &&
      widget.canUseReward(reward) &&
      _positive(_summary['available_credits']) &&
      (num.tryParse(_text(reward['points_cost'])) ?? double.infinity) <=
          (num.tryParse(_text(_summary['available_credits'])) ?? 0);

  Future<void> _use(Map<String, dynamic> reward) async {
    if (!_authorized(reward)) return;
    final cost = _text(reward['points_cost']);
    final name = _text(reward['name']);
    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      showDragHandle: true,
      builder: (sheet) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 6, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                _action(reward) + ' cet avantage ?',
                style: Theme.of(sheet).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(name),
              const SizedBox(height: 5),
              Text(
                '$cost crédits',
                style: TextStyle(
                  color: Theme.of(sheet).colorScheme.primary,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 18),
              FilledButton(
                onPressed: () => Navigator.pop(sheet, true),
                child: const Text('Confirmer'),
              ),
              TextButton(
                onPressed: () => Navigator.pop(sheet, false),
                child: const Text('Annuler'),
              ),
            ],
          ),
        ),
      ),
    );
    if (confirmed != true || !mounted || !_authorized(reward)) return;
    setState(() => _working = true);
    try {
      final response = await widget.onRedeem(reward);
      if (!mounted || !_current || response == null) return;
      // A committed spend invalidates the old amount until an owner GET.
      setState(() => _balanceUnverified = true);
      final refreshed = await widget.onReload();
      if (!mounted || !_current) return;
      if (refreshed != null) {
        setState(() {
          _data = refreshed;
          _balanceUnverified = false;
        });
      }
      final fulfilled = _text(response['status']) == 'fulfilled';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            fulfilled ? 'Avantage activé.' : 'Demande enregistrée.',
          ),
        ),
      );
    } finally {
      if (mounted && _current) setState(() => _working = false);
    }
  }

  Widget _rewardCard(Map<String, dynamic> reward) {
    final colors = Theme.of(context).colorScheme;
    final presentation = _map(reward['presentation']);
    final duration = presentation['duration_days'];
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(17),
        side: BorderSide(color: colors.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(13),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: colors.primaryContainer,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(
                _category(reward) == 'subscription'
                    ? Icons.workspace_premium_outlined
                    : _category(reward) == 'feature'
                    ? Icons.lock_open_outlined
                    : Icons.card_giftcard_outlined,
                color: colors.onPrimaryContainer,
              ),
            ),
            const SizedBox(width: 11),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _text(reward['name']),
                    style: Theme.of(context).textTheme.titleSmall
                        ?.copyWith(fontWeight: FontWeight.w700),
                  ),
                  if (_text(reward['description']).isNotEmpty) ...[
                    const SizedBox(height: 3),
                    Text(
                      _text(reward['description']),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                  if (duration is int && duration > 0)
                    Text(
                      '$duration jours',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  const SizedBox(height: 5),
                  Text(
                    '${_text(reward['points_cost'])} crédits',
                    style: TextStyle(
                      color: colors.primary,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 6),
            TextButton(
              onPressed: _authorized(reward) ? () => _use(reward) : null,
              child: Text(_action(reward)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _group(String title, List<Map<String, dynamic>> items) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(2, 22, 2, 9),
          child: Text(
            title,
            style: Theme.of(context).textTheme.titleLarge
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
        ),
        for (final reward in items) _rewardCard(reward),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    if (!_current) return const SizedBox.shrink();
    final rewards = _rewards;
    final subscriptions = rewards
        .where((row) => _category(row) == 'subscription')
        .toList();
    final features = rewards
        .where((row) => _category(row) == 'feature')
        .toList();
    final others = rewards
        .where(
          (row) =>
              _category(row) != 'feature' && _category(row) != 'subscription',
        )
        .toList();
    final money = _money;
    final color = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.space ? 'Utiliser nos crédits' : 'Utiliser mes crédits',
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 10, 16, 32),
        children: [
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF5232DB), Color(0xFF2B176E)],
              ),
              borderRadius: BorderRadius.circular(19),
            ),
            child: Row(
              children: [
                const Icon(
                  Icons.toll_outlined,
                  color: Color(0xFFF4D98A),
                  size: 28,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    _balanceUnverified
                        ? 'Crédits à confirmer'
                        : '${_text(_summary['available_credits'])} crédits',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (money.isNotEmpty && !_balanceUnverified) ...[
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(15),
              decoration: BoxDecoration(
                border: Border.all(color: color.outlineVariant),
                borderRadius: BorderRadius.circular(17),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Valeur en argent',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const SizedBox(height: 3),
                        Text(
                          '${_text(money['amount'])} ${_text(money['currency'])}',
                          style: Theme.of(context).textTheme.titleLarge
                              ?.copyWith(fontWeight: FontWeight.w800),
                        ),
                      ],
                    ),
                  ),
                  const OutlinedButton(onPressed: null, child: Text('Retirer')),
                ],
              ),
            ),
          ],
          _group('Abonnements', subscriptions),
          _group('Fonctionnalités', features),
          _group('Autres avantages', others),
          if (rewards.isEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 24),
              child: Text(
                'Aucune récompense disponible pour le moment.',
                style: TextStyle(color: color.onSurfaceVariant),
              ),
            ),
        ],
      ),
    );
  }
}
