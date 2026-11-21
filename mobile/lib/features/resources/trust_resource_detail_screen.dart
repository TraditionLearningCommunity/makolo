import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/action_controls.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../platform/sharing/share_gateway.dart';
import '../../sync/freshness.dart';
import 'trust_resource_repository.dart';

class TrustResourceDetailScreen extends StatefulWidget {
  const TrustResourceDetailScreen({
    super.key,
    required this.family,
    required this.id,
    required this.repository,
    required this.onOpenJourney,
    this.onOpenPassport,
    this.sharing = const SystemShareGateway(),
  });

  final TrustResourceFamily family;
  final String id;
  final TrustResourceRepository repository;
  final ValueChanged<String> onOpenJourney;
  final VoidCallback? onOpenPassport;
  final ShareGateway sharing;

  @override
  State<TrustResourceDetailScreen> createState() =>
      _TrustResourceDetailScreenState();
}

class _TrustResourceDetailScreenState extends State<TrustResourceDetailScreen> {
  bool _refreshing = false;
  _TrustDetail? _cachedSummary;
  late Stream<StoredProjection?> _detail;
  late Stream<TrustResourceSourceState> _source;

  String get _title =>
      widget.family == TrustResourceFamily.proofs ? 'Preuve' : 'Titre';

  @override
  void initState() {
    super.initState();
    _bind();
  }

  @override
  void didUpdateWidget(covariant TrustResourceDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository ||
        oldWidget.family != widget.family ||
        oldWidget.id != widget.id) {
      _cachedSummary = null;
      _bind();
    }
  }

  void _bind() {
    _detail = widget.repository.watchDetail(widget.family, widget.id);
    _source = widget.repository.watchDetailSource(widget.family, widget.id);
    unawaited(_loadKnownSummary());
    unawaited(_ensureFresh());
  }

  Future<void> _loadKnownSummary() async {
    final pages = await widget.repository.store.readProjections(
      widget.family.collectionProjection,
    );
    final known = _TrustDetail.fromKnownCollection(
      pages,
      widget.family,
      widget.id,
    );
    if (mounted) setState(() => _cachedSummary = known);
  }

  Future<void> _ensureFresh() async {
    if (_refreshing) return;
    try {
      if (!await widget.repository.shouldRefreshDetail(
        widget.family,
        widget.id,
      )) {
        return;
      }
      if (mounted) setState(() => _refreshing = true);
      await widget.repository.refreshDetail(widget.family, widget.id);
    } on Object {
      // Keep already acquired Trust metadata visible.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshDetail(widget.family, widget.id);
    } on Object {
      // Keep already acquired Trust metadata visible.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Uri? _verificationUri(_TrustDetail detail) {
    final link = detail.verifyPath;
    final api = widget.repository.api;
    if (link == null || api == null) return null;
    final relative = Uri.tryParse(link);
    if (relative == null ||
        relative.hasScheme ||
        relative.hasAuthority ||
        relative.hasQuery ||
        relative.hasFragment ||
        !relative.path.startsWith('/trust/')) {
      return null;
    }
    return api.baseUri.resolveUri(relative);
  }

  Future<void> _shareVerification(_TrustDetail detail) async {
    final target = _verificationUri(detail);
    if (target == null) {
      _message('Partage indisponible.');
      return;
    }
    try {
      await widget.sharing.shareText('${detail.title}\n$target');
    } on Object {
      if (mounted) _message('Partage indisponible.');
    }
  }

  void _message(String value) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(value)));
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<TrustResourceSourceState>(
      stream: _source,
      initialData: TrustResourceSourceState.unknown,
      builder: (context, sourceSnapshot) {
        final source = sourceSnapshot.data ?? TrustResourceSourceState.unknown;
        return StreamBuilder<StoredProjection?>(
          stream: _detail,
          builder: (context, snapshot) {
            final projection = snapshot.data;
            final detail = projection == null
                ? _cachedSummary
                : _TrustDetail.fromPayload(widget.family, projection.payload);
            final ownerAvailable = !source.invalidated && !source.ownerDenied;
            final canShareVerification =
                ownerAvailable && detail?.verifyPath != null;

            return Scaffold(
              appBar: AppBar(
                title: Text(_title),
                actions: [
                  if (detail?.verifyPath != null &&
                      widget.repository.api != null &&
                      ownerAvailable)
                    MakoloIconActionButton(
                      tooltip: 'Partager le lien de vérification',
                      icon: Icons.share_outlined,
                      onPressed: canShareVerification
                          ? () => _shareVerification(detail!)
                          : null,
                    ),
                  MakoloIconActionButton(
                    tooltip: 'Actualiser',
                    icon: Icons.refresh_rounded,
                    onPressed: _refreshing ? null : _refresh,
                  ),
                ],
              ),
              body: detail == null
                  ? Center(
                      child: _refreshing
                          ? const CircularProgressIndicator.adaptive()
                          : Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(
                                  widget.family == TrustResourceFamily.proofs
                                      ? 'Preuve indisponible'
                                      : 'Titre indisponible',
                                ),
                                const SizedBox(height: MakoloSpacing.md),
                                MakoloActionButton(
                                  label: 'Réessayer',
                                  appearance: MakoloActionAppearance.quiet,
                                  onPressed: _refresh,
                                ),
                              ],
                            ),
                    )
                  : source.invalidated
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            widget.family == TrustResourceFamily.proofs
                                ? 'Preuve indisponible'
                                : 'Titre indisponible',
                          ),
                          const SizedBox(height: MakoloSpacing.md),
                          MakoloActionButton(
                            label: 'Réessayer',
                            appearance: MakoloActionAppearance.quiet,
                            onPressed: _refresh,
                          ),
                        ],
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _refresh,
                      child: Center(
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 760),
                          child: ListView(
                            physics: const AlwaysScrollableScrollPhysics(),
                            padding: const EdgeInsets.all(MakoloSpacing.inner),
                            children: [
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Icon(
                                    widget.family == TrustResourceFamily.proofs
                                        ? Icons.verified_outlined
                                        : Icons.workspace_premium_outlined,
                                    size: 34,
                                    color: Theme.of(context)
                                        .colorScheme
                                        .primary,
                                  ),
                                  const SizedBox(width: MakoloSpacing.md),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          detail.title,
                                          style: Theme.of(context)
                                              .textTheme
                                              .headlineSmall,
                                        ),
                                        if (detail.typeLabel != null) ...[
                                          const SizedBox(
                                            height: MakoloSpacing.xs,
                                          ),
                                          Text(
                                            detail.typeLabel!,
                                            style: Theme.of(context)
                                                .textTheme
                                                .bodyMedium
                                                ?.copyWith(
                                                  color: Theme.of(context)
                                                      .colorScheme
                                                      .onSurfaceVariant,
                                                ),
                                          ),
                                        ],
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                              if (source.reachability ==
                                  ReachabilityState.unreachable) ...[
                                const SizedBox(height: MakoloSpacing.sm),
                                Semantics(
                                  liveRegion: true,
                                  child: const Row(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Icon(Icons.cloud_off_outlined, size: 18),
                                      SizedBox(width: MakoloSpacing.xs),
                                      Expanded(
                                        child: Text(
                                          'Données enregistrées sur cet appareil. '
                                          'Vérification en ligne indisponible.',
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                              const SizedBox(height: MakoloSpacing.lg),
                              MakoloCard(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Wrap(
                                      spacing: MakoloSpacing.sm,
                                      runSpacing: MakoloSpacing.sm,
                                      children: [
                                        Chip(label: Text(detail.statusLabel)),
                                        if (detail.issuer != null)
                                          Chip(label: Text(detail.issuer!)),
                                      ],
                                    ),
                                    if (detail.statement != null) ...[
                                      const SizedBox(height: MakoloSpacing.md),
                                      Text(
                                        detail.statement!,
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodyLarge,
                                      ),
                                    ],
                                    const SizedBox(height: MakoloSpacing.md),
                                    _Fact(
                                      label: 'Activité',
                                      value: detail.activity ?? '—',
                                    ),
                                    _Fact(
                                      label:
                                          widget.family ==
                                              TrustResourceFamily.proofs
                                          ? 'Établie le'
                                          : 'Délivré le',
                                      value: detail.issuedAt ?? '—',
                                    ),
                                    if (detail.occurrence != null)
                                      _Fact(
                                        label: 'Occurrence',
                                        value: detail.occurrence!,
                                      ),
                                    if (detail.revokedAt != null)
                                      _Fact(
                                        label: 'Révoqué le',
                                        value: detail.revokedAt!,
                                      ),
                                    if (detail.revokeReason != null)
                                      _Fact(
                                        label: 'Motif',
                                        value: detail.revokeReason!,
                                      ),
                                  ],
                                ),
                              ),
                              if ((widget.onOpenPassport != null &&
                                      detail.passportPath != null) ||
                                  detail.journeyId != null) ...[
                                const SizedBox(height: MakoloSpacing.md),
                                Wrap(
                                  alignment: WrapAlignment.end,
                                  spacing: MakoloSpacing.sm,
                                  runSpacing: MakoloSpacing.sm,
                                  children: [
                                    if (widget.onOpenPassport != null &&
                                        detail.passportPath != null)
                                      MakoloActionButton(
                                        label: 'Passeport',
                                        icon: Icons.badge_outlined,
                                        appearance:
                                            MakoloActionAppearance.quiet,
                                        onPressed: widget.onOpenPassport,
                                      ),
                                    if (detail.journeyId != null)
                                      MakoloActionButton(
                                        label: 'Voir la démarche',
                                        icon: Icons.route_outlined,
                                        appearance:
                                            MakoloActionAppearance.quiet,
                                        onPressed: () => widget.onOpenJourney(
                                          detail.journeyId!,
                                        ),
                                      ),
                                  ],
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                    ),
            );
          },
        );
      },
    );
  }
}

class _Fact extends StatelessWidget {
  const _Fact({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: MakoloSpacing.sm),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 110,
          child: Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        const SizedBox(width: MakoloSpacing.sm),
        Expanded(
          child: Text(
            value,
            style: Theme.of(context).textTheme.bodyMedium
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
        ),
      ],
    ),
  );
}

class _TrustDetail {
  const _TrustDetail({
    required this.title,
    required this.typeLabel,
    required this.statusLabel,
    required this.activity,
    required this.issuer,
    required this.statement,
    required this.issuedAt,
    required this.occurrence,
    required this.revokedAt,
    required this.revokeReason,
    required this.journeyId,
    required this.verifyPath,
    required this.passportPath,
  });

  final String title;
  final String? typeLabel;
  final String statusLabel;
  final String? activity;
  final String? issuer;
  final String? statement;
  final String? issuedAt;
  final String? occurrence;
  final String? revokedAt;
  final String? revokeReason;
  final String? journeyId;
  final String? verifyPath;
  final String? passportPath;

  factory _TrustDetail.fromPayload(
    TrustResourceFamily family,
    Map<String, dynamic> payload,
  ) {
    final activity = _map(payload['activity']);
    final issuer = _map(payload['issuer']);
    final occurrence = _map(payload['occurrence']);
    final journey = _map(payload['journey']);
    final revocation = _map(payload['revocation']);
    final links = _map(payload['links']);
    final title = family == TrustResourceFamily.proofs
        ? _string(payload['proof_type_label']) ?? 'Preuve'
        : _string(payload['title']) ?? 'Titre';
    return _TrustDetail(
      title: title,
      typeLabel: family == TrustResourceFamily.proofs
          ? null
          : _string(payload['credential_type_label']),
      statusLabel: _string(payload['status_label']) ?? 'Statut inconnu',
      activity: _string(activity['title']),
      issuer: family == TrustResourceFamily.titles
          ? _string(issuer['name'])
          : null,
      statement: _string(payload['statement']),
      issuedAt: _displayDateTime(_string(payload['issued_at'])),
      occurrence:
          _string(occurrence['label']) ??
          _displayDate(_string(occurrence['start_date'])),
      revokedAt: _displayDateTime(
        _string(revocation['revoked_at']) ?? _string(payload['revoked_at']),
      ),
      revokeReason: _string(revocation['reason']),
      journeyId: _string(journey['id']),
      verifyPath: _string(links['verify']),
      passportPath: _string(links['passport']),
    );
  }

  static _TrustDetail? fromKnownCollection(
    Iterable<StoredProjection> pages,
    TrustResourceFamily family,
    String id,
  ) {
    for (final page in pages) {
      if (page.kind != family.collectionProjection) continue;
      final rows = page.payload['items'];
      if (rows is! List) continue;
      for (final raw in rows) {
        final row = _map(raw);
        if (_string(row['id']) != id) continue;
        return _TrustDetail.fromPayload(family, row);
      }
    }
    return null;
  }
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const {};
}

String? _string(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}

String? _displayDate(String? value) {
  if (value == null) return null;
  final date = DateTime.tryParse(value);
  if (date == null) return value;
  final local = date.toLocal();
  final day = local.day.toString().padLeft(2, '0');
  final month = local.month.toString().padLeft(2, '0');
  return '$day/$month/${local.year}';
}

String? _displayDateTime(String? value) {
  if (value == null) return null;
  final date = DateTime.tryParse(value);
  if (date == null) return value;
  final local = date.toLocal();
  final day = local.day.toString().padLeft(2, '0');
  final month = local.month.toString().padLeft(2, '0');
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '$day/$month/${local.year} · $hour:$minute';
}
