import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import '../../network/makolo_api_client.dart';
import '../../data/local/profile_store.dart';

import '../../design/behavior_primitives.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/humanization.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import '../continuity/conversation_context_screen.dart';
import '../continuity/conversation_repository.dart';
import '../preparation/preparation_repository.dart';
import 'journey_repository.dart';
import 'journey_selector.dart';

class JourneyDetailScreen extends StatefulWidget {
  const JourneyDetailScreen({
    super.key,
    required this.journeyId,
    required this.repository,
    this.api,
    this.resourcesRepository,
    this.onOpenPaymentObligation,
    this.onOpenCommerceOrder,
    required this.onOpenForm,
    required this.onOpenRequirement,
    required this.onOpenResources,
    required this.onOpenActivity,
    required this.onOpenOccurrence,
    required this.onOpenAccess,
    required this.onOpenDayOf,
    required this.onOpenLive,
    this.conversations,
    this.onOpenConversation,
  });

  final ConversationRepository? conversations;
  final ValueChanged<String>? onOpenConversation;
  final String journeyId;
  final JourneyRepository repository;
  final MakoloApiClient? api;
  final PreparationResourcesRepository? resourcesRepository;
  final ValueChanged<String>? onOpenPaymentObligation;
  final ValueChanged<String>? onOpenCommerceOrder;
  final void Function(JourneyFormSummary form) onOpenForm;
  final void Function(JourneyReference requirement) onOpenRequirement;
  final void Function(String resourcesLink) onOpenResources;
  final void Function(JourneyReference activity) onOpenActivity;
  final void Function(JourneyReference occurrence) onOpenOccurrence;
  final void Function(JourneyReference access) onOpenAccess;
  final void Function(String dayOfLink) onOpenDayOf;
  final void Function(String liveLink) onOpenLive;

  @override
  State<JourneyDetailScreen> createState() => _JourneyDetailScreenState();
}

class _JourneyDetailScreenState extends State<JourneyDetailScreen> {
  static const _selector = JourneyDetailSelector();
  static const _surfaceAdapter = ProjectionSurfaceAdapter();

  bool _refreshing = false;
  bool _respondingInvitation = false;
  String? _invitationNotice;
  bool _requestedInitialRefresh = false;
  int _identityRevision = 0;

  bool _isCurrent(int revision, String id, JourneyRepository repository) =>
      mounted &&
      revision == _identityRevision &&
      id == widget.journeyId &&
      identical(repository, widget.repository);

  @override
  void initState() {
    super.initState();
    unawaited(_acquireOrRefresh());
  }

  @override
  void didUpdateWidget(covariant JourneyDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.journeyId != widget.journeyId ||
        oldWidget.repository != widget.repository) {
      // Old owner responses must not change another Journey/Profile's page.
      _identityRevision++;
      _refreshing = false;
      _respondingInvitation = false;
      _invitationNotice = null;
      _requestedInitialRefresh = false;
      unawaited(_acquireOrRefresh());
    }
  }

  Future<void> _acquireOrRefresh() async {
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;
    final revision = _identityRevision;
    final id = widget.journeyId;
    final repository = widget.repository;
    final local = await repository.readDetail(id);
    final source = await repository.readSource(id);
    if (!_isCurrent(revision, id, repository)) return;
    if (local == null) {
      await _refresh();
      return;
    }
    final presentation = _selector.select(
      projection: local,
      source: source,
      now: DateTime.now(),
    );
    if (presentation.freshness != null &&
        presentation.freshness != FreshnessState.fresh) {
      await _refresh();
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final revision = _identityRevision;
    final id = widget.journeyId;
    final repository = widget.repository;
    setState(() => _refreshing = true);
    try {
      await repository.refreshDetail(id);
    } on Object {
      // Local content stays available independently of a transport result.
    } finally {
      if (_isCurrent(revision, id, repository)) {
        setState(() => _refreshing = false);
      }
    }
  }

  Future<void> _respondToInvitation(String decision) async {
    final api = widget.api;
    if (_respondingInvitation || api == null) return;
    final revision = _identityRevision;
    final id = widget.journeyId;
    final repository = widget.repository;
    setState(() {
      _respondingInvitation = true;
      _invitationNotice = null;
    });
    try {
      final endpoint =
          'api/v1/me/journeys/${Uri.encodeComponent(id)}/invitation/';
      final current = (await api.get(endpoint)).jsonObject();
      if (!_isCurrent(revision, id, repository)) return;
      final actions = current['capabilities'];
      if (current['journey_id'] != id ||
          actions is! List ||
          !actions.contains(decision)) {
        await _refresh();
        if (_isCurrent(revision, id, repository)) {
          setState(
            () => _invitationNotice =
                'Cette invitation a changé. Consultez son état actuel.',
          );
        }
        return;
      }
      final result = (await api.post(
        endpoint,
        body: {'decision': decision},
      )).jsonObject();
      if (!_isCurrent(revision, id, repository)) return;
      if (result['journey_id'] != id ||
          (decision == 'accept' && result['status'] != 'confirmed') ||
          (decision == 'decline' && result['status'] != 'cancelled')) {
        throw const FormatException('Unconfirmed Journey invitation');
      }
      await _refresh();
      if (_isCurrent(revision, id, repository)) {
        setState(
          () => _invitationNotice = decision == 'accept'
              ? 'Invitation acceptée.'
              : 'Invitation refusée.',
        );
      }
    } on Object {
      // A lost acknowledgement cannot be treated as failure or success.
      if (!_isCurrent(revision, id, repository)) return;
      try {
        final current = (await api.get(
          'api/v1/me/journeys/${Uri.encodeComponent(id)}/invitation/',
        )).jsonObject();
        if (!_isCurrent(revision, id, repository)) return;
        await _refresh();
        if (_isCurrent(revision, id, repository)) {
          final status = current['status'];
          setState(
            () => _invitationNotice = status == 'confirmed'
                ? 'Invitation acceptée.'
                : status == 'cancelled'
                ? 'Invitation refusée.'
                : 'Vérifiez votre invitation avant de réessayer.',
          );
        }
      } on Object {
        if (_isCurrent(revision, id, repository)) {
          setState(
            () => _invitationNotice =
                'Aucune confirmation pour le moment. Vous pouvez réessayer.',
          );
        }
      }
    } finally {
      if (_isCurrent(revision, id, repository)) {
        setState(() => _respondingInvitation = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      key: ValueKey(
        'journey:${widget.repository.profileId}:${widget.journeyId}',
      ),
      stream: widget.repository.watchDetail(widget.journeyId),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<JourneySourceState>(
          stream: widget.repository.watchSource(widget.journeyId),
          initialData: JourneySourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = projectionSnapshot.data;
            final source = sourceSnapshot.data ?? JourneySourceState.unknown;
            final presentation = _selector.select(
              projection: projection,
              source: source,
              now: DateTime.now(),
            );
            final available = presentation.available;
            // A missing local detail is not a transport failure. Keep the
            // page in its normal shell; only an explicit owner denial removes it.
            final ownerDenied =
                !available &&
                source.invalidated &&
                const {
                  'permission_denied',
                  'not_found',
                }.contains(source.lastErrorCode);
            final surface = _surfaceAdapter.adapt(
              projection: ProjectionPresentationModel(
                available: available,
                payload: projection?.payload,
                freshness: presentation.freshness,
                resources: const [],
                drafts: const [],
                pendingOperations: const [],
              ),
              availability: available
                  ? MakoloAvailabilityCue.content
                  : _refreshing ||
                        projectionSnapshot.connectionState ==
                            ConnectionState.waiting
                  ? MakoloAvailabilityCue.loading
                  : MakoloAvailabilityCue.empty,
              reachability: source.reachability,
              failure: ownerDenied
                  ? MakoloFailureCue.permissionDenied
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );

            return Scaffold(
              appBar: AppBar(
                title: const Text('Démarche'),
                actions: [
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              body: MakoloNetworkContextFrame(
                child: MakoloSurfaceStateView(
                  state: surface,
                  initialLoading: const MakoloLoadingState(
                    label: 'Chargement de la démarche…',
                  ),
                  empty: const MakoloEmptyState(
                    title: 'Démarche non disponible',
                    body: 'Aucun détail à afficher pour le moment.',
                  ),
                  onRetry: _refresh,
                  content: StreamBuilder<StoredProjection?>(
                    stream: widget.resourcesRepository?.watchResources(
                      widget.journeyId,
                    ),
                    builder: (context, resourcesSnapshot) => _JourneyContent(
                      presentation: presentation,
                      resourcesPreview: JourneyResourcePreview.fromProjection(
                        resourcesSnapshot.data,
                      ),
                      resourcesKnown: resourcesSnapshot.data != null,
                      onOpenPaymentObligation: widget.onOpenPaymentObligation,
                      onOpenCommerceOrder: widget.onOpenCommerceOrder,
                      invitationEnabled:
                          widget.api != null && !_respondingInvitation,
                      invitationNotice: _invitationNotice,
                      onInvitationDecision: _respondToInvitation,
                      onOpenForm: widget.onOpenForm,
                      onOpenRequirement: widget.onOpenRequirement,
                      onOpenResources: widget.onOpenResources,
                      onOpenActivity: widget.onOpenActivity,
                      onOpenOccurrence: widget.onOpenOccurrence,
                      onOpenAccess: widget.onOpenAccess,
                      onOpenDayOf: widget.onOpenDayOf,
                      onOpenLive: widget.onOpenLive,
                      conversationEntry:
                          widget.conversations != null &&
                              widget.onOpenConversation != null
                          ? ConversationContextAction(
                              repository: widget.conversations!,
                              kind: 'journey',
                              contextId: widget.journeyId,
                              onOpen: widget.onOpenConversation!,
                            )
                          : null,
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

class _JourneyContent extends StatelessWidget {
  const _JourneyContent({
    required this.presentation,
    required this.resourcesPreview,
    required this.resourcesKnown,
    this.onOpenPaymentObligation,
    this.onOpenCommerceOrder,
    required this.invitationEnabled,
    required this.invitationNotice,
    required this.onInvitationDecision,
    required this.onOpenForm,
    required this.onOpenRequirement,
    required this.onOpenResources,
    required this.onOpenActivity,
    required this.onOpenOccurrence,
    required this.onOpenAccess,
    required this.onOpenDayOf,
    required this.onOpenLive,
    this.conversationEntry,
  });

  final Widget? conversationEntry;
  final JourneyDetailPresentation presentation;
  final List<JourneyResourcePreview> resourcesPreview;
  final bool resourcesKnown;
  final ValueChanged<String>? onOpenPaymentObligation;
  final ValueChanged<String>? onOpenCommerceOrder;
  final bool invitationEnabled;
  final String? invitationNotice;
  final void Function(String decision) onInvitationDecision;
  final void Function(JourneyFormSummary form) onOpenForm;
  final void Function(JourneyReference requirement) onOpenRequirement;
  final void Function(String resourcesLink) onOpenResources;
  final void Function(JourneyReference activity) onOpenActivity;
  final void Function(JourneyReference occurrence) onOpenOccurrence;
  final void Function(JourneyReference access) onOpenAccess;
  final void Function(String dayOfLink) onOpenDayOf;
  final void Function(String liveLink) onOpenLive;

  @override
  Widget build(BuildContext context) {
    final action = _nextActionButton();
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 760),
        child: ListView(
          key: const PageStorageKey<String>('journey-detail-content'),
          padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
          children: [
            _JourneyIdentity(presentation: presentation),
            if (presentation.steps.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Où j’en suis',
                child: _JourneyPath(steps: presentation.steps),
              ),
            ],
            if (presentation.isTerminal) ...[
              const SizedBox(height: MakoloSpacing.lg),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: _JourneyOutcomeCard(presentation: presentation),
              ),
            ],
            if (presentation.canRespondInvitation &&
                !presentation.isTerminal) ...[
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                  vertical: MakoloSpacing.lg,
                ),
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(MakoloSpacing.inner),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Votre invitation',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: MakoloSpacing.md),
                        Wrap(
                          spacing: 12,
                          runSpacing: 8,
                          children: [
                            MakoloActionButton(
                              label: 'Accepter',
                              onPressed: invitationEnabled
                                  ? () => onInvitationDecision('accept')
                                  : null,
                              appearance: MakoloActionAppearance.primary,
                            ),
                            MakoloActionButton(
                              label: 'Refuser',
                              onPressed: invitationEnabled
                                  ? () => onInvitationDecision('decline')
                                  : null,
                              appearance: MakoloActionAppearance.secondary,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
            if (invitationNotice != null)
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: Text(invitationNotice!),
              ),
            if (!presentation.isTerminal &&
                presentation.nextActionLabel != null) ...[
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: MakoloCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(
                            Icons.arrow_outward_rounded,
                            color: Color(0xFF5232DB),
                          ),
                          const SizedBox(width: MakoloSpacing.sm),
                          Text(
                            'Pour avancer',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ],
                      ),
                      const SizedBox(height: MakoloSpacing.sm),
                      Text(presentation.nextActionLabel!),
                      if (action != null) ...[
                        const SizedBox(height: MakoloSpacing.md),
                        action,
                      ],
                    ],
                  ),
                ),
              ),
              const SizedBox(height: MakoloSpacing.lg),
            ],
            if (presentation.rejectedRequests > 0) ...[
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: MakoloAttentionBlock(
                  title: 'Une demande a été refusée',
                  body: 'Consultez les informations de votre démarche.',
                  icon: Icons.info_outline_rounded,
                ),
              ),
              const SizedBox(height: MakoloSpacing.lg),
            ],
            if (presentation.pendingRequests > 0 &&
                presentation.waiting.isEmpty &&
                presentation.actorInterventions.isEmpty) ...[
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: const MakoloCard(
                  child: ListTile(
                    leading: Icon(Icons.hourglass_empty_rounded),
                    title: Text('En attente de réponse'),
                  ),
                ),
              ),
              const SizedBox(height: MakoloSpacing.lg),
            ],
            if (presentation.liveLink != null ||
                presentation.dayOfLink != null) ...[
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: MakoloSpacing.inner,
                ),
                child: MakoloCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            presentation.liveLink != null
                                ? Icons.bolt_rounded
                                : Icons.today_rounded,
                            color: const Color(0xFF5232DB),
                          ),
                          const SizedBox(width: MakoloSpacing.sm),
                          Text(
                            presentation.liveLink != null
                                ? 'Makolo Live'
                                : 'Jour J',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ],
                      ),
                      const SizedBox(height: MakoloSpacing.sm),
                      MakoloActionButton(
                        label: presentation.liveLink != null
                            ? 'Ouvrir Makolo Live'
                            : 'Ouvrir Jour J',
                        onPressed: presentation.liveLink != null
                            ? () => onOpenLive(presentation.liveLink!)
                            : () => onOpenDayOf(presentation.dayOfLink!),
                        appearance: MakoloActionAppearance.primary,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: MakoloSpacing.lg),
            ],
            if (!presentation.isTerminal &&
                (presentation.actorInterventions.isNotEmpty ||
                    presentation.blockers.isNotEmpty ||
                    presentation.waiting.isNotEmpty ||
                    presentation.ready.isNotEmpty)) ...[
              MakoloSection(
                title: 'Préparation',
                child: _ReadinessGroups(
                  presentation: presentation,
                  ownerAction: _ownerActionForLink,
                ),
              ),
            ],
            if (presentation.resourcesLink != null &&
                (!resourcesKnown || resourcesPreview.isNotEmpty)) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Documents et instructions',
                child: MakoloCard(
                  semanticLabel: 'Voir les documents et instructions',
                  onTap: () => onOpenResources(presentation.resourcesLink!),
                  child: Column(
                    children: [
                      for (final resource in resourcesPreview.take(3))
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: Icon(switch (resource.kind) {
                            'file' => Icons.insert_drive_file_outlined,
                            'url' => Icons.link_rounded,
                            'text' => Icons.notes_rounded,
                            _ => Icons.description_outlined,
                          }, color: const Color(0xFF5232DB)),
                          title: Text(resource.title),
                          subtitle: resource.description == null
                              ? null
                              : Text(
                                  resource.description!,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                          trailing: const Icon(Icons.chevron_right_rounded),
                        ),
                      if (resourcesPreview.isEmpty)
                        const MakoloStatusMetadataAction(
                          title: 'Documents et instructions',
                          action: Icon(Icons.chevron_right_rounded),
                        ),
                      if (resourcesPreview.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: MakoloSpacing.sm),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.end,
                            children: [
                              Text(
                                resourcesPreview.length > 3
                                    ? 'Voir les ${resourcesPreview.length} ressources'
                                    : 'Voir les ressources',
                                style: const TextStyle(
                                  color: Color(0xFF5232DB),
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              const Icon(Icons.chevron_right_rounded),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ],
            if (presentation.forms.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.xl),
              MakoloSection(
                title: 'Formulaires',
                child: Column(
                  children: [
                    for (
                      var index = 0;
                      index < presentation.forms.length;
                      index++
                    ) ...[
                      _FormCard(
                        form: presentation.forms[index],
                        onOpen: onOpenForm,
                      ),
                      if (index < presentation.forms.length - 1)
                        const SizedBox(height: MakoloSpacing.sm),
                    ],
                  ],
                ),
              ),
            ],
            if (presentation.requirements.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.xl),
              MakoloSection(
                title: 'Éléments nécessaires',
                child: Column(
                  children: [
                    for (
                      var index = 0;
                      index < presentation.requirements.length;
                      index++
                    ) ...[
                      _ReferenceCard(
                        reference: presentation.requirements[index],
                        onTap: () =>
                            onOpenRequirement(presentation.requirements[index]),
                      ),
                      if (index < presentation.requirements.length - 1)
                        const SizedBox(height: MakoloSpacing.sm),
                    ],
                  ],
                ),
              ),
            ],
            if (presentation.practical?.hasContent == true) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'À retenir',
                child: _JourneyPracticalCard(facts: presentation.practical!),
              ),
            ],
            if (presentation.payments.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Paiement',
                child: Column(
                  children: [
                    for (final item in presentation.payments) ...[
                      _JourneyPaymentCard(
                        payment: item,
                        onOpenPaymentObligation: onOpenPaymentObligation,
                        onOpenCommerceOrder: onOpenCommerceOrder,
                      ),
                      const SizedBox(height: MakoloSpacing.sm),
                    ],
                  ],
                ),
              ),
            ],
            if (presentation.activity != null ||
                presentation.occurrence != null) ...[
              const SizedBox(height: MakoloSpacing.xl),
              MakoloSection(
                title: 'Contexte',
                child: Column(
                  children: [
                    if (presentation.activity != null)
                      _ReferenceCard(
                        reference: presentation.activity!,
                        contextLabel: 'Activité',
                        hideRepeatedTitle:
                            presentation.activity!.label == presentation.title,
                        onTap: presentation.activity!.link == null
                            ? null
                            : () => onOpenActivity(presentation.activity!),
                      ),
                    if (presentation.activity != null &&
                        presentation.occurrence != null)
                      const SizedBox(height: MakoloSpacing.sm),
                    if (presentation.occurrence != null)
                      _ReferenceCard(
                        reference: presentation.occurrence!,
                        contextLabel: 'Occurrence',
                        hideRepeatedTitle:
                            presentation.occurrence!.label ==
                            presentation.title,
                        onTap: presentation.occurrence!.link == null
                            ? null
                            : () => onOpenOccurrence(presentation.occurrence!),
                      ),
                  ],
                ),
              ),
            ],
            if (presentation.access != null) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloSection(
                title: 'Accès',
                child: _ReferenceCard(
                  reference: presentation.access!,
                  onTap: presentation.access!.link == null
                      ? null
                      : () => onOpenAccess(presentation.access!),
                ),
              ),
            ],
            if (conversationEntry != null) ...[
              const SizedBox(height: MakoloSpacing.lg),
              conversationEntry!,
            ],
          ],
        ),
      ),
    );
  }

  Widget? _nextActionButton() => _ownerActionForLink(
    presentation.nextActionLabel ?? 'Continuer',
    presentation.nextActionLink,
    primary: true,
  );

  /// Follow only links exposed by the actual owner projection. An unknown
  /// next-action URL remains visible as information, never as a false CTA.
  Widget? _ownerActionForLink(
    String label,
    String? link, {
    bool primary = false,
  }) {
    if (link == null || link.isEmpty || presentation.isTerminal) return null;
    final appearance = primary
        ? MakoloActionAppearance.primary
        : MakoloActionAppearance.secondary;

    for (final form in presentation.forms) {
      if (form.canComplete && form.detailLink == link) {
        return MakoloActionButton(
          appearance: appearance,
          label: label,
          onPressed: () => onOpenForm(form),
        );
      }
    }
    for (final requirement in presentation.requirements) {
      if (requirement.link == link) {
        return MakoloActionButton(
          appearance: appearance,
          label: label,
          onPressed: () => onOpenRequirement(requirement),
        );
      }
    }
    if (presentation.resourcesLink == link) {
      return MakoloActionButton(
        appearance: appearance,
        label: label,
        onPressed: () => onOpenResources(link),
      );
    }
    if (presentation.activity?.link == link) {
      return MakoloActionButton(
        appearance: appearance,
        label: label,
        onPressed: () => onOpenActivity(presentation.activity!),
      );
    }
    if (presentation.occurrence?.link == link) {
      return MakoloActionButton(
        appearance: appearance,
        label: label,
        onPressed: () => onOpenOccurrence(presentation.occurrence!),
      );
    }
    if (presentation.access?.link == link) {
      return MakoloActionButton(
        appearance: appearance,
        label: label,
        onPressed: () => onOpenAccess(presentation.access!),
      );
    }
    if (presentation.liveLink == link) {
      return MakoloActionButton(
        appearance: appearance,
        label: label,
        onPressed: () => onOpenLive(link),
      );
    }
    if (presentation.dayOfLink == link) {
      return MakoloActionButton(
        appearance: appearance,
        label: label,
        onPressed: () => onOpenDayOf(link),
      );
    }
    return null;
  }
}

/// Terminal labels are solely the owner Journey state, never an invented
/// success or a percentage computed from unrelated capabilities.
class _JourneyOutcomeCard extends StatelessWidget {
  const _JourneyOutcomeCard({required this.presentation});

  final JourneyDetailPresentation presentation;

  @override
  Widget build(BuildContext context) {
    final outcome = switch (presentation.stateCode) {
      'fulfilled' => ('Démarche réalisée', Icons.check_circle_outline_rounded),
      'rejected' => ('Demande refusée', Icons.info_outline_rounded),
      'cancelled' => ('Démarche annulée', Icons.cancel_outlined),
      'expired' => ('Démarche expirée', Icons.event_busy_outlined),
      _ => ('Démarche', Icons.route_outlined),
    };
    return MakoloCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(outcome.$2, size: 28, color: const Color(0xFF5232DB)),
          const SizedBox(width: MakoloSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  outcome.$1,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                if (presentation.journeyState.trim().isNotEmpty)
                  Text(presentation.journeyState),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Only the owner projection stored in ProfileStore feeds this header.
class _JourneyIdentity extends StatelessWidget {
  const _JourneyIdentity({required this.presentation});

  final JourneyDetailPresentation presentation;

  IconData get _symbol => switch (presentation.workflowKind) {
    'purchase' => Icons.shopping_bag_outlined,
    'reservation' => Icons.event_available_outlined,
    'registration' => Icons.how_to_reg_outlined,
    'invitation' => Icons.mark_email_read_outlined,
    'service' => Icons.handyman_outlined,
    'fulfillment' => Icons.task_alt_outlined,
    'order_approval' => Icons.fact_check_outlined,
    _ => Icons.route_outlined,
  };

  @override
  Widget build(BuildContext context) {
    final state = MakoloHumanization.presentationLabel(
      presentation.journeyState,
    );
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        MakoloSpacing.inner,
        MakoloSpacing.lg,
        MakoloSpacing.inner,
        0,
      ),
      child: Card(
        margin: EdgeInsets.zero,
        clipBehavior: Clip.antiAlias,
        child: Container(
          width: double.infinity,
          color: const Color(0xFF2B176E),
          padding: const EdgeInsets.all(MakoloSpacing.inner),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(MakoloSpacing.md),
                    decoration: BoxDecoration(
                      color: const Color(0xFF5232DB),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Icon(_symbol, color: Colors.white, size: 28),
                  ),
                  const SizedBox(width: MakoloSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'MON OBJECTIF',
                          style: TextStyle(
                            color: Color(0xFFD5CCFF),
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0.8,
                          ),
                        ),
                        const SizedBox(height: MakoloSpacing.sm),
                        Text(
                          presentation.title,
                          style: Theme.of(context).textTheme.headlineSmall
                              ?.copyWith(
                                color: Colors.white,
                                fontWeight: FontWeight.w800,
                              ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              if (presentation.summary != null) ...[
                const SizedBox(height: MakoloSpacing.md),
                Text(
                  presentation.summary!,
                  style: const TextStyle(color: Color(0xFFE6DEFF)),
                ),
              ],
              if (state != null || presentation.kindLabel != 'Démarche') ...[
                const SizedBox(height: MakoloSpacing.lg),
                Wrap(
                  spacing: MakoloSpacing.md,
                  runSpacing: MakoloSpacing.sm,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    if (state != null)
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(
                            Icons.circle,
                            color: Color(0xFFFFB29E),
                            size: 9,
                          ),
                          const SizedBox(width: MakoloSpacing.sm),
                          Text(
                            state,
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    if (presentation.kindLabel != 'Démarche')
                      Text(
                        presentation.kindLabel,
                        style: const TextStyle(color: Color(0xFFD5CCFF)),
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// JourneySteps are shown as facts, not a locally computed percentage/timeline.
/// Dependencies are named only when the owner supplied both linked steps.
class _JourneyPath extends StatelessWidget {
  const _JourneyPath({required this.steps});

  final List<JourneyStepSummary> steps;

  @override
  Widget build(BuildContext context) {
    final active = steps.where((step) => !step.isTerminal).toList();
    final past = steps.where((step) => step.isTerminal).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final step in active) ...[
          _JourneyStepRow(step: step, allSteps: steps),
          const SizedBox(height: MakoloSpacing.sm),
        ],
        if (past.isNotEmpty && active.isNotEmpty)
          Card(
            margin: EdgeInsets.zero,
            child: ExpansionTile(
              leading: const Icon(Icons.check_circle_outline_rounded),
              title: Text(
                '${past.length} étape${past.length > 1 ? 's' : ''} passée${past.length > 1 ? 's' : ''}',
              ),
              children: [
                for (final step in past)
                  _JourneyStepRow(step: step, allSteps: steps),
              ],
            ),
          ),
        if (active.isEmpty)
          for (final step in past) ...[
            _JourneyStepRow(step: step, allSteps: steps),
            const SizedBox(height: MakoloSpacing.sm),
          ],
      ],
    );
  }
}

class _JourneyStepRow extends StatelessWidget {
  const _JourneyStepRow({required this.step, required this.allSteps});

  final JourneyStepSummary step;
  final List<JourneyStepSummary> allSteps;

  @override
  Widget build(BuildContext context) {
    final label = switch (step.status) {
      'completed' => 'Terminée',
      'skipped' => 'Non retenue',
      'cancelled' => 'Annulée',
      'in_progress' => 'En cours',
      'blocked' => 'Bloquée',
      'ready' => 'Prête',
      'pending' => 'En attente',
      _ => null,
    };
    final icon = switch (step.status) {
      'completed' => Icons.check_circle_outline_rounded,
      'skipped' || 'cancelled' => Icons.remove_circle_outline_rounded,
      'blocked' => Icons.error_outline_rounded,
      'in_progress' => Icons.radio_button_checked_rounded,
      'ready' => Icons.play_circle_outline_rounded,
      _ => Icons.radio_button_unchecked_rounded,
    };
    final dependencies = [
      for (final id in step.dependsOn)
        for (final candidate in allSteps)
          if (candidate.id == id) candidate.title,
    ];
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(MakoloSpacing.md),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 24, color: const Color(0xFF5232DB)),
            const SizedBox(width: MakoloSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    step.title,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  if (label != null)
                    Text(label, style: Theme.of(context).textTheme.bodySmall),
                  if (dependencies.isNotEmpty)
                    Text(
                      'Après : ${dependencies.join(', ')}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ReadinessGroups extends StatelessWidget {
  const _ReadinessGroups({
    required this.presentation,
    required this.ownerAction,
  });

  final JourneyDetailPresentation presentation;
  final Widget? Function(String label, String? link) ownerAction;

  @override
  Widget build(BuildContext context) {
    final actorInterventions = [
      for (final item in presentation.actorInterventions)
        if (presentation.nextActionKey == null ||
            item.key != presentation.nextActionKey)
          item,
    ];
    final groups = <(String, List<JourneyReadinessItem>, IconData)>[
      ('De votre côté', actorInterventions, Icons.touch_app_outlined),
      (
        'Bloque la suite',
        presentation.blockers,
        Icons.report_gmailerrorred_rounded,
      ),
      ('En attente', presentation.waiting, Icons.hourglass_empty_rounded),
    ];
    final visible = groups.where((item) => item.$2.isNotEmpty).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final group in visible) ...[
          MakoloCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(group.$3, size: 20, color: const Color(0xFF5232DB)),
                    const SizedBox(width: MakoloSpacing.sm),
                    Expanded(
                      child: Text(
                        group.$1,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: MakoloSpacing.sm),
                for (final item in group.$2)
                  Padding(
                    padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(item.summary),
                        if (item.nextLabel != null &&
                            item.nextLink != presentation.nextActionLink)
                          Padding(
                            padding: const EdgeInsets.only(
                              top: MakoloSpacing.sm,
                            ),
                            child:
                                ownerAction(item.nextLabel!, item.nextLink) ??
                                const SizedBox.shrink(),
                          ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: MakoloSpacing.sm),
        ],
        if (presentation.ready.isNotEmpty)
          Card(
            margin: EdgeInsets.zero,
            child: ExpansionTile(
              leading: const Icon(
                Icons.check_circle_outline_rounded,
                color: Color(0xFF5232DB),
              ),
              title: Text('En ordre · ${presentation.ready.length}'),
              children: [
                for (final item in presentation.ready)
                  ListTile(
                    dense: true,
                    leading: const Icon(
                      Icons.check_rounded,
                      color: Color(0xFF5232DB),
                    ),
                    title: Text(item.summary),
                  ),
              ],
            ),
          ),
      ],
    );
  }
}

class _JourneyPracticalCard extends StatelessWidget {
  const _JourneyPracticalCard({required this.facts});

  final JourneyPracticalFacts facts;

  @override
  Widget build(BuildContext context) {
    final localization = MaterialLocalizations.of(context);
    final ownerDate = facts.startDate == null
        ? null
        : DateTime.tryParse(facts.startDate!);
    final date = ownerDate != null
        ? localization.formatCompactDate(ownerDate)
        : facts.startAt != null
        ? localization.formatCompactDate(facts.startAt!.toLocal())
        : null;
    final time = facts.startTime != null && facts.startTime!.length >= 5
        ? facts.startTime!.substring(0, 5)
        : facts.startAt != null
        ? localization.formatTimeOfDay(
            TimeOfDay.fromDateTime(facts.startAt!.toLocal()),
          )
        : null;
    return MakoloCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (date != null || time != null)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.calendar_month_outlined),
              title: const Text('Début prévu'),
              subtitle: Text(
                [
                  if (date != null) date,
                  if (time != null) time,
                  if (ownerDate != null && facts.timezone != null)
                    facts.timezone!,
                ].join(' · '),
              ),
            ),
          if (facts.placeName != null || facts.placeAddress != null)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.place_outlined),
              title: Text(facts.placeName ?? 'Lieu'),
              subtitle:
                  [facts.placeAddress, facts.placeLocality]
                      .whereType<String>()
                      .where((value) => value.isNotEmpty)
                      .isEmpty
                  ? null
                  : Text(
                      [facts.placeAddress, facts.placeLocality]
                          .whereType<String>()
                          .where((value) => value.isNotEmpty)
                          .join(', '),
                    ),
            ),
          if (facts.accessInstructions != null)
            Padding(
              padding: const EdgeInsets.only(top: MakoloSpacing.sm),
              child: Text(facts.accessInstructions!),
            ),
        ],
      ),
    );
  }
}

class _JourneyPaymentCard extends StatelessWidget {
  const _JourneyPaymentCard({
    required this.payment,
    this.onOpenPaymentObligation,
    this.onOpenCommerceOrder,
  });

  final JourneyPaymentSummary payment;
  final ValueChanged<String>? onOpenPaymentObligation;
  final ValueChanged<String>? onOpenCommerceOrder;

  @override
  Widget build(BuildContext context) {
    final title = '${payment.amount} ${payment.currency}';
    final state = switch (payment.state) {
      'paid' || 'succeeded' || 'completed' || 'settled' => 'Payé',
      'pending' || 'pending_payment' => 'En attente',
      'processing' => 'En cours',
      'satisfied' => 'Réglé',
      'waived' => 'Dispensé',
      'refunded' => 'Remboursé',
      'expired' => 'Expiré',
      'failed' => 'Échec',
      'cancelled' => 'Annulé',
      _ => null,
    };
    VoidCallback? open;
    if (payment.obligationId != null && onOpenPaymentObligation != null) {
      open = () => onOpenPaymentObligation!(payment.obligationId!);
    } else if (payment.orderId != null && onOpenCommerceOrder != null) {
      open = () => onOpenCommerceOrder!(payment.orderId!);
    }
    return MakoloCard(
      onTap: open,
      semanticLabel: 'Paiement',
      child: MakoloStatusMetadataAction(
        title: title,
        subtitle: payment.reason,
        status: state == null ? null : MakoloStatus(label: state),
        action: open == null ? null : const Icon(Icons.chevron_right_rounded),
      ),
    );
  }
}

class _FormCard extends StatelessWidget {
  const _FormCard({required this.form, required this.onOpen});

  final JourneyFormSummary form;
  final void Function(JourneyFormSummary form) onOpen;

  @override
  Widget build(BuildContext context) {
    final metadata = <MakoloMetadataItem>[
      if (form.required) const MakoloMetadataItem('Obligatoire'),
      if (form.dueAt != null)
        MakoloMetadataItem(
          'Échéance ${MaterialLocalizations.of(context).formatCompactDate(form.dueAt!.toLocal())}',
          icon: Icons.event_outlined,
        ),
    ];
    return MakoloCard(
      semanticLabel: 'Formulaire',
      onTap: form.detailLink.isNotEmpty ? () => onOpen(form) : null,
      child: MakoloStatusMetadataAction(
        title: form.title,
        subtitle: form.canComplete
            ? 'À compléter'
            : form.state == 'completed'
            ? 'Terminé'
            : null,
        status: MakoloHumanization.presentationLabel(form.state) == null
            ? null
            : MakoloStatus(
                label: MakoloHumanization.presentationLabel(form.state)!,
              ),
        metadata: metadata,
        action: form.detailLink.isNotEmpty
            ? const Icon(Icons.chevron_right_rounded)
            : null,
      ),
    );
  }
}

class _ReferenceCard extends StatelessWidget {
  const _ReferenceCard({
    required this.reference,
    this.onTap,
    this.contextLabel,
    this.hideRepeatedTitle = false,
  });

  final JourneyReference reference;
  final VoidCallback? onTap;
  final String? contextLabel;
  final bool hideRepeatedTitle;

  @override
  Widget build(BuildContext context) {
    return MakoloCard(
      onTap: onTap,
      child: MakoloStatusMetadataAction(
        title: contextLabel ?? reference.label,
        subtitle: contextLabel == null
            ? (reference.isRequired ? 'Obligatoire' : null)
            : hideRepeatedTitle
            ? null
            : reference.label,
        status: MakoloHumanization.presentationLabel(reference.state) == null
            ? null
            : MakoloStatus(
                label: MakoloHumanization.presentationLabel(reference.state)!,
              ),
        action: onTap == null ? null : const Icon(Icons.chevron_right_rounded),
      ),
    );
  }
}
