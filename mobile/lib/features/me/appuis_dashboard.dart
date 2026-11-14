import 'dart:async';

import 'package:flutter/material.dart';

import 'appuis_program_depth.dart';
import 'appuis_credits_use_screen.dart';

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
      if (id.isNotEmpty) {
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

  static List<Map<String, dynamic>> activePartners(Map<String, dynamic> data) =>
      rows(data['relationships'])
          .where((row) => text(row['status']).toLowerCase() == 'active')
          .toList(growable: false);

  static bool visible(String family, Map<String, dynamic> data, bool space) {
    if (family == 'loyalty') {
      return space
          ? map(data['program']).isNotEmpty
          : programs(data).isNotEmpty || rows(data['rewards']).isNotEmpty;
    }
    if (family == 'recognition') {
      return positive(map(data['summary'])['available_credits']) ||
          positive(map(data['summary'])['pending_credits']) ||
          rows(data['incoming']).isNotEmpty ||
          rows(data['rewards']).isNotEmpty ||
          rows(data['achievements']).isNotEmpty ||
          rows(data['benefits_received']).isNotEmpty ||
          rows(data['redemptions']).isNotEmpty ||
          rows(data['recent_activity']).isNotEmpty;
    }
    return family == 'partners' && activePartners(data).isNotEmpty;
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
typedef AppuisProgramReader = Future<Map<String, dynamic>?> Function(
  String programId,
);
typedef AppuisSpaceCreator = Future<bool> Function(
  Map<String, dynamic> owner,
  String action,
  Map<String, dynamic> body,
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
    required this.onReadProgram,
    required this.onCreateSpaceItem,
    required this.canMutate,
    required this.canSpendRecognition,
    required this.onRedeemRecognition,
    required this.onReloadRecognition,
    this.actorChanges,
    this.actorIsCurrent,
    required this.allowed,
  });

  final Map<String, Map<String, dynamic>> snapshots;
  final bool space;
  final String actorKey;
  final bool busy;
  final AppuisAction onAction;
  final AppuisProgramReader onReadProgram;
  final AppuisSpaceCreator onCreateSpaceItem;
  final bool canMutate;
  final bool Function() canSpendRecognition;
  final Future<Map<String, dynamic>?> Function(Map<String, dynamic>)
  onRedeemRecognition;
  final Future<Map<String, dynamic>?> Function() onReloadRecognition;
  final Listenable? actorChanges;
  final bool Function()? actorIsCurrent;
  final AppuisAllowed allowed;

  @override
  State<AppuisDashboard> createState() => _AppuisDashboardState();
}

class _AppuisDashboardState extends State<AppuisDashboard> {
  Map<String, dynamic> _data(String family) => widget.snapshots[family] ?? {};

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

  Widget _heading(String family, {bool seeAll = false}) {
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
          if (seeAll)
            TextButton.icon(
              onPressed: () => _openFamily(family),
              label: const Text('Tout voir'),
              icon: const Icon(Icons.arrow_forward_rounded, size: 18),
            ),
        ],
      ),
    );
  }

  Widget _recognitionCard() {
    final data = _data('recognition');
    final summary = AppuisViewData.map(data['summary']);
    final account = AppuisViewData.map(data['account']);
    final credit = summary['available_credits'];
    final pending = summary['pending_credits'];
    final hasAccount = account.isNotEmpty;
    final caps = data['capabilities'];
    final maySpend = !widget.space || (caps is List && caps.contains('spend'));
    return Container(
      padding: const EdgeInsets.all(17),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF5232DB), Color(0xFF2B176E)],
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.toll_outlined,
                color: Color(0xFFF3DA91),
                size: 27,
              ),
              const SizedBox(width: 9),
              Text(
                widget.space ? 'Notre reconnaissance' : 'Ma reconnaissance',
                style: const TextStyle(
                  fontSize: 17,
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          if (hasAccount && AppuisViewData.positive(credit)) ...[
            const SizedBox(height: 14),
            Text(
              AppuisViewData.text(credit) + ' crédits',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 27,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
          if (AppuisViewData.positive(pending)) ...[
            const SizedBox(height: 6),
            Text(
              AppuisViewData.text(pending) + ' crédits en attente',
              style: const TextStyle(color: Color(0xFFE5DDFF), fontSize: 13),
            ),
          ],
          if (hasAccount && maySpend && AppuisViewData.positive(credit)) ...[
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: const Color(0xFF2B176E),
                ),
                onPressed: () {
                  Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (context) => AppuisCreditsUseScreen(
                        initial: data,
                        space: widget.space,
                        canSpend: widget.canSpendRecognition,
                        canUseReward: (reward) =>
                            widget.allowed(reward, 'recognition', 'redeem'),
                        onRedeem: widget.onRedeemRecognition,
                        onReload: widget.onReloadRecognition,
                        actorChanges: widget.actorChanges,
                        actorIsCurrent: widget.actorIsCurrent,
                      ),
                    ),
                  );
                },
                icon: const Icon(Icons.card_giftcard_outlined),
                label: Text(
                  widget.space
                      ? 'Utiliser nos crédits'
                      : 'Utiliser mes crédits',
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _accomplishments() {
    final data = _data('recognition');
    final rows = _recognitionRows()
        .where((row) => row['_icon'] != 'reward')
        .toList(growable: false);
    final history = AppuisViewData.rows(data['recent_activity']);
    if (rows.isEmpty && history.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(3, 22, 3, 10),
          child: Row(
            children: [
              Icon(
                Icons.military_tech_outlined,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(width: 9),
              Expanded(
                child: Text(
                  widget.space
                      ? 'Nos accomplissements'
                      : 'Mes accomplissements',
                  style: Theme.of(context).textTheme.titleLarge
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
              ),
              if (rows.length > 3 || history.isNotEmpty)
                TextButton(
                  onPressed: () => _openFamily('recognition'),
                  child: const Text('Tout voir'),
                ),
            ],
          ),
        ),
        if (rows.isNotEmpty)
          for (final row in rows.take(3))
            _card(
              row['_icon'] == 'incoming'
                  ? Icons.mark_email_unread_outlined
                  : Icons.workspace_premium_outlined,
              AppuisViewData.label(row),
              subtitle: AppuisViewData.text(row['_kind']),
              open: () => _openFamily('recognition'),
            )
        else
          _card(
            Icons.history_outlined,
            'Historique des crédits',
            open: () => _openFamily('recognition'),
          ),
      ],
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
                'Notre programme de fidélité',
                subtitle: 'Niveaux, formules et avantages',
                open: () => _openProgram(null),
              );
      }
      final programs = AppuisViewData.programs(data);
      final availableRewards = AppuisViewData.rows(data['available_rewards']);
      final obtained = AppuisViewData.rows(data['rewards']);
      if (programs.isEmpty && obtained.isEmpty) {
        return const SizedBox.shrink();
      }
      if (all) {
        return Column(
          children: [
            for (final row in programs)
              _card(
                Icons.card_giftcard_outlined,
                AppuisViewData.text(row['program_name']).isEmpty
                    ? 'Programme de fidélité'
                    : AppuisViewData.text(row['program_name']),
                subtitle: AppuisViewData.text(row['organization_name']),
                highlight: [
                  if (AppuisViewData.positive(row['points_balance']))
                    AppuisViewData.text(row['points_balance']) +
                        ' ' +
                        AppuisViewData.text(row['points_name']),
                  if (AppuisViewData.availableRewardCount(data, row) > 0)
                    AppuisViewData.availableRewardCount(data, row).toString() +
                        ' avantages disponibles',
                ].join(' · '),
                open: () => _openProgram(row),
              ),
          ],
        );
      }
      // No program catalog on the Appuis landing. Open it intentionally.
      return _card(
        Icons.card_giftcard_outlined,
        'Mes avantages',
        subtitle: 'Programmes et adhésions',
        highlight: availableRewards.isEmpty
            ? ''
            : availableRewards.length.toString() + ' avantages disponibles',
        open: () => _openFamily(family),
      );
    }

    if (family == 'recognition') {
      final rows = _recognitionRows();
      final credits = AppuisViewData.map(data['summary'])['available_credits'];
      final pending = AppuisViewData.map(data['summary'])['pending_credits'];
      return Column(
        children: [
          if (AppuisViewData.positive(credits))
            _card(
              Icons.stars_outlined,
              'Crédits Recognition',
              highlight: '${AppuisViewData.text(credits)} disponibles',
              open: () => _openFamily(family),
            ),
          if (AppuisViewData.positive(pending))
            _card(
              Icons.hourglass_top_outlined,
              'Crédits en attente',
              highlight: AppuisViewData.text(pending) + ' crédits',
              open: () => _openFamily(family),
            ),
          if (rows.isEmpty &&
              !AppuisViewData.positive(credits) &&
              AppuisViewData.rows(data['recent_activity']).isNotEmpty)
            _card(
              Icons.history_outlined,
              'Historique des reconnaissances',
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
    final rows = AppuisViewData.activePartners(data);
    return Column(
      children: [
        for (final row in (all ? rows : rows.take(3)))
          _card(
            Icons.handshake_outlined,
            AppuisViewData.label(row),
            subtitle: AppuisViewData.text(
              AppuisViewData.map(row['organization'])['name'] ??
                  AppuisViewData.map(row['space'])['name'] ??
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
                  // Root owner reconciliation must not leave a stale depth.
                  final navigator = Navigator.of(context);
                  if (navigator.canPop()) navigator.pop();
                  unawaited(widget.onAction(row, family, action));
                },
              ),
          ],
        ),
      ),
    );
  }

  String _detailDescription(
    String family,
    String section,
    Map<String, dynamic> row,
  ) {
    final parts = <String>[];
    if (family == 'recognition' && section == 'Récompenses') {
      final cost = row['points_cost'];
      if (AppuisViewData.positive(cost)) {
        parts.add(AppuisViewData.text(cost) + ' crédits');
      }
      final kind = AppuisViewData.text(row['kind_label']);
      if (kind.isNotEmpty) parts.add(kind);
    } else if (family == 'recognition' && section == 'Mouvements') {
      final delta = row['credits_delta'];
      if (delta is num && delta != 0) {
        parts.add(
          (delta > 0 ? '+' : '') + AppuisViewData.text(delta) + ' crédits',
        );
      }
    }
    for (final field in [
      row['status_label'],
      row['description'],
      row['status'],
    ]) {
      final value = AppuisViewData.text(field);
      if (value.isNotEmpty && !parts.contains(value)) {
        parts.add(value);
        break;
      }
    }
    return parts.join(' · ');
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
            subtitle: _detailDescription(family, title, row),
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
    final loyalty = _data('loyalty');
    final spaceProgram = AppuisViewData.map(loyalty['program']);
    final selected = widget.space
        ? spaceProgram
        : (account ?? <String, dynamic>{});
    final id = widget.space
        ? AppuisViewData.text(spaceProgram['id'])
        : AppuisViewData.programId(selected);
    if (id.isEmpty) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => AppuisProgramDepth(
          programId: id,
          initialProgram: selected,
          loyalty: loyalty,
          space: widget.space,
          onReadProgram: widget.onReadProgram,
          onAction: widget.onAction,
          allowed: widget.allowed,
          onCreateSpaceItem: widget.onCreateSpaceItem,
          canMutate: widget.canMutate,
        ),
      ),
    );
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
      final summary = AppuisViewData.map(data['summary']);
      final account = AppuisViewData.map(data['account']);
      final balance = summary['available_credits'];
      final pending = summary['pending_credits'];
      _open(_name(family), [
        if (AppuisViewData.positive(balance) ||
            AppuisViewData.positive(pending) ||
            AppuisViewData.positive(account['lifetime_earned']))
          _card(
            Icons.toll_outlined,
            widget.space ? 'Nos crédits' : 'Mes crédits',
            subtitle: widget.space
                ? 'Crédits de cet Espace'
                : 'Crédits de reconnaissance',
            highlight: [
              if (AppuisViewData.positive(balance))
                AppuisViewData.text(balance) + ' disponibles',
              if (AppuisViewData.positive(pending))
                AppuisViewData.text(pending) + ' en attente',
              if (AppuisViewData.positive(account['lifetime_earned']))
                AppuisViewData.text(account['lifetime_earned']) +
                    ' obtenus au total',
            ].join(' · '),
          ),
        _details(
          family,
          'Réponses attendues',
          data['incoming'],
          Icons.mark_email_unread_outlined,
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
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (available.contains('recognition')) ...[
          _recognitionCard(),
          _accomplishments(),
        ],
        if (available.contains('loyalty')) ...[
          _heading('loyalty'),
          _preview('loyalty'),
        ],
        if (available.contains('partners')) ...[
          _heading(
            'partners',
            seeAll: AppuisViewData.activePartners(_data('partners')).length > 3,
          ),
          _preview('partners'),
        ],
      ],
    );
  }
}
