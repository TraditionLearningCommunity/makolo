import 'dart:async';

import 'package:flutter/material.dart';

/// The three owners remain authoritative: this is presentation only.
class AppuisViewData {
  const AppuisViewData._();

  static Map<String, dynamic> map(Object? value) => value is Map
      ? value.map((k, v) => MapEntry(k.toString(), v))
      : <String, dynamic>{};
  static List<Map<String, dynamic>> rows(Object? value) {
    final raw = value is Map ? value['items'] : value;
    return raw is List ? raw.whereType<Map>().map(map).toList() : [];
  }

  static String text(Object? value) => value?.toString() ?? '';
  static bool positive(Object? value) => value is num
      ? value > 0
      : (num.tryParse(text(value).replaceAll(',', '.')) ?? 0) > 0;
  static String programId(Map<String, dynamic> value) {
    final program = value['program'];
    return text(program is Map ? program['id'] : program);
  }

  static List<Map<String, dynamic>> programs(Map<String, dynamic> loyalty) {
    final grouped = <String, Map<String, dynamic>>{};
    for (final row in rows(loyalty['accounts'])) {
      final id = programId(row);
      if (id.isNotEmpty) grouped.putIfAbsent(id, () => row);
    }
    for (final row in [
      ...rows(loyalty['memberships']),
      ...rows(loyalty['available_rewards']),
    ]) {
      final id = programId(row);
      if (id.isNotEmpty)
        grouped.putIfAbsent(
          id,
          () => {
            'program': id,
            'program_name': '',
            'organization_name': text(
              row['organization_name'] ?? map(row['organization'])['name'],
            ),
          },
        );
    }
    return grouped.values.toList(growable: false);
  }

  static int availableRewardCount(
    Map<String, dynamic> loyalty,
    Map<String, dynamic> program,
  ) {
    final id = programId(program);
    if (id.isEmpty) return 0;
    return rows(loyalty['available_rewards'])
        .where((reward) => programId(reward) == id)
        .length;
  }

  static bool visible(String family, Map<String, dynamic> data, bool space) {
    if (family == 'loyalty') {
      return space
          ? map(data['program']).isNotEmpty
          : programs(data).isNotEmpty || rows(data['rewards']).isNotEmpty;
    }
    if (family == 'recognition') {
      return positive(map(data['summary'])['available_credits']) ||
          rows(data['incoming']).isNotEmpty ||
          rows(data['rewards']).isNotEmpty ||
          rows(data['achievements']).isNotEmpty ||
          rows(data['benefits_received']).isNotEmpty ||
          rows(data['redemptions']).isNotEmpty;
    }
    return family == 'partners' && rows(data['relationships']).isNotEmpty;
  }

  static List<String> available(
    Map<String, Map<String, dynamic>> data,
    bool space,
  ) => ['recognition', 'loyalty', 'partners']
      .where(
        (family) =>
            data[family] != null && visible(family, data[family]!, space),
      )
      .toList(growable: false);

  static String label(Map<String, dynamic> row) {
    for (final value in [
      row['name'],
      row['program_name'],
      row['display_name'],
      row['reward_name'],
      row['plan_name'],
      map(row['achievement'])['name'],
      map(row['reward'])['name'],
      row['code'],
      row['description'],
    ]) {
      if (text(value).isNotEmpty) return text(value);
    }
    return 'Élément';
  }
}

typedef AppuisAction = Future<void> Function(
  Map<String, dynamic> row,
  String family,
  String action,
);
typedef AppuisAllowed = bool Function(
  Map<String, dynamic> row,
  String family,
  String action,
);

/// Shared Profile / Space widget. Only the actor-backed data changes.
class AppuisDashboard extends StatefulWidget {
  const AppuisDashboard({
    super.key,
    required this.snapshots,
    required this.space,
    required this.actorKey,
    required this.busy,
    required this.onAction,
    required this.allowed,
  });

  final Map<String, Map<String, dynamic>> snapshots;
  final bool space;
  final String actorKey;
  final bool busy;
  final AppuisAction onAction;
  final AppuisAllowed allowed;

  @override
  State<AppuisDashboard> createState() => _AppuisDashboardState();
}

class _AppuisDashboardState extends State<AppuisDashboard> {
  String _filter = 'all';
  Map<String, dynamic> _data(String family) => widget.snapshots[family] ?? {};

  @override
  void didUpdateWidget(covariant AppuisDashboard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.actorKey != widget.actorKey) _filter = 'all';
    final allowed = AppuisViewData.available(widget.snapshots, widget.space);
    if (_filter != 'all' && !allowed.contains(_filter)) _filter = 'all';
  }

  String _name(String family) => switch (family) {
    'recognition' =>
      widget.space ? 'Nos reconnaissances' : 'Mes reconnaissances',
    'loyalty' => widget.space ? 'Notre fidélité' : 'Ma fidélité',
    _ => widget.space ? 'Nos partenariats' : 'Mes partenariats',
  };
  IconData _icon(String family) => switch (family) {
    'recognition' => Icons.workspace_premium_outlined,
    'loyalty' => Icons.card_giftcard_outlined,
    _ => Icons.handshake_outlined,
  };

  Widget _card(
    IconData icon,
    String title, {
    String subtitle = '',
    String highlight = '',
    VoidCallback? open,
  }) {
    final color = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      elevation: 0,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(17),
        side: BorderSide(color: color.outlineVariant),
      ),
      child: InkWell(
        onTap: open,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 14),
          child: Row(
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  color: color.primaryContainer,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: color.onPrimaryContainer),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleSmall
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    if (subtitle.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(
                          subtitle,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(color: color.onSurfaceVariant),
                        ),
                      ),
                    if (highlight.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 5),
                        child: Text(
                          highlight,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: color.primary,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              if (open != null) ...[
                const SizedBox(width: 4),
                Text(
                  'Ouvrir',
                  style: TextStyle(
                    color: color.primary,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Icon(
                  Icons.chevron_right_rounded,
                  color: color.primary,
                  size: 18,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _heading(String family) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 20, 4, 10),
      child: Row(
        children: [
          Icon(_icon(family), color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              _name(family),
              style: Theme.of(context).textTheme.titleLarge
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
          ),
          TextButton.icon(
            onPressed: () => _openFamily(family),
            label: const Text('Tout voir'),
            icon: const Icon(Icons.arrow_forward_rounded, size: 18),
          ),
        ],
      ),
    );
  }

  Widget _metric(IconData icon, int count, String singular, String plural) =>
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 11),
        decoration: BoxDecoration(
          color: const Color(0xFFF0EAFE),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: const Color(0xFF5232DB), size: 22),
            Text(
              count.toString(),
              style: const TextStyle(
                color: Color(0xFF2B176E),
                fontSize: 22,
                fontWeight: FontWeight.w800,
              ),
            ),
            Text(
              count == 1 ? singular : plural,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Color(0xFF2B176E), fontSize: 10),
            ),
          ],
        ),
      );

  Widget _hero(List<String> available) {
    final loyalty = _data('loyalty');
    final programCount = widget.space
        ? (AppuisViewData.map(loyalty['program']).isNotEmpty ? 1 : 0)
        : AppuisViewData.programs(loyalty).length;
    final recognition = _data('recognition');
    final achievements = AppuisViewData.rows(recognition['achievements'])
        .length;
    final recognitionRewards = AppuisViewData.rows(recognition['rewards'])
        .length;
    final loyaltyRewards = widget.space
        ? 0
        : AppuisViewData.rows(loyalty['available_rewards']).length;
    final credits = AppuisViewData.map(
      recognition['summary'],
    )['available_credits'];
    final partnerCount = AppuisViewData.rows(_data('partners')['relationships'])
        .length;
    // Each metric has one owner; never aggregate unrelated reward catalogs.
    final metrics = <Widget>[
      if (available.contains('loyalty') && programCount > 0)
        _metric(
          Icons.loyalty_outlined,
          programCount,
          'Programme',
          'Programmes',
        ),
      if (available.contains('recognition') && achievements > 0)
        _metric(
          Icons.workspace_premium_outlined,
          achievements,
          'Reconnaissance',
          'Reconnaissances',
        )
      else if (available.contains('recognition') && recognitionRewards > 0)
        _metric(
          Icons.redeem_outlined,
          recognitionRewards,
          'Récompense Recognition',
          'Récompenses Recognition',
        )
      else if (loyaltyRewards > 0)
        _metric(
          Icons.redeem_outlined,
          loyaltyRewards,
          'Avantage fidélité',
          'Avantages fidélité',
        )
      else if (available.contains('recognition') &&
          AppuisViewData.positive(credits))
        _metric(
          Icons.stars_outlined,
          int.tryParse(AppuisViewData.text(credits)) ?? 0,
          'Crédit Recognition',
          'Crédits Recognition',
        ),
      if (available.contains('partners') && partnerCount > 0)
        _metric(
          Icons.handshake_outlined,
          partnerCount,
          'Partenariat',
          'Partenariats',
        ),
    ];
    if (metrics.isEmpty) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF5232DB), Color(0xFF2B176E)],
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.space ? 'Nos appuis' : 'Mes appuis',
            style: const TextStyle(
              fontSize: 23,
              fontWeight: FontWeight.w800,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 3),
          const Text(
            'Ce qui est déjà disponible',
            style: TextStyle(color: Color(0xFFE5DDFF)),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              for (var i = 0; i < metrics.length; i++) ...[
                if (i != 0) const SizedBox(width: 8),
                Expanded(child: metrics[i]),
              ],
            ],
          ),
        ],
      ),
    );
  }

  List<Map<String, dynamic>> _recognitionRows() {
    final data = _data('recognition');
    final incoming = AppuisViewData.rows(data['incoming']);
    final incomingIds = incoming
        .map((row) => AppuisViewData.text(row['id']))
        .toSet();
    return [
      for (final row in incoming)
        {...row, '_kind': 'Réponse attendue', '_icon': 'incoming'},
      for (final row in AppuisViewData.rows(data['rewards']))
        {...row, '_kind': 'Récompense', '_icon': 'reward'},
      for (final row in AppuisViewData.rows(data['achievements']))
        {...row, '_kind': 'Contribution reconnue', '_icon': 'achievement'},
      for (final row in AppuisViewData.rows(data['benefits_received']))
        if (!incomingIds.contains(AppuisViewData.text(row['id'])))
          {...row, '_kind': 'Avantage reçu', '_icon': 'benefit'},
    ];
  }

  Widget _preview(String family, {bool all = false}) {
    final data = _data(family);
    if (family == 'loyalty') {
      if (widget.space) {
        final program = AppuisViewData.map(data['program']);
        return program.isEmpty
            ? const SizedBox.shrink()
            : _card(
                Icons.storefront_outlined,
                AppuisViewData.text(program['name']),
                subtitle: 'Programme de cet Espace',
                open: () => _openProgram(null),
              );
      }
      final programs = AppuisViewData.programs(data);
      return Column(
        children: [
          for (final row in (all ? programs : programs.take(3)))
            _card(
              Icons.card_giftcard_outlined,
              AppuisViewData.text(row['program_name']).isNotEmpty
                  ? AppuisViewData.text(row['program_name'])
                  : AppuisViewData.text(row['organization_name']),
              subtitle: AppuisViewData.text(row['program_name']).isNotEmpty
                  ? AppuisViewData.text(row['organization_name'])
                  : '',
              highlight: [
                if (AppuisViewData.positive(row['points_balance']))
                  AppuisViewData.text(row['points_balance']) +
                      ' ' +
                      AppuisViewData.text(row['points_name']),
                if (AppuisViewData.text(
                  AppuisViewData.map(row['current_tier'])['name'],
                ).isNotEmpty)
                  AppuisViewData.text(
                    AppuisViewData.map(row['current_tier'])['name'],
                  ),
                if (AppuisViewData.availableRewardCount(data, row) > 0)
                  AppuisViewData.availableRewardCount(data, row).toString() +
                      ' avantage(s) disponible(s)',
              ].join(' · '),
              open: () => _openProgram(row),
            ),
        ],
      );
    }
    if (family == 'recognition') {
      final rows = _recognitionRows();
      final credits = AppuisViewData.map(data['summary'])['available_credits'];
      return Column(
        children: [
          if (AppuisViewData.positive(credits))
            _card(
              Icons.stars_outlined,
              'Crédits Recognition',
              highlight: AppuisViewData.text(credits) + ' disponibles',
              open: () => _openFamily(family),
            ),
          for (final row in (all ? rows : rows.take(3)))
            _card(
              row['_icon'] == 'incoming'
                  ? Icons.mark_email_unread_outlined
                  : row['_icon'] == 'reward'
                  ? Icons.redeem_outlined
                  : Icons.workspace_premium_outlined,
              AppuisViewData.label(row),
              subtitle: AppuisViewData.text(row['_kind']),
              open: () => _openFamily(family),
            ),
        ],
      );
    }
    final rows = AppuisViewData.rows(data['relationships']);
    return Column(
      children: [
        for (final row in (all ? rows : rows.take(3)))
          _card(
            Icons.handshake_outlined,
            AppuisViewData.label(row),
            subtitle: AppuisViewData.text(
              AppuisViewData.map(row['organization'])['name'] ??
                  row['organization_name'] ??
                  row['status_label'],
            ),
            open: () => _openPartner(row),
          ),
      ],
    );
  }

  void _open(String title, List<Widget> sections) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (routeContext) => Scaffold(
          appBar: AppBar(title: Text(title)),
          body: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
            children: sections,
          ),
        ),
      ),
    );
  }

  void _actionMenu(Map<String, dynamic> row, String family) {
    final actions = [
      'accept',
      'decline',
      'redeem',
      'cancel',
    ].where((action) => widget.allowed(row, family, action)).toList();
    if (actions.isEmpty) return;
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheet) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(title: Text(AppuisViewData.label(row))),
            for (final action in actions)
              ListTile(
                leading: const Icon(Icons.task_alt_outlined),
                enabled: !widget.busy,
                title: Text(switch (action) {
                  'accept' => 'Accepter',
                  'decline' => 'Refuser',
                  'cancel' => 'Annuler cette adhésion',
                  _ => 'Utiliser',
                }),
                onTap: () {
                  Navigator.pop(sheet);
                  unawaited(widget.onAction(row, family, action));
                },
              ),
          ],
        ),
      ),
    );
  }

  Widget _details(
    String family,
    String title,
    Object? values,
    IconData icon, {
    bool actions = false,
  }) {
    final rows = AppuisViewData.rows(values);
    if (rows.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 18, 4, 8),
          child: Text(title, style: Theme.of(context).textTheme.titleMedium),
        ),
        for (final row in rows)
          _card(
            icon,
            AppuisViewData.label(row),
            subtitle: AppuisViewData.text(
              row['status_label'] ?? row['status'] ?? row['description'],
            ),
            open:
                actions &&
                    [
                      'accept',
                      'decline',
                      'redeem',
                      'cancel',
                    ].any((action) => widget.allowed(row, family, action))
                ? () => _actionMenu(row, family)
                : null,
          ),
      ],
    );
  }

  void _openProgram(Map<String, dynamic>? account) {
    final data = _data('loyalty');
    final id = account == null ? '' : AppuisViewData.programId(account);
    final memberships = AppuisViewData.rows(data['memberships'])
        .where((row) => AppuisViewData.programId(row) == id)
        .toList();
    final rewards = AppuisViewData.rows(data['available_rewards'])
        .where((row) => AppuisViewData.programId(row) == id)
        .toList();
    final program = AppuisViewData.map(data['program']);
    final name = AppuisViewData.text(
      account?['program_name'] ?? program['name'],
    );
    _open(name.isEmpty ? 'Programme de fidélité' : name, [
      if (account != null)
        _card(
          Icons.storefront_outlined,
          AppuisViewData.text(account['organization_name']),
          highlight: AppuisViewData.positive(account['points_balance'])
              ? AppuisViewData.text(account['points_balance']) +
                    ' ' +
                    AppuisViewData.text(account['points_name'])
              : '',
        ),
      _details(
        'loyalty',
        'Mes adhésions',
        memberships,
        Icons.card_membership_outlined,
        actions: true,
      ),
      _details(
        'loyalty',
        'Avantages disponibles',
        rewards,
        Icons.redeem_outlined,
        actions: true,
      ),
      if (account != null)
        _details(
          'loyalty',
          'Mouvements',
          account['recent_activity'],
          Icons.history_outlined,
        ),
      if (account == null) ...[
        _details('loyalty', 'Niveaux', program['tiers'], Icons.layers_outlined),
        _details(
          'loyalty',
          'Formules',
          program['membership_plans'],
          Icons.card_membership_outlined,
        ),
        _details(
          'loyalty',
          'Récompenses proposées',
          program['rewards'],
          Icons.redeem_outlined,
        ),
      ],
    ]);
  }

  void _openPartner(Map<String, dynamic> partner) {
    final id = AppuisViewData.text(partner['id']);
    final data = _data('partners');
    final codes = AppuisViewData.rows(data['codes'])
        .where((row) => AppuisViewData.text(row['partner']) == id)
        .toList();
    final campaignIds = codes
        .map((row) => AppuisViewData.text(row['campaign']))
        .toSet();
    _open(AppuisViewData.label(partner), [
      _card(Icons.handshake_outlined, AppuisViewData.label(partner)),
      _details(
        'partners',
        'Campagnes',
        AppuisViewData.rows(data['campaigns'])
            .where(
              (row) => campaignIds.contains(AppuisViewData.text(row['id'])),
            )
            .toList(),
        Icons.campaign_outlined,
      ),
      _details(
        'partners',
        'Codes de parrainage',
        codes,
        Icons.qr_code_outlined,
      ),
      for (final category in ['commissions', 'payouts'])
        _details(
          'partners',
          category == 'commissions' ? 'Commissions' : 'Versements',
          AppuisViewData.rows(data[category])
              .where((row) => AppuisViewData.text(row['partner']) == id)
              .toList(),
          category == 'commissions'
              ? Icons.receipt_long_outlined
              : Icons.payments_outlined,
        ),
    ]);
  }

  void _openFamily(String family) {
    final data = _data(family);
    if (family == 'loyalty') {
      _open(_name(family), [
        _preview(family, all: true),
        _details(
          family,
          'Récompenses obtenues',
          data['rewards'],
          Icons.workspace_premium_outlined,
        ),
      ]);
    } else if (family == 'recognition') {
      _open(_name(family), [
        _details(
          family,
          'Réponses attendues',
          data['incoming'],
          Icons.mark_email_unread_outlined,
          actions: true,
        ),
        _details(
          family,
          'Récompenses',
          data['rewards'],
          Icons.redeem_outlined,
          actions: true,
        ),
        _details(
          family,
          'Contributions reconnues',
          data['achievements'],
          Icons.workspace_premium_outlined,
        ),
        _details(
          family,
          'Avantages reçus',
          data['benefits_received'],
          Icons.card_giftcard_outlined,
        ),
        _details(
          family,
          'Utilisations',
          data['redemptions'],
          Icons.check_circle_outline,
        ),
        _details(
          family,
          'Mouvements',
          data['recent_activity'],
          Icons.history_outlined,
        ),
      ]);
    } else {
      _open(_name(family), [
        _preview(family, all: true),
        _details(
          family,
          'Campagnes',
          data['campaigns'],
          Icons.campaign_outlined,
        ),
        _details(
          family,
          'Codes de parrainage',
          data['codes'],
          Icons.qr_code_outlined,
        ),
        _details(
          family,
          'Commissions',
          data['commissions'],
          Icons.receipt_long_outlined,
        ),
        _details(
          family,
          'Versements',
          data['payouts'],
          Icons.payments_outlined,
        ),
      ]);
    }
  }

  @override
  Widget build(BuildContext context) {
    final available = AppuisViewData.available(widget.snapshots, widget.space);
    if (available.isEmpty) return const SizedBox.shrink();
    final showing = _filter == 'all'
        ? available
        : available.where((family) => family == _filter);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          widget.space
              ? 'Retrouvez les avantages et partenariats de cet Espace.'
              : 'Retrouve tes reconnaissances, avantages et partenariats.',
          style: Theme.of(context).textTheme.bodyMedium
              ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
        ),
        const SizedBox(height: 18),
        _hero(available),
        if (available.length > 1) ...[
          const SizedBox(height: 18),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                for (final option in ['all', ...available]) ...[
                  ChoiceChip(
                    label: Text(
                      option == 'all'
                          ? 'Tous'
                          : switch (option) {
                              'recognition' => 'Reconnaissance',
                              'loyalty' => 'Fidélité',
                              _ => 'Partenariats',
                            },
                    ),
                    selected: option == _filter,
                    onSelected: (_) => setState(() => _filter = option),
                  ),
                  const SizedBox(width: 8),
                ],
              ],
            ),
          ),
        ],
        for (final family in showing) ...[_heading(family), _preview(family)],
      ],
    );
  }
}
