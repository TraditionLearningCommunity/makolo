import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_primitives.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/surface_states.dart';
import '../../navigation/refresh_boundary.dart';
import '../../repositories/personal_repository.dart';
import 'me_selector.dart';

class MeScreen extends StatelessWidget {
  const MeScreen({
    super.key,
    required this.repository,
    this.now,
    this.reachability = MakoloReachabilityCue.unknown,
    this.failure = MakoloFailureCue.none,
  });

  final PersonalRepository repository;
  final DateTime Function()? now;
  final MakoloReachabilityCue reachability;
  final MakoloFailureCue failure;

  @override
  Widget build(BuildContext context) => MakoloRefreshBoundary(
    child: StreamBuilder<StoredProjection?>(
      stream: repository.watchMe(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting &&
            !snapshot.hasData) {
          return const MakoloSurfaceStateView(
            state: MakoloSurfacePresentation(
              availability: MakoloAvailabilityCue.loading,
            ),
            content: SizedBox.shrink(),
          );
        }

        final projection = snapshot.data;
        if (projection == null) {
          return const MakoloEmptyState(
            title: 'Pas encore disponible sur cet appareil',
            body:
                'Une première connexion est nécessaire pour retrouver ici '
                'ce qui est déjà en place autour de vous.',
            icon: Icons.person_outline_rounded,
          );
        }

        final selection = const MeSelector().select(
          projection: projection,
          now: (now?.call() ?? DateTime.now()).toUtc(),
          reachability: reachability,
          failure: failure,
        );
        return MeView(selection: selection);
      },
    ),
  );
}

class MeView extends StatefulWidget {
  const MeView({super.key, required this.selection});

  final MeSelection selection;

  @override
  State<MeView> createState() => _MeViewState();
}

class _MeViewState extends State<MeView> {
  final ScrollController _controller = ScrollController();
  MeItemPresentation? _selectedItem;

  @override
  void didUpdateWidget(covariant MeView oldWidget) {
    super.didUpdateWidget(oldWidget);
    final selected = _selectedItem;
    if (selected == null) return;
    final stillExists = widget.selection.territories.any(
      (territory) => territory.items.any(
        (item) =>
            item.destination.kind == selected.destination.kind &&
            item.destination.id == selected.destination.id,
      ),
    );
    if (!stillExists) _selectedItem = null;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final field = MakoloContentFrame(
      child: _MeField(
        selection: widget.selection,
        controller: _controller,
        onSelectItem: (item) => setState(() => _selectedItem = item),
      ),
    );

    final selected = _selectedItem;
    final content = selected == null
        ? field
        : MakoloAdaptiveSplit(
            splitAt: MakoloLayout.meTwoColumnMinWidth,
            field: field,
            focus: MakoloContentFrame(
              child: _MeDepth(item: selected, onClose: _closeDepth),
            ),
            narrow: MakoloContentFrame(
              child: _MeDepth(item: selected, onClose: _closeDepth),
            ),
          );

    return WillPopScope(
      onWillPop: () async {
        if (_selectedItem == null) return true;
        _closeDepth();
        return false;
      },
      child: MakoloSurfaceStateView(
        state: widget.selection.state,
        recoverableErrorMessage:
            'La mise à jour n’a pas abouti. Ce qui est déjà disponible reste visible.',
        content: content,
      ),
    );
  }

  void _closeDepth() {
    if (_selectedItem == null) return;
    setState(() => _selectedItem = null);
  }
}

class _MeField extends StatelessWidget {
  const _MeField({
    required this.selection,
    required this.controller,
    required this.onSelectItem,
  });

  final MeSelection selection;
  final ScrollController controller;
  final ValueChanged<MeItemPresentation> onSelectItem;

  @override
  Widget build(BuildContext context) {
    return ListView(
      key: const PageStorageKey<String>('me-field-scroll'),
      controller: controller,
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
      children: [
        _MeIdentity(selection: selection),
        const SizedBox(height: MakoloSpacing.strong),
        Text(
          'Déjà en place',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        const SizedBox(height: MakoloSpacing.xs),
        Text(
          'Ce capital durable peut faciliter la suite sans devenir une nouvelle vérité métier.',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: MakoloSpacing.lg),
        LayoutBuilder(
          builder: (context, constraints) {
            final cards = [
              for (final territory in selection.territories)
                _MeTerritory(
                  territory: territory,
                  onSelectItem: onSelectItem,
                ),
            ];
            if (constraints.maxWidth < MakoloLayout.meTwoColumnMinWidth) {
              return Column(
                key: const Key('me-territories-compact'),
                children: [
                  for (var index = 0; index < cards.length; index++) ...[
                    cards[index],
                    if (index != cards.length - 1)
                      const SizedBox(height: MakoloSpacing.lg),
                  ],
                ],
              );
            }
            return MakoloAdaptiveGrid(
              key: const Key('me-territories-wide'),
              minUnitWidth: 320,
              maxColumns: 2,
              children: cards,
            );
          },
        ),
      ],
    );
  }
}

class _MeIdentity extends StatelessWidget {
  const _MeIdentity({required this.selection});

  final MeSelection selection;

  @override
  Widget build(BuildContext context) {
    if (selection.identityState.failure == MakoloFailureCue.blocking) {
      return const MakoloErrorState(
        message: 'Votre identité ne peut pas être présentée correctement pour le moment.',
      );
    }

    return Semantics(
      container: true,
      header: true,
      label: selection.presentation.identityLabel,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Moi', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: MakoloSpacing.sm),
          Text(
            selection.presentation.identityLabel,
            style: Theme.of(context).textTheme.headlineLarge,
          ),
          if (selection.identitySubtitle != null) ...[
            const SizedBox(height: MakoloSpacing.sm),
            Text(
              selection.identitySubtitle!,
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          if (selection.identityDetail != null) ...[
            const SizedBox(height: MakoloSpacing.md),
            Text(selection.identityDetail!),
          ],
        ],
      ),
    );
  }
}

class _MeTerritory extends StatelessWidget {
  const _MeTerritory({
    required this.territory,
    required this.onSelectItem,
  });

  final MeTerritorySelection territory;
  final ValueChanged<MeItemPresentation> onSelectItem;

  @override
  Widget build(BuildContext context) {
    final presentation = territory.presentation;
    return MakoloSection(
      title: presentation.label,
      description: presentation.summary,
      padding: EdgeInsets.zero,
      child: _body(context),
    );
  }

  Widget _body(BuildContext context) {
    final state = territory.presentation.state;
    if (state.failure == MakoloFailureCue.blocking) {
      return const MakoloErrorState(
        message: 'Cette section n’est pas disponible pour le moment.',
      );
    }

    if (state.availability == MakoloAvailabilityCue.empty) {
      return Text(
        'Rien ici pour le moment.',
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      );
    }

    final notices = <Widget>[
      if (state.freshness != MakoloFreshnessCue.unknown &&
          state.freshness != MakoloFreshnessCue.current)
        MakoloFreshnessNotice(freshness: state.freshness),
      if (state.reachability == MakoloReachabilityCue.temporarilyUnavailable)
        const MakoloNotice(
          message: 'Contenu disponible hors connexion.',
          kind: MakoloNoticeKind.warning,
        ),
    ];

    final items = territory.items;
    final body = items.isEmpty
        ? const MakoloStatus(
            label: 'Disponible',
            tone: MakoloStatusTone.success,
            icon: Icons.check_rounded,
          )
        : Column(
            children: [
              for (var index = 0; index < items.length; index++) ...[
                _MeItemRow(
                  item: items[index],
                  onTap: () => onSelectItem(items[index]),
                ),
                if (index != items.length - 1)
                  const SizedBox(height: MakoloSpacing.sm),
              ],
            ],
          );

    if (notices.isEmpty) return body;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final notice in notices) ...[
          notice,
          const SizedBox(height: MakoloSpacing.sm),
        ],
        body,
      ],
    );
  }
}

class _MeItemRow extends StatelessWidget {
  const _MeItemRow({required this.item, required this.onTap});

  final MeItemPresentation item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return MakoloCard(
      onTap: onTap,
      semanticLabel: '${item.title}. Ouvrir le détail.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(item.title, style: Theme.of(context).textTheme.titleMedium),
          if (item.subtitle != null) ...[
            const SizedBox(height: MakoloSpacing.xs),
            Text(
              item.subtitle!,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          if (item.metadata.isNotEmpty) ...[
            const SizedBox(height: MakoloSpacing.sm),
            MakoloMetadata(
              items: [
                for (final label in item.metadata) MakoloMetadataItem(label),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _MeDepth extends StatelessWidget {
  const _MeDepth({required this.item, required this.onClose});

  final MeItemPresentation item;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
      child: MakoloFocusPane(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: TextButton.icon(
                onPressed: onClose,
                icon: const Icon(Icons.arrow_back_rounded),
                label: const Text('Moi'),
              ),
            ),
            const SizedBox(height: MakoloSpacing.md),
            Text(item.title, style: Theme.of(context).textTheme.headlineMedium),
            if (item.subtitle != null) ...[
              const SizedBox(height: MakoloSpacing.sm),
              Text(
                item.subtitle!,
                style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
            if (item.metadata.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloMetadata(
                items: [
                  for (final label in item.metadata) MakoloMetadataItem(label),
                ],
              ),
            ],
            const SizedBox(height: MakoloSpacing.xl),
            MakoloNotice(
              message: _boundaryMessage(item.destination.kind),
              kind: MakoloNoticeKind.info,
            ),
          ],
        ),
      ),
    );
  }

  String _boundaryMessage(String kind) {
    return switch (kind.toLowerCase()) {
      'personal_asset' =>
        'Posséder cette ressource ne signifie pas qu’un Requirement est satisfait.',
      'proof' =>
        'Cette preuve reste distincte d’un document, d’un credential et d’un droit d’accès.',
      'credential' =>
        'Ce credential de confiance reste distinct d’un AccessCredential.',
      'group' || 'team' =>
        'Cette appartenance ne crée ni Permission ni Mandate.',
      'space' =>
        'Le contexte affiché n’accorde aucune autorité au-delà de celle décidée par le serveur.',
      _ =>
        'Cette profondeur représente la réalité existante sans en devenir propriétaire.',
    };
  }
}
