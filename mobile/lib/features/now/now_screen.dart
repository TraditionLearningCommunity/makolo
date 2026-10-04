import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../design/presentation_layout.dart';
import '../../design/surface_states.dart';
import '../../navigation/destination.dart';
import '../../navigation/refresh_boundary.dart';
import '../../presentation/contracts/now_presentation.dart';
import '../../repositories/personal_repository.dart';
import 'now_selector.dart';

class NowScreen extends StatelessWidget {
  const NowScreen({super.key, required this.repository, this.now});

  final PersonalRepository repository;
  final DateTime Function()? now;

  @override
  Widget build(BuildContext context) {
    return MakoloRefreshBoundary(
      child: StreamBuilder<StoredProjection?>(
        stream: repository.watchNow(),
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
                  'Une première connexion est nécessaire pour rendre '
                  'Maintenant disponible ici.',
              icon: Icons.cloud_off_outlined,
            );
          }

          final selection = const NowSelector().select(
            projection: projection,
            now: (now?.call() ?? DateTime.now()).toUtc(),
          );
          return NowView(
            selection: selection,
            onOpenOwner: (destination) => _openOwner(context, destination),
          );
        },
      ),
    );
  }

  void _openOwner(BuildContext context, StructuredDestination destination) {
    final path = ownerPathFor(destination);
    if (path != null) context.push(path);
  }

  static String? ownerPathFor(StructuredDestination destination) {
    final id = Uri.encodeComponent(destination.id);
    return switch (destination.kind.toLowerCase()) {
      'journey' => '/journeys/$id',
      _ => null,
    };
  }
}

class NowView extends StatefulWidget {
  const NowView({super.key, required this.selection, this.onOpenOwner});

  final NowSelection selection;
  final ValueChanged<StructuredDestination>? onOpenOwner;

  @override
  State<NowView> createState() => _NowViewState();
}

class _NowViewState extends State<NowView> {
  final ScrollController _fieldController = ScrollController();
  String? _selectedKey;

  @override
  void didUpdateWidget(covariant NowView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_selectedKey != null &&
        !_situations.any((item) => _keyOf(item) == _selectedKey)) {
      _selectedKey = null;
    }
  }

  @override
  void dispose() {
    _fieldController.dispose();
    super.dispose();
  }

  List<NowSituationPresentation> get _situations => widget.selection.situations;

  NowSituationPresentation? get _selected {
    final key = _selectedKey;
    if (key == null) return null;
    for (final item in _situations) {
      if (_keyOf(item) == key) return item;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final selected = _selected;
    final field = _NowField(
      situations: _situations,
      controller: _fieldController,
      selectedKey: _selectedKey,
      onSelect: _select,
      onOpenOwner: widget.onOpenOwner,
    );

    final content = selected == null
        ? MakoloContentFrame(
            maxContentWidth: MakoloLayout.calmMaxWidth,
            child: field,
          )
        : MakoloAdaptiveSplit(
            splitAt: MakoloLayout.nowFocusSplitMinWidth,
            field: MakoloContentFrame(child: field),
            focus: MakoloContentFrame(
              child: _NowDepth(
                situation: selected,
                onClose: _closeDepth,
                onOpenOwner: widget.onOpenOwner,
              ),
            ),
            narrow: MakoloContentFrame(
              maxContentWidth: MakoloLayout.calmMaxWidth,
              child: _NowDepth(
                situation: selected,
                onClose: _closeDepth,
                onOpenOwner: widget.onOpenOwner,
              ),
            ),
          );

    return PopScope<Object?>(
      canPop: _selected == null,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop && _selected != null) _closeDepth();
      },
      child: MakoloSurfaceStateView(
        state: widget.selection.state,
        empty: const _NowCalm(),
        content: content,
      ),
    );
  }

  void _select(NowSituationPresentation situation) {
    setState(() => _selectedKey = _keyOf(situation));
  }

  void _closeDepth() {
    if (_selectedKey == null) return;
    setState(() => _selectedKey = null);
  }

  String _keyOf(NowSituationPresentation situation) =>
      '${situation.reference.kind}:${situation.reference.id}';
}

class _NowField extends StatelessWidget {
  const _NowField({
    required this.situations,
    required this.controller,
    required this.selectedKey,
    required this.onSelect,
    required this.onOpenOwner,
  });

  final List<NowSituationPresentation> situations;
  final ScrollController controller;
  final String? selectedKey;
  final ValueChanged<NowSituationPresentation> onSelect;
  final ValueChanged<StructuredDestination>? onOpenOwner;

  @override
  Widget build(BuildContext context) {
    if (situations.isEmpty) return const _NowCalm();

    final primary = situations.first;
    final secondary = situations.skip(1).toList(growable: false);

    return ListView(
      key: const PageStorageKey<String>('now-field-scroll'),
      controller: controller,
      padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
      children: [
        _NowPrimarySituation(
          situation: primary,
          selected: selectedKey == _keyOf(primary),
          onSelect: () => onSelect(primary),
          onOpenOwner: onOpenOwner,
        ),
        if (secondary.isNotEmpty) ...[
          const SizedBox(height: MakoloSpacing.strong),
          Text(
            'Aussi maintenant',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: MakoloSpacing.md),
          for (var index = 0; index < secondary.length; index++) ...[
            _NowSecondarySituation(
              situation: secondary[index],
              onSelect: () => onSelect(secondary[index]),
            ),
            if (index != secondary.length - 1)
              const SizedBox(height: MakoloSpacing.md),
          ],
        ],
      ],
    );
  }

  String _keyOf(NowSituationPresentation situation) =>
      '${situation.reference.kind}:${situation.reference.id}';
}

class _NowPrimarySituation extends StatelessWidget {
  const _NowPrimarySituation({
    required this.situation,
    required this.selected,
    required this.onSelect,
    required this.onOpenOwner,
  });

  final NowSituationPresentation situation;
  final bool selected;
  final VoidCallback onSelect;
  final ValueChanged<StructuredDestination>? onOpenOwner;

  @override
  Widget build(BuildContext context) {
    final ownerPath = NowScreen.ownerPathFor(situation.ownerDestination);
    final canOpenOwner =
        situation.responseCapability == 'open_detail' &&
        ownerPath != null &&
        onOpenOwner != null;

    return Semantics(
      container: true,
      button: true,
      selected: selected,
      label: '${situation.humanContext}. ${situation.meaning}',
      child: InkWell(
        onTap: onSelect,
        borderRadius: BorderRadius.circular(MakoloRadii.card),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.compact),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                situation.humanContext,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: MakoloSpacing.compact),
              Text(
                situation.meaning,
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              if (situation.whyNow != null) ...[
                const SizedBox(height: MakoloSpacing.md),
                Text(
                  situation.whyNow!,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
              if (situation.metadata.isNotEmpty) ...[
                const SizedBox(height: MakoloSpacing.md),
                MakoloMetadata(
                  items: [
                    for (final item in situation.metadata)
                      MakoloMetadataItem(item),
                  ],
                ),
              ],
              if (canOpenOwner) ...[
                const SizedBox(height: MakoloSpacing.lg),
                FilledButton(
                  onPressed: () => onOpenOwner!(situation.ownerDestination),
                  child: Text(situation.responseLabel ?? 'Ouvrir'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _NowSecondarySituation extends StatelessWidget {
  const _NowSecondarySituation({
    required this.situation,
    required this.onSelect,
  });

  final NowSituationPresentation situation;
  final VoidCallback onSelect;

  @override
  Widget build(BuildContext context) {
    return MakoloCard(
      onTap: onSelect,
      semanticLabel:
          '${situation.humanContext}. ${situation.meaning}. Ouvrir le détail.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            situation.humanContext,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: MakoloSpacing.sm),
          Text(situation.meaning, style: Theme.of(context).textTheme.bodyLarge),
          if (situation.metadata.isNotEmpty) ...[
            const SizedBox(height: MakoloSpacing.sm),
            MakoloMetadata(
              items: [
                for (final item in situation.metadata) MakoloMetadataItem(item),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _NowDepth extends StatelessWidget {
  const _NowDepth({
    required this.situation,
    required this.onClose,
    required this.onOpenOwner,
  });

  final NowSituationPresentation situation;
  final VoidCallback onClose;
  final ValueChanged<StructuredDestination>? onOpenOwner;

  @override
  Widget build(BuildContext context) {
    final canOpenOwner =
        NowScreen.ownerPathFor(situation.ownerDestination) != null &&
        onOpenOwner != null;

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
                label: const Text('Now'),
              ),
            ),
            const SizedBox(height: MakoloSpacing.md),
            Text(
              situation.humanContext,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: MakoloSpacing.md),
            Text(
              situation.meaning,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            if (situation.whyNow != null) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Pourquoi maintenant',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(situation.whyNow!),
                  ],
                ),
              ),
            ],
            if (situation.metadata.isNotEmpty) ...[
              const SizedBox(height: MakoloSpacing.lg),
              MakoloMetadata(
                items: [
                  for (final item in situation.metadata)
                    MakoloMetadataItem(item),
                ],
              ),
            ],
            if (canOpenOwner) ...[
              const SizedBox(height: MakoloSpacing.xl),
              OutlinedButton(
                onPressed: () => onOpenOwner!(situation.ownerDestination),
                child: const Text('Ouvrir la démarche'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _NowCalm extends StatelessWidget {
  const _NowCalm();

  @override
  Widget build(BuildContext context) {
    return MakoloContentFrame(
      maxContentWidth: MakoloLayout.calmMaxWidth,
      child: ListView(
        padding: const EdgeInsets.symmetric(
          vertical: MakoloSpacing.exceptional,
        ),
        children: [
          Text(
            'Tout est en ordre. ✓',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.headlineMedium,
          ),
        ],
      ),
    );
  }
}
