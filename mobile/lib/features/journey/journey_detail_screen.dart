import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/humanization.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import 'journey_repository.dart';
import 'journey_selector.dart';

class JourneyDetailScreen extends StatefulWidget {
  const JourneyDetailScreen({
    super.key,
    required this.journeyId,
    required this.repository,
    required this.onOpenForm,
    required this.onOpenRequirement,
    required this.onOpenResources,
  });

  final String journeyId;
  final JourneyRepository repository;
  final void Function(JourneyFormSummary form) onOpenForm;
  final void Function(JourneyReference requirement) onOpenRequirement;
  final void Function(String resourcesLink) onOpenResources;

  @override
  State<JourneyDetailScreen> createState() => _JourneyDetailScreenState();
}

class _JourneyDetailScreenState extends State<JourneyDetailScreen> {
  static const _selector = JourneyDetailSelector();
  static const _surfaceAdapter = ProjectionSurfaceAdapter();

  bool _refreshing = false;
  bool _requestedInitialRefresh = false;

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
      _requestedInitialRefresh = false;
      unawaited(_acquireOrRefresh());
    }
  }

  Future<void> _acquireOrRefresh() async {
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;

    final local = await widget.repository.readDetail(widget.journeyId);
    final source = await widget.repository.readSource(widget.journeyId);
    if (!mounted) return;

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
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshDetail(widget.journeyId);
    } on Object {
      // SyncSource records the failure while preserving usable local content.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
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
            final unavailableWithoutContent =
                !available &&
                (source.invalidated ||
                    source.reachability == ReachabilityState.unreachable) &&
                !_refreshing;
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
                  : _refreshing
                  ? MakoloAvailabilityCue.loading
                  : MakoloAvailabilityCue.initial,
              reachability: source.reachability,
              failure: unavailableWithoutContent
                  ? MakoloFailureCue.blocking
                  : source.lastErrorCode != null && available
                  ? MakoloFailureCue.recoverable
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
              body: MakoloSurfaceStateView(
                state: surface,
                initialLoading: const MakoloLoadingState(
                  label: 'Chargement de la démarche…',
                ),
                blockingErrorMessage: 'Cette démarche n’est pas disponible dans votre contexte actuel.',
                preservedMessage: 'Aucune copie locale utilisable n’est disponible sur cet appareil.',
                onRetry: _refresh,
                content: _JourneyContent(
                  presentation: presentation,
                  onOpenForm: widget.onOpenForm,
                  onOpenRequirement: widget.onOpenRequirement,
                  onOpenResources: widget.onOpenResources,
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
    required this.onOpenForm,
    required this.onOpenRequirement,
    required this.onOpenResources,
  });

  final JourneyDetailPresentation presentation;
  final void Function(JourneyFormSummary form) onOpenForm;
  final void Function(JourneyReference requirement) onOpenRequirement;
  final void Function(String resourcesLink) onOpenResources;

  @override
  Widget build(BuildContext context) {
    return ListView(
      key: const Key('journey-detail-content'),
      padding: const EdgeInsets.only(bottom: MakoloSpacing.xl),
      children: [
        MakoloDetailHeader(
          eyebrow: presentation.kindLabel,
          title: presentation.title,
          subtitle: presentation.summary,
          status:
              MakoloHumanization.presentationLabel(presentation.journeyState) ==
                  null
              ? null
              : MakoloStatus(
                  label: MakoloHumanization.presentationLabel(
                    presentation.journeyState,
                  )!,
                ),
        ),
        if (presentation.nextActionLabel != null) ...[
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: MakoloSpacing.inner,
            ),
            child: MakoloAttentionBlock(
              title: 'À faire maintenant',
              body: presentation.nextActionLabel!,
            ),
          ),
          const SizedBox(height: MakoloSpacing.xl),
        ],
        MakoloSection(
          title: 'Préparation',
          child: _ReadinessGroups(presentation: presentation),
        ),
        if (presentation.resourcesLink != null) ...[
          const SizedBox(height: MakoloSpacing.xl),
          MakoloSection(
            title: 'Documents et instructions',
            child: MakoloCard(
              semanticLabel: 'Ouvrir les documents et instructions',
              onTap: () => onOpenResources(presentation.resourcesLink!),
              child: const MakoloStatusMetadataAction(
                title: 'Ressources de préparation',
                subtitle: 'Consultez ce que le propriétaire de la démarche a rendu disponible.',
                action: Icon(Icons.chevron_right_rounded),
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
        if (presentation.activity != null ||
            presentation.occurrence != null) ...[
          const SizedBox(height: MakoloSpacing.xl),
          MakoloSection(
            title: 'Contexte',
            child: Column(
              children: [
                if (presentation.activity != null)
                  _ReferenceCard(reference: presentation.activity!),
                if (presentation.activity != null &&
                    presentation.occurrence != null)
                  const SizedBox(height: MakoloSpacing.sm),
                if (presentation.occurrence != null)
                  _ReferenceCard(reference: presentation.occurrence!),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _ReadinessGroups extends StatelessWidget {
  const _ReadinessGroups({required this.presentation});

  final JourneyDetailPresentation presentation;

  @override
  Widget build(BuildContext context) {
    final primary = presentation.nextActionLabel?.trim();
    final actorInterventions = [
      for (final item in presentation.actorInterventions)
        if (primary == null || item.summary.trim() != primary) item,
    ];
    final groups = <(String, List<JourneyReadinessItem>, IconData)>[
      (
        'Demande votre attention',
        actorInterventions,
        Icons.bolt_rounded,
      ),
      ('Bloque la suite', presentation.blockers, Icons.block_rounded),
      ('En attente', presentation.waiting, Icons.schedule_rounded),
      ('En ordre', presentation.ready, Icons.check_circle_outline_rounded),
    ];
    final visible = groups.where((group) => group.$2.isNotEmpty).toList();

    if (visible.isEmpty) {
      return const MakoloCard(
        child: Text('Aucun détail de préparation supplémentaire.'),
      );
    }

    return Column(
      children: [
        for (var index = 0; index < visible.length; index++) ...[
          MakoloCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(visible[index].$3, size: 20),
                    const SizedBox(width: MakoloSpacing.sm),
                    Expanded(
                      child: Text(
                        visible[index].$1,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: MakoloSpacing.sm),
                for (final item in visible[index].$2)
                  Padding(
                    padding: const EdgeInsets.only(bottom: MakoloSpacing.xs),
                    child: Text('• ${item.summary}'),
                  ),
              ],
            ),
          ),
          if (index < visible.length - 1)
            const SizedBox(height: MakoloSpacing.sm),
        ],
      ],
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
      onTap: form.canComplete && form.detailLink.isNotEmpty
          ? () => onOpen(form)
          : null,
      child: MakoloStatusMetadataAction(
        title: 'Formulaire',
        subtitle: form.canComplete
            ? 'Une réponse est attendue.'
            : 'Consultation uniquement pour le moment.',
        status: MakoloHumanization.presentationLabel(form.state) == null
            ? null
            : MakoloStatus(
                label: MakoloHumanization.presentationLabel(form.state)!,
              ),
        metadata: metadata,
        action: form.canComplete && form.detailLink.isNotEmpty
            ? const Icon(Icons.chevron_right_rounded)
            : null,
      ),
    );
  }
}

class _ReferenceCard extends StatelessWidget {
  const _ReferenceCard({required this.reference, this.onTap});

  final JourneyReference reference;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return MakoloCard(
      onTap: onTap,
      child: MakoloStatusMetadataAction(
        title: reference.label,
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
