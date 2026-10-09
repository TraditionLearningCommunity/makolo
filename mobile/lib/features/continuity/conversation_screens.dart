import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/humanization.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import 'conversation_repository.dart';

class ConversationListScreen extends StatefulWidget {
  const ConversationListScreen({
    super.key,
    required this.repository,
    required this.onOpen,
  });

  final ConversationRepository repository;
  final void Function(String id) onOpen;

  @override
  State<ConversationListScreen> createState() => _ConversationListScreenState();
}

class _ConversationListScreenState extends State<ConversationListScreen> {
  static const _surfaceAdapter = ProjectionSurfaceAdapter();
  bool _refreshing = false;
  bool _requestedInitialRefresh = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquireOrRefresh());
  }

  Future<void> _acquireOrRefresh() async {
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;
    final local = await widget.repository.readList();
    final source = await widget.repository.readListSource();
    final invitations = await widget.repository.readInvitations();
    final invitationSource = await widget.repository.readInvitationsSource();
    if (!mounted) return;
    if (invitations == null ||
        ConversationRepository.invitationsFreshness.evaluate(
              invitations,
              now: DateTime.now(),
              invalidated: invitationSource.invalidated,
            ) !=
            FreshnessState.fresh) {
      unawaited(widget.repository.refreshInvitations());
    }
    if (local == null) {
      await _refresh();
      return;
    }
    final freshness = ConversationRepository.listFreshness.evaluate(
      local,
      now: DateTime.now(),
      invalidated: source.invalidated,
    );
    if (freshness != FreshnessState.fresh) await _refresh();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await Future.wait([
        widget.repository.refreshList(),
        widget.repository.refreshInvitations(),
      ]);
    } on Object {
      // Preserve the local collection.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchList(),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<OwnerSourceState>(
          stream: widget.repository.watchListSource(),
          initialData: OwnerSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = projectionSnapshot.data;
            final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
            final items = _ConversationSummary.fromProjection(projection);
            final freshness = projection == null
                ? null
                : ConversationRepository.listFreshness.evaluate(
                    projection,
                    now: DateTime.now(),
                    invalidated: source.invalidated,
                  );
            final available = projection != null;
            final surface = _surfaceAdapter.adapt(
              projection: ProjectionPresentationModel(
                available: available,
                payload: projection?.payload,
                freshness: freshness,
                resources: const [],
                drafts: const [],
                pendingOperations: const [],
              ),
              availability: available
                  ? items.isEmpty
                        ? MakoloAvailabilityCue.empty
                        : MakoloAvailabilityCue.content
                  : _refreshing
                  ? MakoloAvailabilityCue.loading
                  : MakoloAvailabilityCue.initial,
              reachability: source.reachability,
              failure: source.lastErrorCode != null && available
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );
            return Scaffold(
              appBar: AppBar(
                title: const Text('Conversations'),
                actions: [
                  PopupMenuButton<String>(
                    tooltip: 'État personnel',
                    onSelected: (action) =>
                        _updatePersonalState(action, detail.personalState),
                    itemBuilder: (context) => [
                      PopupMenuItem(
                        value: 'pin',
                        child: Text(
                          detail.personalState.pinned
                              ? 'Retirer l’épingle'
                              : 'Épingler pour moi',
                        ),
                      ),
                      PopupMenuItem(
                        value: 'mute',
                        child: Text(
                          detail.personalState.muted
                              ? 'Réactiver les signaux'
                              : 'Mettre les signaux en sourdine',
                        ),
                      ),
                      PopupMenuItem(
                        value: 'revisit',
                        child: Text(
                          detail.personalState.revisit
                              ? 'Retirer le rappel de revisite'
                              : 'Revoir plus tard',
                        ),
                      ),
                      PopupMenuItem(
                        value: 'archive',
                        child: Text(
                          detail.personalState.archived
                              ? 'Retirer de mes archives'
                              : 'Archiver pour moi',
                        ),
                      ),
                      PopupMenuItem(
                        value: 'hide',
                        child: Text(
                          detail.personalState.hidden
                              ? 'Afficher de nouveau'
                              : 'Masquer pour moi',
                        ),
                      ),
                    ],
                  ),
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              body: MakoloSurfaceStateView(
                state: surface,
                empty: const MakoloEmptyState(
                  title: 'Aucune conversation',
                  body: 'Rien ne demande votre attention ici pour le moment.',
                ),
                initialLoading: const MakoloLoadingState(
                  label: 'Chargement des conversations…',
                ),
                onRetry: _refresh,
                content: _ConversationListBody(
                  repository: widget.repository,
                  items: items,
                  onOpen: widget.onOpen,
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _ConversationListBody extends StatefulWidget {
  const _ConversationListBody({
    required this.repository,
    required this.items,
    required this.onOpen,
  });

  final ConversationRepository repository;
  final List<_ConversationSummary> items;
  final void Function(String id) onOpen;

  @override
  State<_ConversationListBody> createState() => _ConversationListBodyState();
}

class _ConversationListBodyState extends State<_ConversationListBody> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final normalized = _query.trim().toLowerCase();
    final filtered = normalized.isEmpty
        ? widget.items
        : widget.items
              .where(
                (item) =>
                    item.title.toLowerCase().contains(normalized) ||
                    (item.contextLabel ?? '').toLowerCase().contains(
                      normalized,
                    ),
              )
              .toList(growable: false);

    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchInvitations(),
      builder: (context, invitationsSnapshot) {
        final invitations = _ConversationInvitation.fromProjection(
          invitationsSnapshot.data,
        );
        return ListView(
          key: const Key('conversation-list-content'),
          padding: const EdgeInsets.all(MakoloSpacing.inner),
          children: [
            TextField(
              key: const Key('conversation-search-field'),
              onChanged: (value) => setState(() => _query = value),
              decoration: const InputDecoration(
                labelText: 'Rechercher dans mes conversations',
                prefixIcon: Icon(Icons.search_rounded),
              ),
            ),
            if (invitations.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.md),
              Text(
                'Invitations',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: MakoloSpacing.sm),
              for (final invitation in invitations) ...[
                _ConversationInvitationCard(
                  invitation: invitation,
                  repository: widget.repository,
                  onOpen: widget.onOpen,
                ),
                const SizedBox(height: MakoloSpacing.sm),
              ],
            ],
            const SizedBox(height: MakoloSpacing.md),
            if (filtered.isEmpty)
              const MakoloCard(
                child: Text(
                  'Aucune coordination ne correspond à cette recherche.',
                ),
              )
            else
              for (var index = 0; index < filtered.length; index++) ...[
                MakoloCard(
                  onTap: () => widget.onOpen(filtered[index].id),
                  child: MakoloStatusMetadataAction(
                    title: filtered[index].title,
                    subtitle: filtered[index].contextLabel,
                    status: filtered[index].lifecycle == null
                        ? null
                        : MakoloStatus(label: filtered[index].lifecycle!),
                    metadata: [
                      if (filtered[index].attentionCount > 0)
                        MakoloMetadataItem(
                          filtered[index].attentionCount.toString() +
                              ' élément(s) à voir',
                          icon: Icons.notifications_active_outlined,
                        ),
                      if (filtered[index].allClear)
                        const MakoloMetadataItem(
                          'Tout est en ordre',
                          icon: Icons.check_circle_outline_rounded,
                        ),
                    ],
                    action: const Icon(Icons.chevron_right_rounded),
                  ),
                ),
                if (index < filtered.length - 1)
                  const SizedBox(height: MakoloSpacing.sm),
              ],
          ],
        );
      },
    );
  }
}

class _ConversationInvitationCard extends StatefulWidget {
  const _ConversationInvitationCard({
    required this.invitation,
    required this.repository,
    required this.onOpen,
  });

  final _ConversationInvitation invitation;
  final ConversationRepository repository;
  final void Function(String id) onOpen;

  @override
  State<_ConversationInvitationCard> createState() =>
      _ConversationInvitationCardState();
}

class _ConversationInvitationCardState
    extends State<_ConversationInvitationCard> {
  bool _busy = false;
  String? _error;

  Future<void> _respond(bool accept) async {
    if (_busy || widget.invitation.expired) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final conversationId = await widget.repository.respondToInvitation(
        invitationId: widget.invitation.id,
        accept: accept,
      );
      if (!mounted) return;
      if (accept && conversationId != null) widget.onOpen(conversationId);
    } on Object {
      if (!mounted) return;
      setState(
        () => _error =
            'Cette invitation a changé. Actualisez pour voir son état actuel.',
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return MakoloCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Invitation à rejoindre une coordination',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          if (widget.invitation.expired)
            const Padding(
              padding: EdgeInsets.only(top: MakoloSpacing.xs),
              child: Text('Cette invitation a expiré.'),
            ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.xs),
              child: Text(_error!),
            ),
          const SizedBox(height: MakoloSpacing.sm),
          Wrap(
            spacing: MakoloSpacing.sm,
            children: [
              OutlinedButton(
                onPressed: _busy || widget.invitation.expired
                    ? null
                    : () => _respond(false),
                child: const Text('Refuser'),
              ),
              FilledButton(
                onPressed: _busy || widget.invitation.expired
                    ? null
                    : () => _respond(true),
                child: Text(_busy ? 'En cours…' : 'Accepter'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class ConversationDetailScreen extends StatefulWidget {
  const ConversationDetailScreen({
    super.key,
    required this.id,
    required this.repository,
    this.representedSpaceId,
  });

  final String id;
  final ConversationRepository repository;
  final String? representedSpaceId;

  @override
  State<ConversationDetailScreen> createState() =>
      _ConversationDetailScreenState();
}

class _ConversationDetailScreenState extends State<ConversationDetailScreen> {
  static const _surfaceAdapter = ProjectionSurfaceAdapter();
  bool _refreshing = false;
  bool _requestedInitialRefresh = false;

  @override
  void initState() {
    super.initState();
    unawaited(_acquireOrRefresh());
  }

  Future<void> _acquireOrRefresh() async {
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;
    final local = await widget.repository.readDetail(widget.id);
    final source = await widget.repository.readDetailSource(widget.id);
    if (!mounted) return;
    if (local == null) {
      await _refresh();
      return;
    }
    final freshness = ConversationRepository.detailFreshness.evaluate(
      local,
      now: DateTime.now(),
      invalidated: source.invalidated,
    );
    if (freshness != FreshnessState.fresh) await _refresh();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshDetail(widget.id);
    } on Object {
      // Preserve the local detail.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _updatePersonalState(
    String action,
    _ConversationPersonalState state,
  ) async {
    try {
      switch (action) {
        case 'pin':
          await widget.repository.updatePersonalState(
            conversationId: widget.id,
            pinned: !state.pinned,
          );
          break;
        case 'mute':
          await widget.repository.updatePersonalState(
            conversationId: widget.id,
            mute: !state.muted,
          );
          break;
        case 'archive':
          await widget.repository.updatePersonalState(
            conversationId: widget.id,
            archived: !state.archived,
          );
          break;
        case 'hide':
          await widget.repository.updatePersonalState(
            conversationId: widget.id,
            hidden: !state.hidden,
          );
          break;
        case 'revisit':
          await widget.repository.updatePersonalState(
            conversationId: widget.id,
            revisit: !state.revisit,
          );
          break;
      }
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Cet état personnel n’a pas été confirmé. L’état serveur connu est conservé.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchDetail(widget.id),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<OwnerSourceState>(
          stream: widget.repository.watchDetailSource(widget.id),
          initialData: OwnerSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = projectionSnapshot.data;
            final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
            final detail = _ConversationDetail.fromProjection(projection);
            final freshness = projection == null
                ? null
                : ConversationRepository.detailFreshness.evaluate(
                    projection,
                    now: DateTime.now(),
                    invalidated: source.invalidated,
                  );
            final available = projection != null;
            final surface = _surfaceAdapter.adapt(
              projection: ProjectionPresentationModel(
                available: available,
                payload: projection?.payload,
                freshness: freshness,
                resources: const [],
                drafts: const [],
                pendingOperations: const [],
              ),
              availability: available
                  ? MakoloAvailabilityCue.content
                  : _refreshing
                  ? MakoloAvailabilityCue.loading
                  : MakoloAvailabilityCue.initial,
              reachability: source.reachability,
              failure: !available && source.invalidated && !_refreshing
                  ? MakoloFailureCue.blocking
                  : source.lastErrorCode != null && available
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );
            return Scaffold(
              appBar: AppBar(
                title: const Text('Conversation'),
                actions: [
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              body: MakoloSurfaceStateView(
                state: surface,
                initialLoading: const MakoloLoadingState(
                  label: 'Chargement de la conversation…',
                ),
                blockingErrorMessage: 'Cette conversation n’est pas disponible dans votre contexte actuel.',
                onRetry: _refresh,
                content: ListView(
                  key: const Key('conversation-detail-content'),
                  padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
                  children: [
                    MakoloDetailHeader(
                      eyebrow: detail.contextLabel,
                      title: detail.title,
                      subtitle: detail.purpose,
                      status: detail.lifecycle == null
                          ? null
                          : MakoloStatus(label: detail.lifecycle!),
                    ),
                    MakoloSection(
                      title: 'Points',
                      description:
                          'Ce qui demande votre attention apparaît ici.',
                      child: detail.points.isEmpty
                          ? const MakoloCard(
                              child: Text('Aucun point à afficher.'),
                            )
                          : Column(
                              children: [
                                for (
                                  var index = 0;
                                  index < detail.points.length;
                                  index++
                                ) ...[
                                  _PointCard(
                                    point: detail.points[index],
                                    repository: widget.repository,
                                    conversationId: widget.id,
                                    representedSpaceId:
                                        widget.representedSpaceId,
                                  ),
                                  if (index < detail.points.length - 1)
                                    const SizedBox(height: MakoloSpacing.sm),
                                ],
                              ],
                            ),
                    ),
                    if (detail.essential.isNotEmpty)
                      MakoloSection(
                        title: 'Essentiel',
                        description: 'Les décisions et résultats actuels restent lisibles sans relire tout le passé.',
                        child: Column(
                          children: [
                            for (
                              var index = 0;
                              index < detail.essential.length;
                              index++
                            ) ...[
                              _PointCard(
                                point: detail.essential[index],
                                repository: widget.repository,
                                conversationId: widget.id,
                                representedSpaceId: widget.representedSpaceId,
                                readOnly: true,
                              ),
                              if (index < detail.essential.length - 1)
                                const SizedBox(height: MakoloSpacing.sm),
                            ],
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _PointCard extends StatefulWidget {
  const _PointCard({
    required this.point,
    required this.repository,
    required this.conversationId,
    this.representedSpaceId,
    this.readOnly = false,
  });

  final _ConversationPoint point;
  final ConversationRepository repository;
  final String conversationId;
  final String? representedSpaceId;
  final bool readOnly;

  @override
  State<_PointCard> createState() => _PointCardState();
}

class _PointCardState extends State<_PointCard> {
  bool _busy = false;
  String? _feedback;
  String? _clientReference;

  String _newClientReference() {
    _clientReference ??=
        'mobile-' +
        widget.point.id +
        '-' +
        DateTime.now().microsecondsSinceEpoch.toString();
    return _clientReference!;
  }

  Future<void> _acknowledge() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _feedback = null;
    });
    try {
      await widget.repository.acknowledgePoint(
        conversationId: widget.conversationId,
        pointId: widget.point.id,
      );
    } on Object {
      if (!mounted) return;
      await widget.repository.refreshDetail(widget.conversationId);
      if (!mounted) return;
      setState(
        () => _feedback =
            'Ce point a changé. Voici son état actuel après actualisation.',
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _respond() async {
    if (_busy) return;
    final value = await _collectResponseValue(context, widget.point);
    if (!mounted || identical(value, _cancelledResponse)) return;
    setState(() {
      _busy = true;
      _feedback = null;
    });
    try {
      await widget.repository.respondToPoint(
        conversationId: widget.conversationId,
        pointId: widget.point.id,
        value: value,
        clientReference: _newClientReference(),
        representedSpaceId: widget.representedSpaceId,
      );
      _clientReference = null;
    } on Object {
      if (!mounted) return;
      await widget.repository.refreshDetail(widget.conversationId);
      if (!mounted) return;
      setState(
        () => _feedback = 'Ce point a changé ou la réponse n’a pas été confirmée. Votre ancienne saisie n’a pas été déclarée envoyée.',
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final point = widget.point;
    final metadata = <MakoloMetadataItem>[
      if (point.attentionReason != null)
        MakoloMetadataItem(
          point.attentionReason!,
          icon: Icons.priority_high_rounded,
        ),
      if (point.section != null) MakoloMetadataItem(point.section!),
      if (point.requiresAcknowledgement)
        const MakoloMetadataItem(
          'Confirmation de lecture requise',
          icon: Icons.visibility_outlined,
        ),
      if (point.canRespond)
        const MakoloMetadataItem(
          'Vous pouvez répondre',
          icon: Icons.reply_rounded,
        ),
    ];
    return MakoloCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          MakoloStatusMetadataAction(
            title: point.title,
            subtitle: point.body,
            status: point.lifecycle == null
                ? null
                : MakoloStatus(label: point.lifecycle!),
            metadata: metadata,
          ),
          if (point.resolutionSummary != null) ...[
            const SizedBox(height: MakoloSpacing.sm),
            Text('✓ ' + point.resolutionSummary!),
          ],
          if (_feedback != null) ...[
            const SizedBox(height: MakoloSpacing.sm),
            Text(_feedback!),
          ],
          if (!widget.readOnly &&
              point.requiresAcknowledgement &&
              point.attentionReason == 'acknowledge') ...[
            const SizedBox(height: MakoloSpacing.sm),
            FilledButton(
              onPressed: _busy ? null : _acknowledge,
              child: Text(_busy ? 'En cours…' : 'J’ai pris connaissance'),
            ),
          ],
          if (!widget.readOnly &&
              point.canRespond &&
              point.supportsInteractiveResponse) ...[
            const SizedBox(height: MakoloSpacing.sm),
            FilledButton(
              onPressed: _busy ? null : _respond,
              child: Text(_busy ? 'Envoi…' : point.responseActionLabel),
            ),
          ],
          if (!widget.readOnly &&
              point.canRespond &&
              !point.supportsInteractiveResponse) ...[
            const SizedBox(height: MakoloSpacing.sm),
            const Text(
              'Ce type de réponse nécessite une capacité média ou formulaire explicitement disponible.',
            ),
          ],
        ],
      ),
    );
  }
}

final Object _cancelledResponse = Object();

Future<Object?> _collectResponseValue(
  BuildContext context,
  _ConversationPoint point,
) async {
  switch (point.responseMode) {
    case 'boolean':
      return await showDialog<Object?>(
            context: context,
            builder: (context) => SimpleDialog(
              title: Text(point.title),
              children: [
                SimpleDialogOption(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('Oui'),
                ),
                SimpleDialogOption(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('Non'),
                ),
              ],
            ),
          ) ??
          _cancelledResponse;
    case 'single_choice':
      return await showDialog<Object?>(
            context: context,
            builder: (context) => SimpleDialog(
              title: Text(point.title),
              children: [
                for (final option in point.options)
                  SimpleDialogOption(
                    onPressed: () => Navigator.pop(context, option.id),
                    child: Text(option.label),
                  ),
              ],
            ),
          ) ??
          _cancelledResponse;
    case 'multiple_choice':
      final selected = <String>{};
      return await showDialog<Object?>(
            context: context,
            builder: (context) => StatefulBuilder(
              builder: (context, setDialogState) => AlertDialog(
                title: Text(point.title),
                content: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      for (final option in point.options)
                        CheckboxListTile(
                          value: selected.contains(option.id),
                          title: Text(option.label),
                          onChanged: (checked) {
                            setDialogState(() {
                              if (checked == true) {
                                selected.add(option.id);
                              } else {
                                selected.remove(option.id);
                              }
                            });
                          },
                        ),
                    ],
                  ),
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context, _cancelledResponse),
                    child: const Text('Annuler'),
                  ),
                  FilledButton(
                    onPressed: selected.isEmpty
                        ? null
                        : () => Navigator.pop(
                            context,
                            selected.toList(growable: false),
                          ),
                    child: const Text('Continuer'),
                  ),
                ],
              ),
            ),
          ) ??
          _cancelledResponse;
    case 'date':
      final date = await showDatePicker(
        context: context,
        firstDate: DateTime(1900),
        lastDate: DateTime(2200),
        initialDate: DateTime.now(),
      );
      if (date == null) return _cancelledResponse;
      return date.toIso8601String().split('T').first;
    case 'datetime':
      final date = await showDatePicker(
        context: context,
        firstDate: DateTime(1900),
        lastDate: DateTime(2200),
        initialDate: DateTime.now(),
      );
      if (date == null || !context.mounted) return _cancelledResponse;
      final time = await showTimePicker(
        context: context,
        initialTime: TimeOfDay.now(),
      );
      if (time == null) return _cancelledResponse;
      return DateTime(
        date.year,
        date.month,
        date.day,
        time.hour,
        time.minute,
      ).toUtc().toIso8601String();
    case 'free_text':
    case 'number':
      final controller = TextEditingController();
      final result = await showDialog<Object?>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(point.title),
          content: TextField(
            controller: controller,
            autofocus: true,
            keyboardType: point.responseMode == 'number'
                ? const TextInputType.numberWithOptions(decimal: true)
                : TextInputType.multiline,
            minLines: 1,
            maxLines: point.responseMode == 'number' ? 1 : 5,
            decoration: InputDecoration(
              labelText: point.responseMode == 'number'
                  ? 'Valeur'
                  : 'Votre réponse',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, _cancelledResponse),
              child: const Text('Annuler'),
            ),
            FilledButton(
              onPressed: () {
                final value = controller.text.trim();
                if (value.isNotEmpty) Navigator.pop(context, value);
              },
              child: const Text('Envoyer'),
            ),
          ],
        ),
      );
      controller.dispose();
      return result ?? _cancelledResponse;
    default:
      return _cancelledResponse;
  }
}

class _ConversationSummary {
  const _ConversationSummary({
    required this.id,
    required this.title,
    required this.lifecycle,
    required this.attentionCount,
    required this.allClear,
    this.contextLabel,
  });

  final String id;
  final String title;
  final String? lifecycle;
  final int attentionCount;
  final bool allClear;
  final String? contextLabel;

  static List<_ConversationSummary> fromProjection(
    StoredProjection? projection,
  ) {
    final raw = projection?.payload['results'];
    if (raw is! List) return const [];
    return raw
        .map((item) {
          final row = _map(item);
          final context = _map(row['context']);
          return _ConversationSummary(
            id: _string(row['id']) ?? '',
            title: _string(row['title']) ?? 'Conversation',
            lifecycle: MakoloHumanization.presentationLabel(
              _string(row['lifecycle']),
            ),
            attentionCount: row['attention_count'] is num
                ? (row['attention_count'] as num).toInt()
                : 0,
            allClear: row['all_clear'] == true,
            contextLabel: _string(context['label']),
          );
        })
        .where((item) => item.id.isNotEmpty)
        .toList(growable: false);
  }
}

class _ConversationDetail {
  const _ConversationDetail({
    required this.title,
    required this.points,
    required this.essential,
    required this.personalState,
    this.purpose,
    this.lifecycle,
    this.contextLabel,
  });

  final String title;
  final String? purpose;
  final String? lifecycle;
  final String? contextLabel;
  final List<_ConversationPoint> points;
  final List<_ConversationPoint> essential;
  final _ConversationPersonalState personalState;

  factory _ConversationDetail.fromProjection(StoredProjection? projection) {
    if (projection == null) {
      return const _ConversationDetail(
        title: 'Conversation',
        points: [],
        essential: [],
        personalState: _ConversationPersonalState(),
      );
    }
    final payload = projection.payload;
    final context = _map(payload['context']);
    return _ConversationDetail(
      title: _string(payload['title']) ?? 'Conversation',
      purpose: _string(payload['purpose']),
      lifecycle: MakoloHumanization.presentationLabel(
        _string(payload['lifecycle']),
      ),
      contextLabel: _string(context['label']),
      points: _maps(payload['points'])
          .map(_ConversationPoint.fromMap)
          .toList(growable: false),
      essential: _maps(payload['essential'])
          .map(_ConversationPoint.fromMap)
          .toList(growable: false),
      personalState: _ConversationPersonalState.fromMap(
        _map(payload['personal_state']),
      ),
    );
  }
}

class _ConversationPersonalState {
  const _ConversationPersonalState({
    this.muted = false,
    this.hidden = false,
    this.archived = false,
    this.pinned = false,
    this.revisit = false,
  });

  final bool muted;
  final bool hidden;
  final bool archived;
  final bool pinned;
  final bool revisit;

  factory _ConversationPersonalState.fromMap(Map<String, dynamic> row) =>
      _ConversationPersonalState(
        muted: row['muted'] == true,
        hidden: row['hidden'] == true,
        archived: row['archived'] == true,
        pinned: row['pinned'] == true,
        revisit: row['revisit'] == true,
      );
}

class _ConversationOption {
  const _ConversationOption({required this.id, required this.label});

  final String id;
  final String label;

  factory _ConversationOption.fromMap(Map<String, dynamic> row) =>
      _ConversationOption(
        id: _string(row['id']) ?? '',
        label: _string(row['label']) ?? '',
      );
}

class _ConversationPoint {
  const _ConversationPoint({
    required this.id,
    required this.title,
    required this.responseMode,
    required this.lifecycle,
    required this.requiresAcknowledgement,
    required this.canRespond,
    required this.options,
    this.body,
    this.attentionReason,
    this.section,
    this.resolutionSummary,
  });

  final String id;
  final String title;
  final String responseMode;
  final String? body;
  final String? lifecycle;
  final bool requiresAcknowledgement;
  final bool canRespond;
  final List<_ConversationOption> options;
  final String? attentionReason;
  final String? section;
  final String? resolutionSummary;

  bool get supportsInteractiveResponse => switch (responseMode) {
    'free_text' ||
    'boolean' ||
    'single_choice' ||
    'multiple_choice' ||
    'number' ||
    'date' ||
    'datetime' => true,
    _ => false,
  };

  String get responseActionLabel => switch (responseMode) {
    'boolean' => 'Confirmer',
    'single_choice' || 'multiple_choice' => 'Choisir',
    'date' || 'datetime' => 'Indiquer',
    _ => 'Répondre',
  };

  factory _ConversationPoint.fromMap(Map<String, dynamic> row) {
    return _ConversationPoint(
      id: _string(row['id']) ?? '',
      title: _string(row['title']) ?? 'Point',
      responseMode: _string(row['response_mode']) ?? 'none',
      body: _string(row['body']),
      lifecycle: MakoloHumanization.presentationLabel(
        _string(row['lifecycle']),
      ),
      requiresAcknowledgement: row['requires_acknowledgement'] == true,
      canRespond: row['can_respond'] == true,
      options: _maps(row['options'])
          .map(_ConversationOption.fromMap)
          .where((option) => option.id.isNotEmpty)
          .toList(growable: false),
      attentionReason: _string(row['attention_reason']),
      section: _string(row['section']),
      resolutionSummary: _string(row['resolution_summary']),
    );
  }
}

class _ConversationInvitation {
  const _ConversationInvitation({
    required this.id,
    required this.conversationId,
    required this.status,
    this.expiresAt,
  });

  final String id;
  final String conversationId;
  final String status;
  final DateTime? expiresAt;

  bool get expired {
    final value = expiresAt;
    return status == 'expired' ||
        (value != null && !DateTime.now().isBefore(value));
  }

  static List<_ConversationInvitation> fromProjection(
    StoredProjection? projection,
  ) => _maps(projection?.payload['results'])
      .map(
        (row) => _ConversationInvitation(
          id: _string(row['id']) ?? '',
          conversationId: _string(row['conversation_id']) ?? '',
          status: _string(row['status']) ?? '',
          expiresAt: DateTime.tryParse(_string(row['expires_at']) ?? ''),
        ),
      )
      .where((item) => item.id.isNotEmpty)
      .toList(growable: false);
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const {};
}

List<Map<String, dynamic>> _maps(Object? value) {
  if (value is! List) return const [];
  return value.map(_map).where((row) => row.isNotEmpty).toList(growable: false);
}

String? _string(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}
