import 'dart:async';

import 'package:flutter/material.dart';

/// Detail of a Loyalty owner program, shared between Profile and Space.
///
/// The overview is immediately readable from its actor-scoped snapshot;
/// optional details are fetched from the owner without blocking the page.
class AppuisProgramDepth extends StatefulWidget {
  const AppuisProgramDepth({
    super.key,
    required this.programId,
    required this.initialProgram,
    required this.loyalty,
    required this.space,
    required this.onReadProgram,
    required this.onAction,
    required this.allowed,
    required this.onCreateSpaceItem,
    required this.canMutate,
  });

  final String programId;
  final Map<String, dynamic> initialProgram;
  final Map<String, dynamic> loyalty;
  final bool space;
  final Future<Map<String, dynamic>?> Function(String programId) onReadProgram;
  final Future<void> Function(Map<String, dynamic>, String, String) onAction;
  final bool Function(Map<String, dynamic>, String, String) allowed;
  final Future<bool> Function(
    Map<String, dynamic>,
    String,
    Map<String, dynamic>,
  )
  onCreateSpaceItem;
  final bool canMutate;

  @override
  State<AppuisProgramDepth> createState() => _AppuisProgramDepthState();
}

class _AppuisProgramDepthState extends State<AppuisProgramDepth> {
  Map<String, dynamic> _owner = {};
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  static Map<String, dynamic> _map(Object? value) => value is Map
      ? value.map((k, v) => MapEntry(k.toString(), v))
      : <String, dynamic>{};

  static List<Map<String, dynamic>> _rows(Object? value) {
    final raw = value is Map ? value['items'] : value;
    return raw is List
        ? raw.whereType<Map>().map(_map).toList(growable: false)
        : const <Map<String, dynamic>>[];
  }

  static String _text(Object? value) => value?.toString() ?? '';

  static bool _positive(Object? value) {
    if (value is num) return value > 0;
    return (num.tryParse(_text(value).replaceAll(',', '.')) ?? 0) > 0;
  }

  Map<String, dynamic> get _program {
    final verified = _map(_owner['program']);
    return verified.isNotEmpty ? verified : widget.initialProgram;
  }

  List<Map<String, dynamic>> get _memberships {
    final matching = _rows(widget.loyalty['memberships'])
        .where((row) => _text(row['program']) == widget.programId)
        .toList();
    final owner = _map(_owner['my_membership']);
    if (owner.isNotEmpty &&
        !matching.any((row) => _text(row['id']) == _text(owner['id']))) {
      matching.insert(0, owner);
    }
    return matching;
  }

  Future<void> _load() async {
    final response = await widget.onReadProgram(widget.programId);
    if (mounted && response != null) setState(() => _owner = response);
  }

  String _date(Object? value) {
    final date = DateTime.tryParse(_text(value));
    if (date == null) return '';
    return MaterialLocalizations.of(context).formatMediumDate(date.toLocal());
  }

  String _status(Object? value) => switch (_text(value)) {
    'active' => 'Active',
    'pending' => 'En attente',
    'cancelled' => 'Annulée',
    'expired' => 'Expirée',
    _ => _text(value),
  };

  Widget _card(
    IconData icon,
    String title, {
    String detail = '',
    String note = '',
    Widget? action,
    VoidCallback? open,
  }) {
    final colors = Theme.of(context).colorScheme;
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 9),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: colors.outlineVariant),
      ),
      clipBehavior: Clip.antiAlias,
      child: ListTile(
        onTap: open,
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        leading: Container(
          width: 43,
          height: 43,
          decoration: BoxDecoration(
            color: colors.primaryContainer,
            borderRadius: BorderRadius.circular(13),
          ),
          child: Icon(icon, color: colors.onPrimaryContainer, size: 22),
        ),
        title: Text(
          title,
          style: Theme.of(context).textTheme.titleSmall
              ?.copyWith(fontWeight: FontWeight.w700),
        ),
        subtitle: detail.trim().isEmpty && note.trim().isEmpty
            ? null
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (detail.trim().isNotEmpty) Text(detail),
                  if (note.trim().isNotEmpty)
                    Text(note, style: TextStyle(color: colors.primary)),
                ],
              ),
        trailing:
            action ??
            (open == null
                ? null
                : Icon(Icons.chevron_right_rounded, color: colors.primary)),
      ),
    );
  }

  Widget _heading(String title, {VoidCallback? create}) => Padding(
    padding: const EdgeInsets.fromLTRB(2, 22, 2, 10),
    child: Row(
      children: [
        Expanded(
          child: Text(
            title,
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
        ),
        if (create != null)
          TextButton.icon(
            onPressed: widget.canMutate && !_saving ? create : null,
            icon: const Icon(Icons.add, size: 18),
            label: const Text('Ajouter'),
          ),
      ],
    ),
  );

  String _planPrice(Map<String, dynamic> plan) {
    if (plan['is_free'] == true || !_positive(plan['price'])) return 'Gratuite';
    return _text(plan['price']) + ' ' + _text(plan['currency']);
  }

  String _planDetail(Map<String, dynamic> plan) {
    final details = [
      _planPrice(plan),
      if (_positive(plan['duration_days']))
        'Durée : ' + _text(plan['duration_days']) + ' jours',
      if (_text(plan['description']).isNotEmpty) _text(plan['description']),
      if (_text(plan['benefits']).isNotEmpty) _text(plan['benefits']),
    ];
    return details.join(' · ');
  }

  void _memberDetail(Map<String, dynamic> membership) {
    final plans = _rows(_program['membership_plans']);
    final plan = plans
        .where((p) => _text(p['id']) == _text(membership['plan']))
        .firstOrNull;
    final planName = _text(membership['plan_name']);
    final status = _status(membership['status']);
    final start = _date(membership['starts_at']);
    final end = _date(membership['ends_at']);
    final infos = [
      if (status.isNotEmpty) status,
      if (start.isNotEmpty) 'Depuis le ' + start,
      if (end.isNotEmpty) 'Jusqu’au ' + end,
      if (plan != null && _text(plan['benefits']).isNotEmpty)
        _text(plan['benefits']),
    ];
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (sheet) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                planName.isEmpty ? 'Mon adhésion' : planName,
                style: Theme.of(sheet).textTheme.titleLarge,
              ),
              const SizedBox(height: 10),
              for (final info in infos)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(info),
                ),
              if (widget.canMutate &&
                  widget.allowed(membership, 'loyalty', 'cancel')) ...[
                const Divider(height: 28),
                TextButton(
                  onPressed: () {
                    Navigator.pop(sheet);
                    Navigator.of(context).pop();
                    unawaited(widget.onAction(membership, 'loyalty', 'cancel'));
                  },
                  child: const Text('Mettre fin à cette adhésion'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  void _join(Map<String, dynamic> plan) {
    if (!widget.canMutate || !widget.allowed(plan, 'loyalty', 'join')) return;
    Navigator.pop(context);
    unawaited(widget.onAction(plan, 'loyalty', 'join'));
  }

  bool _canCreate(String action) {
    final capabilities = _owner['capabilities'];
    return widget.space &&
        capabilities is List &&
        capabilities.contains(action) &&
        _map(_owner['links'])[action] is String;
  }

  String _generatedCode(String name) {
    final compact = name
        .toUpperCase()
        .replaceAll(RegExp(r'[^A-Z0-9]+'), '_')
        .replaceAll(RegExp(r'^_|_$'), '');
    final prefix = compact.isEmpty ? 'APPUI' : compact;
    final stamp = DateTime.now().microsecondsSinceEpoch.toRadixString(36);
    final length = prefix.length > 25 ? 25 : prefix.length;
    return prefix.substring(0, length) + '_' + stamp;
  }

  Future<void> _add(String kind) async {
    if (!_canCreate(kind) || !widget.canMutate) return;
    final title = TextEditingController();
    final value = TextEditingController();
    final benefits = TextEditingController();
    final label = switch (kind) {
      'create_tier' => 'Ajouter un niveau',
      'create_plan' => 'Ajouter une formule gratuite',
      _ => 'Ajouter une récompense',
    };
    try {
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (sheet) => Padding(
          padding: EdgeInsets.fromLTRB(
            20,
            8,
            20,
            MediaQuery.viewInsetsOf(sheet).bottom + 24,
          ),
          child: SafeArea(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(label, style: Theme.of(sheet).textTheme.titleLarge),
                const SizedBox(height: 16),
                TextField(
                  controller: title,
                  maxLength: 120,
                  decoration: const InputDecoration(
                    labelText: 'Nom',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 8),
                if (kind != 'create_plan') ...[
                  TextField(
                    controller: value,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(
                      labelText: kind == 'create_tier'
                          ? 'Points requis'
                          : 'Coût en points',
                      border: const OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                ],
                TextField(
                  controller: benefits,
                  maxLines: 2,
                  maxLength: 500,
                  decoration: InputDecoration(
                    labelText: kind == 'create_reward'
                        ? 'Description (facultative)'
                        : 'Avantages (facultatif)',
                    border: const OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 8),
                FilledButton(
                  onPressed: _saving
                      ? null
                      : () async {
                          final name = title.text.trim();
                          final points = int.tryParse(value.text.trim());
                          if (name.isEmpty ||
                              (kind != 'create_plan' &&
                                  (points == null ||
                                      points <
                                          (kind == 'create_tier' ? 0 : 1)))) {
                            ScaffoldMessenger.of(sheet).showSnackBar(
                              const SnackBar(
                                content: Text('Vérifiez le nom et les points.'),
                              ),
                            );
                            return;
                          }
                          final body = <String, dynamic>{
                            'program_id': widget.programId,
                            'name': name,
                            'code': _generatedCode(name),
                            if (kind == 'create_tier')
                              'threshold_points': points,
                            if (kind == 'create_plan') 'price': '0.00',
                            if (kind == 'create_reward') 'points_cost': points,
                            if (kind == 'create_reward')
                              'description': benefits.text.trim(),
                            if (kind != 'create_reward')
                              'benefits': benefits.text.trim(),
                          };
                          setState(() => _saving = true);
                          final accepted = await widget.onCreateSpaceItem(
                            _owner,
                            kind,
                            body,
                          );
                          if (!mounted) return;
                          setState(() => _saving = false);
                          if (!accepted) return;
                          if (sheet.mounted) Navigator.pop(sheet);
                          await _load();
                        },
                  child: const Text('Ajouter'),
                ),
              ],
            ),
          ),
        ),
      );
    } finally {
      title.dispose();
      value.dispose();
      benefits.dispose();
    }
  }

  @override
  Widget build(BuildContext context) {
    final program = _program;
    final memberships = _memberships;
    final tiers = _rows(program['tiers'])
        .where((row) => row['is_active'] != false)
        .toList();
    final plans = _rows(program['membership_plans'])
        .where((row) => row['is_active'] != false)
        .toList();
    final rewards = _rows(program['rewards'])
        .where((row) => row['is_active'] != false)
        .toList();
    final activeMembership = memberships.any(
      (row) => row['status'] == 'active' || row['status'] == 'pending',
    );
    final name = _text(program['name'] ?? program['program_name']);
    final organization = _text(program['organization_name']);
    final account = _rows(widget.loyalty['accounts'])
        .where((row) => _text(row['program']) == widget.programId)
        .firstOrNull;
    final balance = account?['points_balance'];
    final tier = _text(_map(account?['current_tier'])['name']);
    return Scaffold(
      appBar: AppBar(
        title: Text(
          name.isEmpty ? 'Fidélité' : name,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
        children: [
          _card(
            Icons.card_giftcard_outlined,
            name.isEmpty ? 'Programme de fidélité' : name,
            detail: _text(program['description']).isNotEmpty
                ? _text(program['description'])
                : (organization.isNotEmpty
                      ? organization
                      : 'Niveaux, formules et avantages'),
            note: [
              if (_positive(balance)) _text(balance) + ' points',
              if (tier.isNotEmpty) tier,
            ].join(' · '),
          ),
          if (memberships.isNotEmpty) ...[
            _heading(widget.space ? 'Adhésions' : 'Mon adhésion'),
            for (final membership in memberships)
              _card(
                Icons.card_membership_outlined,
                _text(membership['plan_name']).isNotEmpty
                    ? _text(membership['plan_name'])
                    : 'Adhésion',
                detail: _status(membership['status']),
                note: _date(membership['ends_at']).isNotEmpty
                    ? 'Jusqu’au ' + _date(membership['ends_at'])
                    : '',
                open: widget.space ? null : () => _memberDetail(membership),
              ),
          ],
          if (tiers.isNotEmpty || _canCreate('create_tier')) ...[
            _heading(
              'Niveaux',
              create: _canCreate('create_tier')
                  ? () => _add('create_tier')
                  : null,
            ),
            for (final item in tiers)
              _card(
                Icons.layers_outlined,
                _text(item['name']),
                detail: [
                  if (_positive(item['threshold_points']))
                    'Dès ' + _text(item['threshold_points']) + ' points',
                  if (_text(item['benefits']).isNotEmpty)
                    _text(item['benefits']),
                ].join(' · '),
              ),
          ],
          if (plans.isNotEmpty || _canCreate('create_plan')) ...[
            _heading(
              'Formules',
              create: _canCreate('create_plan')
                  ? () => _add('create_plan')
                  : null,
            ),
            for (final item in plans)
              _card(
                Icons.card_membership_outlined,
                _text(item['name']),
                detail: _planDetail(item),
                action:
                    !widget.space &&
                        !activeMembership &&
                        widget.canMutate &&
                        widget.allowed(item, 'loyalty', 'join')
                    ? TextButton(
                        onPressed: () => _join(item),
                        child: const Text('Rejoindre'),
                      )
                    : null,
              ),
          ],
          if (rewards.isNotEmpty || _canCreate('create_reward')) ...[
            _heading(
              'Récompenses',
              create: _canCreate('create_reward')
                  ? () => _add('create_reward')
                  : null,
            ),
            for (final item in rewards)
              _card(
                Icons.redeem_outlined,
                _text(item['name']),
                detail: [
                  if (_positive(item['points_cost']))
                    _text(item['points_cost']) +
                        ' ' +
                        _text(program['points_name']).trim(),
                  if (_text(item['description']).isNotEmpty)
                    _text(item['description']),
                  if (_text(item['fulfillment_instructions']).isNotEmpty)
                    _text(item['fulfillment_instructions']),
                ].join(' · '),
              ),
          ],
          if (account != null) ...[finalHistory(account)],
        ],
      ),
    );
  }

  Widget finalHistory(Map<String, dynamic> account) {
    final entries = _rows(account['recent_activity']);
    if (entries.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _heading('Mouvements'),
        for (final entry in entries)
          _card(
            Icons.history_outlined,
            _text(entry['description']).isEmpty
                ? 'Mouvement'
                : _text(entry['description']),
            detail: [
              if (_text(entry['kind']).isNotEmpty) _text(entry['kind']),
              if (_positive(entry['points_delta']))
                '+' + _text(entry['points_delta']) + ' points',
            ].join(' · '),
          ),
      ],
    );
  }
}
